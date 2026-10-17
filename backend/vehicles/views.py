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

from django.db import transaction

from accounts.models import User
from accounts.permissions import IsAdminRole, is_admin
from core.validators import validate_document
from recognition import service as recog

from .claims import claim_vehicle
from .models import UserVehicle, Vehicle, assignments_prefetch, fuzzy_find_vehicle, normalize_plate
from .serializers import (
    UserVehicleSerializer,
    VehicleCreateSerializer,
    VehicleSerializer,
)


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.prefetch_related(assignments_prefetch()).all()
    permission_classes = [IsAdminRole]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return VehicleCreateSerializer
        return VehicleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            from .models import plate_canonical

            qs = qs.filter(plate_canonical__icontains=plate_canonical(search))
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
        return Response(self._fresh(vehicle))

    @action(detail=True, methods=["post"], url_path="unblock")
    def unblock(self, request, pk=None):
        """Restore a BLOCKED vehicle to ACTIVE."""
        vehicle = self.get_object()
        vehicle.status = Vehicle.Status.ACTIVE
        vehicle.block_reason = ""
        vehicle.save(update_fields=["status", "block_reason"])
        return Response(self._fresh(vehicle))

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """Move an UNDER_REVIEW vehicle to ACTIVE and verify the linked driver's documents."""
        vehicle = self.get_object()
        if vehicle.status != Vehicle.Status.UNDER_REVIEW:
            return Response(
                {"detail": "Only UNDER_REVIEW vehicles can be approved."},
                status=400,
            )
        with transaction.atomic():
            vehicle.status = Vehicle.Status.ACTIVE
            vehicle.save(update_fields=["status"])
            # Approving a vehicle approves the links of the people who registered it.
            UserVehicle.objects.filter(vehicle=vehicle, approved=False).update(approved=True)

        # Also mark documents_verified for any linked user who has uploaded
        # both their driving licence and CNIC — approving the vehicle is the
        # admin's signal that they've reviewed the driver's compliance too.
        for link in vehicle.uservehicle_set.select_related("user").all():
            u = link.user
            if u.driving_license_doc and u.cnic_doc and not u.documents_verified:
                u.documents_verified = True
                u.save(update_fields=["documents_verified"])

        return Response(self._fresh(vehicle))

    def _fresh(self, vehicle):
        v = Vehicle.objects.prefetch_related(assignments_prefetch()).get(pk=vehicle.pk)
        return VehicleSerializer(v, context={"request": self.request}).data

    @action(detail=False, methods=["get"], url_path=r"lookup/(?P<plate>[^/.]+)")
    def lookup(self, request, plate=None):
        vehicle = fuzzy_find_vehicle(plate)
        if not vehicle:
            return Response(
                {"detail": "Vehicle not registered.", "plate": normalize_plate(plate)},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self._fresh(vehicle))

    # ---------- Assignments sub-resource ----------
    @action(detail=True, methods=["get", "post"], url_path="assignments")
    def assignments(self, request, pk=None):
        vehicle = self.get_object()
        if request.method == "GET":
            qs = UserVehicle.objects.filter(vehicle=vehicle).select_related("user", "user__biometric")
            return Response(UserVehicleSerializer(qs, many=True, context={"request": request}).data)

        # POST – add or update an assignment
        user_id = request.data.get("user") or request.data.get("user_id")
        relationship = (request.data.get("relationship") or "DRIVER").upper()
        if not user_id:
            return Response({"detail": "user is required"}, status=400)
        if relationship not in dict(UserVehicle.Relationship.choices):
            return Response(
                {"detail": "relationship must be OWNER, DRIVER, or BOTH"},
                status=400,
            )
        user = get_object_or_404(User, pk=user_id)
        # An admin assigning someone is an approval by definition.
        link, _ = UserVehicle.objects.update_or_create(
            user=user, vehicle=vehicle, defaults={"relationship": relationship, "approved": True}
        )
        return Response(
            UserVehicleSerializer(link, context={"request": request}).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path=r"assignments/(?P<assignment_id>\d+)/approve")
    def approve_assignment(self, request, pk=None, assignment_id=None):
        vehicle = self.get_object()
        link = get_object_or_404(UserVehicle, pk=assignment_id, vehicle=vehicle)
        link.approved = True
        link.save(update_fields=["approved"])
        return Response(UserVehicleSerializer(link, context={"request": request}).data)

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
    """Vehicles linked to the current user (approved or pending)."""
    qs = (
        Vehicle.objects.filter(uservehicle__user=request.user)
        .prefetch_related(assignments_prefetch())
        .distinct()
    )
    data = VehicleSerializer(qs, many=True, context={"request": request}).data
    pending = set(
        UserVehicle.objects.filter(user=request.user, approved=False).values_list("vehicle_id", flat=True)
    )
    for row in data:
        row["my_link_pending"] = row["id"] in pending
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def add_my_vehicle(request):
    """
    Driver self-service: add a vehicle to my account (see vehicles/claims.py).
    Body: plate_number, make?, model?, color?, vehicle_type?, registration_doc?
    """
    plate = (request.data.get("plate_number") or "").strip()
    if not plate:
        return Response({"detail": "plate_number is required"}, status=400)
    doc = request.FILES.get("registration_doc")
    if doc is not None:
        validate_document(doc, "registration_doc")

    res = claim_vehicle(
        request.user,
        plate,
        make=request.data.get("make", ""),
        model=request.data.get("model", ""),
        color=request.data.get("color", ""),
        vehicle_type=request.data.get("vehicle_type", "CAR"),
        registration_doc=doc,
    )
    v = Vehicle.objects.prefetch_related(assignments_prefetch()).get(pk=res["vehicle"].pk)
    return Response(
        {
            "vehicle": VehicleSerializer(v, context={"request": request}).data,
            "duplicate": res["duplicate"],
            "link_approved": res["link"].approved,
            "message": res["message"],
        },
        status=status.HTTP_201_CREATED if res["created"] else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_driver_to_my_vehicle(request, vehicle_id: int):
    """
    An approved OWNER adds another driver to their own car by username.
    (The old UI called admin-only endpoints for this, so it always failed.)
    Body: { username, relationship?: DRIVER|BOTH }
    """
    owner_link = UserVehicle.objects.filter(
        user=request.user,
        vehicle_id=vehicle_id,
        approved=True,
        relationship__in=[UserVehicle.Relationship.OWNER, UserVehicle.Relationship.BOTH],
    ).select_related("vehicle").first()
    if not owner_link:
        return Response({"detail": "Only an approved owner of this vehicle can add drivers."}, status=403)
    username = (request.data.get("username") or "").strip()
    target = User.objects.filter(username=username, is_active=True).first()
    if not target:
        return Response({"detail": f'User "{username}" not found.'}, status=404)
    rel = (request.data.get("relationship") or "DRIVER").upper()
    if rel not in (UserVehicle.Relationship.DRIVER, UserVehicle.Relationship.BOTH):
        rel = UserVehicle.Relationship.DRIVER
    link, _ = UserVehicle.objects.update_or_create(
        user=target, vehicle=owner_link.vehicle, defaults={"relationship": rel, "approved": True}
    )
    return Response(UserVehicleSerializer(link, context={"request": request}).data, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def upload_vehicle_doc(request, vehicle_id: int):
    """Driver uploads registration doc for one of their own vehicles."""
    link = UserVehicle.objects.filter(
        user=request.user, vehicle_id=vehicle_id
    ).first()
    if not link:
        return Response({"detail": "Vehicle not found in your account."}, status=404)
    if "registration_doc" not in request.FILES:
        return Response({"detail": "registration_doc file required."}, status=400)
    vehicle = link.vehicle
    vehicle.registration_doc = validate_document(request.FILES["registration_doc"], "registration_doc")
    vehicle.save(update_fields=["registration_doc"])
    v = Vehicle.objects.prefetch_related(assignments_prefetch()).get(pk=vehicle.pk)
    return Response(VehicleSerializer(v, context={"request": request}).data)


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
    with transaction.atomic():
        link.delete()
        # Remove the vehicle only if nobody is left AND it has no history:
        # deleting a car with sessions would cascade away its audit trail.
        if not vehicle.uservehicle_set.exists() and not vehicle.parking_sessions.exists():
            vehicle.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAdminRole])
def pending_approvals(request):
    """All vehicles waiting for admin approval (status=UNDER_REVIEW)."""
    qs = (
        Vehicle.objects.filter(status=Vehicle.Status.UNDER_REVIEW)
        .prefetch_related(assignments_prefetch())
        .order_by("-created_at")
    )
    return Response(VehicleSerializer(qs, many=True, context={"request": request}).data)


@api_view(["GET"])
@permission_classes([IsAdminRole])
def pending_claims(request):
    """Drivers asking to be linked to an already-registered vehicle."""
    qs = (
        UserVehicle.objects.filter(approved=False)
        .select_related("user", "user__biometric", "vehicle")
        .order_by("-created_at")
    )
    return Response(
        [
            {
                "id": link.id,
                "relationship": link.relationship,
                "created_at": link.created_at.isoformat(),
                "vehicle": {
                    "id": link.vehicle.id,
                    "plate_number": link.vehicle.plate_number,
                    "make": link.vehicle.make,
                    "model": link.vehicle.model,
                    "status": link.vehicle.status,
                },
                "user": {
                    "id": link.user.id,
                    "username": link.user.username,
                    "first_name": link.user.first_name,
                    "last_name": link.user.last_name,
                    "documents_verified": link.user.documents_verified,
                },
            }
            for link in qs[:200]
        ]
    )


@api_view(["GET"])
@permission_classes([IsAdminRole])
def pending_documents(request):
    """
    Drivers who have uploaded at least one personal document (driving
    licence or CNIC) but are not yet documents_verified — regardless of
    whether they own a vehicle. This catches drivers who only uploaded
    docs without registering a car, who would otherwise never appear
    anywhere for admin review.
    """
    from django.db.models import Q
    from accounts.serializers import UserSerializer
    from accounts.models import User

    qs = (
        User.objects.filter(role=User.Role.DRIVER, documents_verified=False)
        .filter(Q(driving_license_doc__isnull=False) & ~Q(driving_license_doc="")
                | Q(cnic_doc__isnull=False) & ~Q(cnic_doc=""))
        .order_by("-id")
    )
    return Response(UserSerializer(qs.select_related("biometric"), many=True, context={"request": request}).data)


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
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            validate_password(password)
        except DjangoValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=400)
        driver = User.objects.create_user(
            username=username,
            password=password,
            first_name=driver_payload.get("first_name", ""),
            last_name=driver_payload.get("last_name", ""),
            phone=driver_payload.get("phone", ""),
            cnic=driver_payload.get("cnic", ""),
            email=driver_payload.get("email", ""),
            role=User.Role.DRIVER,
            gate_registered=True,  # no biometric enrolled yet
        )

    if driver:
        UserVehicle.objects.update_or_create(
            user=driver,
            vehicle=vehicle,
            defaults={"relationship": relationship, "approved": True},
        )

    from accounts.serializers import UserSerializer

    vehicle = Vehicle.objects.prefetch_related(assignments_prefetch()).get(pk=vehicle.pk)
    return Response(
        {
            "vehicle": VehicleSerializer(vehicle, context={"request": request}).data,
            "driver": UserSerializer(driver, context={"request": request}).data if driver else None,
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
@permission_classes([IsAdminRole])
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
        result = recog.read_plate(img_bytes)
    except recog.RecognitionError as exc:
        return Response({"detail": str(exc)}, status=400)
    except recog.RecognitionUnavailable as exc:
        return Response({"detail": str(exc)}, status=503)
    matched_vehicle = fuzzy_find_vehicle(result["plate_number"]) if result["plate_number"] else None
    result["registered"] = matched_vehicle is not None
    if matched_vehicle:
        v = Vehicle.objects.prefetch_related(assignments_prefetch()).get(pk=matched_vehicle.pk)
        result["vehicle"] = VehicleSerializer(v, context={"request": request}).data
    return Response(result)
