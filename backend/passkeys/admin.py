from django.contrib import admin

from .models import PickupToken, WebAuthnChallenge, WebAuthnCredential


@admin.register(WebAuthnCredential)
class WebAuthnCredentialAdmin(admin.ModelAdmin):
    list_display = ("user", "nickname", "created_at", "last_used_at", "sign_count")
    search_fields = ("user__username", "nickname")
    readonly_fields = ("credential_id", "public_key", "sign_count", "created_at", "last_used_at")


@admin.register(WebAuthnChallenge)
class WebAuthnChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "created_at", "expires_at", "consumed")
    list_filter = ("purpose", "consumed")
    readonly_fields = ("challenge", "created_at")


@admin.register(PickupToken)
class PickupTokenAdmin(admin.ModelAdmin):
    list_display = ("token", "vehicle", "status", "user", "created_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("token", "vehicle__plate_number", "user__username")
    readonly_fields = ("token", "created_at", "redeemed_at")
