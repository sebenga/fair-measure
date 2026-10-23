"""Production settings. Fails loudly rather than starting up insecure."""

from .base import *  # noqa: F403
from pathlib import Path

from .base import (
    ALLOWED_HOSTS,
    CORS_ALLOWED_ORIGINS,
    CSRF_TRUSTED_ORIGINS,
    REST_FRAMEWORK,
    SECRET_KEY,
    SPA_DIR,
    env,
    env_bool,
    env_int,
)

DEBUG = False

if SECRET_KEY in {"", "insecure-dev-key-change-me"}:
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
    for origin in (env("PUBLIC_APP_ORIGIN"), env("PUBLIC_API_ORIGIN")):
        if origin and origin not in CORS_ALLOWED_ORIGINS:
            CORS_ALLOWED_ORIGINS.append(origin)
        if origin and origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)
