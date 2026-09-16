"""Base Django settings shared by every environment."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int) -> int:
    try:
        return int(os.environ[key])
    except (KeyError, ValueError):
        return default


def env_list(key: str, default: str = "") -> list[str]:
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --- Core -------------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

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
    "django_filters",
    "drf_spectacular",
    # Local
    "apps.core",
    "apps.accounts",
    "apps.competitions",
    "apps.fixtures",
    "apps.standings",
    "apps.social",
    "apps.media_assets",
    "apps.notifications",
    "apps.search",
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

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

# --- Database ---------------------------------------------------------------
# PostgreSQL is the target database. When DATABASE_URL is unset we fall back to
# SQLite so the project can be cloned and migrated without any services running.

DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Cache (Redis) ----------------------------------------------------------

REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# --- i18n / static ----------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- REST framework ---------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "1000/hour"},
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Fair Measure API",
    "DESCRIPTION": (
        "Build any competition you can describe: custom scoring categories, custom "
        "rules, dynamic fixtures, a points policy that drives the league table, and "
        "a social feed with photos and video."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SORT_OPERATIONS": False,
    # Several models each have a `status` or `kind` field with different
    # choices; naming them explicitly keeps the generated client readable.
    "ENUM_NAME_OVERRIDES": {
        "CompetitionStatusEnum": "apps.competitions.models.COMPETITION_STATUS_CHOICES",
        "CompetitionFormatEnum": "apps.competitions.models.COMPETITION_FORMAT_CHOICES",
        "StageKindEnum": "apps.competitions.models.STAGE_KIND_CHOICES",
        "FixtureStatusEnum": "apps.fixtures.models.FIXTURE_STATUS_CHOICES",
        "FixtureOutcomeEnum": "apps.fixtures.models.FIXTURE_OUTCOME_CHOICES",
        "MediaStatusEnum": "apps.media_assets.models.MEDIA_STATUS_CHOICES",
        "MediaKindEnum": "apps.media_assets.models.MEDIA_KIND_CHOICES",
        "ReactionKindEnum": "apps.social.models.REACTION_KIND_CHOICES",
    },
}

# --- JWT --------------------------------------------------------------------
# The realtime Node service verifies these tokens with the same key and
# algorithm, so keep JWT_SIGNING_KEY in sync across both services.

JWT_SIGNING_KEY = env("JWT_SIGNING_KEY") or SECRET_KEY

SIMPLE_JWT = {
    "ALGORITHM": "HS256",
    "SIGNING_KEY": JWT_SIGNING_KEY,
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_LIFETIME_MINUTES", 60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_LIFETIME_DAYS", 14)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET")

# --- CORS -------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:8100,http://localhost:4200"
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# --- Object storage ---------------------------------------------------------

STORAGE_PROVIDER = env("STORAGE_PROVIDER", "r2")  # r2 | s3
STORAGE_BUCKET = env("STORAGE_BUCKET", "fair-measure-media")
STORAGE_REGION = env("STORAGE_REGION", "auto")
STORAGE_ACCESS_KEY_ID = env("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = env("STORAGE_SECRET_ACCESS_KEY")
STORAGE_ENDPOINT_URL = env("STORAGE_ENDPOINT_URL")
STORAGE_PUBLIC_BASE_URL = env("STORAGE_PUBLIC_BASE_URL")
STORAGE_UPLOAD_URL_TTL_SECONDS = env_int("STORAGE_UPLOAD_URL_TTL_SECONDS", 900)
MAX_UPLOAD_BYTES = env_int("MAX_UPLOAD_BYTES", 512 * 1024 * 1024)

# --- Video ------------------------------------------------------------------

VIDEO_PROVIDER = env("VIDEO_PROVIDER", "cloudflare_stream")  # cloudflare_stream | mux
CLOUDFLARE_ACCOUNT_ID = env("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_STREAM_API_TOKEN = env("CLOUDFLARE_STREAM_API_TOKEN")
CLOUDFLARE_STREAM_WEBHOOK_SECRET = env("CLOUDFLARE_STREAM_WEBHOOK_SECRET")
MUX_TOKEN_ID = env("MUX_TOKEN_ID")
MUX_TOKEN_SECRET = env("MUX_TOKEN_SECRET")
MUX_WEBHOOK_SECRET = env("MUX_WEBHOOK_SECRET")

# --- Push notifications -----------------------------------------------------

FIREBASE_CREDENTIALS_FILE = env("FIREBASE_CREDENTIALS_FILE")
FIREBASE_CREDENTIALS_JSON = env("FIREBASE_CREDENTIALS_JSON")
FIREBASE_PROJECT_ID = env("FIREBASE_PROJECT_ID")

# --- Search -----------------------------------------------------------------

SEARCH_ENABLED = env_bool("SEARCH_ENABLED", False)
MEILISEARCH_URL = env("MEILISEARCH_URL", "http://localhost:7700")
MEILISEARCH_API_KEY = env("MEILISEARCH_API_KEY")

# --- Realtime / worker bridge ----------------------------------------------
# Django never talks to Socket.io or BullMQ directly. It pushes onto Redis and
# the Node service picks the work up. See apps/core/bus.py.

REALTIME_EVENT_CHANNEL = env("REALTIME_EVENT_CHANNEL", "fm:events")
JOB_INBOX_KEY = env("JOB_INBOX_KEY", "fm:jobs:inbox")
INTERNAL_API_TOKEN = env("INTERNAL_API_TOKEN")

# --- Logging ----------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": True},
    },
}
