from rest_framework.permissions import BasePermission


def is_admin(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, "role", None) == "ADMIN")
    )


class IsAdminRole(BasePermission):
    """Only allow users with role == ADMIN (or Django superusers)."""

    def has_permission(self, request, view):
        return is_admin(request.user)
