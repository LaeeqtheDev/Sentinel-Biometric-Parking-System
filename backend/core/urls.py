"""
Top-level URL configuration for the Sentinel Biometric Parking System.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from .files import serve_signed_file
from .health import healthz, readyz

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("readyz/", readyz, name="readyz"),
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/files/<str:token>/", serve_signed_file, name="signed_file"),
    path("api/auth/", include("accounts.urls")),
    path("api/vehicles/", include("vehicles.urls")),
    path("api/biometrics/", include("biometrics.urls")),
    path("api/access/", include("access.urls")),
    path("api/parking/", include("parking.urls")),
    path("api/passkeys/", include("passkeys.urls")),
]
# Media is intentionally NOT exposed at /media/. Files are only reachable
# through short-lived signed links (see core/files.py).
