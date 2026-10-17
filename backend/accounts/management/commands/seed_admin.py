"""
Create the first admin account (idempotent).

    python manage.py seed_admin --username admin --password '<strong password>'
    ADMIN_PASSWORD='<strong password>' python manage.py seed_admin

Changes from the original:
  * No baked-in default password ("admin12345") on reachable hosts. Outside
    DEBUG a password must be supplied and must pass the password validators.
  * An existing admin's password is NOT silently reset on every run (the old
    command reset it each time, so a deploy hook could revert a changed
    password). Use --reset-password explicitly.
  * The password is never printed to logs.
"""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the admin user (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.environ.get("ADMIN_USERNAME", "admin"))
        parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", ""))
        parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL", "admin@sentinel.local"))
        parser.add_argument("--reset-password", action="store_true")

    def handle(self, *args, **options):
        User = get_user_model()
        username, password = options["username"], options["password"]

        if not password:
            if not settings.DEBUG:
                raise CommandError("Provide --password or ADMIN_PASSWORD (no default in production).")
            password = "admin12345"
            self.stdout.write(self.style.WARNING("DEBUG: using the development password 'admin12345'."))
        elif not settings.DEBUG:
            try:
                validate_password(password)
            except ValidationError as exc:
                raise CommandError(" ".join(exc.messages)) from exc

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": options["email"],
                "first_name": "System",
                "last_name": "Administrator",
                "role": "ADMIN",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created or options["reset_password"]:
            user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.role = "ADMIN"
        user.save()

        verb = "Created" if created else ("Updated (password reset)" if options["reset_password"] else "Already exists")
        self.stdout.write(self.style.SUCCESS(f"{verb}: admin user '{username}'."))
