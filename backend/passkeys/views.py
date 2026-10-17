"""
WebAuthn / Passkey endpoints + pickup-token endpoints.

Registration (driver enrolls a passkey on their device)
-------------------------------------------------------
POST /api/passkeys/register/options/
POST /api/passkeys/register/verify/      body: { credential, nickname? }

Authentication (driver proves identity later)
---------------------------------------------
POST /api/passkeys/auth/options/         body: { username }
POST /api/passkeys/auth/verify/          body: { username, credential }
    -> { matched, user_id, username, passkey_ticket }
    The passkey_ticket is the ONLY proof of passkey identity the gate
    endpoints accept (see passkeys/tickets.py).

Pickup tokens (kiosk QR flow)
-----------------------------
POST /api/passkeys/pickup-tokens/                     { vehicle_id, event_type? }
GET  /api/passkeys/pickup-tokens/<token>/             public status
POST /api/passkeys/pickup-tokens/<token>/authorize/   { username, credential }
"""

import json

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from accounts.models import User
from core.throttling import PasskeyThrottle
from vehicles.models import UserVehicle, Vehicle

from .models import PickupToken, WebAuthnChallenge, WebAuthnCredential
from .tickets import issue_ticket


# ---------------------------------------------------------------------- #
#  Helpers
# ---------------------------------------------------------------------- #
def _rp_id() -> str:
    return settings.WEBAUTHN_RP_ID


def _expected_origins() -> list[str]:
    return list(settings.WEBAUTHN_ORIGINS)


def _user_handle(user: User) -> bytes:
    return str(user.id).encode()


def _credential_dict(cred: WebAuthnCredential) -> dict:
    return {
        "id": cred.id,
        "credential_id_b64": bytes_to_base64url(bytes(cred.credential_id)),
        "nickname": cred.nickname,
        "transports": cred.transports.split(",") if cred.transports else [],
        "created_at": cred.created_at.isoformat(),
        "last_used_at": cred.last_used_at.isoformat() if cred.last_used_at else None,
    }


def _challenge_from_payload(payload: dict) -> bytes | None:
    """Pull the challenge the browser actually signed out of clientDataJSON."""
    try:
        cdj = payload["response"]["clientDataJSON"]
        client_data = json.loads(base64url_to_bytes(cdj))
        return base64url_to_bytes(client_data["challenge"])
    except Exception:  # noqa: BLE001
        return None


def _claim_challenge(user: User, purpose: str, payload: dict) -> WebAuthnChallenge | None:
    """
    Find the exact challenge this response answers and consume it atomically.

    The old code picked "the most recent unconsumed challenge for the user",
    so two devices (or two tabs) authenticating at once broke each other,
    and a challenge could be raced. Now the challenge is matched by value
    and the consume is a conditional UPDATE: only one request can win it.
    """
    challenge = _challenge_from_payload(payload)
    if not challenge:
        return None
    obj = (
        WebAuthnChallenge.objects.filter(
            user=user,
            purpose=purpose,
            consumed=False,
            challenge=challenge,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )
    if not obj:
        return None
    won = WebAuthnChallenge.objects.filter(pk=obj.pk, consumed=False).update(consumed=True)
    return obj if won == 1 else None


def _generic_auth_failure():
    # Same response whether the username exists or not (no user enumeration).
    return Response({"detail": "Passkey sign-in is not available for this account."}, status=404)


# ---------------------------------------------------------------------- #
#  REGISTRATION
# ---------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([PasskeyThrottle])
def register_options(request):
    user = request.user
    exclude = [
        PublicKeyCredentialDescriptor(id=bytes(c.credential_id))
        for c in WebAuthnCredential.objects.filter(user=user).only("credential_id")
    ]
    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=_user_handle(user),
        user_name=user.username,
        user_display_name=user.get_full_name() or user.username,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            # A "biometric" gate must actually require the fingerprint/face
            # unlock, not just device possession.
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )
    WebAuthnChallenge.issue(
        user=user, challenge=options.challenge, purpose=WebAuthnChallenge.Purpose.REGISTER
    )
    return Response(json.loads(options_to_json(options)))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([PasskeyThrottle])
def register_verify(request):
    user = request.user
    nickname = (request.data.get("nickname") or "")[:80]
    payload = request.data.get("credential") or request.data

    challenge_obj = _claim_challenge(user, WebAuthnChallenge.Purpose.REGISTER, payload)
    if not challenge_obj:
        return Response({"detail": "Challenge expired or missing. Re-fetch options."}, status=400)

    try:
        verification = verify_registration_response(
            credential=payload,
            expected_challenge=bytes(challenge_obj.challenge),
            expected_origin=_expected_origins(),
            expected_rp_id=_rp_id(),
            require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001
        return Response({"detail": f"Registration verification failed: {exc}"}, status=400)

    transports = payload.get("response", {}).get("transports") or []
    cred = WebAuthnCredential.objects.create(
        user=user,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=",".join(t for t in transports if isinstance(t, str))[:120],
        nickname=nickname,
    )
    return Response(
        {"detail": "Passkey registered.", "credential": _credential_dict(cred)},
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------- #
#  AUTHENTICATION
# ---------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasskeyThrottle])
def auth_options(request):
    username = request.data.get("username")
    if username:
        user = User.objects.filter(username=username, is_active=True).first()
    elif request.user.is_authenticated:
        user = request.user
    else:
        return Response({"detail": "username required"}, status=400)
    if not user:
        return _generic_auth_failure()

    creds = list(WebAuthnCredential.objects.filter(user=user).only("credential_id"))
    if not creds:
        return _generic_auth_failure()

    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=[PublicKeyCredentialDescriptor(id=bytes(c.credential_id)) for c in creds],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    WebAuthnChallenge.issue(
        user=user, challenge=options.challenge, purpose=WebAuthnChallenge.Purpose.AUTHENTICATE
    )
    return Response(json.loads(options_to_json(options)))


def _verify_authentication_payload(user: User, payload: dict):
    """Returns (matched, error_or_None, credential_or_None)."""
    cred_id_b64 = payload.get("id") or payload.get("rawId")
    if not cred_id_b64:
        return False, "Missing credential id.", None
    try:
        cred_id_bytes = base64url_to_bytes(cred_id_b64)
    except Exception:  # noqa: BLE001
        return False, "Invalid credential id encoding.", None

    cred = WebAuthnCredential.objects.filter(user=user, credential_id=cred_id_bytes).first()
    if not cred:
        return False, "No matching passkey for this user.", None

    challenge_obj = _claim_challenge(user, WebAuthnChallenge.Purpose.AUTHENTICATE, payload)
    if not challenge_obj:
        return False, "Challenge expired, already used, or missing.", None

    try:
        verification = verify_authentication_response(
            credential=payload,
            expected_challenge=bytes(challenge_obj.challenge),
            expected_origin=_expected_origins(),
            expected_rp_id=_rp_id(),
            credential_public_key=bytes(cred.public_key),
            credential_current_sign_count=cred.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Verification failed: {exc}", None

    WebAuthnCredential.objects.filter(pk=cred.pk).update(
        sign_count=verification.new_sign_count, last_used_at=timezone.now()
    )
    return True, None, cred


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasskeyThrottle])
def auth_verify(request):
    username = request.data.get("username")
    if not username:
        return Response({"detail": "username required"}, status=400)
    user = User.objects.filter(username=username, is_active=True).first()
    if not user:
        return Response({"matched": False, "detail": "Verification failed."}, status=400)

    ok, err, cred = _verify_authentication_payload(user, request.data.get("credential") or request.data)
    if not ok:
        return Response({"matched": False, "detail": err}, status=400)

    return Response(
        {
            "matched": True,
            "user_id": user.id,
            "username": user.username,
            "credential_id": cred.id if cred else None,
            # Single-use, 60 s, bound to this user. Send it to the gate.
            "passkey_ticket": issue_ticket(user.id),
        }
    )


# ---------------------------------------------------------------------- #
#  Listing / deleting credentials
# ---------------------------------------------------------------------- #
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_credentials(request):
    creds = WebAuthnCredential.objects.filter(user=request.user)
    return Response([_credential_dict(c) for c in creds])


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_credential(request, credential_id: int):
    cred = get_object_or_404(WebAuthnCredential, pk=credential_id, user=request.user)
    cred.delete()
    return Response(status=204)


# ---------------------------------------------------------------------- #
#  Pickup tokens (QR-code based mobile pickup flow)
# ---------------------------------------------------------------------- #
def _is_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or getattr(user, "role", None) == "ADMIN"))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_pickup_token(request):
    """
    Generate a QR token. Admins (the gate kiosk) can issue one for any
    vehicle; a driver only for a vehicle they are an approved user of.
    (Previously any logged-in user could mint tokens for any car.)
    """
    vehicle_id = request.data.get("vehicle_id")
    event_type = (request.data.get("event_type") or "EXIT").upper()
    if not vehicle_id:
        return Response({"detail": "vehicle_id required"}, status=400)
    if event_type not in ("ENTRY", "EXIT"):
        return Response({"detail": "event_type must be ENTRY or EXIT"}, status=400)
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    if not _is_admin(request.user) and not vehicle.is_authorized_user(request.user):
        return Response({"detail": "Not allowed for this vehicle."}, status=403)

    # Reuse a live PENDING token so rapid clicks don't print several QRs.
    pt = (
        PickupToken.objects.filter(
            vehicle=vehicle,
            event_type=event_type,
            status=PickupToken.Status.PENDING,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    ) or PickupToken.issue(vehicle=vehicle, event_type=event_type)

    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return Response(
        {
            "token": pt.token,
            "event_type": pt.event_type,
            "vehicle": {"id": vehicle.id, "plate_number": vehicle.plate_number},
            "expires_at": pt.expires_at.isoformat(),
            "deep_link": f"{base}/driver/scan/{pt.token}",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([PasskeyThrottle])
def get_pickup_token(request, token: str):
    pt = get_object_or_404(PickupToken.objects.select_related("vehicle"), token=token)
    if pt.expires_at < timezone.now() and pt.status == PickupToken.Status.PENDING:
        pt.mark_expired()
    return Response(
        {
            "token": pt.token,
            "status": pt.status,
            "event_type": pt.event_type,
            "vehicle": {
                "id": pt.vehicle.id,
                "plate_number": pt.vehicle.plate_number,
                "make": pt.vehicle.make,
                "model": pt.vehicle.model,
            },
            "expires_at": pt.expires_at.isoformat(),
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PasskeyThrottle])
def authorize_pickup_token(request, token: str):
    """
    Phone-side: WebAuthn assertion + username. The token row is locked for
    the whole operation so it can be redeemed exactly once, and the gate
    action goes through parking.services (atomic, capacity-aware).
    """
    from access.gate import log_factory
    from access.models import AccessLog
    from parking.services import GateDenied, admit, release

    username = request.data.get("username")
    if not username:
        return Response({"detail": "username required"}, status=400)
    user = User.objects.filter(username=username, is_active=True).first()

    with transaction.atomic():
        pt = get_object_or_404(PickupToken.objects.select_for_update(), token=token)
        if not pt.is_valid():
            return Response({"detail": "Token expired or already used.", "status": pt.status}, status=400)

        def deny(reason: str, code: int = 400):
            pt.status = PickupToken.Status.DENIED
            pt.deny_reason = reason[:255]
            pt.save(update_fields=["status", "deny_reason"])
            return Response({"detail": pt.deny_reason, "status": pt.status}, status=code)

        if not user or not UserVehicle.objects.filter(
            user=user, vehicle=pt.vehicle, approved=True
        ).exists():
            return deny("User is not an approved user of this vehicle.", 403)

        ok, err, _ = _verify_authentication_payload(user, request.data.get("credential") or request.data)
        if not ok:
            return deny(err or "WebAuthn verification failed.")

        if pt.vehicle.status == Vehicle.Status.BLOCKED:
            return deny(f"Vehicle is BLOCKED: {pt.vehicle.block_reason or 'no reason given'}", 403)

        make_log = log_factory(
            event_type=pt.event_type,
            plate=pt.vehicle.plate_number,
            vehicle=pt.vehicle,
            user=user,
            plate_ok=True,
            webauthn_ok=True,
            confidence="high",
            via="mobile_qr",
            gate="KIOSK_QR",
        )
        try:
            if pt.event_type == "ENTRY":
                admit(pt.vehicle, user=user, make_log=make_log, reason="Verified via mobile QR (passkey).")
            else:
                release(pt.vehicle, user=user, make_log=make_log, reason="Verified via mobile QR (passkey).")
        except GateDenied as gd:
            make_log(AccessLog.Decision.DENIED, gd.reason)
            return deny(gd.reason)

        pt.status = PickupToken.Status.AUTHORIZED
        pt.user = user
        pt.redeemed_at = timezone.now()
        pt.save(update_fields=["status", "user", "redeemed_at"])

    return Response(
        {
            "detail": f"{pt.event_type} authorized.",
            "status": pt.status,
            "event_type": pt.event_type,
            "user": {"id": user.id, "username": user.username},
        }
    )
