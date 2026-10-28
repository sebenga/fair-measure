"""Commercial placements and partnership enquiries for the public landing page."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Placement(BaseModel):
    class Audience(models.TextChoices):
        CORPORATE = "corporate", _("Corporate")
        GOVERNMENT = "government", _("Government")
        GENERAL = "general", _("General")

    class Slot(models.TextChoices):
        FEATURE = "feature", _("Feature card")
        BANNER = "banner", _("Commercial banner")
        LOGO = "logo", _("Sponsor logo")

    audience = models.CharField(max_length=20, choices=Audience.choices)
    slot = models.CharField(max_length=16, choices=Slot.choices, default=Slot.FEATURE)
    name = models.CharField(max_length=160)
    tagline = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.URLField(blank=True)
    logo_url = models.URLField(blank=True)
    active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        indexes = [
            models.Index(fields=["active", "audience", "slot"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.audience}/{self.slot})"


class Enquiry(BaseModel):
    class Audience(models.TextChoices):
        CORPORATE = "corporate", _("Corporate")
        GOVERNMENT = "government", _("Government")

    audience = models.CharField(max_length=20, choices=Audience.choices)
    organisation = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=160)
    email = models.EmailField()
    message = models.TextField()

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self) -> str:
        return f"{self.organisation} · {self.audience}"
