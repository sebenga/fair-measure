"""Officials, result sheets and the audit trail for performance-based results.

A result sheet holds what happened to each entrant in one event (a placing, a
faults-and-time round, judges' marks, phase penalties, vet gates or runs). How
that becomes a ranking is decided by the competition's preset data, through
`calculators.py`. Nothing here names a sport.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class CompetitionOfficial(BaseModel):
    """A steward, judge, ground jury member, umpire or vet for one competition.

    In competitions whose preset says results are official, only these people can
    finalise or amend a result, disqualify an entrant or record a vet elimination.
    """

    class Title(models.TextChoices):
        STEWARD = "steward", _("Steward")
        JUDGE = "judge", _("Judge")
        GROUND_JURY = "ground_jury", _("Ground jury")
        UMPIRE = "umpire", _("Umpire")
        REFEREE = "referee", _("Referee")
        VET = "vet", _("Veterinary official")
        TECHNICAL_DELEGATE = "technical_delegate", _("Technical delegate")

    competition = models.ForeignKey(
        "competitions.Competition", on_delete=models.CASCADE, related_name="officials"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="officiating"
    )
    title = models.CharField(max_length=24, choices=Title.choices, default=Title.STEWARD)
    appointed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["title", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "user", "title"], name="uniq_official_title"
            )
        ]


class ResultSheet(BaseModel):
    """Event-level settings (time allowed, judges, loop distances...) and finalisation."""

    fixture = models.OneToOneField(
        "fixtures.Fixture", on_delete=models.CASCADE, related_name="result_sheet"
    )
    config = models.JSONField(
        default=dict, blank=True, help_text=_("Overrides for this event, on top of the preset.")
    )
    finalised_at = models.DateTimeField(null=True, blank=True)
    finalised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    @property
    def is_final(self) -> bool:
        return self.finalised_at is not None


class EntryResult(BaseModel):
    """One entrant's raw inputs for one event, and what the engine made of them."""

    side = models.OneToOneField(
        "fixtures.FixtureSide", on_delete=models.CASCADE, related_name="entry_result"
    )
    data = models.JSONField(default=dict, blank=True)
    # Set by an official (EL, RT, WD, DNF, DQ ...). Overrides any calculated status.
    status = models.CharField(max_length=12, blank=True)
    status_reason = models.CharField(max_length=280, blank=True)
    # A welfare (vet) elimination can never be overridden in the app.
    welfare_locked = models.BooleanField(default=False)
    # Calculated from `data` by the preset's result type.
    computed_status = models.CharField(max_length=12, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    primary = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    breakdown = models.JSONField(default=dict, blank=True)

    @property
    def effective_status(self) -> str:
        return self.status or self.computed_status


class ResultAmendment(BaseModel):
    """Append-only record of every change to an official result, with its reason."""

    class Action(models.TextChoices):
        PROVISIONAL = "provisional", _("Provisional result saved")
        FINALISED = "finalised", _("Result finalised")
        AMENDED = "amended", _("Result amended")
        STATUS = "status", _("Status set")
        WELFARE = "welfare", _("Welfare elimination")
        REOPENED = "reopened", _("Result reopened")

    fixture = models.ForeignKey(
        "fixtures.Fixture", on_delete=models.CASCADE, related_name="result_amendments"
    )
    side = models.ForeignKey(
        "fixtures.FixtureSide",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    reason = models.CharField(max_length=500, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Result amendments are an audit trail and cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Result amendments are an audit trail and cannot be deleted.")
