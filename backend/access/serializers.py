from rest_framework import serializers

from accounts.serializers import UserSerializer
from vehicles.serializers import VehicleSerializer

from .models import AccessLog


class AccessLogSerializer(serializers.ModelSerializer):
    vehicle_detail = VehicleSerializer(source="vehicle", read_only=True)
    user_detail = UserSerializer(source="user", read_only=True)

    class Meta:
        model = AccessLog
        fields = (
            "id",
            "plate_detected",
            "vehicle",
            "vehicle_detail",
            "user",
            "user_detail",
            "status",
            "reason",
            "plate_match",
            "biometric_match",
            "biometric_distance",
            "snapshot",
            "timestamp",
        )
        read_only_fields = fields
