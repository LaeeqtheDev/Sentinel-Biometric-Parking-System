"""
Vehicle model.

Plates are stored normalised (uppercase, no whitespace) so that lookups during
recognition are reliable.
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

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="vehicles"
    )
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

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        self.plate_number = normalize_plate(self.plate_number)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.plate_number} ({self.owner.username})"
