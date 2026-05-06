"""
Vehicle endpoints
=================

* /api/vehicles/                       CRUD (admin only)
* /api/vehicles/lookup/<plate>/        Find vehicle by plate
* /api/vehicles/<id>/assignments/      GET/POST – manage user↔vehicle links
* /api/vehicles/<id>/assignments/<aid>/ DELETE – remove a link
* /api/vehicles/detect-plate/          POST image -> OCR result
* /api/vehicles/my/                    Current user's vehicles (driver view)
"""

import base64
import binascii

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    parser_classes,
    permission_classes,
)
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminRole
from recognition.plate_ocr import recognize_plate

from .models import UserVehicle, Vehicle, normalize_plate
from .serializers import (
    UserVehicleSerializer,
    VehicleCreateSerializer,
    VehicleSerializer,
)


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.prefetch_related("uservehicle_set__user").all()
    permission_classes = [IsAdminRole]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return VehicleCreateSerializer
        return VehicleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(plate_number__icontains=search.upper().strip())
        active = self.request.query_params.get("active")
        if active is not None:
            qs = qs.filter(is_active=active.lower() in ("1", "true", "yes"))
        return qs

    @action(detail=False, methods=["get"], url_path=r"lookup/(?P<plate>[^/.]+)")
    def lookup(self, request, plate=None):
        plate = normalize_plate(plate)
        try:
            vehicle = Vehicle.objects.get(plate_number=plate)
        except Vehicle.DoesNotExist:
            return Response(
                {"detail": "Vehicle not registered.", "plate": plate},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(VehicleSerializer(vehicle).data)

    # ---------- Assignments sub-resource ----------
    @action(detail=True, methods=["get", "post"], url_path="assignments")
    def assignments(self, request, pk=None):
        vehicle = self.get_object()
        if request.method == "GET":
            qs = UserVehicle.objects.filter(vehicle=vehicle).select_related("user")
            return Response(UserVehicleSerializer(qs, many=True).data)

        # POST – add or update an assignment
        user_id = request.data.get("user")
        relationship = (request.data.get("relationship") or "DRIVER").upper()
        if not user_id:
            return Response({"detail": "user is required"}, status=400)
        if relationship not in dict(UserVehicle.Relationship.choices):
            return Response(
                {"detail": "relationship must be OWNER, DRIVER, or BOTH"},
                status=400,
            )
        user = get_object_or_404(User, pk=user_id)
        link, _ = UserVehicle.objects.update_or_create(
            user=user, vehicle=vehicle, defaults={"relationship": relationship}
        )
        return Response(
            UserVehicleSerializer(link).data, status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"assignments/(?P<assignment_id>\d+)",
    )
    def remove_assignment(self, request, pk=None, assignment_id=None):
        vehicle = self.get_object()
        link = get_object_or_404(UserVehicle, pk=assignment_id, vehicle=vehicle)
        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------- #
#  Driver's own vehicles
# ---------------------------------------------------------------------- #
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_vehicles(request):
    """Vehicles linked to the current user (any relationship)."""
    qs = (
        Vehicle.objects.filter(users=request.user)
        .prefetch_related("uservehicle_set__user")
        .distinct()
    )
    return Response(VehicleSerializer(qs, many=True).data)


# ---------------------------------------------------------------------- #
#  Plate OCR helper
# ---------------------------------------------------------------------- #
def _extract_image_bytes(request) -> bytes | None:
    if "image" in request.FILES:
        return request.FILES["image"].read()
    b64 = request.data.get("image_base64")
    if b64:
        if "," in b64:
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
    """Run OCR on an image. Returns plate text + match status."""
    img_bytes = _extract_image_bytes(request)
    if not img_bytes:
        return Response(
            {"detail": "No image provided. Send `image` (multipart) or `image_base64`."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        result = recognize_plate(img_bytes)
    except Exception as exc:  # noqa: BLE001
        return Response(
            {"detail": f"OCR failed: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    matched_vehicle = None
    if result["plate_number"]:
        matched_vehicle = Vehicle.objects.filter(
            plate_number=result["plate_number"]
        ).first()
    result["registered"] = matched_vehicle is not None
    if matched_vehicle:
        result["vehicle"] = VehicleSerializer(matched_vehicle).data
    return Response(result)
