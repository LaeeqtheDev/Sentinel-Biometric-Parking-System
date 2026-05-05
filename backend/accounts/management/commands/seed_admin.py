"""
Seeds the database with a default admin account.

Usage:
    python manage.py seed_admin
    python manage.py seed_admin --username admin --password admin12345
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the default admin user (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--password", default="admin12345")
        parser.add_argument("--email", default="admin@sentinel.local")

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        password = options["password"]
        email = options["email"]

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": "System",
                "last_name": "Administrator",
                "role": "ADMIN",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        # Always (re)set password and ensure flags are correct.
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.role = "ADMIN"
        user.save()

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} admin user → username='{username}'  password='{password}'"
            )
        )
