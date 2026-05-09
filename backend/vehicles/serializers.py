from rest_framework import serializers

from accounts.serializers import UserSerializer
from accounts.models import User

from .models import Vehicle, UserVehicle, normalize_plate


class UserVehicleSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source="user", read_only=True)

    class Meta:
        model = UserVehicle
        fields = ("id", "user", "user_detail", "relationship", "created_at")
        read_only_fields = ("id", "created_at", "user_detail")


class VehicleSerializer(serializers.ModelSerializer):
    """Full vehicle detail including assignments."""

    assignments = UserVehicleSerializer(
        source="uservehicle_set", many=True, read_only=True
    )
    owners_detail = UserSerializer(source="owners", many=True, read_only=True)
    drivers_detail = UserSerializer(source="drivers", many=True, read_only=True)

    class Meta:
        model = Vehicle
        fields = (
            "id",
            "plate_number",
            "vehicle_type",
            "make",
            "model",
            "color",
            "is_active",
            "status",
            "block_reason",
            "registration_doc",
            "assignments",
            "owners_detail",
            "drivers_detail",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_plate_number(self, value: str) -> str:
        return normalize_plate(value)


class VehicleCreateSerializer(serializers.ModelSerializer):
    """Used on POST – accepts a list of `{user, relationship}` assignments."""

    assignments = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        write_only=True,
        help_text='[{"user": <id>, "relationship": "OWNER|DRIVER|BOTH"}]',
    )

    class Meta:
        model = Vehicle
        fields = (
            "id",
            "plate_number",
            "vehicle_type",
            "make",
            "model",
            "color",
            "is_active",
            "assignments",
        )
        read_only_fields = ("id",)

    def validate_plate_number(self, value: str) -> str:
        return normalize_plate(value)

    def create(self, validated_data):
        assignments = validated_data.pop("assignments", [])
        vehicle = super().create(validated_data)
        self._sync_assignments(vehicle, assignments)
        return vehicle

    def update(self, instance, validated_data):
        assignments = validated_data.pop("assignments", None)
        vehicle = super().update(instance, validated_data)
        if assignments is not None:
            self._sync_assignments(vehicle, assignments, replace=True)
        return vehicle

    def _sync_assignments(self, vehicle, assignments, replace: bool = False):
        if replace:
            UserVehicle.objects.filter(vehicle=vehicle).delete()
        for a in assignments:
            user_id = a.get("user")
            rel = (a.get("relationship") or "DRIVER").upper()
            if rel not in dict(UserVehicle.Relationship.choices):
                continue
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                continue
            UserVehicle.objects.update_or_create(
                user=user, vehicle=vehicle, defaults={"relationship": rel}
            )
