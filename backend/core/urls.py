"""
Top-level URL configuration for the Biometric Parking System.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/vehicles/", include("vehicles.urls")),
    path("api/biometrics/", include("biometrics.urls")),
    path("api/access/", include("access.urls")),
    path("api/parking/", include("parking.urls")),
    path("api/passkeys/", include("passkeys.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
