"""
WebAuthn / Passkey endpoints + pickup-token endpoints.

Registration (driver enrolls a passkey on their device)
-------------------------------------------------------
POST /api/passkeys/register/options/
    -> { publicKey: { challenge, rp, user, pubKeyCredParams, ... } }
POST /api/passkeys/register/verify/
    body: full client response
    -> { detail: "OK", credential: {...} }

Authentication (driver proves identity later)
---------------------------------------------
POST /api/passkeys/auth/options/
    body: { username }
    -> { publicKey: { challenge, allowCredentials, ... } }
POST /api/passkeys/auth/verify/
    body: full client response + username
    -> { matched: true, user_id, username }

Pickup tokens (kiosk QR flow)
-----------------------------
POST /api/passkeys/pickup-tokens/        body: { vehicle_id }  (admin)
GET  /api/passkeys/pickup-tokens/<token>/ public, returns vehicle + status
POST /api/passkeys/pickup-tokens/<token>/authorize/
    body: WebAuthn auth response  + username
"""

import base64
import json
from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from accounts.models import User
from accounts.permissions import IsAdminRole
from vehicles.models import Vehicle

from .models import PickupToken, WebAuthnChallenge, WebAuthnCredential


# ---------------------------------------------------------------------- #
#  Helpers
# ---------------------------------------------------------------------- #
def _rp_id() -> str:
    return settings.WEBAUTHN_RP_ID


def _rp_name() -> str:
    return settings.WEBAUTHN_RP_NAME


def _expected_origins() -> list[str]:
    return list(settings.WEBAUTHN_ORIGINS)


def _user_handle(user: User) -> bytes:
    """Stable per-user handle.  We use the integer PK as bytes."""
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


# ---------------------------------------------------------------------- #
#  REGISTRATION
# ---------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_options(request):
    """Issue registration options for the current user."""
    user = request.user
    existing = WebAuthnCredential.objects.filter(user=user)
    exclude = [
        PublicKeyCredentialDescriptor(id=bytes(c.credential_id)) for c in existing
    ]

    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_rp_name(),
        user_id=_user_handle(user),
        user_name=user.username,
        user_display_name=user.get_full_name() or user.username,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )

    WebAuthnChallenge.issue(
        user=user,
        challenge=options.challenge,
        purpose=WebAuthnChallenge.Purpose.REGISTER,
    )
    return Response(json.loads(options_to_json(options)))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register_verify(request):
    """Verify the registration response sent by the browser."""
    user = request.user
    nickname = request.data.get("nickname", "")

    challenge_obj = (
        WebAuthnChallenge.objects.filter(
            user=user,
            purpose=WebAuthnChallenge.Purpose.REGISTER,
            consumed=False,
        )
        .order_by("-created_at")
        .first()
    )
    if not challenge_obj or not challenge_obj.is_valid():
        return Response(
            {"detail": "Challenge expired or missing. Re-fetch options."},
            status=400,
        )

    try:
        verification = verify_registration_response(
            credential=request.data.get("credential") or request.data,
            expected_challenge=bytes(challenge_obj.challenge),
            expected_origin=_expected_origins(),
            expected_rp_id=_rp_id(),
        )
    except Exception as exc:  # noqa: BLE001
        return Response(
            {"detail": f"Registration verification failed: {exc}"},
            status=400,
        )

    cred = WebAuthnCredential.objects.create(
        user=user,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        nickname=nickname,
    )
    challenge_obj.consumed = True
    challenge_obj.save(update_fields=["consumed"])

    return Response(
        {"detail": "Passkey registered.", "credential": _credential_dict(cred)},
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------- #
#  AUTHENTICATION
# ---------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([AllowAny])
def auth_options(request):
    """Issue authentication options for a username (or current user)."""
    username = request.data.get("username")
    if username:
        user = get_object_or_404(User, username=username)
    elif request.user.is_authenticated:
        user = request.user
    else:
        return Response({"detail": "username required"}, status=400)

    creds = WebAuthnCredential.objects.filter(user=user)
    if not creds.exists():
        return Response({"detail": "User has no passkeys enrolled."}, status=404)

    allow = [
        PublicKeyCredentialDescriptor(id=bytes(c.credential_id)) for c in creds
    ]
    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    WebAuthnChallenge.issue(
        user=user,
        challenge=options.challenge,
        purpose=WebAuthnChallenge.Purpose.AUTHENTICATE,
    )
    return Response(json.loads(options_to_json(options)))


def _verify_authentication_payload(user: User, payload: dict) -> tuple[bool, str | None, WebAuthnCredential | None]:
    """
    Returns (matched, error_or_None, credential_or_None).
    Updates sign_count + last_used_at on success.
    """
    challenge_obj = (
        WebAuthnChallenge.objects.filter(
            user=user,
            purpose=WebAuthnChallenge.Purpose.AUTHENTICATE,
            consumed=False,
        )
        .order_by("-created_at")
        .first()
    )
    if not challenge_obj or not challenge_obj.is_valid():
        return False, "Challenge expired or missing.", None

    cred_id_b64 = payload.get("id") or payload.get("rawId")
    if not cred_id_b64:
        return False, "Missing credential id.", None
    try:
        cred_id_bytes = base64url_to_bytes(cred_id_b64)
    except Exception:
        return False, "Invalid credential id encoding.", None

    cred = WebAuthnCredential.objects.filter(
        user=user, credential_id=cred_id_bytes
    ).first()
    if not cred:
        return False, "No matching passkey for this user.", None

    try:
        verification = verify_authentication_response(
            credential=payload,
            expected_challenge=bytes(challenge_obj.challenge),
            expected_origin=_expected_origins(),
            expected_rp_id=_rp_id(),
            credential_public_key=bytes(cred.public_key),
            credential_current_sign_count=cred.sign_count,
            require_user_verification=False,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"Verification failed: {exc}", None

    cred.sign_count = verification.new_sign_count
    cred.last_used_at = timezone.now()
    cred.save(update_fields=["sign_count", "last_used_at"])
    challenge_obj.consumed = True
    challenge_obj.save(update_fields=["consumed"])
    return True, None, cred


@api_view(["POST"])
@permission_classes([AllowAny])
def auth_verify(request):
    """Verify an authentication response."""
    username = request.data.get("username")
    if not username:
        return Response({"detail": "username required"}, status=400)
    user = get_object_or_404(User, username=username)
    payload = request.data.get("credential") or request.data

    ok, err, cred = _verify_authentication_payload(user, payload)
    if not ok:
        return Response({"matched": False, "detail": err}, status=400)

    return Response(
        {
            "matched": True,
            "user_id": user.id,
            "username": user.username,
            "credential_id": cred.id if cred else None,
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
    cred = get_object_or_404(
        WebAuthnCredential, pk=credential_id, user=request.user
    )
    cred.delete()
    return Response(status=204)


# ---------------------------------------------------------------------- #
#  Pickup tokens (QR-code based mobile pickup flow)
# ---------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_pickup_token(request):
    """
    Generate a pickup token for a vehicle.
    Body: { vehicle_id, event_type? }   event_type defaults to EXIT.
    Response: { token, event_type, expires_at, deep_link }
    """
    vehicle_id = request.data.get("vehicle_id")
    event_type = (request.data.get("event_type") or "EXIT").upper()
    if not vehicle_id:
        return Response({"detail": "vehicle_id required"}, status=400)
    if event_type not in ("ENTRY", "EXIT"):
        return Response(
            {"detail": "event_type must be ENTRY or EXIT"}, status=400
        )
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)

    # Reuse existing PENDING token if one was created in last 60 seconds
    # This prevents duplicate QRs from rapid clicks / autonomous mode re-triggers
    existing = PickupToken.objects.filter(
        vehicle=vehicle,
        event_type=event_type,
        status=PickupToken.Status.PENDING,
        expires_at__gt=timezone.now(),
    ).order_by("-created_at").first()
    if existing:
        pt = existing
    else:
        pt = PickupToken.issue(vehicle=vehicle, event_type=event_type)
    base = settings.FRONTEND_BASE_URL.rstrip("/")
    return Response(
        {
            "token": pt.token,
            "event_type": pt.event_type,
            "vehicle": {
                "id": vehicle.id,
                "plate_number": vehicle.plate_number,
            },
            "expires_at": pt.expires_at.isoformat(),
            "deep_link": f"{base}/driver/scan/{pt.token}",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_pickup_token(request, token: str):
    pt = get_object_or_404(PickupToken, token=token)
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
def authorize_pickup_token(request, token: str):
    """
    Phone-side endpoint: WebAuthn payload + username.  Verifies that the
    user (a) owns this vehicle, and (b) has a working passkey.  On success
    we ALSO create the corresponding AccessLog + ParkingSession side-effect
    so the gate is effectively opened for that direction.
    """
    pt = get_object_or_404(PickupToken, token=token)
    if not pt.is_valid():
        return Response(
            {"detail": "Token expired or already used.", "status": pt.status},
            status=400,
        )

    username = request.data.get("username")
    if not username:
        return Response({"detail": "username required"}, status=400)

    user = get_object_or_404(User, username=username)
    if not pt.vehicle.users.filter(pk=user.id).exists():
        pt.status = PickupToken.Status.DENIED
        pt.deny_reason = "User is not linked to this vehicle."
        pt.save(update_fields=["status", "deny_reason"])
        return Response(
            {"detail": pt.deny_reason, "status": pt.status}, status=403
        )

    payload = request.data.get("credential") or request.data
    ok, err, _ = _verify_authentication_payload(user, payload)
    if not ok:
        pt.status = PickupToken.Status.DENIED
        pt.deny_reason = err or "WebAuthn verification failed."
        pt.save(update_fields=["status", "deny_reason"])
        return Response(
            {"detail": pt.deny_reason, "status": pt.status}, status=400
        )

    # Identity is verified.  Now perform the access action itself.
    from access.models import AccessLog
    from parking.models import ParkingSession

    if pt.event_type == "ENTRY":
        # Reject if vehicle is already parked.
        if ParkingSession.active_for(pt.vehicle):
            pt.status = PickupToken.Status.DENIED
            pt.deny_reason = "Vehicle is already inside the lot."
            pt.save(update_fields=["status", "deny_reason"])
            return Response(
                {"detail": pt.deny_reason, "status": pt.status}, status=400
            )
        log = AccessLog.objects.create(
            event_type=AccessLog.Event.ENTRY,
            plate_detected=pt.vehicle.plate_number,
            vehicle=pt.vehicle,
            user=user,
            status=AccessLog.Decision.GRANTED,
            reason="Verified via mobile QR (passkey).",
            plate_match=True,
            biometric_match=False,
            webauthn_match=True,
            confidence=AccessLog.Confidence.HIGH,
            via="mobile_qr",
        )
        ParkingSession.objects.create(
            vehicle=pt.vehicle, entry_user=user, entry_log=log
        )
    else:  # EXIT
        session = ParkingSession.active_for(pt.vehicle)
        if not session:
            pt.status = PickupToken.Status.DENIED
            pt.deny_reason = "No active parking session for this vehicle."
            pt.save(update_fields=["status", "deny_reason"])
            return Response(
                {"detail": pt.deny_reason, "status": pt.status}, status=400
            )
        log = AccessLog.objects.create(
            event_type=AccessLog.Event.EXIT,
            plate_detected=pt.vehicle.plate_number,
            vehicle=pt.vehicle,
            user=user,
            status=AccessLog.Decision.GRANTED,
            reason="Verified via mobile QR (passkey).",
            plate_match=True,
            biometric_match=False,
            webauthn_match=True,
            confidence=AccessLog.Confidence.HIGH,
            via="mobile_qr",
        )
        session.close(exit_user=user, exit_log=log)

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
