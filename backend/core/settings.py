"""
Django settings for the Biometric Parking System.
"""

from pathlib import Path
from datetime import timedelta
from decouple import config, Csv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ #
#  Security
# ------------------------------------------------------------------ #
SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-CHANGE-ME-in-production-this-is-just-a-dev-key",
)
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1,*", cast=Csv())

# ------------------------------------------------------------------ #
#  Applications
# ------------------------------------------------------------------ #
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # Local apps
    "accounts",
    "vehicles",
    "biometrics",
    "access",
    "parking",
    "passkeys",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# ------------------------------------------------------------------ #
#  Database — Postgres on Render, SQLite locally
# ------------------------------------------------------------------ #
DATABASE_URL = config("DATABASE_URL", default="")
if DATABASE_URL:
    import dj_database_url
    DATABASES = {"default": dj_database_url.config(default=DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ------------------------------------------------------------------ #
#  Static & Media
# ------------------------------------------------------------------ #
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "media"))

# ------------------------------------------------------------------ #
#  Auth
# ------------------------------------------------------------------ #
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------------ #
#  Internationalisation
# ------------------------------------------------------------------ #
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------ #
#  Static / Media
# ------------------------------------------------------------------ #
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------ #
#  Django REST Framework
# ------------------------------------------------------------------ #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ------------------------------------------------------------------ #
#  CORS
# ------------------------------------------------------------------ #
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

# ------------------------------------------------------------------ #
#  Recognition Settings
# ------------------------------------------------------------------ #
TESSERACT_CMD = config("TESSERACT_CMD", default="")
FACE_MATCH_TOLERANCE = config("FACE_MATCH_TOLERANCE", default=0.6, cast=float)

# Live-OCR debounce: same plate within this many seconds is ignored.
OCR_DEBOUNCE_SECONDS = config("OCR_DEBOUNCE_SECONDS", default=30, cast=int)
# Minimum OCR confidence to act on a detection during live mode.
OCR_MIN_CONFIDENCE = config("OCR_MIN_CONFIDENCE", default="medium")

# Autonomous mode: when True, trusted users' vehicles are auto-granted access
# from live camera detections without requiring biometric.  Suspicious users
# and off-hours entries always require biometric regardless.
AUTONOMOUS_MODE = config("AUTONOMOUS_MODE", default=True, cast=bool)

# ------------------------------------------------------------------ #
#  WebAuthn (Passkeys)
# ------------------------------------------------------------------ #
# Relying-Party identity – MUST match the host the frontend runs on.
# For local dev: "localhost".  For production: your real domain.
WEBAUTHN_RP_ID = config("WEBAUTHN_RP_ID", default="localhost")
WEBAUTHN_RP_NAME = config("WEBAUTHN_RP_NAME", default="Sentinel Parking")
# Allowed origins (frontend URLs).  Comma-separated.
WEBAUTHN_ORIGINS = config(
    "WEBAUTHN_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000",
    cast=Csv(),
)

# ------------------------------------------------------------------ #
#  Pickup token (QR-based mobile pickup)
# ------------------------------------------------------------------ #
PICKUP_TOKEN_TTL_SECONDS = config(
    "PICKUP_TOKEN_TTL_SECONDS", default=300, cast=int
)  # 5 minutes
FRONTEND_BASE_URL = config(
    "FRONTEND_BASE_URL", default="http://localhost:3000"
)

# Increase upload size to allow base64 images.
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024  # 25 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
