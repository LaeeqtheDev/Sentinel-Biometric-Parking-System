"""
Django settings for the Sentinel Biometric Parking System.

Everything environment-specific comes from env vars (see .env.example).
Defaults are safe for local development only; production refuses to boot
with a missing SECRET_KEY or a wildcard ALLOWED_HOSTS.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ #
#  Security
# ------------------------------------------------------------------ #
DEBUG = config("DEBUG", default=False, cast=bool)

_DEV_SECRET = "django-insecure-dev-only-key-do-not-use-in-production"
SECRET_KEY = config("SECRET_KEY", default=_DEV_SECRET if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is False.")

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1" if DEBUG else "",
    cast=Csv(),
)
if not DEBUG and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must list explicit hostnames in production (no '*')."
    )

CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
# Move the Django admin off the default path in production.
ADMIN_URL = config("ADMIN_URL", default="admin/")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SECURE_REDIRECT_EXEMPT = [r"^healthz/?$", r"^readyz/?$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

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
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # Local apps
    "core",
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
ASGI_APPLICATION = "core.asgi.application"

# ------------------------------------------------------------------ #
#  Database: Postgres in production (DATABASE_URL), SQLite for local dev
# ------------------------------------------------------------------ #
DATABASE_URL = config("DATABASE_URL", default="")
if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            # Persistent connections, verified before reuse so a dropped
            # connection (failover, idle timeout) never surfaces as a 500.
            conn_max_age=config("DB_CONN_MAX_AGE", default=60, cast=int),
            conn_health_checks=True,
        )
    }
else:
    if not DEBUG:
        raise ImproperlyConfigured("DATABASE_URL must be set in production.")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }

# ------------------------------------------------------------------ #
#  Cache: shared Redis across every web and worker process.
#  Debounce windows, single-use passkey tickets, throttles and the cached
#  policy all live here, so they must be shared, not per-process.
# ------------------------------------------------------------------ #
REDIS_URL = config("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": False,
            },
            "KEY_PREFIX": "sentinel",
        }
    }
else:
    if not DEBUG:
        raise ImproperlyConfigured(
            "REDIS_URL must be set in production: debounce, throttles and "
            "single-use passkey tickets need a cache shared by all workers."
        )
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "sentinel-dev",
        }
    }

# ------------------------------------------------------------------ #
#  Static & media storage
# ------------------------------------------------------------------ #
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "media"))

# Media holds CNIC scans, licences, face reference photos and gate
# snapshots. It is never served publicly: files are streamed through
# /api/files/<signed-token>/ which expires (see core/files.py).
# Set AWS_STORAGE_BUCKET_NAME to use any S3-compatible bucket
# (Oracle Object Storage, AWS S3, Cloudflare R2) so every API instance
# reads and writes the same files instead of its own local disk.
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
if AWS_STORAGE_BUCKET_NAME:
    _media_backend = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "endpoint_url": config("AWS_S3_ENDPOINT_URL", default="") or None,
            "region_name": config("AWS_S3_REGION_NAME", default="") or None,
            "default_acl": "private",
            "querystring_auth": True,
            "file_overwrite": False,
        },
    }
else:
    _media_backend = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": _media_backend,
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}

SIGNED_FILE_URL_TTL_SECONDS = config("SIGNED_FILE_URL_TTL_SECONDS", default=900, cast=int)
# Public base URL of this API, used to build absolute signed file links
# when a serializer has no request in context.
BACKEND_BASE_URL = config("BACKEND_BASE_URL", default="http://localhost:8000")

# Uploads: camera frames are base64 JSON, so allow a few MB but not 25.
DATA_UPLOAD_MAX_MEMORY_SIZE = config("DATA_UPLOAD_MAX_MEMORY_SIZE", default=8 * 1024 * 1024, cast=int)
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = config("MAX_IMAGE_PIXELS", default=16_000_000, cast=int)
MAX_DOCUMENT_BYTES = config("MAX_DOCUMENT_BYTES", default=10 * 1024 * 1024, cast=int)

# ------------------------------------------------------------------ #
#  Auth
# ------------------------------------------------------------------ #
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------------ #
#  Internationalisation
# ------------------------------------------------------------------ #
LANGUAGE_CODE = "en-us"
TIME_ZONE = config("TIME_ZONE", default="Asia/Karachi")
USE_I18N = True
USE_TZ = True

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
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": config("THROTTLE_ANON", default="60/min"),
        "user": config("THROTTLE_USER", default="600/min"),
        "login": config("THROTTLE_LOGIN", default="10/min"),
        "register": config("THROTTLE_REGISTER", default="5/hour"),
        "passkey": config("THROTTLE_PASSKEY", default="30/min"),
        "gate": config("THROTTLE_GATE", default="60/min"),
        "camera": config("THROTTLE_CAMERA", default="120/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("JWT_ACCESS_MINUTES", default=15, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=config("JWT_REFRESH_DAYS", default=7, cast=int)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ------------------------------------------------------------------ #
#  CORS
# ------------------------------------------------------------------ #
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000" if DEBUG else "",
    cast=Csv(),
)
# The frontend uses Bearer tokens, not cookies.
CORS_ALLOW_CREDENTIALS = False

# ------------------------------------------------------------------ #
#  Recognition
# ------------------------------------------------------------------ #
TESSERACT_CMD = config("TESSERACT_CMD", default="")
FACE_MATCH_TOLERANCE = config("FACE_MATCH_TOLERANCE", default=0.6, cast=float)
# Same plate within this many seconds is ignored by the live camera.
OCR_DEBOUNCE_SECONDS = config("OCR_DEBOUNCE_SECONDS", default=30, cast=int)
# Frames are downscaled to this width before OCR (keeps CPU per frame flat).
OCR_MAX_WIDTH = config("OCR_MAX_WIDTH", default=1280, cast=int)
# When true, OCR and face matching run on Celery workers instead of the
# web process, so heavy CV work never blocks API requests.
RECOGNITION_ASYNC = config("RECOGNITION_ASYNC", default=False, cast=bool)
RECOGNITION_TIMEOUT_SECONDS = config("RECOGNITION_TIMEOUT_SECONDS", default=8, cast=int)

# ------------------------------------------------------------------ #
#  WebAuthn (Passkeys)
# ------------------------------------------------------------------ #
WEBAUTHN_RP_ID = config("WEBAUTHN_RP_ID", default="localhost")
WEBAUTHN_RP_NAME = config("WEBAUTHN_RP_NAME", default="Sentinel Parking")
WEBAUTHN_ORIGINS = config(
    "WEBAUTHN_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000",
    cast=Csv(),
)
# A verified passkey assertion is exchanged for a single-use ticket that
# the gate endpoints accept. It is bound to one user and expires quickly.
PASSKEY_TICKET_TTL_SECONDS = config("PASSKEY_TICKET_TTL_SECONDS", default=60, cast=int)

# ------------------------------------------------------------------ #
#  Pickup token (QR-based mobile pickup)
# ------------------------------------------------------------------ #
PICKUP_TOKEN_TTL_SECONDS = config("PICKUP_TOKEN_TTL_SECONDS", default=300, cast=int)
FRONTEND_BASE_URL = config("FRONTEND_BASE_URL", default="http://localhost:3000")

# ------------------------------------------------------------------ #
#  Celery (recognition workers + periodic cleanup)
# ------------------------------------------------------------------ #
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL or "memory://")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL or "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = not bool(REDIS_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_EXPIRES = 300
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ROUTES = {
    "recognition.tasks.*": {"queue": "recognition"},
    "core.tasks.*": {"queue": "default"},
}
CELERY_BEAT_SCHEDULE = {
    "purge-expired-auth-artifacts": {
        "task": "core.tasks.purge_expired",
        "schedule": 600.0,
    },
}

# ------------------------------------------------------------------ #
#  Logging: structured to stdout so the platform collects it
# ------------------------------------------------------------------ #
LOG_LEVEL = config("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "sentinel": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
