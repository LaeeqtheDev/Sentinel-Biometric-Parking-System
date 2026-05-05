from rest_framework import serializers

from accounts.serializers import UserSerializer

from .models import Vehicle, normalize_plate


class VehicleSerializer(serializers.ModelSerializer):
    owner_detail = UserSerializer(source="owner", read_only=True)

    class Meta:
        model = Vehicle
        fields = (
            "id",
            "owner",
            "owner_detail",
            "plate_number",
            "vehicle_type",
            "make",
            "model",
            "color",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_plate_number(self, value: str) -> str:
        return normalize_plate(value)
