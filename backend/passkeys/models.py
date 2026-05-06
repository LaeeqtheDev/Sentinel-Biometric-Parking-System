"""
Passkey (WebAuthn) credentials + short-lived pickup tokens.

WebAuthnCredential
==================
Stores the public-key credential a phone or laptop creates during
registration.  We store:

    credential_id   – binary ID returned by the authenticator
    public_key      – CBOR-encoded public key bytes
    sign_count      – monotonically increasing counter (replay protection)
    transports      – "internal", "usb", "ble", … (CSV)

WebAuthnChallenge
=================
A short-lived nonce we issue when the client asks for register/auth options.
The browser signs it and sends it back; we verify the signature using the
stored public key.

PickupToken
===========
When a driver wants the kiosk-QR pickup flow, an admin/kiosk generates a
PickupToken.  The driver scans the QR which opens a phone URL containing the
token.  The phone runs WebAuthn auth, posts back, gets a GRANTED decision
and (server-side) closes the parking session.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import User
from vehicles.models import Vehicle


# ---------------------------------------------------------------------- #
#  WebAuthn
# ---------------------------------------------------------------------- #
class WebAuthnCredential(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="webauthn_credentials"
    )
    credential_id = models.BinaryField(unique=True)
    public_key = models.BinaryField()
    sign_count = models.BigIntegerField(default=0)
    transports = models.CharField(
        max_length=120,
        blank=True,
        help_text="Comma-separated list, e.g. 'internal,hybrid'.",
    )
    nickname = models.CharField(
        max_length=80,
        blank=True,
        help_text="A friendly label – e.g. 'My iPhone'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Passkey of {self.user.username} ({self.nickname or 'unnamed'})"


class WebAuthnChallenge(models.Model):
    class Purpose(models.TextChoices):
        REGISTER = "REGISTER", "Register"
        AUTHENTICATE = "AUTH", "Authenticate"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="webauthn_challenges"
    )
    challenge = models.BinaryField()
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)

    @classmethod
    def issue(cls, user: User, challenge: bytes, purpose: str, ttl_seconds: int = 300):
        return cls.objects.create(
            user=user,
            challenge=challenge,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(seconds=ttl_seconds),
        )

    def is_valid(self) -> bool:
        return not self.consumed and self.expires_at > timezone.now()


# ---------------------------------------------------------------------- #
#  Pickup token (QR-based mobile pickup)
# ---------------------------------------------------------------------- #
def _generate_token() -> str:
    return secrets.token_urlsafe(32)


class PickupToken(models.Model):
    """
    Short-lived token for QR-based mobile access verification.
    Used for BOTH entry-from-gate and exit-pickup QR flows.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        AUTHORIZED = "AUTHORIZED", "Authorized"
        EXPIRED = "EXPIRED", "Expired"
        DENIED = "DENIED", "Denied"

    class EventType(models.TextChoices):
        ENTRY = "ENTRY", "Entry"
        EXIT = "EXIT", "Exit"

    event_type = models.CharField(
        max_length=10,
        choices=EventType.choices,
        default=EventType.EXIT,
        help_text="Whether this token authorizes ENTRY (arrival) or EXIT (pickup).",
    )
    token = models.CharField(
        max_length=64, unique=True, default=_generate_token, db_index=True
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="pickup_tokens"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="pickup_tokens",
        help_text="The user who actually authorized this pickup (filled in after WebAuthn).",
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    redeemed_at = models.DateTimeField(null=True, blank=True)
    deny_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"PickupToken[{self.status}] for {self.vehicle.plate_number}"

    @classmethod
    def issue(cls, vehicle: Vehicle, event_type: str = "EXIT"):
        ttl = getattr(settings, "PICKUP_TOKEN_TTL_SECONDS", 300)
        return cls.objects.create(
            vehicle=vehicle,
            event_type=event_type,
            expires_at=timezone.now() + timedelta(seconds=ttl),
        )

    def is_valid(self) -> bool:
        return self.status == self.Status.PENDING and self.expires_at > timezone.now()

    def mark_expired(self):
        self.status = self.Status.EXPIRED
        self.save(update_fields=["status"])
