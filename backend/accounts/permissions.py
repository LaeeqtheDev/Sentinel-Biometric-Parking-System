from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Only allow users with role == ADMIN (or Django superusers)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or getattr(user, "role", None) == "ADMIN")
        )
