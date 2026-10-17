"""Account views: JWT login, current user, user CRUD (admin only)."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    parser_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from core.throttling import LoginThrottle, RegisterThrottle
from core.validators import validate_document

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
    throttle_classes = [LoginThrottle]


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    """Revoke the refresh token so it can't mint new access tokens."""
    try:
        RefreshToken(request.data.get("refresh")).blacklist()
    except (TokenError, TypeError):
        pass
    return Response(status=status.HTTP_205_RESET_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([RegisterThrottle])
def register(request):
    """
    Public self-registration. Always creates a DRIVER.
    Optionally claims a vehicle in the same flow (see vehicles/claims.py).
    Returns user info + JWT tokens so the frontend can auto-login.
    """
    from vehicles.claims import claim_vehicle

    data = {k: request.data.get(k) for k in ("username", "email", "password", "first_name", "last_name", "phone", "cnic")}
    data = {k: v for k, v in data.items() if v is not None}
    data["role"] = User.Role.DRIVER  # admins are never self-registered

    serializer = UserCreateSerializer(data=data)
    serializer.is_valid(raise_exception=True)

    vehicle_plate = (request.data.get("vehicle_plate") or "").strip()
    with transaction.atomic():
        user = serializer.save()
        vehicle_info = None
        if vehicle_plate:
            res = claim_vehicle(
                user,
                vehicle_plate,
                make=request.data.get("vehicle_make", ""),
                model=request.data.get("vehicle_model", ""),
                color=request.data.get("vehicle_color", ""),
                vehicle_type=request.data.get("vehicle_type", "CAR"),
            )
            v = res["vehicle"]
            vehicle_info = {
                "id": v.id,
                "plate_number": v.plate_number,
                "status": v.status,
                "duplicate": res["duplicate"],
                "link_approved": res["link"].approved,
                "message": res["message"],
            }

    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    refresh["username"] = user.username

    return Response(
        {
            "user": UserSerializer(user, context={"request": request}).data,
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
    return Response(UserSerializer(request.user, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={"user": request.user})
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

    queryset = User.objects.select_related("biometric").order_by("-created_at")
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
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
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
        raw = request.data.get("verified", True)
        user.documents_verified = raw is True or str(raw).lower() in ("1", "true", "yes")
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
    fields = []
    for name in ("driving_license_doc", "cnic_doc"):
        if name in request.FILES:
            setattr(user, name, validate_document(request.FILES[name], name))
            fields.append(name)
    if not fields:
        return Response({"detail": "No documents provided"}, status=400)
    user.documents_verified = False
    user.save(update_fields=[*fields, "documents_verified"])
    return Response(UserSerializer(user, context={"request": request}).data)
