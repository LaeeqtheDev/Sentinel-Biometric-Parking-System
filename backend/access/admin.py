from django.contrib import admin

from .models import AccessLog


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "event_type",
        "plate_detected",
        "status",
        "plate_match",
        "biometric_match",
        "webauthn_match",
        "confidence",
        "user",
        "via",
    )
    list_filter = ("event_type", "status", "via", "confidence")
    search_fields = ("plate_detected", "user__username", "vehicle__plate_number")
    readonly_fields = tuple(f.name for f in AccessLog._meta.fields)

    def has_add_permission(self, request):
        return False
