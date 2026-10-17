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
from decimal import Decimal

from django.core.cache import cache
from django.core.validators import MinValueValidator
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

    # Off-hours window (was hard-coded to 23:00-05:00 in two places).
    off_hours_start = models.TimeField(default=time(23, 0))
    off_hours_end = models.TimeField(default=time(5, 0))

    # Capacity: 0 means unlimited. Enforced atomically on every entry path.
    capacity = models.PositiveIntegerField(
        default=0, help_text="Total parking spots. 0 = unlimited."
    )

    # Dynamic pricing: peak minutes are billed at the peak rate, the rest at
    # the normal rate. Stays shorter than the grace period are free.
    currency = models.CharField(max_length=3, default="PKR")
    hourly_rate = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    peak_hourly_rate = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    grace_minutes = models.PositiveIntegerField(default=10)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = "Policy configuration"
        verbose_name_plural = "Policy configuration"

    def __str__(self) -> str:
        return f"PolicyConfig (peak {self.peak_start}-{self.peak_end}, autonomous={self.autonomous_mode})"

    CACHE_KEY = "policy_config:v2"
    CACHE_TTL = 300

    @classmethod
    def current(cls) -> "PolicyConfig":
        """
        The single config row. Read on every gate decision, so it is served
        from the shared cache and invalidated whenever it is saved, instead
        of a get_or_create query per request.
        """
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, cls.CACHE_TTL)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    @staticmethod
    def _in_window(now: time, start: time, end: time) -> bool:
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end  # overnight wrap (e.g. 22:00 -> 02:00)

    def is_peak_now(self, at=None) -> bool:
        if not self.peak_enabled:
            return False
        now = timezone.localtime(at).time() if at else timezone.localtime().time()
        return self._in_window(now, self.peak_start, self.peak_end)

    def is_off_hours_now(self, at=None) -> bool:
        now = timezone.localtime(at).time() if at else timezone.localtime().time()
        return self._in_window(now, self.off_hours_start, self.off_hours_end)


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
    # Billing, computed once when the session closes.
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fee_currency = models.CharField(max_length=3, blank=True)
    fee_breakdown = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-entry_time",)
        indexes = [
            models.Index(fields=("status",)),
            models.Index(fields=("-entry_time",)),
            models.Index(fields=("vehicle", "status")),
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
        """Close the session and compute its fee. Call inside a transaction
        (parking.services does this) so the row is locked while it closes."""
        from .pricing import compute_fee

        self.status = self.Status.EXITED
        self.exit_time = timezone.now()
        if exit_user:
            self.exit_user = exit_user
        if exit_log:
            self.exit_log = exit_log
        cfg = PolicyConfig.current()
        amount, breakdown = compute_fee(self.entry_time, self.exit_time, cfg)
        self.fee_amount = amount
        self.fee_currency = cfg.currency
        self.fee_breakdown = breakdown
        self.save(
            update_fields=[
                "status", "exit_time", "exit_user", "exit_log",
                "fee_amount", "fee_currency", "fee_breakdown",
            ]
        )
