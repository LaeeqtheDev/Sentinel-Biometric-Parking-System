"""Account views: JWT login, current user, user CRUD (admin only)."""

from django.contrib.auth import get_user_model
from rest_framework import generics, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
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
