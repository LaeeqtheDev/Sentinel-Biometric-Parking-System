"""
Biometric data linked one-to-one to a User.

The 128-dimensional face encoding is stored as raw bytes in a BinaryField –
that's the most space-efficient and avoids JSON parsing on every check.
"""

from django.db import models

from accounts.models import User


def biometric_image_path(instance, filename: str) -> str:
    return f"biometrics/{instance.user_id}/{filename}"


class BiometricProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="biometric"
    )
    encoding = models.BinaryField(null=True, blank=True)
    reference_image = models.ImageField(
        upload_to=biometric_image_path, null=True, blank=True
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Biometric profile for {self.user.username}"
