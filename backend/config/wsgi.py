import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()

_log = logging.getLogger("config.wsgi")


def _seed_if_empty() -> None:
    """First boot on Render has an empty SQLite file unless we seed it."""
    try:
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        if get_user_model().objects.exists():
            return
        _log.info("No users yet — running seed_demo")
        call_command("seed_demo")
    except Exception:
        _log.exception("seed_demo skipped")


if os.environ.get("RENDER"):
    _seed_if_empty()
