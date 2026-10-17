"""
Delete expired / consumed WebAuthn challenges and stale pickup tokens.

Without this, every passkey prompt and every QR shown at the gate left a
row behind forever, so these tables grew without bound.
Runs every 10 minutes via Celery beat, or manually / from cron:

    python manage.py purge_expired
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from passkeys.models import PickupToken, WebAuthnChallenge


class Command(BaseCommand):
    help = "Purge expired WebAuthn challenges and old pickup tokens."

    def add_arguments(self, parser):
        parser.add_argument(
            "--token-retention-days",
            type=int,
            default=30,
            help="Keep redeemed/denied/expired pickup tokens this long for audit.",
        )

    def handle(self, *args, **opts):
        now = timezone.now()
        ch_deleted, _ = WebAuthnChallenge.objects.filter(
            Q(expires_at__lt=now) | Q(consumed=True)
        ).delete()

        expired = PickupToken.objects.filter(
            status=PickupToken.Status.PENDING, expires_at__lt=now
        ).update(status=PickupToken.Status.EXPIRED)

        cutoff = now - timedelta(days=opts["token_retention_days"])
        tok_deleted, _ = PickupToken.objects.filter(
            created_at__lt=cutoff
        ).exclude(status=PickupToken.Status.PENDING).delete()

        self.stdout.write(
            f"challenges deleted={ch_deleted} tokens expired={expired} tokens deleted={tok_deleted}"
        )
