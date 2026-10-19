"""Local development settings."""

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, STORAGE_ACCESS_KEY_ID, env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = ["*"]

# Let the API be browsed from a browser session during development.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}

CORS_ALLOW_ALL_ORIGINS = True

# Without object-storage credentials, keep photo and video uploads on local disk.
LOCAL_MEDIA_UPLOADS = env_bool("LOCAL_MEDIA_UPLOADS", not STORAGE_ACCESS_KEY_ID)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
