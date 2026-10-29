"""Test settings: no external services required."""

import dj_database_url

from .base import *  # noqa: F403
from .base import BASE_DIR, REST_FRAMEWORK, SIMPLE_JWT, SQLITE_LIKE_POSTGRES, env

DEBUG = False
ALLOWED_HOSTS = ["*"]

# HS256 wants at least 32 bytes. Tests shouldn't depend on whatever happens to
# be in the developer's .env, so pin a key that is long enough here.
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": "fair-measure-test-signing-key-not-a-secret"}

# SQLite ignores varchar lengths and serialises writes, so it hides bugs that
# Postgres (production) raises. Set TEST_DATABASE_URL to run against Postgres.
if env("TEST_DATABASE_URL"):
    DATABASES = {"default": dj_database_url.parse(env("TEST_DATABASE_URL"))}
else:
    DATABASES = {"default": {"ENGINE": SQLITE_LIKE_POSTGRES, "NAME": BASE_DIR / "test.sqlite3"}}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"anon": "10000/min", "user": "10000/min", "auth": "10000/min"},
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

SEARCH_ENABLED = False
