from django.apps import AppConfig


class ScoutingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.scouting"
    verbose_name = "Talent scouting"

    def ready(self) -> None:
        from . import signals  # noqa: F401
