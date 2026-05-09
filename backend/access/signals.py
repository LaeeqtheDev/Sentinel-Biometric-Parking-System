"""
Signal handlers that adjust the linked user's trust_score whenever an
AccessLog row is created.  Trust scoring rules:

    +2  successful access (granted)
    +5  successful access verified by passkey (passkey is harder to fake)
    -5  denied attempt
    -15 denied because biometric mismatched a known user
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import AccessLog


@receiver(post_save, sender=AccessLog)
def adjust_trust_on_access_log(sender, instance: AccessLog, created: bool, **kwargs):
    if not created or not instance.user:
        return

    user = instance.user
    delta = 0
    if instance.status == AccessLog.Decision.GRANTED:
        delta += 2
        if instance.webauthn_match:
            delta += 3
    elif instance.status == AccessLog.Decision.DENIED:
        delta -= 5
        # Stronger penalty for biometric mismatch — the user was identified
        # but their face didn't match.  Could be impersonation.
        if instance.user and instance.plate_match and not instance.biometric_match:
            delta -= 10

    if delta != 0:
        user.adjust_trust(delta, save=True)

    # Touch last_activity_at regardless
    user.last_activity_at = timezone.now()
    user.save(update_fields=["last_activity_at"])
