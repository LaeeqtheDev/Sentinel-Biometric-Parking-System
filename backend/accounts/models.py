"""
Custom User model
-----------------

Two roles exist in the system:

* ADMIN  – manages users, vehicles and views logs
* DRIVER – the person who actually drives a vehicle into the parking lot

We extend AbstractUser instead of starting from scratch so we keep all the
goodies (password hashing, permissions, etc.) and just add a `role`,
`phone` and `cnic` (Pakistani national-ID) field.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        DRIVER = "DRIVER", "Driver"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.DRIVER,
    )
    phone = models.CharField(max_length=20, blank=True)
    cnic = models.CharField(
        max_length=20,
        blank=True,
        help_text="National ID number (CNIC for Pakistan).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.role})"

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def has_biometric(self) -> bool:
        # Lazy reverse-lookup; biometrics app provides the related model.
        return hasattr(self, "biometric") and self.biometric.encoding is not None
