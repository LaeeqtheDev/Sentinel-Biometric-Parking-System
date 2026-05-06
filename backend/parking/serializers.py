from rest_framework import serializers

from accounts.serializers import UserSerializer
from access.serializers import AccessLogSerializer
from vehicles.serializers import VehicleSerializer

from .models import ParkingSession


class ParkingSessionSerializer(serializers.ModelSerializer):
    vehicle_detail = VehicleSerializer(source="vehicle", read_only=True)
    entry_user_detail = UserSerializer(source="entry_user", read_only=True)
    exit_user_detail = UserSerializer(source="exit_user", read_only=True)
    entry_log_detail = AccessLogSerializer(source="entry_log", read_only=True)
    exit_log_detail = AccessLogSerializer(source="exit_log", read_only=True)
    duration_seconds = serializers.IntegerField(read_only=True)

    class Meta:
        model = ParkingSession
        fields = (
            "id",
            "vehicle",
            "vehicle_detail",
            "entry_user",
            "entry_user_detail",
            "exit_user",
            "exit_user_detail",
            "entry_log",
            "entry_log_detail",
            "exit_log",
            "exit_log_detail",
            "entry_time",
            "exit_time",
            "duration_seconds",
            "status",
        )
        read_only_fields = fields
