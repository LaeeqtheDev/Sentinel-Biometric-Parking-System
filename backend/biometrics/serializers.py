from rest_framework import serializers

from .models import BiometricProfile


class BiometricProfileSerializer(serializers.ModelSerializer):
    has_encoding = serializers.SerializerMethodField()
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = BiometricProfile
        fields = (
            "id",
            "user",
            "user_username",
            "has_encoding",
            "reference_image",
            "enrolled_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "has_encoding",
            "enrolled_at",
            "updated_at",
            "user_username",
        )

    def get_has_encoding(self, obj) -> bool:
        return bool(obj.encoding)
