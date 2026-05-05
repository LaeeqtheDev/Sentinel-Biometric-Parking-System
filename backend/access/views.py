"""
Access endpoints
================

* GET  /api/access/logs/                List & filter access logs (admin)
* GET  /api/access/stats/               Dashboard statistics (admin)
* POST /api/access/verify-entry/        End-to-end gate decision
                                        body: plate_image (or plate_number)
                                              + face_image
                                        ->  {decision, log_id, ...}
"""

import base64
import binascii
from io import BytesIO

from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import filters, generics, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from recognition.face_engine import verify_face
from recognition.plate_ocr import recognize_plate
from vehicles.models import Vehicle, normalize_plate

from .models import AccessLog
from .serializers import AccessLogSerializer


# ---------------------------------------------------------------------- #
#  Helpers
# ---------------------------------------------------------------------- #
def _read_image(request, field: str) -> bytes | None:
    """Pull a binary image out of either a multipart upload or a base64 field."""
    if field in request.FILES:
        return request.FILES[field].read()

    b64 = request.data.get(f"{field}_base64")
    if b64:
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            return base64.b64decode(b64)
        except (binascii.Error, ValueError):
            return None
    return None


# ---------------------------------------------------------------------- #
#  Logs
# ---------------------------------------------------------------------- #
class AccessLogList(generics.ListAPIView):
    serializer_class = AccessLogSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["timestamp", "status"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        qs = AccessLog.objects.select_related("vehicle", "user").all()
        params = self.request.query_params

        if (s := params.get("status")):
            qs = qs.filter(status=s.upper())

        if (plate := params.get("plate")):
            qs = qs.filter(plate_detected__icontains=plate.upper())

        if (start := params.get("from")):
            qs = qs.filter(timestamp__date__gte=start)
        if (end := params.get("to")):
            qs = qs.filter(timestamp__date__lte=end)
        return qs


# ---------------------------------------------------------------------- #
#  Stats
# ---------------------------------------------------------------------- #
@api_view(["GET"])
@permission_classes([IsAdminRole])
def stats(request):
    today = timezone.localdate()
    qs = AccessLog.objects.all()

    total = qs.count()
    granted = qs.filter(status=AccessLog.Decision.GRANTED).count()
    denied = qs.filter(status=AccessLog.Decision.DENIED).count()
    today_qs = qs.filter(timestamp__date=today)

    last_7 = (
        qs.filter(timestamp__date__gte=today - timezone.timedelta(days=6))
        .extra({"day": "date(timestamp)"})
        .values("day")
        .annotate(
            granted=Count("id", filter=Q(status=AccessLog.Decision.GRANTED)),
            denied=Count("id", filter=Q(status=AccessLog.Decision.DENIED)),
        )
        .order_by("day")
    )

    return Response(
        {
            "totals": {
                "all_time": total,
                "granted": granted,
                "denied": denied,
                "today": today_qs.count(),
                "today_granted": today_qs.filter(
                    status=AccessLog.Decision.GRANTED
                ).count(),
                "today_denied": today_qs.filter(
                    status=AccessLog.Decision.DENIED
                ).count(),
            },
            "registered_vehicles": Vehicle.objects.filter(is_active=True).count(),
            "last_7_days": list(last_7),
            "recent_logs": AccessLogSerializer(qs[:5], many=True).data,
        }
    )


# ---------------------------------------------------------------------- #
#  The big one: end-to-end gate decision
# ---------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def verify_entry(request):
    """
    Combined gate-decision endpoint.

    Inputs (any combination):
        plate_image       (file or _base64) – we OCR it
        plate_number      (string)          – skip OCR, use this directly
        face_image        (file or _base64) – mandatory for biometric step

    Returns:
        {
          decision: GRANTED | DENIED,
          reason:   "...",
          plate: { number, registered, ... },
          biometric: { matched, distance, ... },
          log_id: int
        }
    """
    response = {
        "plate": {"number": "", "registered": False},
        "biometric": {"matched": False, "distance": None, "found_face": False},
    }

    # -------- 1. Resolve plate ------------------------------------------------
    plate_number = (request.data.get("plate_number") or "").strip()
    plate_img_bytes = _read_image(request, "plate_image")

    if not plate_number and plate_img_bytes:
        ocr = recognize_plate(plate_img_bytes)
        plate_number = ocr["plate_number"]
        response["plate"].update(
            {
                "ocr_confidence": ocr["confidence"],
                "raw_text": ocr["raw_text"],
                "found_plate": ocr["found_plate"],
            }
        )

    plate_number = normalize_plate(plate_number)
    response["plate"]["number"] = plate_number

    vehicle = None
    if plate_number:
        vehicle = Vehicle.objects.filter(
            plate_number=plate_number, is_active=True
        ).select_related("owner").first()
    response["plate"]["registered"] = vehicle is not None

    # -------- 2. Biometric step ----------------------------------------------
    face_img_bytes = _read_image(request, "face_image")
    user = vehicle.owner if vehicle else None

    if user and face_img_bytes:
        profile = getattr(user, "biometric", None)
        if profile and profile.encoding:
            face_result = verify_face(face_img_bytes, bytes(profile.encoding))
            response["biometric"] = face_result
        else:
            response["biometric"]["reason"] = "Owner has no biometric enrolled."
    elif not face_img_bytes:
        response["biometric"]["reason"] = "No face image provided."

    # -------- 3. Decision ----------------------------------------------------
    plate_match = response["plate"]["registered"]
    bio_match = bool(response["biometric"].get("matched"))

    if plate_match and bio_match:
        decision = AccessLog.Decision.GRANTED
        reason = "Vehicle registered and biometric verified."
    elif not plate_number:
        decision = AccessLog.Decision.DENIED
        reason = "License plate could not be read."
    elif not plate_match:
        decision = AccessLog.Decision.DENIED
        reason = f"Plate '{plate_number}' is not registered."
    elif not bio_match:
        decision = AccessLog.Decision.DENIED
        reason = response["biometric"].get(
            "reason", "Biometric verification failed."
        )
    else:
        decision = AccessLog.Decision.DENIED
        reason = "Verification failed."

    # -------- 4. Persist log -------------------------------------------------
    log = AccessLog(
        plate_detected=plate_number or "UNREADABLE",
        vehicle=vehicle,
        user=user,
        status=decision,
        reason=reason,
        plate_match=plate_match,
        biometric_match=bio_match,
        biometric_distance=response["biometric"].get("distance"),
    )
    if plate_img_bytes:
        log.snapshot.save(
            f"entry_{timezone.now().strftime('%Y%m%d%H%M%S')}.jpg",
            ContentFile(plate_img_bytes),
            save=False,
        )
    log.save()

    response["decision"] = decision
    response["reason"] = reason
    response["log_id"] = log.id
    response["timestamp"] = log.timestamp.isoformat()

    return Response(response, status=status.HTTP_200_OK)
