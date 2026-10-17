"""
Side effects of every AccessLog row.

Trust scoring (capped at +6 earned per user per day to prevent farming):
    +2  successful grant
    +3  bonus if verified by passkey
    -5  denied attempt
    -10 extra if denied for a biometric mismatch on a registered plate

Also: marks the plate as recently seen (shared debounce for the cameras)
and opens an Incident for high-risk patterns.

Changes from the original:
  * Runs after the gate transaction commits (transaction.on_commit), so the
    vehicle row lock is never held while trust/incident work happens, and
    nothing is applied for a decision that was rolled back.
  * Trust is updated with a single atomic UPDATE (F expressions + clamp)
    instead of read-modify-write, so two concurrent events can't lose an
    update.
  * The daily cap is tracked per user in the shared cache. The old formula
    (grants_today * 5) over-counted and could block all earning after one
    grant.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest, Least
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import AccessLog, Incident

log = logging.getLogger("sentinel.access")

DAILY_TRUST_CAP = 6


@receiver(post_save, sender=AccessLog)
def on_access_log(sender, instance: AccessLog, created: bool, **kwargs):
    if not created:
        return
    log_id = instance.pk
    transaction.on_commit(lambda: _after_commit(log_id))


def _after_commit(log_id: int):
    try:
        instance = AccessLog.objects.select_related("vehicle", "user").get(pk=log_id)
    except AccessLog.DoesNotExist:
        return
    if instance.plate_detected and instance.plate_detected not in ("UNREADABLE", "MANUAL"):
        from .views import debounce_key

        cache.set(debounce_key(instance.plate_detected), 1, settings.OCR_DEBOUNCE_SECONDS)
    try:
        _maybe_create_incident(instance)
    except Exception:  # noqa: BLE001
        log.exception("incident detection failed for log %s", log_id)
    try:
        _adjust_trust(instance)
    except Exception:  # noqa: BLE001
        log.exception("trust update failed for log %s", log_id)


def _earn_budget(user_id: int, wanted: int) -> int:
    """Reserve up to `wanted` trust points from today's cap, atomically."""
    key = f"trust-earned:{user_id}:{timezone.localdate().isoformat()}"
    cache.add(key, 0, 60 * 60 * 26)
    try:
        after = cache.incr(key, wanted)
    except ValueError:
        cache.set(key, wanted, 60 * 60 * 26)
        after = wanted
    before = after - wanted
    return max(0, min(wanted, DAILY_TRUST_CAP - before))


def _adjust_trust(instance: AccessLog):
    if not instance.user_id:
        return
    from accounts.models import User

    delta = 0
    if instance.status == AccessLog.Decision.GRANTED:
        delta = _earn_budget(instance.user_id, 2 + (3 if instance.webauthn_match else 0))
    elif instance.status == AccessLog.Decision.DENIED:
        delta = -5
        if instance.plate_match and not instance.biometric_match and instance.biometric_distance is not None:
            delta -= 10

    now = timezone.now()
    if delta:
        User.objects.filter(pk=instance.user_id).update(
            trust_score=Greatest(Value(0), Least(Value(100), F("trust_score") + delta)),
            last_activity_at=now,
        )
        user = User.objects.get(pk=instance.user_id)
        user.recompute_trust_level(save=True)
    else:
        User.objects.filter(pk=instance.user_id).update(last_activity_at=now)


def _maybe_create_incident(log_row: AccessLog):
    if log_row.status != AccessLog.Decision.DENIED:
        return
    if Incident.objects.filter(access_log=log_row).exists():
        return

    severity = reason = None
    if log_row.vehicle and log_row.vehicle.status == "BLOCKED":
        severity = Incident.Severity.HIGH
        reason = f"BLOCKED vehicle {log_row.plate_detected} attempted {log_row.event_type}."
    elif log_row.plate_match and not log_row.biometric_match and log_row.biometric_distance is not None:
        severity = Incident.Severity.MEDIUM
        reason = (
            f"Biometric mismatch for registered plate {log_row.plate_detected}. "
            "Possible impersonation."
        )
    elif log_row.plate_detected and log_row.plate_detected != "UNREADABLE":
        cutoff = timezone.now() - timedelta(minutes=10)
        count = AccessLog.objects.filter(
            plate_detected=log_row.plate_detected,
            status=AccessLog.Decision.DENIED,
            timestamp__gte=cutoff,
        ).count()
        # Exactly at the threshold, so a burst opens one incident, not one per denial.
        if count == 3:
            severity = Incident.Severity.HIGH
            reason = f"{count} consecutive denials for {log_row.plate_detected} in 10 mins."

    if severity and reason:
        Incident.objects.create(
            access_log=log_row, vehicle=log_row.vehicle, severity=severity, reason=reason
        )
