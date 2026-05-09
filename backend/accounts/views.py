"""Account views: JWT login, current user, user CRUD (admin only)."""

from django.contrib.auth import get_user_model
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import IsAdminRole
from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    UserCreateSerializer,
    UserSerializer,
)

User = get_user_model()


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    """
    Public self-registration. Always creates a DRIVER role.
    Optionally creates a vehicle in the same flow (status=UNDER_REVIEW).
    Returns user info + JWT tokens so the frontend can auto-login.
    """
    data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
    # Force role to DRIVER — admins are never self-registered.
    data["role"] = User.Role.DRIVER if hasattr(User, "Role") else "DRIVER"

    # Pop vehicle fields before serializing the user
    vehicle_plate = (data.pop("vehicle_plate", "") or "").strip()
    vehicle_make = data.pop("vehicle_make", "")
    vehicle_model = data.pop("vehicle_model", "")
    vehicle_color = data.pop("vehicle_color", "")
    vehicle_type = (data.pop("vehicle_type", "") or "CAR").upper()

    serializer = UserCreateSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()

    # Optionally onboard a vehicle.  Always UNDER_REVIEW so an admin can
    # confirm ownership before the gate trusts it.
    vehicle_info = None
    if vehicle_plate:
        from vehicles.models import (
            Vehicle,
            UserVehicle,
            normalize_plate,
            fuzzy_find_vehicle,
        )
        norm_plate = normalize_plate(vehicle_plate)
        existing = fuzzy_find_vehicle(vehicle_plate)
        if existing:
            # Don't auto-grant ownership of an existing plate; flag for admin review.
            UserVehicle.objects.update_or_create(
                user=user,
                vehicle=existing,
                defaults={"relationship": UserVehicle.Relationship.DRIVER},
            )
            existing.status = Vehicle.Status.UNDER_REVIEW
            existing.save(update_fields=["status"])
            vehicle_info = {
                "id": existing.id,
                "plate_number": existing.plate_number,
                "status": existing.status,
                "duplicate": True,
                "message": "This plate already exists. Your assignment is pending admin review.",
            }
        else:
            v = Vehicle.objects.create(
                plate_number=norm_plate,
                vehicle_type=vehicle_type if vehicle_type in ("CAR","BIKE","SUV","TRUCK","OTHER") else "CAR",
                make=vehicle_make,
                model=vehicle_model,
                color=vehicle_color,
                status=Vehicle.Status.UNDER_REVIEW,
            )
            UserVehicle.objects.create(
                user=user,
                vehicle=v,
                relationship=UserVehicle.Relationship.OWNER,
            )
            vehicle_info = {
                "id": v.id,
                "plate_number": v.plate_number,
                "status": v.status,
                "duplicate": False,
                "message": "Vehicle registered (pending admin approval).",
            }

    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["username"] = user.username

    return Response(
        {
            "user": UserSerializer(user).data,
            "vehicle": vehicle_info,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Return the currently authenticated user."""
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = request.user
    if not user.check_password(serializer.validated_data["old_password"]):
        return Response(
            {"detail": "Old password is incorrect."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    user.set_password(serializer.validated_data["new_password"])
    user.save()
    return Response({"detail": "Password updated."})


class UserViewSet(viewsets.ModelViewSet):
    """Full CRUD for users.  Admin-only."""

    queryset = User.objects.all().order_by("-created_at")
    permission_classes = [IsAdminRole]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role.upper())
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(username__icontains=search) | qs.filter(
                first_name__icontains=search
            ) | qs.filter(last_name__icontains=search)
        return qs

    @action(detail=True, methods=["post"], url_path="trust")
    def set_trust(self, request, pk=None):
        """
        Admin override of a user's trust score / level.
        Body: { trust_score?: 0..100, trust_level?: TRUSTED|NORMAL|SUSPICIOUS, note?: str }
        """
        user = self.get_object()
        score = request.data.get("trust_score")
        level = request.data.get("trust_level")
        if score is not None:
            try:
                user.trust_score = max(0, min(100, int(score)))
            except (TypeError, ValueError):
                return Response({"detail": "trust_score must be an integer"}, status=400)
            user.save(update_fields=["trust_score"])
            user.recompute_trust_level(save=True)
        if level:
            level = level.upper()
            if level not in dict(User.TrustLevel.choices):
                return Response({"detail": "Invalid trust_level"}, status=400)
            user.trust_level = level
            user.save(update_fields=["trust_level"])
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="verify-documents")
    def verify_documents(self, request, pk=None):
        """Admin marks the driver's compliance docs as verified."""
        user = self.get_object()
        user.documents_verified = bool(request.data.get("verified", True))
        user.save(update_fields=["documents_verified"])
        return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def upload_my_documents(request):
    """
    Driver self-uploads compliance documents.
    Body (multipart): driving_license_doc?, cnic_doc?
    Setting documents_verified resets to False — admin must re-approve.
    """
    user = request.user
    changed = False
    if "driving_license_doc" in request.FILES:
        user.driving_license_doc = request.FILES["driving_license_doc"]
        changed = True
    if "cnic_doc" in request.FILES:
        user.cnic_doc = request.FILES["cnic_doc"]
        changed = True
    if not changed:
        return Response({"detail": "No documents provided"}, status=400)
    user.documents_verified = False
    user.save()
    return Response(UserSerializer(user).data)
