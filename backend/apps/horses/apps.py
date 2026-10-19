from django.apps import AppConfig


class HorsesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.horses"
    verbose_name = "Horse registry"
