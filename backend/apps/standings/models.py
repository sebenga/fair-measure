from __future__ import annotations

from django.db import models

from apps.competitions.models import Competition, Participant, Stage
from apps.core.models import BaseModel


class StandingRow(BaseModel):
    """A cached league-table row.

    The table is always derivable from fixtures and the points policy, so this
    is a cache rather than a source of truth. It exists because reading a table
    is far more common than changing one, and mobile clients should not pay for
    the aggregation on every scroll.
    """

    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="standing_rows"
    )
    stage = models.ForeignKey(
        Stage, on_delete=models.CASCADE, null=True, blank=True, related_name="standing_rows"
    )
    participant = models.ForeignKey(
        Participant, on_delete=models.CASCADE, related_name="standing_rows"
    )

    position = models.PositiveIntegerField(default=0)
    played = models.PositiveIntegerField(default=0)
    wins = models.PositiveIntegerField(default=0)
    draws = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)
    score_for = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    score_against = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    score_difference = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    points = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus_points = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    form = models.JSONField(
        default=list, blank=True, help_text="Most recent results first, e.g. ['W','D','L']."
    )
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "stage", "participant"],
                name="uniq_standing_row",
                condition=models.Q(stage__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["competition", "participant"],
                name="uniq_standing_row_no_stage",
                condition=models.Q(stage__isnull=True),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.position}. {self.participant.name} — {self.points} pts"
