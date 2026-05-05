from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "plate_number",
        "owner",
        "vehicle_type",
        "make",
        "model",
        "is_active",
        "created_at",
    )
    list_filter = ("vehicle_type", "is_active")
    search_fields = ("plate_number", "owner__username", "make", "model")
