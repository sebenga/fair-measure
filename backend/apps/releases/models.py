"""Which sports and features the public can see.

The platform admin releases them one at a time. A row only exists once a
switch has been set; without a row the defaults in ``services`` apply.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Release(BaseModel):
    class Kind(models.TextChoices):
        SPORT = "sport", _("Sport or competition type")
        FEATURE = "feature", _("Feature")

    kind = models.CharField(max_length=16, choices=Kind.choices)
    key = models.CharField(max_length=80)
    live = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["kind", "key"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "key"], name="release_kind_key_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.key} ({'live' if self.live else 'hidden'})"
