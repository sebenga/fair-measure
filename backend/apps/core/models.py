"""Abstract base models used across every app."""

from __future__ import annotations

import uuid

from django.db import models
from django.utils.text import slugify


class UUIDModel(models.Model):
    """Public-facing IDs are UUIDs so they are safe to expose and hard to enumerate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self) -> SoftDeleteQuerySet:
        return self.filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    """Content that users can delete without us losing the audit trail."""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        from django.utils import timezone

        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])


def unique_slugify(instance: models.Model, value: str, field_name: str = "slug") -> str:
    """Slugify `value`, appending a counter until it is unique for the model."""

    base = slugify(value)[:220] or "item"
    model = instance.__class__
    candidate = base
    counter = 2
    while (
        model._default_manager.filter(**{field_name: candidate})
        .exclude(pk=instance.pk)
        .exists()
    ):
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate
