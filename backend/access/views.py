"""
Access endpoints
================

* GET  /api/access/logs/                  list & filter access logs
* GET  /api/access/stats/                 dashboard statistics
* POST /api/access/verify-entry/          ENTRY decision (OCR + biometric/passkey)
* POST /api/access/verify-exit/           EXIT decision (OCR + biometric/passkey)
* POST /api/access/live-detect/           live-camera frame OCR with debounce
* POST /api/access/manual-override/       admin force-grant for a plate (entry or exit)
"""

import base64
import binascii
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, generics, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from parking.models import ParkingSession
from recognition.face_engine import verify_face
from recognition.plate_ocr import recognize_plate
from vehicles.models import UserVehicle, Vehicle, normalize_plate

from .models import AccessLog
from .serializers import AccessLogSerializer


# ====================================================================== #
#  Helpers
# ====================================================================== #
def _read_image(request, field: str) -> bytes | None:
    if field in request.FILES:
        return request.FILES[field].read()
    b64 = request.data.get(f"{field}_base64")
    if b64:
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            return base64.b64decode(b64)
        except (binascii.Error, ValueError):
            return None
    return None


def _resolve_plate(request) -> tuple[str, dict]:
    """
    Returns (resolved_plate_number, ocr_meta).
    Order of precedence:
      1. Explicit `plate_number` field (manual override) — fuzzy-matched against DB
      2. OCR on `plate_image` / `plate_image_base64`
    ocr_meta has: ocr_confidence, raw_text, found_plate, sharpness, blurry.
    """
    from vehicles.models import fuzzy_find_vehicle

    plate_number = (request.data.get("plate_number") or "").strip()
    plate_img_bytes = _read_image(request, "plate_image")

    meta: dict = {}

    # If admin supplied a plate manually, fuzzy-resolve it to canonical form.
    if plate_number:
        match = fuzzy_find_vehicle(plate_number)
        if match:
            return match.plate_number, {
                "ocr_confidence": "none",
                "manual": True,
            }
        # No DB match yet, but normalize the typed text so later equality
        # comparisons still work.
        return normalize_plate(plate_number), {
            "ocr_confidence": "none",
            "manual": True,
        }

    # Otherwise run OCR
    if plate_img_bytes:
        ocr = recognize_plate(plate_img_bytes)
        plate_number = ocr["plate_number"]
        meta = {
            "ocr_confidence": ocr["confidence"],
            "raw_text": ocr["raw_text"],
            "found_plate": ocr["found_plate"],
            "sharpness": ocr.get("sharpness"),
            "blurry": ocr.get("blurry", False),
        }
        # Try to fuzzy-match the OCR result against DB
        if plate_number:
            match = fuzzy_find_vehicle(plate_number)
            if match:
                plate_number = match.plate_number  # canonical form
    return normalize_plate(plate_number), meta


def _check_biometric(user, face_img_bytes: bytes | None) -> dict:
    """Run face_recognition against the user's stored encoding."""
    result = {"matched": False, "distance": None, "found_face": False, "available": False}
    if not user:
        result["reason"] = "No user to verify against."
        return result
    profile = getattr(user, "biometric", None)
    if not profile or not profile.encoding:
        result["reason"] = "User has no face biometric enrolled."
        return result
    if not face_img_bytes:
        result["reason"] = "No face image provided."
        return result
    result["available"] = True
    face_result = verify_face(face_img_bytes, bytes(profile.encoding))
    result.update(face_result)
    return result


def _user_can_use_vehicle(user, vehicle) -> bool:
    if not user or not vehicle:
        return False
    return UserVehicle.objects.filter(user=user, vehicle=vehicle).exists()


# ====================================================================== #
#  Verify ENTRY
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def verify_entry(request):
    """
    Combined ENTRY decision.

    Optional inputs:
        plate_image (or plate_number)
        face_image                   – face_recognition fallback
        webauthn_user_id             – if a Passkey already verified the driver
        via                          – string label (manual / live_camera / kiosk)
    """
    response: dict = {"event_type": "ENTRY"}
    plate_number, ocr_meta = _resolve_plate(request)
    response["plate"] = {"number": plate_number, **ocr_meta}
    gate = (request.data.get("gate") or "")[:20]

    # Cooldown: skip if same plate was processed within last 10 seconds
    # (prevents OCR spam creating duplicate logs)
    via = request.data.get("via", "")
    if plate_number and via == "live_camera":
        from django.utils import timezone
        from datetime import timedelta
        recent = AccessLog.objects.filter(
            plate_detected=plate_number,
            timestamp__gte=timezone.now() - timedelta(seconds=10),
            event_type=AccessLog.Event.ENTRY,
        ).exists()
        if recent:
            response["cooldown"] = True
            return Response(response)

    vehicle = (
        Vehicle.objects.filter(plate_number=plate_number, is_active=True)
        .prefetch_related("uservehicle_set__user")
        .first()
        if plate_number
        else None
    )
    response["plate"]["registered"] = vehicle is not None

    # BLOCKED vehicles are rejected outright, regardless of biometric.
    if vehicle and vehicle.status == Vehicle.Status.BLOCKED:
        log = _persist(
            request,
            AccessLog.Event.ENTRY,
            plate_number,
            vehicle,
            None,
            True,
            False,
            False,
            ocr_meta.get("ocr_confidence", "none"),
            f"Vehicle is BLOCKED: {vehicle.block_reason or 'no reason given'}",
            AccessLog.Decision.DENIED,
        )
        _record_risk(log, score=95, band="HIGH",
                     factors={"vehicle_blocked": 95},
                     decision_path="vehicle_blocked")
        response["decision"] = AccessLog.Decision.DENIED
        response["reason"] = log.reason
        response["log_id"] = log.id
        return Response(response)

    # Stop duplicate-entry: if there's already a PARKED session for this vehicle, deny.
    if vehicle and ParkingSession.active_for(vehicle):
        log = _persist(
            request,
            AccessLog.Event.ENTRY,
            plate_number,
            vehicle,
            None,
            False,
            False,
            False,
            ocr_meta.get("ocr_confidence", "none"),
            "Duplicate entry – vehicle is already parked.",
            AccessLog.Decision.DENIED,
        )
        response["decision"] = AccessLog.Decision.DENIED
        response["reason"] = log.reason
        response["log_id"] = log.id
        return Response(response)

    # WebAuthn pre-verified user (frontend already proved identity)?
    webauthn_user_id = request.data.get("webauthn_user_id")
    webauthn_user = None
    if webauthn_user_id:
        from accounts.models import User as _U
        webauthn_user = _U.objects.filter(pk=webauthn_user_id).first()

    # Biometric (face) check – use any user linked to vehicle if not specified.
    face_img_bytes = _read_image(request, "face_image")
    bio_target_user = (
        webauthn_user
        if webauthn_user and vehicle and _user_can_use_vehicle(webauthn_user, vehicle)
        else (vehicle.primary_user if vehicle else None)
    )
    bio = _check_biometric(bio_target_user, face_img_bytes)
    response["biometric"] = bio

    # WebAuthn match flag
    webauthn_match = bool(
        webauthn_user and vehicle and _user_can_use_vehicle(webauthn_user, vehicle)
    )
    response["webauthn"] = {
        "matched": webauthn_match,
        "username": webauthn_user.username if webauthn_user else None,
    }

    # Decision logic – ENTRY requires plate match + (biometric OR webauthn)
    plate_ok = bool(vehicle)
    bio_ok = bool(bio.get("matched"))
    auth_ok = webauthn_match or bio_ok

    # Check if driver has NO biometric at all (gate-registered walk-in)
    no_biometric_enrolled = False
    if bio_target_user:
        has_face = bio_target_user.has_biometric
        from passkeys.models import WebAuthnCredential
        has_passkey = WebAuthnCredential.objects.filter(user=bio_target_user).exists()
        no_biometric_enrolled = not has_face and not has_passkey

    # Admin override: if explicitly set AND no biometric exists, allow entry
    admin_override = request.data.get("admin_override", False)
    if admin_override and no_biometric_enrolled:
        auth_ok = True

    # ---- Risk engine ---------------------------------------------------- #
    from .risk_engine import RiskInputs, compute_risk, recent_failure_count, is_off_hours_now
    from parking.models import PolicyConfig

    cfg = PolicyConfig.current()
    risk = compute_risk(RiskInputs(
        plate_detected=bool(plate_number),
        plate_registered=plate_ok,
        user=bio_target_user,
        vehicle=vehicle,
        ocr_confidence=ocr_meta.get("ocr_confidence", "none"),
        is_peak=cfg.is_peak_now(),
        is_off_hours=is_off_hours_now(),
        has_passkey_match=webauthn_match,
        has_face_match=bio_ok,
        has_active_session=False,  # already checked above
        event_type="ENTRY",
        recent_failures=recent_failure_count(plate_number, minutes=10),
    ))
    response["risk"] = {
        "score": risk.score,
        "band": risk.band,
        "factors": risk.factors,
        "decision_path": risk.decision_path,
    }

    # Risk-band overrides:
    #  HIGH risk → DENY even if other checks passed
    #  LOW + autonomous + trusted user → GRANT without biometric
    can_low_risk_auto_grant = (
        risk.band == "LOW"
        and plate_ok
        and cfg.autonomous_mode
        and cfg.auto_entry_for_trusted
        and bio_target_user is not None
        and bio_target_user.is_trusted
    )

    if risk.band == "HIGH":
        decision = AccessLog.Decision.DENIED
        auth_ok = False
    elif can_low_risk_auto_grant:
        decision = AccessLog.Decision.GRANTED
        auth_ok = True
        response["auto_granted_low_risk"] = True
    else:
        decision = (
            AccessLog.Decision.GRANTED
            if (plate_ok and auth_ok)
            else AccessLog.Decision.DENIED
        )

    if not plate_number:
        reason = "License plate could not be read."
    elif not plate_ok:
        reason = f"Plate '{plate_number}' is not registered."
    elif risk.band == "HIGH":
        reason = f"Access denied — risk score {risk.score} (HIGH). Factors: {risk.decision_path}"
    elif response.get("auto_granted_low_risk"):
        reason = "Trusted vehicle, low risk — auto-granted (no biometric required)."
    elif not auth_ok:
        if no_biometric_enrolled:
            reason = "No biometric enrolled — use admin override to grant entry."
        else:
            reason = bio.get("reason") or "Driver identity could not be verified."
    elif admin_override and no_biometric_enrolled:
        reason = "Admin override entry — driver has no biometric enrolled (gate-registered walk-in)."
    else:
        reason = "Vehicle registered and driver identity verified."

    response["no_biometric_enrolled"] = no_biometric_enrolled

    plate_image_bytes = _read_image(request, "plate_image")
    log = _persist(
        request,
        AccessLog.Event.ENTRY,
        plate_number,
        vehicle,
        webauthn_user or bio_target_user,
        plate_ok,
        bio_ok,
        webauthn_match,
        ocr_meta.get("ocr_confidence", "none"),
        reason,
        decision,
        snapshot_bytes=plate_image_bytes,
    )

    # Open session on successful entry.
    if decision == AccessLog.Decision.GRANTED:
        ParkingSession.objects.create(
            vehicle=vehicle,
            entry_user=webauthn_user or bio_target_user,
            entry_log=log,
        )

    _record_risk(log, risk.score, risk.band, risk.factors, risk.decision_path)

    response.update(
        {
            "decision": decision,
            "reason": reason,
            "log_id": log.id,
            "timestamp": log.timestamp.isoformat(),
        }
    )
    return Response(response)


# ====================================================================== #
#  Verify EXIT
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def verify_exit(request):
    """
    EXIT decision.  Same shape as verify_entry but additionally requires
    that there's an open ParkingSession for the plate.
    """
    response: dict = {"event_type": "EXIT"}
    plate_number, ocr_meta = _resolve_plate(request)
    response["plate"] = {"number": plate_number, **ocr_meta}

    vehicle = (
        Vehicle.objects.filter(plate_number=plate_number, is_active=True).first()
        if plate_number
        else None
    )
    response["plate"]["registered"] = vehicle is not None
    session = ParkingSession.active_for(vehicle) if vehicle else None
    response["session_found"] = session is not None

    webauthn_user_id = request.data.get("webauthn_user_id")
    webauthn_user = None
    if webauthn_user_id:
        from accounts.models import User as _U
        webauthn_user = _U.objects.filter(pk=webauthn_user_id).first()

    face_img_bytes = _read_image(request, "face_image")
    bio_target_user = (
        webauthn_user
        if webauthn_user and vehicle and _user_can_use_vehicle(webauthn_user, vehicle)
        else (vehicle.primary_user if vehicle else None)
    )
    bio = _check_biometric(bio_target_user, face_img_bytes)
    response["biometric"] = bio

    webauthn_match = bool(
        webauthn_user and vehicle and _user_can_use_vehicle(webauthn_user, vehicle)
    )
    response["webauthn"] = {
        "matched": webauthn_match,
        "username": webauthn_user.username if webauthn_user else None,
    }

    plate_ok = bool(vehicle)
    bio_ok = bool(bio.get("matched"))
    auth_ok = webauthn_match or bio_ok

    # Check if this driver has NO biometric enrolled at all (face + passkey).
    # This happens when a driver was registered at the gate on the spot —
    # they never went through normal onboarding so they have nothing to verify with.
    # In this case we allow exit but flag it clearly for the admin to see.
    no_biometric_enrolled = False
    if bio_target_user:
        has_face = bio_target_user.has_biometric
        from passkeys.models import WebAuthnCredential
        has_passkey = WebAuthnCredential.objects.filter(user=bio_target_user).exists()
        no_biometric_enrolled = not has_face and not has_passkey

    # Admin override: if explicitly requested AND no biometric exists, allow exit
    admin_override = request.data.get("admin_override", False)
    if admin_override and no_biometric_enrolled:
        auth_ok = True

    if not plate_ok:
        decision = AccessLog.Decision.DENIED
        reason = (
            "License plate could not be read."
            if not plate_number
            else f"Plate '{plate_number}' is not registered."
        )
    elif not session:
        decision = AccessLog.Decision.DENIED
        reason = "No active parking session for this vehicle (was it ever parked?)."
    elif not auth_ok:
        decision = AccessLog.Decision.DENIED
        if no_biometric_enrolled:
            reason = "No biometric enrolled — use admin override to release this vehicle."
        else:
            reason = bio.get("reason") or "Driver identity could not be verified."
    else:
        decision = AccessLog.Decision.GRANTED
        if admin_override and no_biometric_enrolled:
            reason = "Admin override exit — driver has no biometric enrolled (gate-registered walk-in)."
        else:
            reason = "Vehicle and driver identity verified – exit allowed."

    response["no_biometric_enrolled"] = no_biometric_enrolled
    plate_image_bytes = _read_image(request, "plate_image")
    log = _persist(
        request,
        AccessLog.Event.EXIT,
        plate_number,
        vehicle,
        webauthn_user or bio_target_user,
        plate_ok,
        bio_ok,
        webauthn_match,
        ocr_meta.get("ocr_confidence", "none"),
        reason,
        decision,
        snapshot_bytes=plate_image_bytes,
    )

    if decision == AccessLog.Decision.GRANTED and session:
        session.close(
            exit_user=webauthn_user or bio_target_user,
            exit_log=log,
        )

    # Compute and persist a risk event for the EXIT decision too
    from .risk_engine import RiskInputs, compute_risk, recent_failure_count, is_off_hours_now
    from parking.models import PolicyConfig
    cfg = PolicyConfig.current()
    risk = compute_risk(RiskInputs(
        plate_detected=bool(plate_number),
        plate_registered=plate_ok,
        user=bio_target_user,
        vehicle=vehicle,
        ocr_confidence=ocr_meta.get("ocr_confidence", "none"),
        is_peak=cfg.is_peak_now(),
        is_off_hours=is_off_hours_now(),
        has_passkey_match=webauthn_match,
        has_face_match=bio_ok,
        has_active_session=bool(session),
        event_type="EXIT",
        recent_failures=recent_failure_count(plate_number, minutes=10),
    ))
    _record_risk(log, risk.score, risk.band, risk.factors, risk.decision_path)
    response["risk"] = {
        "score": risk.score,
        "band": risk.band,
        "factors": risk.factors,
        "decision_path": risk.decision_path,
    }

    response.update(
        {
            "decision": decision,
            "reason": reason,
            "log_id": log.id,
            "timestamp": log.timestamp.isoformat(),
        }
    )
    return Response(response)


# ====================================================================== #
#  Live camera frame OCR (with debounce)
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAdminRole])
@parser_classes([MultiPartParser, JSONParser])
def live_detect(request):
    """
    The live-camera page sends a frame every couple of seconds.
    Uses FAST OCR (EasyOCR-only when available) for low latency.
    Face detection only runs when a plate is identified, to keep things snappy.
    """
    img_bytes = _read_image(request, "plate_image")
    if not img_bytes:
        return Response({"detail": "plate_image required"}, status=400)
    try:
        ocr = recognize_plate(img_bytes, fast=True)
    except Exception as exc:  # noqa: BLE001
        return Response({"detail": f"OCR failed: {exc}"}, status=500)

    plate = ocr["plate_number"]
    confidence = ocr["confidence"]

    response = {
        "plate": plate,
        "confidence": confidence,
        "raw_text": ocr["raw_text"],
        "found_plate": ocr["found_plate"],
        "engine": ocr.get("engine", "tesseract"),
        "candidates": ocr.get("candidates", []),
        "registered": False,
        "fresh": False,
        "vehicle": None,
        "active_session": None,
        "face": {"detected": False, "matched_user": None, "distance": None},
    }

    # Fuzzy-match the plate against the DB even at lower confidence
    vehicle = None
    if plate:
        from vehicles.models import fuzzy_find_vehicle
        vehicle = fuzzy_find_vehicle(plate)
        if vehicle:
            # Update plate to the canonical form stored in DB
            plate = vehicle.plate_number
            response["plate"] = plate

    if not vehicle:
        return Response(response)

    response["registered"] = True
    from vehicles.serializers import VehicleSerializer
    response["vehicle"] = VehicleSerializer(vehicle).data

    # ----- Face detection on the SAME frame (smart-gate feature) -----
    # If a face is in the frame AND it matches a user linked to this vehicle,
    # we have a strong "this is the legitimate driver" signal.
    try:
        from biometrics.models import BiometricProfile
        from recognition.face_engine import _load_image
        import face_recognition
        import numpy as _np

        img = _load_image(img_bytes)
        locs = face_recognition.face_locations(img, model="hog")
        if not locs:
            locs = face_recognition.face_locations(img, number_of_times_to_upsample=2, model="hog")
        if locs:
            # Use the largest face in the frame (closest to camera)
            locs.sort(key=lambda r: (r[2] - r[0]) * (r[1] - r[3]), reverse=True)
            encs = face_recognition.face_encodings(img, [locs[0]])
            if encs:
                live_enc = encs[0]
                response["face"]["detected"] = True
                # Match against every user linked to the vehicle
                tolerance = float(getattr(settings, "FACE_MATCH_TOLERANCE", 0.6))
                best_match = None
                best_dist = 999.0
                for uv in vehicle.uservehicle_set.select_related("user").all():
                    user = uv.user
                    profile = BiometricProfile.objects.filter(user=user).first()
                    if not profile or not profile.encoding:
                        continue
                    stored = _np.frombuffer(profile.encoding, dtype=_np.float64)
                    if stored.size == 0:
                        continue
                    dist = float(_np.linalg.norm(stored - live_enc))
                    if dist < best_dist:
                        best_dist = dist
                        best_match = user
                if best_match and best_dist <= tolerance:
                    from accounts.serializers import UserSerializer
                    response["face"]["matched_user"] = {
                        "id": best_match.id,
                        "username": best_match.username,
                        "first_name": best_match.first_name,
                        "last_name": best_match.last_name,
                        "trust_level": best_match.trust_level,
                    }
                    response["face"]["distance"] = round(best_dist, 4)
                else:
                    response["face"]["distance"] = round(best_dist, 4) if best_match else None
    except Exception as exc:  # noqa: BLE001
        # Face detection is best-effort; never break the OCR flow
        response["face"]["error"] = str(exc)[:120]

    # Debounce – don't trigger again if we logged this plate recently.
    cutoff = timezone.now() - timedelta(seconds=settings.OCR_DEBOUNCE_SECONDS)
    recent = AccessLog.objects.filter(
        plate_detected=plate, timestamp__gte=cutoff
    ).exists()
    response["fresh"] = not recent

    session = ParkingSession.active_for(vehicle)
    response["active_session"] = (
        {
            "id": session.id,
            "entry_time": session.entry_time.isoformat(),
        }
        if session
        else None
    )
    response["suggested_event"] = "EXIT" if session else "ENTRY"

    # ----- Risk-based decision (autonomous mode) -----
    primary = vehicle.primary_user
    trust = primary.trust_level if primary else "NORMAL"
    response["trust_level"] = trust
    autonomous = bool(getattr(settings, "AUTONOMOUS_MODE", True))
    is_suspicious_time = _is_off_hours(timezone.localtime().hour)
    risk_factors = []
    if not primary:
        risk_factors.append("no_primary_user")
    if primary and primary.is_suspicious:
        risk_factors.append("user_flagged_suspicious")
    if is_suspicious_time:
        risk_factors.append("off_hours_entry")
    if _recent_failed_attempts(plate, minutes=10) >= 3:
        risk_factors.append("multiple_recent_failures")

    can_auto_grant = (
        autonomous
        and not recent
        and primary is not None
        and primary.is_trusted
        and not risk_factors
    )
    response["risk_factors"] = risk_factors
    response["can_auto_grant"] = can_auto_grant
    response["autonomous_mode"] = autonomous

    # If conditions allow, perform the access action immediately.
    if can_auto_grant and not recent:
        event_type = AccessLog.Event.EXIT if session else AccessLog.Event.ENTRY
        gate = (request.data.get("gate") or "").upper()
        gate_label = "EXIT_CAM" if gate == "EXIT" else "ENTRY_CAM" if gate == "ENTRY" else (gate[:20] or "")
        log = AccessLog.objects.create(
            event_type=event_type,
            plate_detected=plate,
            vehicle=vehicle,
            user=primary,
            status=AccessLog.Decision.GRANTED,
            reason="Autonomous mode: trusted vehicle, OCR matched, no risk factors.",
            plate_match=True,
            biometric_match=False,
            webauthn_match=False,
            confidence=AccessLog.Confidence.HIGH if confidence == "high" else AccessLog.Confidence.MEDIUM,
            via="autonomous",
            gate=gate_label,
        )
        if event_type == AccessLog.Event.ENTRY:
            ParkingSession.objects.create(
                vehicle=vehicle, entry_user=primary, entry_log=log
            )
        else:
            if session:
                session.close(exit_user=primary, exit_log=log)
        response["auto_granted"] = True
        response["log_id"] = log.id

    return Response(response)


def _is_off_hours(hour: int) -> bool:
    """11pm–5am is considered off-hours (configurable later)."""
    return hour >= 23 or hour < 5


def _recent_failed_attempts(plate: str, minutes: int = 10) -> int:
    cutoff = timezone.now() - timedelta(minutes=minutes)
    return AccessLog.objects.filter(
        plate_detected=plate,
        status=AccessLog.Decision.DENIED,
        timestamp__gte=cutoff,
    ).count()


# ====================================================================== #
#  Manual override (admin force-grant)
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAdminRole])
def manual_override(request):
    """
    An admin can force-open the gate for a plate when OCR/biometric isn't
    cooperating.  Logs everything so it's auditable.
    Body: { plate_number, event_type: ENTRY|EXIT, reason }
    """
    plate_number = normalize_plate(request.data.get("plate_number") or "")
    event_type = (request.data.get("event_type") or "ENTRY").upper()
    reason = request.data.get("reason") or "Manual admin override."

    if event_type not in dict(AccessLog.Event.choices):
        return Response({"detail": "event_type must be ENTRY or EXIT"}, status=400)

    vehicle = Vehicle.objects.filter(plate_number=plate_number).first() if plate_number else None
    log = AccessLog.objects.create(
        event_type=event_type,
        plate_detected=plate_number or "MANUAL",
        vehicle=vehicle,
        user=request.user,
        status=AccessLog.Decision.GRANTED,
        reason=f"[OVERRIDE by {request.user.username}] {reason}",
        plate_match=bool(vehicle),
        biometric_match=False,
        webauthn_match=False,
        confidence=AccessLog.Confidence.NONE,
        via="manual_override",
    )

    if vehicle:
        if event_type == "ENTRY":
            if not ParkingSession.active_for(vehicle):
                ParkingSession.objects.create(
                    vehicle=vehicle, entry_user=request.user, entry_log=log
                )
        else:
            session = ParkingSession.active_for(vehicle)
            if session:
                session.close(exit_user=request.user, exit_log=log)

    return Response(AccessLogSerializer(log).data, status=201)


# ====================================================================== #
#  Logs + stats
# ====================================================================== #
class AccessLogList(generics.ListAPIView):
    serializer_class = AccessLogSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["timestamp", "status"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        qs = AccessLog.objects.select_related("vehicle", "user").all()
        params = self.request.query_params
        if (s := params.get("status")):
            qs = qs.filter(status=s.upper())
        if (e := params.get("event")):
            qs = qs.filter(event_type=e.upper())
        if (plate := params.get("plate")):
            qs = qs.filter(plate_detected__icontains=plate.upper())
        if (start := params.get("from")):
            qs = qs.filter(timestamp__date__gte=start)
        if (end := params.get("to")):
            qs = qs.filter(timestamp__date__lte=end)
        return qs


@api_view(["GET"])
@permission_classes([IsAdminRole])
def stats(request):
    today = timezone.localdate()
    qs = AccessLog.objects.all()

    total = qs.count()
    granted = qs.filter(status=AccessLog.Decision.GRANTED).count()
    denied = qs.filter(status=AccessLog.Decision.DENIED).count()
    today_qs = qs.filter(timestamp__date=today)

    last_7 = (
        qs.filter(timestamp__date__gte=today - timezone.timedelta(days=6))
        .extra({"day": "date(timestamp)"})
        .values("day")
        .annotate(
            granted=Count("id", filter=Q(status=AccessLog.Decision.GRANTED)),
            denied=Count("id", filter=Q(status=AccessLog.Decision.DENIED)),
        )
        .order_by("day")
    )

    # Always return all 7 days even when there's no data
    existing = {r["day"]: r for r in last_7}
    full_7_days = []
    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)
        day_str = str(day)
        if day_str in existing:
            full_7_days.append(existing[day_str])
        else:
            full_7_days.append({"day": day_str, "granted": 0, "denied": 0})

    return Response(
        {
            "totals": {
                "all_time": total,
                "granted": granted,
                "denied": denied,
                "today": today_qs.count(),
                "today_granted": today_qs.filter(
                    status=AccessLog.Decision.GRANTED
                ).count(),
                "today_denied": today_qs.filter(
                    status=AccessLog.Decision.DENIED
                ).count(),
            },
            "registered_vehicles": Vehicle.objects.filter(is_active=True).count(),
            "active_sessions": ParkingSession.objects.filter(
                status=ParkingSession.Status.PARKED
            ).count(),
            "last_7_days": full_7_days,
            "recent_logs": AccessLogSerializer(qs[:5], many=True).data,
        }
    )


# ====================================================================== #
#  Internal: persist a log row
# ====================================================================== #
def _persist(
    request,
    event_type,
    plate,
    vehicle,
    user,
    plate_ok,
    bio_ok,
    webauthn_ok,
    confidence,
    reason,
    decision,
    snapshot_bytes: bytes | None = None,
) -> AccessLog:
    log = AccessLog(
        event_type=event_type,
        plate_detected=plate or "UNREADABLE",
        vehicle=vehicle,
        user=user,
        status=decision,
        reason=reason,
        plate_match=plate_ok,
        biometric_match=bio_ok,
        webauthn_match=webauthn_ok,
        confidence=confidence if confidence else AccessLog.Confidence.NONE,
        via=request.data.get("via", "manual"),
        gate=(request.data.get("gate") or "")[:20],
    )
    if snapshot_bytes:
        log.snapshot.save(
            f"snap_{timezone.now().strftime('%Y%m%d%H%M%S')}.jpg",
            ContentFile(snapshot_bytes),
            save=False,
        )
    log.save()
    return log


def _record_risk(
    access_log: AccessLog,
    score: int,
    band: str,
    factors: dict,
    decision_path: str = "",
) -> None:
    """Persist a RiskEvent linked to the AccessLog (best-effort)."""
    from .models import RiskEvent
    try:
        RiskEvent.objects.create(
            access_log=access_log,
            score=score,
            band=band,
            factors=factors,
            decision_path=decision_path,
        )
    except Exception:
        pass


# ====================================================================== #
#  Risk events feed
# ====================================================================== #
@api_view(["GET"])
@permission_classes([IsAdminRole])
def risk_events(request):
    """Recent RiskEvent rows with their AccessLog summary."""
    from .models import RiskEvent
    band = request.query_params.get("band")
    qs = RiskEvent.objects.select_related("access_log__vehicle", "access_log__user").all()
    if band:
        qs = qs.filter(band=band.upper())
    qs = qs[:50]
    out = []
    for r in qs:
        a = r.access_log
        out.append({
            "id": r.id,
            "score": r.score,
            "band": r.band,
            "factors": r.factors,
            "decision_path": r.decision_path,
            "timestamp": r.timestamp.isoformat(),
            "access_log": (
                {
                    "id": a.id,
                    "event_type": a.event_type,
                    "plate_detected": a.plate_detected,
                    "status": a.status,
                    "username": a.user.username if a.user else None,
                    "via": a.via,
                }
                if a
                else None
            ),
        })
    return Response(out)


@api_view(["GET", "PATCH"])
@permission_classes([IsAdminRole])
def incidents(request):
    """List incidents or resolve one (PATCH with ?id=X)."""
    from .models import Incident
    if request.method == "PATCH":
        inc_id = request.query_params.get("id")
        try:
            inc = Incident.objects.get(pk=inc_id)
        except Incident.DoesNotExist:
            return Response({"detail": "Not found"}, status=404)
        inc.resolved = True
        inc.resolved_by = request.user
        inc.resolution_notes = request.data.get("notes", "")
        inc.save()
        return Response({"status": "resolved"})

    severity = request.query_params.get("severity")
    resolved = request.query_params.get("resolved", "false").lower() == "true"
    qs = Incident.objects.select_related("access_log", "vehicle", "resolved_by").filter(
        resolved=resolved
    )
    if severity:
        qs = qs.filter(severity=severity.upper())
    qs = qs[:50]
    out = []
    for i in qs:
        out.append({
            "id": i.id,
            "severity": i.severity,
            "reason": i.reason,
            "resolved": i.resolved,
            "resolved_by": i.resolved_by.username if i.resolved_by else None,
            "resolution_notes": i.resolution_notes,
            "created_at": i.created_at.isoformat(),
            "vehicle": {
                "id": i.vehicle.id,
                "plate_number": i.vehicle.plate_number,
            } if i.vehicle else None,
            "access_log_id": i.access_log_id,
        })
    return Response(out)
