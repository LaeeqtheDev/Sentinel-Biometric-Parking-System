"""
Access log – one row per entry attempt.

`status` represents the final decision (granted / denied / pending).
`reason` stores a human-readable explanation when access was denied.
"""

from django.db import models

from accounts.models import User
from vehicles.models import Vehicle


class AccessLog(models.Model):
    class Decision(models.TextChoices):
        GRANTED = "GRANTED", "Granted"
        DENIED = "DENIED", "Denied"
        PENDING = "PENDING", "Pending"

    plate_detected = models.CharField(max_length=20)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_logs",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_logs",
    )
    status = models.CharField(
        max_length=10, choices=Decision.choices, default=Decision.PENDING
    )
    reason = models.CharField(max_length=255, blank=True)

    plate_match = models.BooleanField(default=False)
    biometric_match = models.BooleanField(default=False)
    biometric_distance = models.FloatField(null=True, blank=True)

    snapshot = models.ImageField(upload_to="access_snapshots/", null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=("-timestamp",)),
            models.Index(fields=("status",)),
        ]

    def __str__(self) -> str:
        return f"[{self.status}] {self.plate_detected} @ {self.timestamp:%Y-%m-%d %H:%M}"
