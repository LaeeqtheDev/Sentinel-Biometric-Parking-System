"""
Vehicle endpoints.

* /api/vehicles/                CRUD
* /api/vehicles/detect-plate/   POST image -> OCR result (no DB lookup)
"""

import base64
import binascii

from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from recognition.plate_ocr import recognize_plate

from .models import Vehicle, normalize_plate
from .serializers import VehicleSerializer


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related("owner").all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            search = search.upper().strip()
            qs = qs.filter(plate_number__icontains=search)

        owner = self.request.query_params.get("owner")
        if owner:
            qs = qs.filter(owner_id=owner)

        active = self.request.query_params.get("active")
        if active is not None:
            qs = qs.filter(is_active=active.lower() in ("1", "true", "yes"))
        return qs

    @action(detail=False, methods=["get"], url_path="lookup/(?P<plate>[^/.]+)")
    def lookup(self, request, plate=None):
        """Find a vehicle by plate number (used during entry verification)."""
        plate = normalize_plate(plate)
        try:
            vehicle = Vehicle.objects.select_related("owner").get(plate_number=plate)
        except Vehicle.DoesNotExist:
            return Response(
                {"detail": "Vehicle not registered.", "plate": plate},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(VehicleSerializer(vehicle).data)


def _extract_image_bytes(request) -> bytes | None:
    """Accept either an uploaded `image` file or a base64 `image_base64` string."""
    if "image" in request.FILES:
        return request.FILES["image"].read()

    b64 = request.data.get("image_base64")
    if b64:
        if "," in b64:                    # data URL prefix
            b64 = b64.split(",", 1)[1]
        try:
            return base64.b64decode(b64)
        except (binascii.Error, ValueError):
            return None
    return None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def detect_plate(request):
    """
    Run OCR on an uploaded image.  Does NOT do DB lookup – the frontend can
    take the result and POST to /vehicles/lookup/<plate>/ if it wants to.
    """
    img_bytes = _extract_image_bytes(request)
    if not img_bytes:
        return Response(
            {"detail": "No image provided. Send `image` (multipart) or `image_base64`."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = recognize_plate(img_bytes)
    except Exception as exc:                                  # noqa: BLE001
        return Response(
            {"detail": f"OCR failed: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Try to match it against a registered vehicle (helpful for the UI).
    matched_vehicle = None
    if result["plate_number"]:
        matched_vehicle = (
            Vehicle.objects.filter(plate_number=result["plate_number"]).first()
        )
    result["registered"] = matched_vehicle is not None
    if matched_vehicle:
        result["vehicle"] = VehicleSerializer(matched_vehicle).data

    return Response(result)
