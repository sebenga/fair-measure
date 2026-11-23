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


class CompanyLegalDetails(BaseModel):
    """Singleton site-wide company identity for legal footers and ECTA disclosures."""

    product = models.CharField(max_length=120, default="Fair Measure", blank=True)
    legal_name = models.CharField(max_length=255, blank=True, default="")
    trading_name = models.CharField(max_length=255, blank=True, default="")
    registration_number = models.CharField(max_length=32, blank=True, default="")
    vat_number = models.CharField(max_length=20, blank=True, default="")
    directors = models.JSONField(default=list, blank=True)
    physical_address = models.JSONField(default=dict, blank=True)
    postal_address = models.JSONField(default=dict, blank=True)
    postal_same_as_physical = models.BooleanField(default=True)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    website = models.URLField(blank=True, default="https://fairmeasure-v2.onrender.com")
    information_officer_name = models.CharField(max_length=255, blank=True, default="")
    information_officer_email = models.EmailField(blank=True, default="")
    privacy_policy_effective_date = models.DateField(null=True, blank=True)
    copyright_holder = models.CharField(max_length=255, blank=True, default="")
    copyright_start_year = models.PositiveIntegerField(default=2026)
    trademarks = models.JSONField(default=list, blank=True)
    terms_effective_date = models.DateField(null=True, blank=True)
    governing_law = models.CharField(
        max_length=255, blank=True, default="Republic of South Africa"
    )

    class Meta:
        verbose_name = "Company legal details"
        verbose_name_plural = "Company legal details"

    def __str__(self) -> str:
        return self.legal_name or self.product or "Company legal details"

    @classmethod
    def get_solo(cls) -> CompanyLegalDetails:
        existing = cls.objects.order_by("created_at").first()
        if existing is not None:
            return existing
        return cls.objects.create(
            product="Fair Measure",
            website="https://fairmeasure-v2.onrender.com",
            copyright_start_year=2026,
            governing_law="Republic of South Africa",
            postal_same_as_physical=True,
            directors=[],
            physical_address={},
            postal_address={},
            trademarks=[],
        )

    # Alias used by callers that prefer load().
    load = get_solo
