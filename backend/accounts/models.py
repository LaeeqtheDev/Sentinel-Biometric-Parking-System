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

    class TrustLevel(models.TextChoices):
        TRUSTED = "TRUSTED", "Trusted (auto-entry, no biometric)"
        NORMAL = "NORMAL", "Normal (biometric required)"
        SUSPICIOUS = "SUSPICIOUS", "Suspicious (always verify + alert)"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.DRIVER,
    )
    trust_level = models.CharField(
        max_length=12,
        choices=TrustLevel.choices,
        default=TrustLevel.NORMAL,
        help_text="Auto-derived from trust_score; admin can override.",
    )
    trust_score = models.IntegerField(
        default=60,
        help_text="0-100 trust score. Updated automatically on every access event.",
    )
    last_activity_at = models.DateTimeField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    cnic = models.CharField(
        max_length=20,
        blank=True,
        help_text="National ID number (CNIC for Pakistan).",
    )
    # Compliance documents (driver-uploaded, admin-reviewed).
    driving_license_doc = models.FileField(
        upload_to="docs/license/", null=True, blank=True
    )
    cnic_doc = models.FileField(
        upload_to="docs/cnic/", null=True, blank=True
    )
    documents_verified = models.BooleanField(
        default=False,
        help_text="Admin has reviewed driving licence + CNIC and confirmed identity.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.get_full_name() or self.username} ({self.role})"

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_trusted(self) -> bool:
        return self.trust_level == self.TrustLevel.TRUSTED

    @property
    def is_suspicious(self) -> bool:
        return self.trust_level == self.TrustLevel.SUSPICIOUS

    @property
    def has_biometric(self) -> bool:
        # Lazy reverse-lookup; biometrics app provides the related model.
        return hasattr(self, "biometric") and self.biometric.encoding is not None

    def recompute_trust_level(self, save: bool = True) -> str:
        """Map trust_score → trust_level using the configured thresholds."""
        from parking.models import PolicyConfig
        cfg = PolicyConfig.current()
        if self.trust_score >= cfg.trusted_threshold:
            new_level = self.TrustLevel.TRUSTED
        elif self.trust_score >= cfg.normal_threshold:
            new_level = self.TrustLevel.NORMAL
        else:
            new_level = self.TrustLevel.SUSPICIOUS
        if new_level != self.trust_level:
            self.trust_level = new_level
            if save:
                self.save(update_fields=["trust_level"])
        return new_level

    def adjust_trust(self, delta: int, save: bool = True) -> int:
        """Bump trust score, clamp to [0, 100], recompute level."""
        self.trust_score = max(0, min(100, self.trust_score + delta))
        if save:
            self.save(update_fields=["trust_score"])
        self.recompute_trust_level(save=save)
        return self.trust_score
