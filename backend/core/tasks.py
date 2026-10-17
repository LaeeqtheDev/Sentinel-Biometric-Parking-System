from celery import shared_task
from django.core.management import call_command


@shared_task(name="core.tasks.purge_expired")
def purge_expired():
    """Periodic cleanup of expired WebAuthn challenges and pickup tokens."""
    call_command("purge_expired")
