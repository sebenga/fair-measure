"""Multi-sport Games: NOCs, athletes, events and medals.

A Games groups many events. Each event owns one ordinary competition created from
a locked preset, so scoring, officials and the amendment log all come from the
existing engine. This app only knows who entered for which NOC, and turns each
event's confirmed result into medals.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Games(BaseModel):
    class Kind(models.TextChoices):
        SUMMER = "summer", _("Summer")
        WINTER = "winter", _("Winter")
        CUSTOM = "custom", _("Custom / local")

    class Ranking(models.TextChoices):
        GOLD_FIRST = "gold_first", _("Golds first (IOC standard)")
        TOTAL_FIRST = "total_first", _("Total medals first")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        LIVE = "live", _("Live")
        COMPLETED = "completed", _("Completed")

    name = models.CharField(max_length=160)
    edition = models.CharField(max_length=60, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.SUMMER)
    host = models.CharField(max_length=120, blank=True)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    logo_url = models.URLField(blank=True, max_length=600)
    # Chosen at creation and then locked, so the table never re-orders mid-Games.
    medal_table_ranking = models.CharField(
        max_length=12, choices=Ranking.choices, default=Ranking.GOLD_FIRST
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    is_private = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_games"
    )
    # Local games: what an "NOC" is called (house, school, province) and the points
    # each place earns towards the overall points table, e.g. [5, 3, 1].
    team_label = models.CharField(max_length=40, blank=True)
    placing_points = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-starts_on", "-created_at"]
        verbose_name_plural = "games"

    def __str__(self) -> str:
        return self.name


class GamesOfficial(BaseModel):
    """A technical delegate for the whole Games: added to every event's officials."""

    games = models.ForeignKey(Games, on_delete=models.CASCADE, related_name="officials")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["games", "user"], name="uniq_games_official")
        ]


class NOC(BaseModel):
    """A National Olympic Committee, or a house, school or province in a local Games."""

    games = models.ForeignKey(Games, on_delete=models.CASCADE, related_name="nocs")
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=3)
    flag_url = models.URLField(blank=True, max_length=600)
    colour = models.CharField(max_length=9, blank=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["games", "code"], name="uniq_noc_code_per_games")
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class Athlete(BaseModel):
    """An athlete, entered for exactly one NOC in a Games."""

    games = models.ForeignKey(Games, on_delete=models.CASCADE, related_name="athletes")
    noc = models.ForeignKey(NOC, on_delete=models.CASCADE, related_name="athletes")
    name = models.CharField(max_length=160)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="games_entries",
    )
    # Marks from before the Games: [{"event": "100 m", "mark": "9.85", "date": "2026-06-01"}].
    personal_bests = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["games", "user"],
                condition=models.Q(user__isnull=False),
                name="uniq_athlete_profile_per_games",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.noc.code})"


class GamesEvent(BaseModel):
    """One medal event, e.g. "Athletics, Men's 100 m". It owns a competition."""

    class Gender(models.TextChoices):
        MEN = "men", _("Men")
        WOMEN = "women", _("Women")
        MIXED = "mixed", _("Mixed")
        OPEN = "open", _("Open")

    class Kind(models.TextChoices):
        INDIVIDUAL = "individual", _("Individual")
        TEAM = "team", _("Team")

    class MedalType(models.TextChoices):
        STANDARD = "standard", _("Gold, silver, bronze")
        BRONZE_MATCH = "bronze_match", _("Bronze decided by a bronze-medal match")
        TWO_BRONZE = "two_bronze", _("Two bronzes (both losing semi-finalists)")

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", _("Scheduled")
        IN_PROGRESS = "in_progress", _("In progress")
        MEDALS_AWARDED = "medals_awarded", _("Medals awarded")

    games = models.ForeignKey(Games, on_delete=models.CASCADE, related_name="events")
    sport_key = models.CharField(max_length=60)
    sport_label = models.CharField(max_length=120)
    discipline = models.CharField(max_length=120, blank=True)
    name = models.CharField(max_length=160)
    gender = models.CharField(max_length=6, choices=Gender.choices, default=Gender.OPEN)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.INDIVIDUAL)
    venue = models.CharField(max_length=160, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    preset_key = models.CharField(max_length=60)
    round_format = models.CharField(max_length=40, blank=True)
    medal_type = models.CharField(
        max_length=14, choices=MedalType.choices, default=MedalType.STANDARD
    )
    custom = models.BooleanField(default=False, help_text=_("Not from the Olympic catalogue."))
    competition = models.OneToOneField(
        "competitions.Competition", on_delete=models.PROTECT, related_name="games_event"
    )
    # Which fixture decides the medals, when it is not the obvious one.
    final_fixture = models.ForeignKey(
        "fixtures.Fixture", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    bronze_fixture = models.ForeignKey(
        "fixtures.Fixture", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    display_order = models.PositiveIntegerField(default=0)
    # How entrants go through, e.g. "First 3 in each heat (Q) and the next 2 fastest (q)",
    # and the qualifying standard, e.g. "10.05".
    qualification_rule = models.CharField(max_length=240, blank=True)
    qualification_mark = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["display_order", "scheduled_at", "sport_label", "name"]

    def __str__(self) -> str:
        return f"{self.sport_label}: {self.name}"


class Entry(BaseModel):
    """Who a competition entrant is in Games terms: an NOC, and the athlete if individual."""

    event = models.ForeignKey(GamesEvent, on_delete=models.CASCADE, related_name="entries")
    participant = models.OneToOneField(
        "competitions.Participant", on_delete=models.CASCADE, related_name="games_entry"
    )
    noc = models.ForeignKey(NOC, on_delete=models.CASCADE, related_name="entries")
    athlete = models.ForeignKey(
        Athlete, on_delete=models.CASCADE, null=True, blank=True, related_name="entries"
    )


class Medal(BaseModel):
    class Kind(models.TextChoices):
        GOLD = "gold", _("Gold")
        SILVER = "silver", _("Silver")
        BRONZE = "bronze", _("Bronze")

    event = models.ForeignKey(GamesEvent, on_delete=models.CASCADE, related_name="medals")
    noc = models.ForeignKey(NOC, on_delete=models.CASCADE, related_name="medals")
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name="medals")
    medal = models.CharField(max_length=6, choices=Kind.choices)
    rank = models.PositiveIntegerField()

    class Meta:
        ordering = ["event", "rank"]


class MedalChange(BaseModel):
    """Append-only log of every award and reallocation of an event's medals."""

    event = models.ForeignKey(GamesEvent, on_delete=models.CASCADE, related_name="medal_changes")
    reason = models.CharField(max_length=500, blank=True)
    before = models.JSONField(default=list, blank=True)
    after = models.JSONField(default=list, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Medal changes are an audit trail and cannot be changed.")
        super().save(*args, **kwargs)


class GamesRecord(BaseModel):
    """A record set at the Games (Games, national, world), kept as data."""

    class Scope(models.TextChoices):
        GAMES = "games", _("Games record")
        NATIONAL = "national", _("National record")
        WORLD = "world", _("World record")

    games = models.ForeignKey(Games, on_delete=models.CASCADE, related_name="records")
    event = models.ForeignKey(GamesEvent, on_delete=models.CASCADE, related_name="records")
    scope = models.CharField(max_length=10, choices=Scope.choices)
    mark = models.CharField(max_length=40)
    previous_mark = models.CharField(max_length=40, blank=True)
    holder = models.CharField(max_length=160)
    noc = models.ForeignKey(NOC, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    athlete = models.ForeignKey(
        Athlete, on_delete=models.SET_NULL, null=True, blank=True, related_name="records"
    )
    set_on = models.DateField(null=True, blank=True)
    note = models.CharField(max_length=240, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]


class GamesFollow(BaseModel):
    """A user following an NOC, a sport or an athlete for start-time and result alerts."""

    class Target(models.TextChoices):
        NOC = "noc", _("NOC")
        SPORT = "sport", _("Sport")
        ATHLETE = "athlete", _("Athlete")

    games = models.ForeignKey(Games, on_delete=models.CASCADE, related_name="follows")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="games_follows"
    )
    target = models.CharField(max_length=8, choices=Target.choices)
    noc = models.ForeignKey(NOC, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    athlete = models.ForeignKey(
        Athlete, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    sport_key = models.CharField(max_length=60, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["games", "user", "target", "noc", "athlete", "sport_key"],
                name="uniq_games_follow",
                nulls_distinct=False,
            )
        ]


class GamesAlert(BaseModel):
    """One alert already sent, so a start-time or result alert never repeats."""

    class Kind(models.TextChoices):
        START = "start", _("Start time")
        RESULT = "result", _("Result")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey(GamesEvent, on_delete=models.CASCADE, related_name="alerts")
    kind = models.CharField(max_length=6, choices=Kind.choices)
    # A fixture id for start alerts, or the medal change id for result alerts.
    key = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event", "kind", "key"], name="uniq_games_alert"
            )
        ]
