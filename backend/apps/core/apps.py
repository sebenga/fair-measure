import logging

from django.apps import AppConfig
from django.db import models
from django.db.models.signals import pre_save

logger = logging.getLogger("apps.core.fit")


def fit_char_fields(instance) -> None:
    """Trim server-built text (labels like "Home v Away") to the column size.

    SQLite stores over-long strings; Postgres rejects them with a 500. User input
    is already length-checked by serializers. Unique columns are left alone so
    an over-long key still fails loudly instead of colliding.
    """

    for field in instance._meta.concrete_fields:
        if not isinstance(field, models.CharField) or field.unique or not field.max_length:
            continue
        value = getattr(instance, field.attname, None)
        if isinstance(value, str) and len(value) > field.max_length:
            logger.warning(
                "Trimmed %s.%s from %s to %s characters",
                type(instance).__name__,
                field.name,
                len(value),
                field.max_length,
            )
            setattr(instance, field.attname, value[: field.max_length])


def _fit_before_save(sender, instance, raw=False, **kwargs) -> None:
    if not raw:
        fit_char_fields(instance)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self) -> None:
        pre_save.connect(_fit_before_save, dispatch_uid="fm-fit-char-fields")
