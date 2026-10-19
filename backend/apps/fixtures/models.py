"""Fixtures and the score events that decide them.

A fixture's score is never entered directly. It is the sum of its `ScoreEvent`
rows, each of which references a `ScoringCategory` belonging to the competition.
That indirection is what makes the platform sport-agnostic: every scoring
action is the same write, and correcting a mistake means deleting one event
rather than recalculating a total by hand.

`FixtureSide.score` is a denormalised cache of that sum. It is recomputed inside
the same transaction as any event change, so it can never drift.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Sum
from django.utils.translation import gettext_lazy as _

from apps.competitions.models import Competition, Participant, RosterMember, ScoringCategory, Stage
from apps.core.models import BaseModel


class Fixture(BaseModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", _("Scheduled")
        LIVE = "live", _("Live")
        COMPLETED = "completed", _("Completed")
        POSTPONED = "postponed", _("Postponed")
        CANCELLED = "cancelled", _("Cancelled")
        FORFEIT = "forfeit", _("Forfeit")

    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="fixtures"
    )
    stage = models.ForeignKey(
        Stage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fixtures",
    )
    round_number = models.PositiveIntegerField(null=True, blank=True)
    label = models.CharField(
        max_length=160, blank=True, help_text=_("e.g. 'Quarter-final 1' or 'Week 3'.")
    )
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # The game's time limit. A game cannot kick off without one.
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    # 0 means an admin removed overtime for this game.
    overtime_minutes = models.PositiveIntegerField(null=True, blank=True)
    location = models.CharField(max_length=240, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.SCHEDULED, db_index=True
    )
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_fixtures",
    )

    class Meta:
        ordering = ["scheduled_at", "created_at"]
        indexes = [
            models.Index(fields=["competition", "status"]),
            models.Index(fields=["competition", "scheduled_at"]),
        ]

    def __str__(self) -> str:
        names = " v ".join(side.participant.name for side in self.sides.all()[:4])
        return names or f"Fixture {self.id}"

    def save(self, *args, **kwargs) -> None:
        if self._state.adding and (self.duration_minutes is None or self.overtime_minutes is None):
            from apps.competitions.presets import default_game_time

            limit, overtime = default_game_time(self.competition.settings_json)
            if self.duration_minutes is None:
                self.duration_minutes = limit
            if self.overtime_minutes is None:
                self.overtime_minutes = overtime
        super().save(*args, **kwargs)

    def kickoff_problems(self) -> list[str]:
        """What still has to be set before this game can start."""

        problems = []
        if not self.duration_minutes:
            problems.append("Set this game's time limit before kickoff.")
        if not self.referees.exists():
            problems.append("Assign a referee before kickoff.")
        return problems

    @property
    def is_counted(self) -> bool:
        """Whether this fixture should affect the league table."""

        return self.status in {self.Status.COMPLETED, self.Status.FORFEIT}

    def recalculate_scores(self) -> None:
        """Recompute each side's cached score from its events, then resolve winners."""

        settings = self.competition.settings_json or {}
        if (settings.get("match_structure") or settings.get("win_condition")) and not (
            self.sides.filter(forfeited=True).exists()
        ):
            from apps.competitions.engine import settle_fixture

            settle_fixture(self)
            return

        totals = (
            ScoreEvent.objects.filter(fixture=self, scoring_category__affects_score=True)
            .values("side_id")
            .annotate(
                total=Sum(F("quantity") * F("scoring_category__points"), default=Decimal("0"))
            )
        )
        by_side = {row["side_id"]: row["total"] or Decimal("0") for row in totals}

        sides = list(self.sides.all())
        for side in sides:
            side.score = by_side.get(side.id, Decimal("0"))

        # Forfeits are decided by the flag, not by whatever was on the scoreboard.
        forfeiting = [side for side in sides if side.forfeited]
        if forfeiting:
            for side in sides:
                side.outcome = (
                    FixtureSide.Outcome.LOSS if side.forfeited else FixtureSide.Outcome.WIN
                )
        elif len(sides) >= 2:
            best = max(side.score for side in sides)
            winners = [side for side in sides if side.score == best]
            for side in sides:
                if len(winners) > 1:
                    side.outcome = (
                        FixtureSide.Outcome.DRAW
                        if side.score == best
                        else FixtureSide.Outcome.LOSS
                    )
                else:
                    side.outcome = (
                        FixtureSide.Outcome.WIN
                        if side.score == best
                        else FixtureSide.Outcome.LOSS
                    )
        else:
            for side in sides:
                side.outcome = FixtureSide.Outcome.PENDING

        FixtureSide.objects.bulk_update(sides, ["score", "outcome"])


class FixtureSide(BaseModel):
    """One participant's involvement in one fixture.

    Modelled as rows rather than home/away columns so the same table supports
    two-sided matches, a four-player golf group and a full-field race.
    """

    class Outcome(models.TextChoices):
        PENDING = "pending", _("Pending")
        WIN = "win", _("Win")
        DRAW = "draw", _("Draw")
        LOSS = "loss", _("Loss")

    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name="sides")
    participant = models.ForeignKey(
        Participant, on_delete=models.CASCADE, related_name="fixture_sides"
    )
    position = models.PositiveIntegerField(
        default=0, help_text=_("0 is the home side or first-listed competitor.")
    )
    is_home = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    outcome = models.CharField(
        max_length=10, choices=Outcome.choices, default=Outcome.PENDING
    )
    forfeited = models.BooleanField(default=False)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["fixture", "participant"], name="uniq_participant_per_fixture"
            )
        ]

    def __str__(self) -> str:
        return f"{self.participant.name}: {self.score}"


FIXTURE_STATUS_CHOICES = Fixture.Status.choices
FIXTURE_OUTCOME_CHOICES = FixtureSide.Outcome.choices


class ScoreEvent(BaseModel):
    """A single scoring occurrence, e.g. "Try, 62nd minute, scored by number 8"."""

    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name="events")
    side = models.ForeignKey(FixtureSide, on_delete=models.CASCADE, related_name="events")
    scoring_category = models.ForeignKey(
        ScoringCategory, on_delete=models.PROTECT, related_name="score_events"
    )
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    minute = models.PositiveIntegerField(null=True, blank=True)
    period = models.CharField(max_length=40, blank=True)
    # Which expanded match unit this event belongs to (0 = first half, first hole, …).
    unit_index = models.PositiveIntegerField(null=True, blank=True)
    player = models.ForeignKey(
        RosterMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="score_events",
    )
    player_name = models.CharField(
        max_length=160,
        blank=True,
        help_text=_("Free text for competitions that do not maintain rosters."),
    )
    note = models.CharField(max_length=280, blank=True)
    occurred_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_events",
    )

    class Meta:
        ordering = ["minute", "created_at"]
        indexes = [models.Index(fields=["fixture", "created_at"])]

    def __str__(self) -> str:
        return f"{self.scoring_category.name} x{self.quantity}"

    @property
    def points(self) -> Decimal:
        if not self.scoring_category.affects_score:
            return Decimal("0")
        return self.quantity * self.scoring_category.points


class PlayerMatchRating(BaseModel):
    """One rating for a roster profile in one fixture."""

    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name="ratings")
    player = models.ForeignKey(
        RosterMember, on_delete=models.CASCADE, related_name="match_ratings"
    )
    rating = models.DecimalField(max_digits=3, decimal_places=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fixture", "player"], name="unique_player_match_rating"
            )
        ]

    def __str__(self) -> str:
        return f"{self.player} {self.rating}"


class FixtureReferee(BaseModel):
    """A person allowed to run scoring for one fixture."""

    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name="referees")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referee_assignments"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["fixture", "user"], name="uniq_referee_per_fixture")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} referees {self.fixture_id}"
