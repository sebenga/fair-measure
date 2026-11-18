"""One-time Paystack payments that unlock competition visibility upgrades."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class VisibilityPayment(BaseModel):
    class Kind(models.TextChoices):
        PRIVATE = "private", _("Private competition")
        LANDING = "landing", _("Landing page placement")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        PAID = "paid", _("Paid")
        FAILED = "failed", _("Failed")
        ABANDONED = "abandoned", _("Abandoned")

    competition = models.ForeignKey(
        "competitions.Competition",
        on_delete=models.CASCADE,
        related_name="visibility_payments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="visibility_payments",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=8, default="ZAR")
    reference = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    authorization_url = models.URLField(blank=True)
    paystack_access_code = models.CharField(max_length=64, blank=True)
    paystack_transaction_id = models.CharField(max_length=64, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["competition", "kind", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.status} {self.reference}"
