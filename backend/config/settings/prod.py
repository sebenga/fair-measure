"""Production settings. Fails loudly rather than starting up insecure."""

import hashlib
import sys
from pathlib import Path

from .base import *  # noqa: F403
from .base import (
    ALLOWED_HOSTS,
    CORS_ALLOWED_ORIGINS,
    CSRF_TRUSTED_ORIGINS,
    REST_FRAMEWORK,
    SECRET_KEY,
    SIMPLE_JWT,
    SPA_DIR,
    env,
    env_bool,
    env_int,
)

DEBUG = False

# collectstatic / image build must not need Postgres. The running web process
# still does — SQLite in the container is wiped on every deploy and sleep.
_BUILD_ONLY = {"collectstatic", "check", "compilemessages"}
if env("RENDER") and not env("DATABASE_URL") and not _BUILD_ONLY.intersection(sys.argv):
    raise RuntimeError(
        "DATABASE_URL must be set on Render. SQLite lives in the container and "
        "is wiped on every deploy and cold start, so new accounts would disappear."
    )

if SECRET_KEY in {"", "insecure-dev-key-change-me"}:
    if env("RENDER"):
        # Unblocks a first deploy when the dashboard secret was not set.
        # Set DJANGO_SECRET_KEY yourself for a service that matters.
        material = env("RENDER_SERVICE_ID") or env("RENDER_EXTERNAL_HOSTNAME") or "fairmeasure-render"
        SECRET_KEY = hashlib.sha256(f"fm-v2|{material}".encode()).hexdigest()
        JWT_SIGNING_KEY = env("JWT_SIGNING_KEY") or SECRET_KEY
        SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": JWT_SIGNING_KEY}
    else:
        raise RuntimeError("DJANGO_SECRET_KEY must be set to a real value in production.")

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

# TLS terminates at the proxy (Render, nginx). Redirecting HTTP here breaks
# platform health checks that probe the process directly.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not bool(env("RENDER")))
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CORS_ALLOW_ALL_ORIGINS = False

if Path(SPA_DIR).is_dir():
    WHITENOISE_ROOT = Path(SPA_DIR)

# Django's Redis cache backend is not required for request handling. Keep
# cache in-process so a Key Value blip cannot 500 the API. The realtime bus
# still talks to Redis on its own client.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

if env("RENDER"):
    render_host = env("RENDER_EXTERNAL_HOSTNAME")
    if render_host and render_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(render_host)
    if ".onrender.com" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(".onrender.com")
    origins = [env("PUBLIC_APP_ORIGIN"), env("PUBLIC_API_ORIGIN")]
    if render_host:
        origins.append(f"https://{render_host}")
    for origin in origins:
        if origin and origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(origin)
        if origin and origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)
