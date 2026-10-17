"""
Access endpoints
================

* GET  /api/access/logs/                  list & filter access logs (admin)
* GET  /api/access/stats/                 dashboard statistics (admin)
* POST /api/access/verify-entry/          ENTRY decision (OCR + biometric/passkey)
* POST /api/access/verify-exit/           EXIT decision (OCR + biometric/passkey)
* POST /api/access/live-detect/           live-camera frame OCR with debounce (admin)
* POST /api/access/manual-override/       admin force-grant (entry or exit)
* GET  /api/access/risk-events/           risk feed (admin)
* GET/PATCH /api/access/incidents/        incidents (admin)

Who may do what
---------------
* Admin / gate kiosk: any vehicle. `admin_override` is honoured only for
  admins and only when the driver has no biometric at all (walk-ins).
* Driver (phone): only vehicles they are an APPROVED user of, and only as
  themselves. Identity must come from a server-verified passkey ticket or a
  face match against their own enrolment. A client-supplied user id is never
  trusted (that was the hole that let any driver open any car's exit).

Every grant goes through parking.services.admit / release, which are atomic
and lock the vehicle row, so concurrent frames or devices can't double-open
or double-close a session.
"""

from __future__ import annotations

import base64
import binascii
import logging
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import filters, generics
from rest_framework.decorators import (
    api_view,
    parser_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminRole, is_admin
from biometrics.models import BiometricProfile
from core.throttling import CameraThrottle, GateThrottle
from parking.models import ParkingSession, PolicyConfig
from parking.services import GateDenied, admit, occupancy, release
from passkeys.models import WebAuthnCredential
from passkeys.tickets import redeem_ticket
from recognition import service as recog
from vehicles.models import (
    UserVehicle,
    Vehicle,
    assignments_prefetch,
    fuzzy_find_vehicle,
    normalize_plate,
)

from .gate import log_factory
from .models import AccessLog, Incident, RiskEvent
from .risk_engine import RiskInputs, compute_risk, recent_failure_count
from .serializers import AccessLogSerializer

log = logging.getLogger("sentinel.access")


# ====================================================================== #
#  Helpers
# ====================================================================== #
def _as_bool(value) -> bool:
    """'false', '0', '' and False are all False (bool('false') is True!)."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _read_image(request, field: str) -> bytes | None:
    if field in request.FILES:
        return request.FILES[field].read()
    b64 = request.data.get(f"{field}_base64")
    if b64:
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            return base64.b64decode(b64, validate=False)
        except (binascii.Error, ValueError):
            return None
    return None


def debounce_key(plate: str) -> str:
    return f"plate-seen:{plate}"


def _resolve_plate(request, plate_img: bytes | None) -> tuple[str, dict, Vehicle | None]:
    """(plate_number, ocr_meta, vehicle). Manual plate wins over OCR."""
    typed = (request.data.get("plate_number") or "").strip()
    if typed:
        vehicle = fuzzy_find_vehicle(typed)
        plate = vehicle.plate_number if vehicle else normalize_plate(typed)
        return plate, {"ocr_confidence": "none", "manual": True}, vehicle

    if not plate_img:
        return "", {"ocr_confidence": "none"}, None

    ocr = recog.read_plate(plate_img)
    meta = {
        "ocr_confidence": ocr["confidence"],
        "raw_text": ocr["raw_text"],
        "found_plate": ocr["found_plate"],
        "sharpness": ocr.get("sharpness"),
        "blurry": ocr.get("blurry", False),
    }
    plate = ocr["plate_number"]
    vehicle = fuzzy_find_vehicle(plate) if plate else None
    if vehicle:
        plate = vehicle.plate_number
    return normalize_plate(plate), meta, vehicle


def _has_any_credential(user: User | None) -> bool:
    if not user:
        return False
    return user.has_biometric or WebAuthnCredential.objects.filter(user=user).exists()


def _approved_users(vehicle: Vehicle) -> list[User]:
    return [
        uv.user
        for uv in UserVehicle.objects.filter(vehicle=vehicle, approved=True).select_related("user")
        if uv.user.is_active
    ]


def _best_face_match(enc, users: list[User]) -> tuple[User | None, float | None]:
    profiles = BiometricProfile.objects.filter(user__in=users).exclude(encoding=None)
    best_user, best = None, None
    by_id = {u.id: u for u in users}
    for p in profiles:
        d = recog.compare(enc, p.encoding)
        if best is None or d < best:
            best, best_user = d, by_id.get(p.user_id)
    return best_user, best


def _risk_payload(risk) -> dict:
    return {
        "score": risk.score,
        "band": risk.band,
        "factors": risk.factors,
        "decision_path": risk.decision_path,
    }


def _record_risk(access_log: AccessLog, risk) -> None:
    try:
        RiskEvent.objects.create(
            access_log=access_log,
            score=risk.score,
            band=risk.band,
            factors=risk.factors,
            decision_path=risk.decision_path[:255],
        )
    except Exception:  # noqa: BLE001
        log.exception("failed to persist RiskEvent for log %s", access_log.pk)


# ====================================================================== #
#  ENTRY / EXIT decision (shared)
# ====================================================================== #
def _decide(request, event_type: str) -> Response:
    caller = request.user
    caller_is_admin = is_admin(caller)
    via = (request.data.get("via") or ("gate" if caller_is_admin else "driver_app"))[:20]
    gate = (request.data.get("gate") or "")[:20]
    response: dict = {"event_type": event_type}

    # ---- Plate --------------------------------------------------------- #
    plate_img = _read_image(request, "plate_image")
    try:
        plate_number, ocr_meta, vehicle = _resolve_plate(request, plate_img)
    except recog.RecognitionError as exc:
        return Response({"detail": str(exc)}, status=400)
    except recog.RecognitionUnavailable as exc:
        return Response({"detail": str(exc)}, status=503)

    if vehicle and not vehicle.is_active:
        vehicle = None
    response["plate"] = {"number": plate_number, **ocr_meta, "registered": vehicle is not None}

    # Live-camera spam guard, shared by all workers via the cache.
    if plate_number and via == "live_camera" and cache.get(debounce_key(plate_number)):
        response["cooldown"] = True
        return Response(response)

    # ---- Drivers may only act on their own approved vehicles ---------- #
    if not caller_is_admin:
        if not vehicle or not vehicle.is_authorized_user(caller):
            return Response(
                {"detail": "This vehicle is not linked to your account (or the link is pending approval)."},
                status=403,
            )

    # ---- Identity: passkey ticket (server-verified) ------------------- #
    passkey_user = None
    ticket = request.data.get("passkey_ticket")
    if ticket:
        uid = redeem_ticket(ticket)
        if uid:
            passkey_user = User.objects.filter(pk=uid, is_active=True).first()
        if not passkey_user:
            response["passkey_error"] = "Passkey ticket invalid, expired or already used."
    if request.data.get("webauthn_user_id") and not ticket:
        response["passkey_error"] = (
            "webauthn_user_id is no longer accepted. Send the passkey_ticket "
            "returned by /passkeys/auth/verify/."
        )
    if passkey_user and not caller_is_admin and passkey_user.pk != caller.pk:
        passkey_user = None
        response["passkey_error"] = "Passkey belongs to a different account."

    webauthn_match = bool(passkey_user and vehicle and vehicle.is_authorized_user(passkey_user))

    # ---- Identity: face fallback -------------------------------------- #
    face_img = _read_image(request, "face_image")
    bio = {"matched": False, "distance": None, "found_face": False, "available": False}
    identity_user = passkey_user if webauthn_match else None
    if not identity_user and vehicle:
        if not caller_is_admin:
            candidates = [caller]
        else:
            candidates = _approved_users(vehicle)
        if face_img and candidates:
            try:
                enc = recog.face_encoding(face_img) if recog.face_available() else None
            except recog.RecognitionError as exc:
                return Response({"detail": str(exc)}, status=400)
            except recog.RecognitionUnavailable as exc:
                return Response({"detail": str(exc)}, status=503)
            bio["available"] = recog.face_available()
            if enc is None:
                bio["reason"] = (
                    "No face detected in the captured image."
                    if bio["available"]
                    else "Face recognition is not available on this deployment. Use a passkey."
                )
            else:
                bio["found_face"] = True
                matched_user, dist = _best_face_match(enc, candidates)
                tol = float(settings.FACE_MATCH_TOLERANCE)
                bio["tolerance"] = tol
                bio["distance"] = round(dist, 4) if dist is not None else None
                if matched_user and dist is not None and dist <= tol:
                    bio["matched"] = True
                    identity_user = matched_user
                else:
                    bio["reason"] = (
                        "Face does not match an approved driver of this vehicle."
                        if dist is not None
                        else "No face enrolment found for the approved drivers of this vehicle."
                    )
        elif not face_img:
            bio["reason"] = "No face image provided."
    response["biometric"] = bio
    response["webauthn"] = {
        "matched": webauthn_match,
        "username": passkey_user.username if passkey_user else None,
    }

    # Who is this event attributed to?
    subject = identity_user or (caller if not caller_is_admin else (vehicle.primary_user if vehicle else None))
    no_biometric_enrolled = bool(subject) and not _has_any_credential(subject)
    response["no_biometric_enrolled"] = no_biometric_enrolled

    plate_ok = vehicle is not None
    bio_ok = bool(bio.get("matched"))
    auth_ok = webauthn_match or bio_ok

    admin_override = caller_is_admin and _as_bool(request.data.get("admin_override", False))
    override_used = admin_override and no_biometric_enrolled and plate_ok
    if override_used:
        auth_ok = True

    # ---- Risk ---------------------------------------------------------- #
    cfg = PolicyConfig.current()
    active = ParkingSession.active_for(vehicle) if vehicle else None
    risk = compute_risk(
        RiskInputs(
            plate_detected=bool(plate_number),
            plate_registered=plate_ok,
            user=subject,
            vehicle=vehicle,
            ocr_confidence=ocr_meta.get("ocr_confidence", "none"),
            is_peak=cfg.is_peak_now(),
            is_off_hours=cfg.is_off_hours_now(),
            has_passkey_match=webauthn_match,
            has_face_match=bio_ok,
            has_active_session=bool(active),
            event_type=event_type,
            recent_failures=recent_failure_count(plate_number, minutes=10),
        ),
        cfg=cfg,
    )
    response["risk"] = _risk_payload(risk)

    # ---- Decision ------------------------------------------------------ #
    reason = None
    granted = False
    if not plate_number:
        reason = "License plate could not be read."
    elif not plate_ok:
        reason = f"Plate '{plate_number}' is not registered."
    elif vehicle.status == Vehicle.Status.BLOCKED:
        reason = f"Vehicle is BLOCKED: {vehicle.block_reason or 'no reason given'}"
    elif event_type == "ENTRY" and active:
        reason = "Duplicate entry: vehicle is already parked."
    elif event_type == "EXIT" and not active:
        reason = "No active parking session for this vehicle (was it ever parked?)."
    elif risk.band == "HIGH" and not override_used:
        reason = f"Access denied: risk score {risk.score} (HIGH). {risk.decision_path}"
    elif (
        event_type == "ENTRY"
        and risk.band == "LOW"
        and cfg.autonomous_mode
        and cfg.auto_entry_for_trusted
        and subject is not None
        and subject.is_trusted
        and not (cfg.force_biometric_during_peak and cfg.is_peak_now())
    ):
        granted = True
        response["auto_granted_low_risk"] = True
        reason = "Trusted vehicle, low risk: auto-granted (no biometric required)."
    elif not auth_ok:
        reason = (
            "No biometric enrolled: an admin override is required."
            if no_biometric_enrolled
            else bio.get("reason") or response.get("passkey_error") or "Driver identity could not be verified."
        )
    else:
        granted = True
        if override_used:
            reason = f"Admin override by {caller.username}: driver has no biometric enrolled (walk-in)."
        elif event_type == "ENTRY":
            reason = "Vehicle registered and driver identity verified."
        else:
            reason = "Vehicle and driver identity verified: exit allowed."

    make_log = log_factory(
        event_type=event_type,
        plate=plate_number,
        vehicle=vehicle,
        user=subject,
        plate_ok=plate_ok,
        bio_ok=bio_ok,
        webauthn_ok=webauthn_match,
        confidence=ocr_meta.get("ocr_confidence", "none"),
        via=via,
        gate=gate,
        distance=bio.get("distance"),
        snapshot_bytes=plate_img,
    )

    session = None
    if granted:
        try:
            if event_type == "ENTRY":
                access_log, session = admit(vehicle, user=subject, make_log=make_log, reason=reason)
            else:
                access_log, session = release(vehicle, user=subject, make_log=make_log, reason=reason)
        except GateDenied as gd:
            granted = False
            reason = gd.reason
            access_log = make_log(AccessLog.Decision.DENIED, reason)
    else:
        access_log = make_log(AccessLog.Decision.DENIED, reason)

    _record_risk(access_log, risk)

    response.update(
        {
            "decision": access_log.status,
            "reason": access_log.reason,
            "log_id": access_log.id,
            "timestamp": access_log.timestamp.isoformat(),
        }
    )
    if session is not None and event_type == "EXIT":
        response["fee"] = {
            "amount": str(session.fee_amount) if session.fee_amount is not None else None,
            "currency": session.fee_currency,
            "breakdown": session.fee_breakdown,
        }
    return Response(response)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
@throttle_classes([GateThrottle])
def verify_entry(request):
    return _decide(request, "ENTRY")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
@throttle_classes([GateThrottle])
def verify_exit(request):
    return _decide(request, "EXIT")


# ====================================================================== #
#  Live camera frame (admin kiosk)
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAdminRole])
@parser_classes([MultiPartParser, JSONParser])
@throttle_classes([CameraThrottle])
def live_detect(request):
    """
    A camera sends a frame every couple of seconds. OCR runs on the
    recognition workers; face matching only runs when a registered plate
    is in frame. Autonomous decisions use the SAME risk engine and policy
    as manual verification (previously a second, hand-rolled rule set that
    read AUTONOMOUS_MODE from env and ignored the admin policy page).
    """
    img_bytes = _read_image(request, "plate_image")
    if not img_bytes:
        return Response({"detail": "plate_image required"}, status=400)
    try:
        ocr = recog.read_plate(img_bytes, fast=True)
    except recog.RecognitionError as exc:
        return Response({"detail": str(exc)}, status=400)
    except recog.RecognitionUnavailable as exc:
        return Response({"detail": str(exc)}, status=503)

    plate = ocr["plate_number"]
    confidence = ocr["confidence"]
    cfg = PolicyConfig.current()
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
        "autonomous_mode": cfg.autonomous_mode,
    }

    vehicle = fuzzy_find_vehicle(plate) if plate else None
    if not vehicle or not vehicle.is_active:
        return Response(response)

    plate = vehicle.plate_number
    response["plate"] = plate
    response["registered"] = True
    from vehicles.serializers import VehicleSerializer

    vehicle = Vehicle.objects.prefetch_related(assignments_prefetch()).get(pk=vehicle.pk)
    response["vehicle"] = VehicleSerializer(vehicle, context={"request": request}).data

    # ----- Face on the same frame (best-effort) ----- #
    users = _approved_users(vehicle)
    face_user = None
    if users and recog.face_available():
        try:
            enc = recog.face_encoding(img_bytes)
            if enc is not None:
                response["face"]["detected"] = True
                best_user, dist = _best_face_match(enc, users)
                if dist is not None:
                    response["face"]["distance"] = round(dist, 4)
                if best_user and dist is not None and dist <= float(settings.FACE_MATCH_TOLERANCE):
                    face_user = best_user
                    response["face"]["matched_user"] = {
                        "id": best_user.id,
                        "username": best_user.username,
                        "first_name": best_user.first_name,
                        "last_name": best_user.last_name,
                        "trust_level": best_user.trust_level,
                    }
        except (recog.RecognitionError, recog.RecognitionUnavailable) as exc:
            response["face"]["error"] = str(exc)[:120]

    recent = bool(cache.get(debounce_key(plate)))
    response["fresh"] = not recent

    session = ParkingSession.active_for(vehicle)
    response["active_session"] = (
        {"id": session.id, "entry_time": session.entry_time.isoformat()} if session else None
    )
    event_type = "EXIT" if session else "ENTRY"
    response["suggested_event"] = event_type

    subject = face_user or vehicle.primary_user
    response["trust_level"] = subject.trust_level if subject else "NORMAL"

    min_conf = cfg.ocr_min_confidence_peak if cfg.is_peak_now() else cfg.ocr_min_confidence_normal
    conf_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
    conf_ok = conf_rank.get(confidence, 0) >= conf_rank.get(min_conf, 2)

    risk = compute_risk(
        RiskInputs(
            plate_detected=True,
            plate_registered=True,
            user=subject,
            vehicle=vehicle,
            ocr_confidence=confidence,
            is_peak=cfg.is_peak_now(),
            is_off_hours=cfg.is_off_hours_now(),
            has_face_match=face_user is not None,
            has_active_session=bool(session),
            event_type=event_type,
            recent_failures=recent_failure_count(plate, minutes=10),
        ),
        cfg=cfg,
    )
    response["risk"] = _risk_payload(risk)
    response["risk_factors"] = [k for k, v in risk.factors.items() if v > 0]

    can_auto_grant = (
        cfg.autonomous_mode
        and cfg.auto_entry_for_trusted
        and not recent
        and conf_ok
        and subject is not None
        and subject.is_trusted
        and risk.band == "LOW"
        and vehicle.status == Vehicle.Status.ACTIVE
        and not (cfg.force_biometric_during_peak and cfg.is_peak_now() and face_user is None)
    )
    response["can_auto_grant"] = can_auto_grant

    # cache.add is atomic: only one worker wins the right to act on this
    # plate inside the debounce window, even with several cameras/workers.
    if can_auto_grant and cache.add(debounce_key(plate), 1, settings.OCR_DEBOUNCE_SECONDS):
        gate_role = (request.data.get("gate") or "").upper()
        gate_label = {"EXIT": "EXIT_CAM", "ENTRY": "ENTRY_CAM"}.get(gate_role, gate_role[:20])
        make_log = log_factory(
            event_type=event_type,
            plate=plate,
            vehicle=vehicle,
            user=subject,
            plate_ok=True,
            bio_ok=face_user is not None,
            confidence=confidence,
            via="autonomous",
            gate=gate_label,
            snapshot_bytes=img_bytes,
        )
        reason = "Autonomous mode: trusted vehicle, OCR matched, low risk."
        try:
            fn = admit if event_type == "ENTRY" else release
            access_log, _ = fn(vehicle, user=subject, make_log=make_log, reason=reason)
            _record_risk(access_log, risk)
            response["auto_granted"] = True
            response["log_id"] = access_log.id
        except GateDenied as gd:
            response["auto_granted"] = False
            response["auto_denied_reason"] = gd.reason

    return Response(response)


# ====================================================================== #
#  Manual override (admin force-grant)
# ====================================================================== #
@api_view(["POST"])
@permission_classes([IsAdminRole])
@throttle_classes([GateThrottle])
def manual_override(request):
    """
    Force-open the gate for a plate when OCR/biometric isn't cooperating.
    Always audited with the admin's identity. Body: {plate_number, event_type, reason}
    """
    raw = request.data.get("plate_number") or ""
    vehicle = fuzzy_find_vehicle(raw) if raw else None
    plate_number = vehicle.plate_number if vehicle else normalize_plate(raw)
    event_type = (request.data.get("event_type") or "ENTRY").upper()
    note = (request.data.get("reason") or "Manual admin override.")[:200]
    if event_type not in dict(AccessLog.Event.choices):
        return Response({"detail": "event_type must be ENTRY or EXIT"}, status=400)

    reason = f"[OVERRIDE by {request.user.username}] {note}"
    make_log = log_factory(
        event_type=event_type,
        plate=plate_number or "MANUAL",
        vehicle=vehicle,
        user=request.user,
        plate_ok=bool(vehicle),
        via="manual_override",
        gate=(request.data.get("gate") or "MANUAL_GATE")[:20],
    )

    if not vehicle:
        # Barrier opened for an unregistered car: logged, no session.
        access_log = make_log(AccessLog.Decision.GRANTED, reason + " (unregistered vehicle, no session)")
        return Response(AccessLogSerializer(access_log, context={"request": request}).data, status=201)

    try:
        fn = admit if event_type == "ENTRY" else release
        access_log, _ = fn(vehicle, user=request.user, make_log=make_log, reason=reason)
    except GateDenied as gd:
        if gd.code in ("duplicate", "no_session"):
            # Gate still opens (admin is physically there), but the session
            # state is already correct, so just audit it.
            access_log = make_log(AccessLog.Decision.GRANTED, f"{reason} ({gd.reason})")
        else:
            access_log = make_log(AccessLog.Decision.DENIED, gd.reason)
    return Response(AccessLogSerializer(access_log, context={"request": request}).data, status=201)


# ====================================================================== #
#  Logs + stats
# ====================================================================== #
def _day_bounds(value: str, end: bool = False):
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    if end:
        d = d + timedelta(days=1)
    return timezone.make_aware(datetime.combine(d, time.min))


class AccessLogList(generics.ListAPIView):
    serializer_class = AccessLogSerializer
    permission_classes = [IsAdminRole]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["timestamp", "status"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        qs = AccessLog.objects.select_related("vehicle", "user", "user__biometric").prefetch_related(
            assignments_prefetch("vehicle__")
        )
        params = self.request.query_params
        if s := params.get("status"):
            qs = qs.filter(status=s.upper())
        if e := params.get("event"):
            qs = qs.filter(event_type=e.upper())
        if plate := params.get("plate"):
            qs = qs.filter(plate_detected__icontains=plate.upper())
        # Range filters (index-friendly) instead of timestamp__date, which
        # forces a function over every row on Postgres.
        if (start := params.get("from")) and (lo := _day_bounds(start)):
            qs = qs.filter(timestamp__gte=lo)
        if (end := params.get("to")) and (hi := _day_bounds(end, end=True)):
            qs = qs.filter(timestamp__lt=hi)
        return qs


@api_view(["GET"])
@permission_classes([IsAdminRole])
def stats(request):
    """
    Dashboard numbers. One aggregate query for the counters plus one for
    the 7-day chart (was 8+ separate COUNT queries), cached for 10 s so a
    wall of dashboards doesn't hammer the database.
    """
    cache_key = "access-stats:v2"
    payload = cache.get(cache_key)
    if payload is None:
        tz = timezone.get_current_timezone()
        today = timezone.localdate()
        today_start = timezone.make_aware(datetime.combine(today, time.min))
        week_start = today_start - timedelta(days=6)

        agg = AccessLog.objects.aggregate(
            all_time=Count("id"),
            granted=Count("id", filter=Q(status=AccessLog.Decision.GRANTED)),
            denied=Count("id", filter=Q(status=AccessLog.Decision.DENIED)),
            today=Count("id", filter=Q(timestamp__gte=today_start)),
            today_granted=Count("id", filter=Q(timestamp__gte=today_start, status=AccessLog.Decision.GRANTED)),
            today_denied=Count("id", filter=Q(timestamp__gte=today_start, status=AccessLog.Decision.DENIED)),
        )
        rows = (
            AccessLog.objects.filter(timestamp__gte=week_start)
            .annotate(day=TruncDate("timestamp", tzinfo=tz))
            .values("day")
            .annotate(
                granted=Count("id", filter=Q(status=AccessLog.Decision.GRANTED)),
                denied=Count("id", filter=Q(status=AccessLog.Decision.DENIED)),
            )
        )
        existing = {str(r["day"]): r for r in rows}
        last_7 = []
        for i in range(6, -1, -1):
            day = str(today - timedelta(days=i))
            r = existing.get(day)
            last_7.append({"day": day, "granted": r["granted"] if r else 0, "denied": r["denied"] if r else 0})

        payload = {
            "totals": agg,
            "registered_vehicles": Vehicle.objects.filter(is_active=True).count(),
            "active_sessions": ParkingSession.objects.filter(status=ParkingSession.Status.PARKED).count(),
            "occupancy": occupancy(),
            "last_7_days": last_7,
        }
        cache.set(cache_key, payload, 10)

    recent = (
        AccessLog.objects.select_related("vehicle", "user", "user__biometric")
        .prefetch_related(assignments_prefetch("vehicle__"))[:5]
    )
    return Response(
        {**payload, "recent_logs": AccessLogSerializer(recent, many=True, context={"request": request}).data}
    )


# ====================================================================== #
#  Risk events feed + incidents
# ====================================================================== #
def _limit(request, default: int = 50, cap: int = 200) -> int:
    try:
        return max(1, min(cap, int(request.query_params.get("limit", default))))
    except (TypeError, ValueError):
        return default


@api_view(["GET"])
@permission_classes([IsAdminRole])
def risk_events(request):
    band = request.query_params.get("band")
    qs = RiskEvent.objects.select_related("access_log__vehicle", "access_log__user")
    if band:
        qs = qs.filter(band=band.upper())
    out = []
    for r in qs[: _limit(request)]:
        a = r.access_log
        out.append(
            {
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
            }
        )
    return Response(out)


@api_view(["GET", "PATCH"])
@permission_classes([IsAdminRole])
def incidents(request):
    """List incidents or resolve one (PATCH with ?id=X)."""
    if request.method == "PATCH":
        inc_id = request.query_params.get("id")
        updated = Incident.objects.filter(pk=inc_id, resolved=False).update(
            resolved=True,
            resolved_by=request.user,
            resolution_notes=(request.data.get("notes") or "")[:2000],
            updated_at=timezone.now(),
        )
        if not updated:
            if Incident.objects.filter(pk=inc_id).exists():
                return Response({"status": "already_resolved"})
            return Response({"detail": "Not found"}, status=404)
        return Response({"status": "resolved"})

    severity = request.query_params.get("severity")
    resolved = _as_bool(request.query_params.get("resolved", "false"))
    qs = Incident.objects.select_related("access_log", "vehicle", "resolved_by").filter(resolved=resolved)
    if severity:
        qs = qs.filter(severity=severity.upper())
    out = [
        {
            "id": i.id,
            "severity": i.severity,
            "reason": i.reason,
            "resolved": i.resolved,
            "resolved_by": i.resolved_by.username if i.resolved_by else None,
            "resolution_notes": i.resolution_notes,
            "created_at": i.created_at.isoformat(),
            "vehicle": {"id": i.vehicle.id, "plate_number": i.vehicle.plate_number} if i.vehicle else None,
            "access_log_id": i.access_log_id,
        }
        for i in qs[: _limit(request)]
    ]
    return Response(out)
