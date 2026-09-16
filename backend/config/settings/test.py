"""Test settings: no external services required."""

from .base import *  # noqa: F403
from .base import BASE_DIR, SIMPLE_JWT

DEBUG = False

# HS256 wants at least 32 bytes. Tests shouldn't depend on whatever happens to
# be in the developer's .env, so pin a key that is long enough here.
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": "fair-measure-test-signing-key-not-a-secret"}

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test.sqlite3"}
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

SEARCH_ENABLED = False
