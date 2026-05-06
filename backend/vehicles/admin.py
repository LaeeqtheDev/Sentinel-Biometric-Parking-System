from django.contrib import admin

from .models import UserVehicle, Vehicle


class UserVehicleInline(admin.TabularInline):
    model = UserVehicle
    extra = 1


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "plate_number",
        "vehicle_type",
        "make",
        "model",
        "is_active",
        "created_at",
    )
    list_filter = ("vehicle_type", "is_active")
    search_fields = ("plate_number", "make", "model")
    inlines = [UserVehicleInline]


@admin.register(UserVehicle)
class UserVehicleAdmin(admin.ModelAdmin):
    list_display = ("user", "vehicle", "relationship", "created_at")
    list_filter = ("relationship",)
    search_fields = ("user__username", "vehicle__plate_number")
