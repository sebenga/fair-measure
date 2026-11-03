from django.apps import AppConfig


class ReleasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.releases"
    verbose_name = "Platform releases"

    def ready(self) -> None:
        from django.db.models.signals import post_delete, post_save

        from .models import Release
        from .services import forget

        post_save.connect(lambda **_: forget(), sender=Release, weak=False)
        post_delete.connect(lambda **_: forget(), sender=Release, weak=False)
