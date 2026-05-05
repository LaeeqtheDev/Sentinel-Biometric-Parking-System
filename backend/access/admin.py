from django.contrib import admin

from .models import AccessLog


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "plate_detected",
        "status",
        "plate_match",
        "biometric_match",
        "user",
        "reason",
    )
    list_filter = ("status", "plate_match", "biometric_match")
    search_fields = ("plate_detected", "user__username", "vehicle__plate_number")
    readonly_fields = (
        "plate_detected",
        "vehicle",
        "user",
        "status",
        "reason",
        "plate_match",
        "biometric_match",
        "biometric_distance",
        "snapshot",
        "timestamp",
    )

    def has_add_permission(self, request):
        return False
