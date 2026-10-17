"""
Policy config endpoints (admin-only).

GET          /api/parking/policy/   read current policy
POST / PATCH /api/parking/policy/   partial update

Input is validated by a serializer. The old view did `setattr` on raw JSON,
so a typo like `"risk_low_max": "abc"` or thresholds in the wrong order
were saved as-is and broke every subsequent gate decision.
"""

from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAdminRole

from .models import PolicyConfig

CONFIDENCE = ("low", "medium", "high")


class PolicySerializer(serializers.ModelSerializer):
    peak_start = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])
    peak_end = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])
    off_hours_start = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"], required=False)
    off_hours_end = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"], required=False)
    ocr_min_confidence_normal = serializers.ChoiceField(choices=CONFIDENCE)
    ocr_min_confidence_peak = serializers.ChoiceField(choices=CONFIDENCE)
    trusted_threshold = serializers.IntegerField(min_value=0, max_value=100)
    normal_threshold = serializers.IntegerField(min_value=0, max_value=100)
    risk_low_max = serializers.IntegerField(min_value=0, max_value=100)
    risk_medium_max = serializers.IntegerField(min_value=0, max_value=100)
    is_peak_now = serializers.SerializerMethodField()

    class Meta:
        model = PolicyConfig
        fields = (
            "trusted_threshold",
            "normal_threshold",
            "peak_start",
            "peak_end",
            "peak_enabled",
            "is_peak_now",
            "off_hours_start",
            "off_hours_end",
            "autonomous_mode",
            "force_biometric_during_peak",
            "auto_entry_for_trusted",
            "ocr_min_confidence_normal",
            "ocr_min_confidence_peak",
            "risk_low_max",
            "risk_medium_max",
            "capacity",
            "currency",
            "hourly_rate",
            "peak_hourly_rate",
            "grace_minutes",
            "updated_at",
        )
        read_only_fields = ("updated_at", "is_peak_now")

    def get_is_peak_now(self, obj) -> bool:
        return obj.is_peak_now()

    def validate(self, attrs):
        get = lambda k: attrs.get(k, getattr(self.instance, k))  # noqa: E731
        if get("normal_threshold") > get("trusted_threshold"):
            raise serializers.ValidationError("normal_threshold must be <= trusted_threshold.")
        if get("risk_low_max") > get("risk_medium_max"):
            raise serializers.ValidationError("risk_low_max must be <= risk_medium_max.")
        if "currency" in attrs:
            attrs["currency"] = attrs["currency"].upper()[:3]
        return attrs


@api_view(["GET", "POST", "PATCH"])
@permission_classes([IsAdminRole])
def policy_config(request):
    cfg = PolicyConfig.objects.get_or_create(pk=1)[0]  # fresh row, not the cached copy
    if request.method == "GET":
        return Response(PolicySerializer(cfg).data)
    ser = PolicySerializer(cfg, data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    ser.save(updated_by=request.user)
    return Response(PolicySerializer(cfg).data)
