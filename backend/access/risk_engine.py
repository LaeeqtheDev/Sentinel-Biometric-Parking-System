"""
Risk engine
===========

Pure-Python decision module.  Given a bundle of signals (vehicle, user, OCR
result, time of day, recent failures, etc.) it returns:

    * a numeric risk score (0..100)
    * a categorical band (LOW / MEDIUM / HIGH) based on PolicyConfig
    * a `factors` dict explaining each contribution
    * a `decision_path` string for human auditors

The engine is stateless — callers persist the result to a `RiskEvent` row
once the access decision has been made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from accounts.models import User
from vehicles.models import Vehicle


@dataclass
class RiskInputs:
    plate_detected: bool
    plate_registered: bool
    user: Optional[User] = None
    vehicle: Optional[Vehicle] = None
    ocr_confidence: str = "none"  # high / medium / low / none
    is_peak: bool = False
    is_off_hours: bool = False
    has_passkey_match: bool = False
    has_face_match: bool = False
    has_active_session: bool = False
    event_type: str = "ENTRY"  # or EXIT
    recent_failures: int = 0


@dataclass
class RiskResult:
    score: int
    band: str  # LOW / MEDIUM / HIGH
    factors: dict = field(default_factory=dict)
    decision_path: str = ""

    def add(self, label: str, delta: int):
        self.factors[label] = self.factors.get(label, 0) + delta
        self.score = max(0, min(100, self.score + delta))


def compute_risk(inputs: RiskInputs) -> RiskResult:
    """
    Score starts at 50 (neutral).  Each signal pushes it up (riskier) or
    down (safer).  Final score is clamped to [0, 100].
    """
    from parking.models import PolicyConfig

    cfg = PolicyConfig.current()
    res = RiskResult(score=50, band="MEDIUM")

    # ---- Plate detection signals -----------------------------------------
    if not inputs.plate_detected:
        res.add("plate_unreadable", +35)
    elif not inputs.plate_registered:
        res.add("plate_not_in_db", +40)
    else:
        res.add("plate_known", -15)

    # ---- OCR confidence (only matters when plate is registered) ----------
    if inputs.plate_registered:
        if inputs.ocr_confidence == "high":
            res.add("ocr_high", -15)
        elif inputs.ocr_confidence == "medium":
            res.add("ocr_medium", -5)
        elif inputs.ocr_confidence == "low":
            res.add("ocr_low", +10)
        elif inputs.ocr_confidence == "none":
            # No OCR ran (manual plate entry) – neutral
            pass

    # ---- Vehicle status --------------------------------------------------
    if inputs.vehicle:
        if inputs.vehicle.status == Vehicle.Status.BLOCKED:
            res.add("vehicle_blocked", +60)
        elif inputs.vehicle.status == Vehicle.Status.UNDER_REVIEW:
            res.add("vehicle_under_review", +25)

    # ---- User / trust ----------------------------------------------------
    if inputs.user:
        if inputs.user.trust_score >= cfg.trusted_threshold:
            res.add("user_trusted", -20)
        elif inputs.user.trust_score < cfg.normal_threshold:
            res.add("user_suspicious", +25)
    else:
        res.add("user_unknown", +10)

    # ---- Time-based ------------------------------------------------------
    if inputs.is_off_hours:
        res.add("off_hours", +15)
    if inputs.is_peak:
        res.add("peak_hours", +5)  # not bad per se but we tighten policy

    # ---- Auth signals ----------------------------------------------------
    if inputs.has_passkey_match:
        res.add("passkey_match", -25)
    if inputs.has_face_match:
        res.add("face_match", -20)

    # ---- Session sanity --------------------------------------------------
    if inputs.event_type == "EXIT" and not inputs.has_active_session:
        res.add("exit_without_session", +50)
    if inputs.event_type == "ENTRY" and inputs.has_active_session:
        res.add("duplicate_entry_attempt", +60)

    # ---- Repeated failures (brute-force / harassment) --------------------
    if inputs.recent_failures >= 3:
        res.add("repeated_failures", +20)
    if inputs.recent_failures >= 5:
        res.add("severe_repeated_failures", +20)

    # Categorize
    if res.score <= cfg.risk_low_max:
        res.band = "LOW"
    elif res.score <= cfg.risk_medium_max:
        res.band = "MEDIUM"
    else:
        res.band = "HIGH"

    # Build a human-readable trace, sorted by absolute contribution
    sorted_factors = sorted(
        res.factors.items(), key=lambda kv: abs(kv[1]), reverse=True
    )
    res.decision_path = " · ".join(
        f"{label}{'+' if delta >= 0 else ''}{delta}"
        for label, delta in sorted_factors
    )
    return res


def recent_failure_count(plate: str, minutes: int = 10) -> int:
    """Helper exposed for callers — counts recent denied attempts."""
    from access.models import AccessLog

    if not plate:
        return 0
    cutoff = timezone.now() - timedelta(minutes=minutes)
    return AccessLog.objects.filter(
        plate_detected=plate,
        status=AccessLog.Decision.DENIED,
        timestamp__gte=cutoff,
    ).count()


def is_off_hours_now() -> bool:
    """11pm–5am is off-hours by convention."""
    h = timezone.localtime().hour
    return h >= 23 or h < 5
