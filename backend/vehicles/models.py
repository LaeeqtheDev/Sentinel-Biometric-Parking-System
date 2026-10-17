"""
Vehicle + UserVehicle (M2M junction).

The UserVehicle through-table lets one driver be linked to many cars and one
car be linked to many users, each with a `relationship` of OWNER, DRIVER, or
BOTH.  This replaces the old single `Vehicle.owner` foreign-key.

Plates are stored normalised (uppercase, no whitespace) so plate lookups
during recognition are reliable.
"""

import re

from django.db import models

from accounts.models import User


def normalize_plate(plate: str) -> str:
    """ABC 123 -> ABC123, abc-123 -> ABC-123 (uppercase, trimmed)."""
    if not plate:
        return ""
    plate = plate.upper().strip()
    plate = re.sub(r"\s+", "", plate)
    return plate


def plate_canonical(plate: str) -> str:
    """
    Canonical form for FUZZY matching: strip everything that isn't A–Z or 0–9.
    'AAP-1478', 'AAP 1478', 'aap1478', 'AAP_1478' all collapse to 'AAP1478'.
    Use this for "is this the same plate?" comparisons.
    """
    if not plate:
        return ""
    return re.sub(r"[^A-Z0-9]", "", plate.upper())


def fuzzy_find_vehicle(plate_text: str):
    """
    Look up a Vehicle by plate.

    Uses the indexed `plate_canonical` column, so this is a single index
    lookup at any fleet size. (The old version loaded every Vehicle row into
    Python and compared them one by one on every camera frame.)
    """
    if not plate_text:
        return None
    canonical = plate_canonical(plate_text)
    if not canonical:
        return None
    return Vehicle.objects.filter(plate_canonical=canonical).first()


class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        CAR = "CAR", "Car"
        BIKE = "BIKE", "Motorcycle"
        SUV = "SUV", "SUV"
        TRUCK = "TRUCK", "Truck"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        BLOCKED = "BLOCKED", "Blocked"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"

    plate_number = models.CharField(max_length=20, unique=True, db_index=True)
    # Punctuation-free form used for matching OCR output ("AAP-1478" and
    # "AAP 1478" both become "AAP1478"). Unique so two records can never
    # describe the same physical plate.
    plate_canonical = models.CharField(max_length=20, unique=True, editable=False)
    vehicle_type = models.CharField(
        max_length=10, choices=VehicleType.choices, default=VehicleType.CAR
    )
    make = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=14,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Operational state — BLOCKED rejects entry, UNDER_REVIEW pends admin approval.",
    )
    block_reason = models.CharField(max_length=255, blank=True)
    # Compliance: vehicle registration document (PDF / image).
    registration_doc = models.FileField(
        upload_to="docs/vehicle/", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # M2M with metadata via UserVehicle.
    users = models.ManyToManyField(
        User, through="UserVehicle", related_name="vehicles"
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["status"], name="vehicle_status_idx")]

    def save(self, *args, **kwargs):
        self.plate_number = normalize_plate(self.plate_number)
        self.plate_canonical = plate_canonical(self.plate_number)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "plate_number" in update_fields:
            kwargs["update_fields"] = set(update_fields) | {"plate_canonical"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.plate_number

    # ----- Convenience accessors ----- #
    # These read the prefetched `uservehicle_set` when it is available, so
    # listing N vehicles costs one extra query in total rather than 2N.
    def _links(self):
        return [uv for uv in self.uservehicle_set.all() if uv.approved]

    @property
    def owners(self):
        return [
            uv.user
            for uv in self._links()
            if uv.relationship in (UserVehicle.Relationship.OWNER, UserVehicle.Relationship.BOTH)
        ]

    @property
    def drivers(self):
        return [
            uv.user
            for uv in self._links()
            if uv.relationship in (UserVehicle.Relationship.DRIVER, UserVehicle.Relationship.BOTH)
        ]

    @property
    def primary_user(self):
        """Best-effort 'who is responsible for this car': first owner, then driver."""
        owners = self.owners
        if owners:
            return owners[0]
        drivers = self.drivers
        return drivers[0] if drivers else None

    def is_authorized_user(self, user) -> bool:
        """True when `user` has an APPROVED link to this vehicle."""
        if not user or not getattr(user, "pk", None):
            return False
        return UserVehicle.objects.filter(vehicle=self, user=user, approved=True).exists()


class UserVehicle(models.Model):
    """Through-table for the User <-> Vehicle M2M relationship."""

    class Relationship(models.TextChoices):
        OWNER = "OWNER", "Owner"
        DRIVER = "DRIVER", "Driver"
        BOTH = "BOTH", "Owner & Driver"

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    relationship = models.CharField(
        max_length=10,
        choices=Relationship.choices,
        default=Relationship.DRIVER,
    )
    # A driver claiming a plate that is already registered to someone else
    # gets an UNAPPROVED link. It grants nothing until an admin approves it.
    # (Previously the claim was linked immediately, which let anyone attach
    # themselves to any car and then unlock it at the exit.)
    approved = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "vehicle")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.user.username} ↔ {self.vehicle.plate_number} ({self.relationship})"


def assignments_prefetch(prefix: str = ""):
    """
    Prefetch for serializing vehicles: assignments + their users + each
    user's biometric row, in two queries total for any number of vehicles.
    Use as `.prefetch_related(assignments_prefetch())`, or with a prefix
    (e.g. "vehicle__") when serializing objects that point at a vehicle.
    """
    return models.Prefetch(
        f"{prefix}uservehicle_set",
        queryset=UserVehicle.objects.select_related("user", "user__biometric"),
    )
