from django.apps import AppConfig


class AccessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "access"

    def ready(self):
        # Hook trust-score signal handlers
        from . import signals  # noqa: F401
