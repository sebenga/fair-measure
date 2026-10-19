from django.apps import AppConfig


class GamesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.games"
    verbose_name = "Multi-sport Games"

    def ready(self) -> None:
        from . import signals  # noqa: F401
