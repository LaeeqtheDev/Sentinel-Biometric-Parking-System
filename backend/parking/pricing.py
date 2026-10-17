"""
Dynamic pricing: peak / off-peak segmentation.

A stay is split into minutes that fall inside the configured peak window and
minutes outside it. Peak minutes are billed at `peak_hourly_rate`, the rest
at `hourly_rate`, both pro-rated per minute. Stays no longer than
`grace_minutes` are free. Works for stays spanning several days and for
peak windows that wrap past midnight.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone


def _peak_intervals(start: datetime, end: datetime, cfg) -> list[tuple[datetime, datetime]]:
    """Every peak window (as aware datetimes) that could overlap [start, end]."""
    if not cfg.peak_enabled:
        return []
    tz = timezone.get_current_timezone()
    local_start = timezone.localtime(start, tz)
    local_end = timezone.localtime(end, tz)
    out = []
    day = local_start.date() - timedelta(days=1)  # catch windows that wrap from yesterday
    while day <= local_end.date():
        w_start = timezone.make_aware(datetime.combine(day, cfg.peak_start), tz)
        end_day = day if cfg.peak_start <= cfg.peak_end else day + timedelta(days=1)
        w_end = timezone.make_aware(datetime.combine(end_day, cfg.peak_end), tz)
        out.append((w_start, w_end))
        day += timedelta(days=1)
    return out


def _overlap_seconds(a_start, a_end, b_start, b_end) -> float:
    lo, hi = max(a_start, b_start), min(a_end, b_end)
    return max(0.0, (hi - lo).total_seconds())


def compute_fee(entry: datetime, exit_: datetime, cfg) -> tuple[Decimal, dict]:
    total_seconds = max(0.0, (exit_ - entry).total_seconds())
    total_minutes = total_seconds / 60

    peak_seconds = sum(
        _overlap_seconds(entry, exit_, ws, we) for ws, we in _peak_intervals(entry, exit_, cfg)
    )
    peak_seconds = min(peak_seconds, total_seconds)
    peak_minutes = peak_seconds / 60
    offpeak_minutes = total_minutes - peak_minutes

    breakdown = {
        "total_minutes": round(total_minutes, 1),
        "peak_minutes": round(peak_minutes, 1),
        "offpeak_minutes": round(offpeak_minutes, 1),
        "hourly_rate": str(cfg.hourly_rate),
        "peak_hourly_rate": str(cfg.peak_hourly_rate),
        "grace_minutes": cfg.grace_minutes,
        "currency": cfg.currency,
    }

    if total_minutes <= cfg.grace_minutes:
        breakdown["waived"] = "within grace period"
        return Decimal("0.00"), breakdown

    amount = (
        Decimal(str(peak_minutes)) / 60 * Decimal(cfg.peak_hourly_rate)
        + Decimal(str(offpeak_minutes)) / 60 * Decimal(cfg.hourly_rate)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return amount, breakdown
