"""
Signal handlers for AccessLog.

Trust scoring rules (capped at +6 per day to prevent farming):
    +2  successful grant
    +3  bonus if verified by passkey
    -5  denied attempt
    -10 denied due to biometric mismatch (possible impersonation)

Daily cap: at most +6 trust earned per calendar day.
Auto-creates Incident rows for HIGH-risk events.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import AccessLog

DAILY_TRUST_CAP = 6


@receiver(post_save, sender=AccessLog)
def adjust_trust_on_access_log(sender, instance: AccessLog, created: bool, **kwargs):
    if not created:
        return

    _maybe_create_incident(instance)

    if not instance.user:
        return

    user = instance.user
    delta = 0

    if instance.status == AccessLog.Decision.GRANTED:
        raw = 2 + (3 if instance.webauthn_match else 0)
        # Daily cap check
        today = timezone.localdate()
        grants_today = AccessLog.objects.filter(
            user=user,
            status=AccessLog.Decision.GRANTED,
            timestamp__date=today,
        ).exclude(pk=instance.pk).count()
        already_earned = min(grants_today * 5, DAILY_TRUST_CAP)
        remaining = max(0, DAILY_TRUST_CAP - already_earned)
        delta = min(raw, remaining)

    elif instance.status == AccessLog.Decision.DENIED:
        delta = -5
        if instance.plate_match and not instance.biometric_match:
            delta -= 10

    if delta != 0:
        user.adjust_trust(delta, save=True)

    user.last_activity_at = timezone.now()
    user.save(update_fields=["last_activity_at"])


def _maybe_create_incident(log: AccessLog):
    try:
        from .models import Incident
        from datetime import timedelta

        if Incident.objects.filter(access_log=log).exists():
            return

        severity = reason = None

        if (log.status == AccessLog.Decision.DENIED
                and log.vehicle
                and getattr(log.vehicle, 'status', None) == 'BLOCKED'):
            severity = Incident.Severity.HIGH
            reason = f"BLOCKED vehicle {log.plate_detected} attempted {log.event_type}."

        elif (log.status == AccessLog.Decision.DENIED
              and log.plate_match and log.biometric_match is False):
            severity = Incident.Severity.MEDIUM
            reason = (
                f"Biometric mismatch for registered plate {log.plate_detected}. "
                "Possible impersonation."
            )

        elif log.status == AccessLog.Decision.DENIED and log.plate_detected:
            cutoff = timezone.now() - timedelta(minutes=10)
            count = AccessLog.objects.filter(
                plate_detected=log.plate_detected,
                status=AccessLog.Decision.DENIED,
                timestamp__gte=cutoff,
            ).count()
            if count >= 3:
                severity = Incident.Severity.HIGH
                reason = f"{count} consecutive denials for {log.plate_detected} in 10 mins."

        if severity and reason:
            Incident.objects.create(
                access_log=log,
                vehicle=log.vehicle,
                severity=severity,
                reason=reason,
            )
    except Exception:
        pass
