"""
Access endpoints
================

* GET  /api/access/logs/                  list & filter access logs
* GET  /api/access/stats/                 dashboard statistics
* POST /api/access/verify-entry/          ENTRY decision (OCR + biometric/passkey)
* POST /api/access/verify-exit/           EXIT decision (OCR + biometric/passkey)
* POST /api/access/live-detect/           live-camera frame OCR with debounce
* POST /api/access/manual-override/       admin force-grant for a plate (entry or exit)
"""

import base64
import binascii
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, generics, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from parking.models import ParkingSession
from recognition.face_engine import verify_face
from recognition.plate_ocr import recognize_plate
from vehicles.models import UserVehicle, Vehicle, normalize_plate

from .models import AccessLog
from .serializers import AccessLogSerializer


# ====================================================================== #
#  Helpers
# ====================================================================== #
def _read_image(request, field: str) -> bytes | None:
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


def _resolve_plate(request) -> tuple[str, dict]:
    """
    Returns (normalized_plate_number, ocr_meta).
    ocr_meta has: ocr_confidence, raw_text, found_plate – only if OCR ran.
    """
    plate_number = (request.data.get("plate_number") or "").strip()
    plate_img_bytes = _read_image(request, "plate_image")

    meta: dict = {}
    if not plate_number and plate_img_bytes:
        ocr = recognize_plate(plate_img_bytes)
        plate_number = ocr["plate_number"]
        meta = {
            "ocr_confidence": ocr["confidence"],
            "raw_text": ocr["raw_text"],
            "found_plate": ocr["found_plate"],
        }
    return normalize_plate(plate_number), meta


def _check_biometric(user, face_img_bytes: bytes | None) -> dict:
    """Run face_recognition against the user's stored encoding."""
    result = {"matched": False, "distance": None, "found_face": False, "available": False}
    if not user:
        result["reason"] = "No user to verify against."
        return result
    profile = getattr(user, "biometric", None)
    if not profile or not profile.encoding:
        result["reason"] = "User has no face biometric enrolled."
        return result
    if not face_img_bytes:
        result["reason"] = "No face image provided."
        return result
    result["available"] = True
    face_result = verify_face(face_img_bytes, bytes(profile.encoding))
    result.update(face_result)
    return result


def _user_can_use_vehicle(user, vehicle) -> bool:
    if not user or not vehicle:
        return False
    return UserVehicle.objects.filter(user=user, vehicle=vehicle).exists()


# ====================================================================== #
#  Verify ENTRY
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def verify_entry(request):
    """
    Combined ENTRY decision.

    Optional inputs:
        plate_image (or plate_number)
        face_image                   – face_recognition fallback
        webauthn_user_id             – if a Passkey already verified the driver
        via                          – string label (manual / live_camera / kiosk)
    """
    response: dict = {"event_type": "ENTRY"}
    plate_number, ocr_meta = _resolve_plate(request)
    response["plate"] = {"number": plate_number, **ocr_meta}

    vehicle = (
        Vehicle.objects.filter(plate_number=plate_number, is_active=True)
        .prefetch_related("uservehicle_set__user")
        .first()
        if plate_number
        else None
    )
    response["plate"]["registered"] = vehicle is not None

    # Stop duplicate-entry: if there's already a PARKED session for this vehicle, deny.
    if vehicle and ParkingSession.active_for(vehicle):
        log = _persist(
            request,
            AccessLog.Event.ENTRY,
            plate_number,
            vehicle,
            None,
            False,
            False,
            False,
            ocr_meta.get("ocr_confidence", "none"),
            "Duplicate entry – vehicle is already parked.",
            AccessLog.Decision.DENIED,
        )
        response["decision"] = AccessLog.Decision.DENIED
        response["reason"] = log.reason
        response["log_id"] = log.id
        return Response(response)

    # WebAuthn pre-verified user (frontend already proved identity)?
    webauthn_user_id = request.data.get("webauthn_user_id")
    webauthn_user = None
    if webauthn_user_id:
        from accounts.models import User as _U
        webauthn_user = _U.objects.filter(pk=webauthn_user_id).first()

    # Biometric (face) check – use any user linked to vehicle if not specified.
    face_img_bytes = _read_image(request, "face_image")
    bio_target_user = (
        webauthn_user
        if webauthn_user and vehicle and _user_can_use_vehicle(webauthn_user, vehicle)
        else (vehicle.primary_user if vehicle else None)
    )
    bio = _check_biometric(bio_target_user, face_img_bytes)
    response["biometric"] = bio

    # WebAuthn match flag
    webauthn_match = bool(
        webauthn_user and vehicle and _user_can_use_vehicle(webauthn_user, vehicle)
    )
    response["webauthn"] = {
        "matched": webauthn_match,
        "username": webauthn_user.username if webauthn_user else None,
    }

    # Decision logic – ENTRY requires plate match + (biometric OR webauthn)
    plate_ok = bool(vehicle)
    bio_ok = bool(bio.get("matched"))
    auth_ok = webauthn_match or bio_ok
    decision = AccessLog.Decision.GRANTED if (plate_ok and auth_ok) else AccessLog.Decision.DENIED

    if not plate_number:
        reason = "License plate could not be read."
    elif not plate_ok:
        reason = f"Plate '{plate_number}' is not registered."
    elif not auth_ok:
        reason = bio.get("reason") or "Driver identity could not be verified."
    else:
        reason = "Vehicle registered and driver identity verified."

    plate_image_bytes = _read_image(request, "plate_image")
    log = _persist(
        request,
        AccessLog.Event.ENTRY,
        plate_number,
        vehicle,
        webauthn_user or bio_target_user,
        plate_ok,
        bio_ok,
        webauthn_match,
        ocr_meta.get("ocr_confidence", "none"),
        reason,
        decision,
        snapshot_bytes=plate_image_bytes,
    )

    # Open session on successful entry.
    if decision == AccessLog.Decision.GRANTED:
        ParkingSession.objects.create(
            vehicle=vehicle,
            entry_user=webauthn_user or bio_target_user,
            entry_log=log,
        )

    response.update(
        {
            "decision": decision,
            "reason": reason,
            "log_id": log.id,
            "timestamp": log.timestamp.isoformat(),
        }
    )
    return Response(response)


# ====================================================================== #
#  Verify EXIT
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def verify_exit(request):
    """
    EXIT decision.  Same shape as verify_entry but additionally requires
    that there's an open ParkingSession for the plate.
    """
    response: dict = {"event_type": "EXIT"}
    plate_number, ocr_meta = _resolve_plate(request)
    response["plate"] = {"number": plate_number, **ocr_meta}

    vehicle = (
        Vehicle.objects.filter(plate_number=plate_number, is_active=True).first()
        if plate_number
        else None
    )
    response["plate"]["registered"] = vehicle is not None
    session = ParkingSession.active_for(vehicle) if vehicle else None
    response["session_found"] = session is not None

    webauthn_user_id = request.data.get("webauthn_user_id")
    webauthn_user = None
    if webauthn_user_id:
        from accounts.models import User as _U
        webauthn_user = _U.objects.filter(pk=webauthn_user_id).first()

    face_img_bytes = _read_image(request, "face_image")
    bio_target_user = (
        webauthn_user
        if webauthn_user and vehicle and _user_can_use_vehicle(webauthn_user, vehicle)
        else (vehicle.primary_user if vehicle else None)
    )
    bio = _check_biometric(bio_target_user, face_img_bytes)
    response["biometric"] = bio

    webauthn_match = bool(
        webauthn_user and vehicle and _user_can_use_vehicle(webauthn_user, vehicle)
    )
    response["webauthn"] = {
        "matched": webauthn_match,
        "username": webauthn_user.username if webauthn_user else None,
    }

    plate_ok = bool(vehicle)
    bio_ok = bool(bio.get("matched"))
    auth_ok = webauthn_match or bio_ok

    if not plate_ok:
        decision = AccessLog.Decision.DENIED
        reason = (
            "License plate could not be read."
            if not plate_number
            else f"Plate '{plate_number}' is not registered."
        )
    elif not session:
        decision = AccessLog.Decision.DENIED
        reason = "No active parking session for this vehicle (was it ever parked?)."
    elif not auth_ok:
        decision = AccessLog.Decision.DENIED
        reason = bio.get("reason") or "Driver identity could not be verified."
    else:
        decision = AccessLog.Decision.GRANTED
        reason = "Vehicle and driver identity verified – exit allowed."

    plate_image_bytes = _read_image(request, "plate_image")
    log = _persist(
        request,
        AccessLog.Event.EXIT,
        plate_number,
        vehicle,
        webauthn_user or bio_target_user,
        plate_ok,
        bio_ok,
        webauthn_match,
        ocr_meta.get("ocr_confidence", "none"),
        reason,
        decision,
        snapshot_bytes=plate_image_bytes,
    )

    if decision == AccessLog.Decision.GRANTED and session:
        session.close(
            exit_user=webauthn_user or bio_target_user,
            exit_log=log,
        )

    response.update(
        {
            "decision": decision,
            "reason": reason,
            "log_id": log.id,
            "timestamp": log.timestamp.isoformat(),
        }
    )
    return Response(response)


# ====================================================================== #
#  Live camera frame OCR (with debounce)
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAdminRole])
@parser_classes([MultiPartParser, JSONParser])
def live_detect(request):
    """
    The live-camera page sends a frame every couple of seconds.
    We OCR it; if the plate looks plausible AND we haven't logged that plate
    in the last OCR_DEBOUNCE_SECONDS seconds, we return the candidate so the
    UI can prompt for the next step.
    """
    img_bytes = _read_image(request, "plate_image")
    if not img_bytes:
        return Response({"detail": "plate_image required"}, status=400)
    try:
        ocr = recognize_plate(img_bytes)
    except Exception as exc:  # noqa: BLE001
        return Response({"detail": f"OCR failed: {exc}"}, status=500)

    plate = ocr["plate_number"]
    confidence = ocr["confidence"]
    min_conf = (settings.OCR_MIN_CONFIDENCE or "medium").lower()
    rank = {"high": 3, "medium": 2, "low": 1, "none": 0}

    response = {
        "plate": plate,
        "confidence": confidence,
        "raw_text": ocr["raw_text"],
        "found_plate": ocr["found_plate"],
        "registered": False,
        "fresh": False,
        "vehicle": None,
        "active_session": None,
    }

    if not plate or rank.get(confidence, 0) < rank.get(min_conf, 2):
        return Response(response)

    vehicle = Vehicle.objects.filter(plate_number=plate).first()
    if not vehicle:
        return Response(response)

    response["registered"] = True
    from vehicles.serializers import VehicleSerializer
    response["vehicle"] = VehicleSerializer(vehicle).data

    # Debounce – don't trigger again if we logged this plate recently.
    cutoff = timezone.now() - timedelta(seconds=settings.OCR_DEBOUNCE_SECONDS)
    recent = AccessLog.objects.filter(
        plate_detected=plate, timestamp__gte=cutoff
    ).exists()
    response["fresh"] = not recent

    session = ParkingSession.active_for(vehicle)
    response["active_session"] = (
        {
            "id": session.id,
            "entry_time": session.entry_time.isoformat(),
        }
        if session
        else None
    )
    response["suggested_event"] = "EXIT" if session else "ENTRY"

    # ----- Risk-based decision (autonomous mode) -----
    # Find the "primary" user linked to the vehicle (first OWNER, else first user).
    primary = vehicle.primary_user
    trust = primary.trust_level if primary else "NORMAL"
    response["trust_level"] = trust
    # Auto-grant rule: if autonomous mode is on, the plate is registered, the
    # primary user is TRUSTED, and there's no risky pattern, the gate can open
    # without biometric.
    autonomous = bool(getattr(settings, "AUTONOMOUS_MODE", True))
    is_suspicious_time = _is_off_hours(timezone.localtime().hour)
    risk_factors = []
    if not primary:
        risk_factors.append("no_primary_user")
    if primary and primary.is_suspicious:
        risk_factors.append("user_flagged_suspicious")
    if is_suspicious_time:
        risk_factors.append("off_hours_entry")
    if _recent_failed_attempts(plate, minutes=10) >= 3:
        risk_factors.append("multiple_recent_failures")

    can_auto_grant = (
        autonomous
        and not recent
        and primary is not None
        and primary.is_trusted
        and not risk_factors
    )
    response["risk_factors"] = risk_factors
    response["can_auto_grant"] = can_auto_grant
    response["autonomous_mode"] = autonomous

    # If conditions allow, perform the access action immediately.
    if can_auto_grant and not recent:
        event_type = AccessLog.Event.EXIT if session else AccessLog.Event.ENTRY
        log = AccessLog.objects.create(
            event_type=event_type,
            plate_detected=plate,
            vehicle=vehicle,
            user=primary,
            status=AccessLog.Decision.GRANTED,
            reason="Autonomous mode: trusted vehicle, OCR matched, no risk factors.",
            plate_match=True,
            biometric_match=False,
            webauthn_match=False,
            confidence=AccessLog.Confidence.HIGH if confidence == "high" else AccessLog.Confidence.MEDIUM,
            via="autonomous",
        )
        if event_type == AccessLog.Event.ENTRY:
            ParkingSession.objects.create(
                vehicle=vehicle, entry_user=primary, entry_log=log
            )
        else:
            if session:
                session.close(exit_user=primary, exit_log=log)
        response["auto_granted"] = True
        response["log_id"] = log.id

    return Response(response)


def _is_off_hours(hour: int) -> bool:
    """11pm–5am is considered off-hours (configurable later)."""
    return hour >= 23 or hour < 5


def _recent_failed_attempts(plate: str, minutes: int = 10) -> int:
    cutoff = timezone.now() - timedelta(minutes=minutes)
    return AccessLog.objects.filter(
        plate_detected=plate,
        status=AccessLog.Decision.DENIED,
        timestamp__gte=cutoff,
    ).count()


# ====================================================================== #
#  Manual override (admin force-grant)
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAdminRole])
def manual_override(request):
    """
    An admin can force-open the gate for a plate when OCR/biometric isn't
    cooperating.  Logs everything so it's auditable.
    Body: { plate_number, event_type: ENTRY|EXIT, reason }
    """
    plate_number = normalize_plate(request.data.get("plate_number") or "")
    event_type = (request.data.get("event_type") or "ENTRY").upper()
    reason = request.data.get("reason") or "Manual admin override."

    if event_type not in dict(AccessLog.Event.choices):
        return Response({"detail": "event_type must be ENTRY or EXIT"}, status=400)

    vehicle = Vehicle.objects.filter(plate_number=plate_number).first() if plate_number else None
    log = AccessLog.objects.create(
        event_type=event_type,
        plate_detected=plate_number or "MANUAL",
        vehicle=vehicle,
        user=request.user,
        status=AccessLog.Decision.GRANTED,
        reason=f"[OVERRIDE by {request.user.username}] {reason}",
        plate_match=bool(vehicle),
        biometric_match=False,
        webauthn_match=False,
        confidence=AccessLog.Confidence.NONE,
        via="manual_override",
    )

    if vehicle:
        if event_type == "ENTRY":
            if not ParkingSession.active_for(vehicle):
                ParkingSession.objects.create(
                    vehicle=vehicle, entry_user=request.user, entry_log=log
                )
        else:
            session = ParkingSession.active_for(vehicle)
            if session:
                session.close(exit_user=request.user, exit_log=log)

    return Response(AccessLogSerializer(log).data, status=201)


# ====================================================================== #
#  Logs + stats
# ====================================================================== #
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
        if (e := params.get("event")):
            qs = qs.filter(event_type=e.upper())
        if (plate := params.get("plate")):
            qs = qs.filter(plate_detected__icontains=plate.upper())
        if (start := params.get("from")):
            qs = qs.filter(timestamp__date__gte=start)
        if (end := params.get("to")):
            qs = qs.filter(timestamp__date__lte=end)
        return qs


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
            "active_sessions": ParkingSession.objects.filter(
                status=ParkingSession.Status.PARKED
            ).count(),
            "last_7_days": list(last_7),
            "recent_logs": AccessLogSerializer(qs[:5], many=True).data,
        }
    )


# ====================================================================== #
#  Internal: persist a log row
# ====================================================================== #
def _persist(
    request,
    event_type,
    plate,
    vehicle,
    user,
    plate_ok,
    bio_ok,
    webauthn_ok,
    confidence,
    reason,
    decision,
    snapshot_bytes: bytes | None = None,
) -> AccessLog:
    log = AccessLog(
        event_type=event_type,
        plate_detected=plate or "UNREADABLE",
        vehicle=vehicle,
        user=user,
        status=decision,
        reason=reason,
        plate_match=plate_ok,
        biometric_match=bio_ok,
        webauthn_match=webauthn_ok,
        confidence=confidence if confidence else AccessLog.Confidence.NONE,
        via=request.data.get("via", "manual"),
    )
    if snapshot_bytes:
        log.snapshot.save(
            f"snap_{timezone.now().strftime('%Y%m%d%H%M%S')}.jpg",
            ContentFile(snapshot_bytes),
            save=False,
        )
    log.save()
    return log
