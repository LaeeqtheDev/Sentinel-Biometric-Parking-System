"""
ParkingSession – represents a vehicle's stay inside the parking lot.

Lifecycle:

    ENTRY granted   → ParkingSession(status=PARKED) is created
    EXIT  granted   → ParkingSession.exit_time is set, status=EXITED

Invariant: at most ONE session per vehicle has status=PARKED at any time.
This makes "duplicate entry" prevention trivial.

Also defines PolicyConfig — system-wide tunables for the gate decision
engine (peak hours, trust thresholds, biometric-required flags).  Modeled
as a singleton: there's only one row, anyone can update it, and other apps
read it via PolicyConfig.current().
"""

from datetime import time

from django.db import models
from django.utils import timezone

from accounts.models import User
from vehicles.models import Vehicle
from access.models import AccessLog


# ====================================================================== #
#  Policy / Rule Engine
# ====================================================================== #
class PolicyConfig(models.Model):
    """
    Singleton holding system-wide policy.  Use PolicyConfig.current() — it
    creates the row on first access if missing.
    """

    # Trust-level thresholds (auto-bucket based on trust_score)
    trusted_threshold = models.IntegerField(
        default=80, help_text="Score >= this is TRUSTED."
    )
    normal_threshold = models.IntegerField(
        default=50, help_text="Score >= this is NORMAL, otherwise SUSPICIOUS."
    )

    # Peak hours
    peak_start = models.TimeField(default=time(18, 0))
    peak_end = models.TimeField(default=time(23, 0))
    peak_enabled = models.BooleanField(default=True)

    # Behavior toggles
    autonomous_mode = models.BooleanField(
        default=True,
        help_text="If False, every access requires explicit verification.",
    )
    force_biometric_during_peak = models.BooleanField(default=True)
    auto_entry_for_trusted = models.BooleanField(
        default=True,
        help_text="If False, even TRUSTED users must verify biometric.",
    )

    # OCR confidence floor per mode (low/medium/high)
    ocr_min_confidence_normal = models.CharField(
        max_length=10, default="medium"
    )
    ocr_min_confidence_peak = models.CharField(max_length=10, default="high")

    # Risk thresholds
    risk_low_max = models.IntegerField(
        default=30,
        help_text="Risk <= this means LOW risk, auto-grant possible.",
    )
    risk_medium_max = models.IntegerField(
        default=70,
        help_text="Risk <= this means MEDIUM (require biometric); above is HIGH (deny/escalate).",
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = "Policy configuration"
        verbose_name_plural = "Policy configuration"

    def __str__(self) -> str:
        return f"PolicyConfig (peak {self.peak_start}-{self.peak_end}, autonomous={self.autonomous_mode})"

    @classmethod
    def current(cls) -> "PolicyConfig":
        """Get the single config row, creating it if it doesn't exist."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def is_peak_now(self) -> bool:
        if not self.peak_enabled:
            return False
        now = timezone.localtime().time()
        if self.peak_start <= self.peak_end:
            return self.peak_start <= now <= self.peak_end
        # Overnight wrap (e.g. 22:00 → 02:00)
        return now >= self.peak_start or now <= self.peak_end


# ====================================================================== #
#  Parking Session
# ====================================================================== #
class ParkingSession(models.Model):
    class Status(models.TextChoices):
        PARKED = "PARKED", "Parked"
        EXITED = "EXITED", "Exited"

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="parking_sessions"
    )
    entry_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entry_sessions",
        help_text="Driver verified at entry.",
    )
    exit_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exit_sessions",
        help_text="Driver verified at exit (may differ from entry_user).",
    )
    entry_log = models.OneToOneField(
        AccessLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entry_session",
    )
    exit_log = models.OneToOneField(
        AccessLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exit_session",
    )
    entry_time = models.DateTimeField(auto_now_add=True)
    exit_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PARKED
    )

    class Meta:
        ordering = ("-entry_time",)
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("-entry_time",)),
        ]
        constraints = [
            # Prevent two PARKED sessions for the same vehicle at DB level
            models.UniqueConstraint(
                fields=["vehicle"],
                condition=models.Q(status="PARKED"),
                name="unique_active_session_per_vehicle",
            )
        ]

    def __str__(self) -> str:
        return f"{self.vehicle.plate_number} [{self.status}] in @ {self.entry_time:%Y-%m-%d %H:%M}"

    @property
    def duration_seconds(self) -> int | None:
        if not self.exit_time:
            return None
        return int((self.exit_time - self.entry_time).total_seconds())

    @classmethod
    def active_for(cls, vehicle: Vehicle) -> "ParkingSession | None":
        return cls.objects.filter(vehicle=vehicle, status=cls.Status.PARKED).first()

    def close(self, exit_user: User | None = None, exit_log: AccessLog | None = None):
        self.status = self.Status.EXITED
        self.exit_time = timezone.now()
        if exit_user:
            self.exit_user = exit_user
        if exit_log:
            self.exit_log = exit_log
        self.save(update_fields=["status", "exit_time", "exit_user", "exit_log"])
