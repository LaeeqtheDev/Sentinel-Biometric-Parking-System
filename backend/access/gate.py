"""Small helpers shared by every gate path (access views, QR pickup)."""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.utils import timezone

from .models import AccessLog

_CONFIDENCES = {c for c, _ in AccessLog.Confidence.choices}


def log_factory(
    *,
    event_type: str,
    plate: str,
    vehicle,
    user,
    plate_ok: bool,
    bio_ok: bool = False,
    webauthn_ok: bool = False,
    confidence: str = "none",
    via: str = "manual",
    gate: str = "",
    distance: float | None = None,
    snapshot_bytes: bytes | None = None,
):
    """Return make_log(decision, reason) -> AccessLog with these fields bound."""

    def make_log(decision: str, reason: str) -> AccessLog:
        log = AccessLog(
            event_type=event_type,
            plate_detected=(plate or "UNREADABLE")[:20],
            vehicle=vehicle,
            user=user,
            status=decision,
            reason=(reason or "")[:255],
            plate_match=plate_ok,
            biometric_match=bio_ok,
            webauthn_match=webauthn_ok,
            biometric_distance=distance,
            confidence=confidence if confidence in _CONFIDENCES else AccessLog.Confidence.NONE,
            via=(via or "manual")[:20],
            gate=(gate or "")[:20],
        )
        if snapshot_bytes:
            log.snapshot.save(
                f"snap_{timezone.now():%Y%m%d%H%M%S%f}.jpg",
                ContentFile(snapshot_bytes),
                save=False,
            )
        log.save()
        return log

    return make_log
