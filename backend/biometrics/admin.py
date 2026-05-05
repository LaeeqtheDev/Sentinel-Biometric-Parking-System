from django.contrib import admin

from .models import BiometricProfile


@admin.register(BiometricProfile)
class BiometricProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "enrolled_at", "updated_at", "_has_encoding")
    readonly_fields = ("enrolled_at", "updated_at")

    @admin.display(boolean=True, description="Has encoding")
    def _has_encoding(self, obj):
        return bool(obj.encoding)
