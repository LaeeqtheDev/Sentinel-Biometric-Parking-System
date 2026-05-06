"""
ParkingSession – represents a vehicle's stay inside the parking lot.

Lifecycle:

    ENTRY granted   → ParkingSession(status=PARKED) is created
    EXIT  granted   → ParkingSession.exit_time is set, status=EXITED

Invariant: at most ONE session per vehicle has status=PARKED at any time.
This makes "duplicate entry" prevention trivial.
"""

from django.db import models
from django.utils import timezone

from accounts.models import User
from vehicles.models import Vehicle
from access.models import AccessLog


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
