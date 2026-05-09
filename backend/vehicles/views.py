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
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        return qs

    @action(detail=True, methods=["post"], url_path="block")
    def block(self, request, pk=None):
        """Mark a vehicle BLOCKED with optional reason."""
        vehicle = self.get_object()
        vehicle.status = Vehicle.Status.BLOCKED
        vehicle.block_reason = request.data.get("reason", "")[:255]
        vehicle.save(update_fields=["status", "block_reason"])
        return Response(VehicleSerializer(vehicle).data)

    @action(detail=True, methods=["post"], url_path="unblock")
    def unblock(self, request, pk=None):
        """Restore a BLOCKED vehicle to ACTIVE."""
        vehicle = self.get_object()
        vehicle.status = Vehicle.Status.ACTIVE
        vehicle.block_reason = ""
        vehicle.save(update_fields=["status", "block_reason"])
        return Response(VehicleSerializer(vehicle).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """Move an UNDER_REVIEW vehicle to ACTIVE."""
        vehicle = self.get_object()
        if vehicle.status != Vehicle.Status.UNDER_REVIEW:
            return Response(
                {"detail": "Only UNDER_REVIEW vehicles can be approved."},
                status=400,
            )
        vehicle.status = Vehicle.Status.ACTIVE
        vehicle.save(update_fields=["status"])
        return Response(VehicleSerializer(vehicle).data)

    @action(detail=False, methods=["get"], url_path=r"lookup/(?P<plate>[^/.]+)")
    def lookup(self, request, plate=None):
        from .models import fuzzy_find_vehicle
        vehicle = fuzzy_find_vehicle(plate)
        if not vehicle:
            return Response(
                {"detail": "Vehicle not registered.", "plate": normalize_plate(plate)},
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def add_my_vehicle(request):
    """
    Driver self-service: add a vehicle to my account.
    Vehicle starts as UNDER_REVIEW until admin approves it.
    Body (multipart or json):
      plate_number, make?, model?, color?, vehicle_type?
      registration_doc?  (file – optional but speeds up approval)
    """
    plate = (request.data.get("plate_number") or "").strip()
    if not plate:
        return Response({"detail": "plate_number is required"}, status=400)

    from .models import fuzzy_find_vehicle

    norm_plate = normalize_plate(plate)
    existing = fuzzy_find_vehicle(plate)
    if existing:
        # Plate exists — link the user as a DRIVER but flag for review.
        link, created = UserVehicle.objects.get_or_create(
            user=request.user,
            vehicle=existing,
            defaults={"relationship": UserVehicle.Relationship.DRIVER},
        )
        if existing.status == Vehicle.Status.ACTIVE:
            existing.status = Vehicle.Status.UNDER_REVIEW
            existing.save(update_fields=["status"])
        return Response(
            {
                "vehicle": VehicleSerializer(existing).data,
                "duplicate": True,
                "message": "This plate already exists; your link is under review.",
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    vt = (request.data.get("vehicle_type") or "CAR").upper()
    if vt not in dict(Vehicle.VehicleType.choices):
        vt = "CAR"
    v = Vehicle.objects.create(
        plate_number=norm_plate,
        vehicle_type=vt,
        make=request.data.get("make", "")[:50],
        model=request.data.get("model", "")[:50],
        color=request.data.get("color", "")[:30],
        status=Vehicle.Status.UNDER_REVIEW,
    )
    if "registration_doc" in request.FILES:
        v.registration_doc = request.FILES["registration_doc"]
        v.save(update_fields=["registration_doc"])
    UserVehicle.objects.create(
        user=request.user,
        vehicle=v,
        relationship=UserVehicle.Relationship.OWNER,
    )
    return Response(
        {
            "vehicle": VehicleSerializer(v).data,
            "duplicate": False,
            "message": "Vehicle added — pending admin approval.",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_my_vehicle(request, vehicle_id: int):
    """Driver removes themselves from a vehicle they're linked to."""
    link = UserVehicle.objects.filter(
        user=request.user, vehicle_id=vehicle_id
    ).first()
    if not link:
        return Response({"detail": "Not found."}, status=404)
    vehicle = link.vehicle
    link.delete()
    # If no users left, also remove the orphaned vehicle.
    if not vehicle.uservehicle_set.exists():
        vehicle.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAdminRole])
def pending_approvals(request):
    """All vehicles waiting for admin approval (status=UNDER_REVIEW)."""
    qs = (
        Vehicle.objects.filter(status=Vehicle.Status.UNDER_REVIEW)
        .prefetch_related("uservehicle_set__user")
        .order_by("-created_at")
    )
    return Response(VehicleSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAdminRole])
def walk_up_register(request):
    """
    Admin endpoint: register a brand-new vehicle + (optionally) driver right
    at the gate.  For walk-in customers who aren't pre-registered.

    Body:
      plate_number  (required)
      make / model / color / vehicle_type  (optional)
      driver: {
          username   (required if creating new user)
          password   (required if creating new user)
          first_name / last_name / phone / cnic  (optional)
      }
      OR
      driver_id     (link to an existing user instead)
      relationship  (OWNER / DRIVER / BOTH, default OWNER)

    Vehicle is created with status=ACTIVE because admin verified in-person.
    Returns the created vehicle + driver info so the caller can immediately
    grant entry.
    """
    from accounts.models import User
    from .models import fuzzy_find_vehicle

    plate = (request.data.get("plate_number") or "").strip()
    if not plate:
        return Response({"detail": "plate_number is required"}, status=400)

    # Find or create vehicle
    norm_plate = normalize_plate(plate)
    vehicle = fuzzy_find_vehicle(plate)
    if vehicle:
        # Already in DB — just unblock if needed and continue.
        if vehicle.status != Vehicle.Status.ACTIVE:
            vehicle.status = Vehicle.Status.ACTIVE
            vehicle.save(update_fields=["status"])
    else:
        vt = (request.data.get("vehicle_type") or "CAR").upper()
        if vt not in dict(Vehicle.VehicleType.choices):
            vt = "CAR"
        vehicle = Vehicle.objects.create(
            plate_number=norm_plate,
            vehicle_type=vt,
            make=request.data.get("make", "")[:50],
            model=request.data.get("model", "")[:50],
            color=request.data.get("color", "")[:30],
            status=Vehicle.Status.ACTIVE,  # admin-verified at gate
        )

    # Find or create driver
    driver = None
    driver_payload = request.data.get("driver")
    driver_id = request.data.get("driver_id")
    relationship = (request.data.get("relationship") or "OWNER").upper()
    if relationship not in dict(UserVehicle.Relationship.choices):
        relationship = "OWNER"

    if driver_id:
        try:
            driver = User.objects.get(pk=driver_id)
        except User.DoesNotExist:
            return Response({"detail": "driver_id not found"}, status=400)
    elif isinstance(driver_payload, dict):
        username = (driver_payload.get("username") or "").strip()
        password = driver_payload.get("password")
        if not username or not password:
            return Response(
                {"detail": "driver.username and driver.password required"},
                status=400,
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {"detail": f"Username '{username}' already exists. Use driver_id to link."},
                status=400,
            )
        driver = User.objects.create_user(
            username=username,
            password=password,
            first_name=driver_payload.get("first_name", ""),
            last_name=driver_payload.get("last_name", ""),
            phone=driver_payload.get("phone", ""),
            cnic=driver_payload.get("cnic", ""),
            email=driver_payload.get("email", ""),
            role=User.Role.DRIVER,
        )

    if driver:
        UserVehicle.objects.update_or_create(
            user=driver,
            vehicle=vehicle,
            defaults={"relationship": relationship},
        )

    from accounts.serializers import UserSerializer
    return Response(
        {
            "vehicle": VehicleSerializer(vehicle).data,
            "driver": UserSerializer(driver).data if driver else None,
            "message": "Vehicle registered at gate. You can now grant entry.",
        },
        status=status.HTTP_201_CREATED,
    )


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
