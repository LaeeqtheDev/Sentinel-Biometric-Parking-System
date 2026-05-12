"""
Biometric endpoints.

* POST /api/biometrics/enroll/         body: user_id + image -> create/update profile
* POST /api/biometrics/verify/         body: user_id + image -> {matched, distance}
* GET  /api/biometrics/profile/<uid>/  fetch profile metadata
"""

import base64
import binascii
from io import BytesIO

from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminRole
from recognition.face_engine import encode_face, verify_face

from .models import BiometricProfile
from .serializers import BiometricProfileSerializer


def _extract_image(request) -> tuple[bytes | None, str]:
    """Return (bytes, filename) from either a multipart upload or base64 JSON."""
    if "image" in request.FILES:
        f = request.FILES["image"]
        return f.read(), f.name

    b64 = request.data.get("image_base64")
    if b64:
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            return base64.b64decode(b64), "capture.png"
        except (binascii.Error, ValueError):
            return None, ""
    return None, ""


# ---------------------------------------------------------------------- #
#  Enrollment
# ---------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def enroll(request):
    # Admins can enroll any user by passing user_id.
    # Drivers can only enroll themselves.
    user_id = request.data.get("user_id") or request.data.get("user")

    if request.user.role == "ADMIN":
        if not user_id:
            return Response({"detail": "user_id is required."}, status=400)
        user = get_object_or_404(User, pk=user_id)
    else:
        # Driver self-enroll — ignore any user_id, always use own account
        user = request.user
    img_bytes, filename = _extract_image(request)
    if not img_bytes:
        return Response(
            {"detail": "An image (multipart `image` or `image_base64`) is required."},
            status=400,
        )

    encoding = encode_face(img_bytes)
    if encoding is None:
        return Response(
            {"detail": "No face detected in the image. Try again with a clearer photo."},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    profile, _ = BiometricProfile.objects.get_or_create(user=user)
    profile.encoding = encoding
    profile.reference_image.save(filename, ContentFile(img_bytes), save=False)
    profile.save()

    return Response(
        {
            "detail": "Biometric enrolled successfully.",
            "profile": BiometricProfileSerializer(profile).data,
        },
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------- #
#  Verification
# ---------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def verify(request):
    user_id = request.data.get("user_id") or request.data.get("user")
    if not user_id:
        return Response({"detail": "user_id is required."}, status=400)

    user = get_object_or_404(User, pk=user_id)
    profile = getattr(user, "biometric", None)
    if not profile or not profile.encoding:
        return Response(
            {"detail": "User has no biometric profile enrolled.", "matched": False},
            status=status.HTTP_404_NOT_FOUND,
        )

    img_bytes, _ = _extract_image(request)
    if not img_bytes:
        return Response({"detail": "Image is required."}, status=400)

    result = verify_face(img_bytes, bytes(profile.encoding))
    result["user_id"] = user.id
    result["username"] = user.username
    return Response(result)


# ---------------------------------------------------------------------- #
#  Read profile
# ---------------------------------------------------------------------- #
@api_view(["GET"])
@permission_classes([IsAdminRole])
def profile_detail(request, user_id: int):
    user = get_object_or_404(User, pk=user_id)
    profile = getattr(user, "biometric", None)
    if not profile:
        return Response(
            {"detail": "No biometric profile.", "user_id": user_id, "has_encoding": False},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(BiometricProfileSerializer(profile).data)
