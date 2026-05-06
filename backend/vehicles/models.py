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


class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        CAR = "CAR", "Car"
        BIKE = "BIKE", "Motorcycle"
        SUV = "SUV", "SUV"
        TRUCK = "TRUCK", "Truck"
        OTHER = "OTHER", "Other"

    plate_number = models.CharField(max_length=20, unique=True, db_index=True)
    vehicle_type = models.CharField(
        max_length=10, choices=VehicleType.choices, default=VehicleType.CAR
    )
    make = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # M2M with metadata via UserVehicle.
    users = models.ManyToManyField(
        User, through="UserVehicle", related_name="vehicles"
    )

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        self.plate_number = normalize_plate(self.plate_number)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.plate_number

    # ----- Convenience accessors (used by older code paths) ----- #
    @property
    def owners(self):
        return User.objects.filter(
            uservehicle__vehicle=self,
            uservehicle__relationship__in=[
                UserVehicle.Relationship.OWNER,
                UserVehicle.Relationship.BOTH,
            ],
        )

    @property
    def drivers(self):
        return User.objects.filter(
            uservehicle__vehicle=self,
            uservehicle__relationship__in=[
                UserVehicle.Relationship.DRIVER,
                UserVehicle.Relationship.BOTH,
            ],
        )

    @property
    def primary_user(self):
        """Best-effort 'who is responsible for this car' – first owner, then driver."""
        return self.owners.first() or self.drivers.first()


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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "vehicle")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.user.username} ↔ {self.vehicle.plate_number} ({self.relationship})"
