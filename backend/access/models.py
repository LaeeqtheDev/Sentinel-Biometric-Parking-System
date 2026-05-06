"""
Access log – one row per ENTRY or EXIT attempt.

Each access attempt is logged with:
  - event_type: ENTRY or EXIT
  - status:     GRANTED, DENIED, or PENDING (in flight)
  - confidence: OCR confidence bucket (high / medium / low)
  - reason:     human-readable explanation
  - which checks passed (plate_match, biometric_match, webauthn_match)
"""

from django.db import models

from accounts.models import User
from vehicles.models import Vehicle


class AccessLog(models.Model):
    class Decision(models.TextChoices):
        GRANTED = "GRANTED", "Granted"
        DENIED = "DENIED", "Denied"
        PENDING = "PENDING", "Pending"

    class Event(models.TextChoices):
        ENTRY = "ENTRY", "Entry"
        EXIT = "EXIT", "Exit"

    class Confidence(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"
        NONE = "none", "None"

    event_type = models.CharField(
        max_length=10, choices=Event.choices, default=Event.ENTRY
    )
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

    # Verification flags
    plate_match = models.BooleanField(default=False)
    biometric_match = models.BooleanField(default=False)
    webauthn_match = models.BooleanField(default=False)
    biometric_distance = models.FloatField(null=True, blank=True)
    confidence = models.CharField(
        max_length=10, choices=Confidence.choices, default=Confidence.NONE
    )

    # How the entry was triggered
    via = models.CharField(
        max_length=20,
        default="manual",
        help_text="manual | live_camera | mobile_pickup | kiosk",
    )

    snapshot = models.ImageField(upload_to="access_snapshots/", null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-timestamp",)
        indexes = [
            models.Index(fields=("-timestamp",)),
            models.Index(fields=("status",)),
            models.Index(fields=("event_type",)),
            models.Index(fields=("plate_detected",)),
        ]

    def __str__(self) -> str:
        return f"[{self.event_type}/{self.status}] {self.plate_detected} @ {self.timestamp:%Y-%m-%d %H:%M}"
