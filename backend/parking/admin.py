from django.contrib import admin

from .models import ParkingSession


@admin.register(ParkingSession)
class ParkingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "vehicle",
        "status",
        "entry_time",
        "exit_time",
        "entry_user",
        "exit_user",
    )
    list_filter = ("status",)
    search_fields = ("vehicle__plate_number",)
    readonly_fields = ("entry_time", "exit_time")
