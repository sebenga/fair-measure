"""The competition definition: what a contest is, how it scores, how it ranks.

Nothing here is sport-specific. A competition is described entirely by data:

* `ScoringCategory` rows define the ways a participant can score. The value of
  each action comes from the preset, not from the model.
* `PointsPolicy` defines how a finished fixture converts into league points and
  how ties are broken.
* `Rule` rows are free-text rules displayed to entrants.
* `Stage` allows a season to mix formats (a group phase then a knockout).

Because scoring and ranking are rows rather than code, every contest uses the
same model. The preset supplies the numbers.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, unique_slugify
from apps.core.permissions import Role


class Competition(BaseModel):
    class Format(models.TextChoices):
        LEAGUE = "league", _("League")
        KNOCKOUT = "knockout", _("Knockout")
        GROUP_KNOCKOUT = "group_knockout", _("Groups then knockout")
        LADDER = "ladder", _("Ladder")
        FREEFORM = "freeform", _("Freeform")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        ACTIVE = "active", _("Active")
        COMPLETED = "completed", _("Completed")
        ARCHIVED = "archived", _("Archived")

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    description = models.TextField(blank=True)
    # Free-text rather than a fixed enum: the platform should not have to ship a
    # release to support a sport nobody has invented yet.
    sport = models.CharField(
        max_length=80,
        blank=True,
        help_text=_("Free text: soccer, KPIs, cleaning, chess — whatever this contest is."),
    )
    logo_url = models.URLField(blank=True)
    banner_url = models.URLField(blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_competitions",
    )
    format = models.CharField(max_length=32, choices=Format.choices, default=Format.LEAGUE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)

    is_private = models.BooleanField(
        default=False, help_text=_("Private competitions are only visible to members.")
    )
    open_to_scouts = models.BooleanField(
        default=False,
        help_text=_(
            "Sport competitions only. Scouts can follow the league, its data feeds scouting "
            "reports, and it can name its own squad. Players still choose their own visibility."
        ),
    )
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    # Which weekdays fixtures are normally played on (0 = Monday).
    match_weekdays = models.JSONField(default=list, blank=True)
    settings_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "is_private"]),
            models.Index(fields=["sport"]),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class Membership(BaseModel):
    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=Role.CHOICES, default=Role.MEMBER)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_invites",
    )

    class Meta:
        ordering = ["role", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "user"], name="uniq_membership_per_competition"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} as {self.role} in {self.competition}"


class ScoringCategory(BaseModel):
    """One way to score, e.g. "Try" worth 5 or "Penalty" worth 3.

    Points are decimal and may be negative, which covers golf strokes, penalty
    deductions and fractional gymnastics scoring alongside whole-number sports.
    """

    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="scoring_categories"
    )
    name = models.CharField(max_length=120)
    code = models.SlugField(
        max_length=60, help_text=_("Short stable key used by clients, e.g. 'try'.")
    )
    description = models.TextField(blank=True)
    points = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    # Some events (a yellow card, a timeout) should be recorded without moving
    # the score. Keeping them here means the fixture timeline stays complete.
    affects_score = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    icon = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "scoring categories"
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "code"], name="uniq_scoring_code_per_competition"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.points})"


class Rule(BaseModel):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="rules")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "created_at"]

    def __str__(self) -> str:
        return self.name


class PointsPolicy(BaseModel):
    """How a completed fixture translates into league-table points."""

    class Tiebreaker(models.TextChoices):
        POINTS = "points", _("League points")
        SCORE_DIFFERENCE = "score_difference", _("Score difference")
        NET_SCORE_DIFFERENCE = "net_score_difference", _("Score difference without head-start goals")
        SCORE_FOR = "score_for", _("Score for")
        SCORE_AGAINST = "score_against", _("Score against (fewest first)")
        WINS = "wins", _("Wins")
        PLAYED = "played", _("Fewest played")
        HEAD_TO_HEAD = "head_to_head", _("Head to head")
        UNITS_DIFFERENCE = "units_difference", _("Units won difference")
        UNITS_FOR = "units_for", _("Units won")
        UNITS_RATIO = "units_ratio", _("Units won divided by units lost")
        SCORE_RATIO = "score_ratio", _("Score for divided by score against")
        RATE = "rate", _("Scoring rate minus the rate conceded")
        SONNEBORN_BERGER = "sonneborn_berger", _("Sum of defeated opponents' scores")
        BEST_SINGLE = "best_single", _("Best single result")
        NEXT_ATTEMPT = "next_attempt", _("Next-best attempt")
        RECENT = "recent", _("Most recent scoring activity")
        COUNTBACK = "countback", _("Countback from the last unit")
        SECONDS = "seconds", _("Second places")
        THIRDS = "thirds", _("Third places")
        PLACINGS = "placings", _("Wins, then seconds, then thirds")
        NAME = "name", _("Alphabetical")

    competition = models.OneToOneField(
        Competition, on_delete=models.CASCADE, related_name="points_policy"
    )
    win_points = models.DecimalField(max_digits=6, decimal_places=2, default=3)
    draw_points = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    loss_points = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    # Optional margin bonus; ignored when the thresholds are null.
    bonus_win_margin = models.PositiveIntegerField(
        null=True, blank=True, help_text=_("Award a bonus point for winning by this margin.")
    )
    bonus_win_points = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    bonus_loss_margin = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Award a bonus point for losing by this margin or fewer."),
    )
    bonus_loss_points = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    forfeit_points = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    # Applied in order; the first difference decides the position.
    tiebreakers = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Ordered list of Tiebreaker values, most significant first."),
    )
    allow_draws = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "points policies"

    def __str__(self) -> str:
        return f"Points policy for {self.competition}"

    @property
    def effective_tiebreakers(self) -> list[str]:
        valid = {choice.value for choice in self.Tiebreaker}
        ordered = [t for t in self.tiebreakers if t in valid or str(t).startswith("category:")]
        return ordered or [
            self.Tiebreaker.POINTS,
            self.Tiebreaker.SCORE_DIFFERENCE,
            self.Tiebreaker.SCORE_FOR,
            self.Tiebreaker.NAME,
        ]


class Stage(BaseModel):
    """A phase within a competition: a group, a season, a knockout round set."""

    class Kind(models.TextChoices):
        LEAGUE = "league", _("League")
        GROUP = "group", _("Group")
        KNOCKOUT = "knockout", _("Knockout")

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.LEAGUE)
    display_order = models.PositiveIntegerField(default=0)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    advances_count = models.PositiveIntegerField(
        default=0, help_text=_("How many participants progress from this stage.")
    )

    class Meta:
        ordering = ["display_order", "created_at"]

    def __str__(self) -> str:
        return f"{self.competition.name} — {self.name}"


class MatchUnit(BaseModel):
    """One block of a match, copied from the preset. The engine never names a sport."""

    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="match_units"
    )
    display_order = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=40)
    count = models.PositiveIntegerField(default=1)
    minutes = models.PositiveIntegerField(null=True, blank=True)
    best_of = models.PositiveIntegerField(null=True, blank=True)
    first_to = models.PositiveIntegerField(null=True, blank=True)
    win_by = models.PositiveIntegerField(null=True, blank=True)
    tiebreak_at = models.PositiveIntegerField(null=True, blank=True)
    affects_total = models.BooleanField(default=True)
    resolves_draw = models.BooleanField(default=False)

    class Meta:
        ordering = ["display_order", "created_at"]

    def __str__(self) -> str:
        return self.unit


class Participant(BaseModel):
    """A team, an individual, a pair — whatever competes.

    A team profile is made of people who hold the Member role in the league.
    """

    class Kind(models.TextChoices):
        INDIVIDUAL = "individual", _("Player")
        TEAM = "team", _("Team")

    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="participants"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.INDIVIDUAL)
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    # Optional: links a participant to a real account so they get notifications.
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_participants",
    )
    stages = models.ManyToManyField(Stage, blank=True, related_name="participants")
    seed = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "name"], name="uniq_participant_name_per_competition"
            )
        ]

    def __str__(self) -> str:
        return self.name


# Module-level aliases so drf-spectacular's ENUM_NAME_OVERRIDES can import them;
# it resolves dotted paths and cannot reach an attribute of a nested class.
COMPETITION_STATUS_CHOICES = Competition.Status.choices
COMPETITION_FORMAT_CHOICES = Competition.Format.choices
STAGE_KIND_CHOICES = Stage.Kind.choices


class TeamPick(BaseModel):
    """A profile invited onto a team. They join the roster only after they accept."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting for the player")
        ACCEPTED = "accepted", _("Accepted")
        DECLINED = "declined", _("Declined")

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="picks")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_picks"
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_picks_sent",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "user"],
                condition=models.Q(status="pending"),
                name="unique_pending_pick_per_team",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} → {self.participant_id} ({self.status})"


class RosterMember(BaseModel):
    """An individual within a participant, so events can name a scorer."""

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="roster")
    name = models.CharField(max_length=160)
    number = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    position = models.CharField(max_length=60, blank=True)
    handicap = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text=_("Playing handicap, where the competition's preset uses one."),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roster_entries",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["number", "name"]

    def __str__(self) -> str:
        return self.name
