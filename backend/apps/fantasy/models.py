"""A fantasy squad picked from a competition's real roster.

Each member builds their own team of rostered players. Points come from those
players' recorded match events — the same numbers the rest of the platform uses.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.competitions.models import Competition, RosterMember
from apps.core.models import BaseModel


class FantasySlot(models.TextChoices):
    GKP = "GKP", _("Goalkeeper")
    DEF = "DEF", _("Defender")
    MID = "MID", _("Midfielder")
    FWD = "FWD", _("Forward")


class FantasyTeam(BaseModel):
    """One manager's squad in one competition."""

    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="fantasy_teams"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fantasy_teams",
    )
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "user"], name="uniq_fantasy_team_per_manager"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.competition})"


class FantasyPick(BaseModel):
    """One rostered player in a fantasy squad, with their shirt slot and role."""

    team = models.ForeignKey(FantasyTeam, on_delete=models.CASCADE, related_name="picks")
    player = models.ForeignKey(
        RosterMember, on_delete=models.CASCADE, related_name="fantasy_picks"
    )
    slot = models.CharField(max_length=3, choices=FantasySlot.choices)
    is_starter = models.BooleanField(default=True)
    is_captain = models.BooleanField(default=False)
    is_vice = models.BooleanField(default=False)
    bench_order = models.PositiveSmallIntegerField(default=0)
    price = models.DecimalField(max_digits=5, decimal_places=1)

    class Meta:
        ordering = ["slot", "bench_order", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["team", "player"], name="uniq_player_per_fantasy_team")
        ]

    def __str__(self) -> str:
        return f"{self.player} in {self.team}"


FANTASY_SLOT_CHOICES = FantasySlot.choices
