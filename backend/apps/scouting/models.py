"""Talent scouting: player profiles, platform roles and consent.

Scouting roles are platform-level and sit alongside competition membership
roles (owner/admin/scorer/member); they never replace them. Every
sport-specific value (sport keys, positions, measurement kinds, regions) is
checked against `catalog.py`, never hard-coded here.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Organisation(BaseModel):
    """A club, academy, school or agency that employs scouts."""

    class Kind(models.TextChoices):
        CLUB = "club", _("Club")
        ACADEMY = "academy", _("Academy")
        SCHOOL = "school", _("School")
        AGENCY = "agency", _("Agency")

    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.CLUB)
    region = models.CharField(max_length=40, blank=True)
    logo_url = models.URLField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="scouting_organisations_created",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ScoutingRole(BaseModel):
    """A platform-level scouting role. A person can hold several."""

    class Role(models.TextChoices):
        PLAYER = "player", _("Player")
        GUARDIAN = "guardian", _("Guardian")
        SCOUT = "scout", _("Scout")
        SCOUT_ADMIN = "scout_admin", _("Scout admin")
        COACH = "coach", _("Coach")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scouting_roles"
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="roles",
        help_text=_("Required for scouts and scout admins."),
    )
    # A coach is tied to the team (competition entrant) they coach.
    team = models.ForeignKey(
        "competitions.Participant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="coaches",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scouting_roles_granted",
    )

    class Meta:
        ordering = ["role", "created_at"]

    def __str__(self) -> str:
        return f"{self.user_id} {self.role}"


class PlayerProfile(BaseModel):
    """What a player chooses to show scouts. Contact details are never stored here."""

    class Visibility(models.TextChoices):
        PRIVATE = "private", _("Only me (and my guardian)")
        SCOUTS = "scouts", _("Scouts only")
        PUBLIC = "public", _("Public")

    class Availability(models.TextChoices):
        AVAILABLE = "available", _("Available")
        LIMITED = "limited", _("Limited availability")
        UNAVAILABLE = "unavailable", _("Not available")
        INJURED = "injured", _("Injured")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="player_profile"
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    photo_url = models.URLField(blank=True, max_length=600)
    photo = models.ForeignKey(
        "media_assets.MediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender_category = models.CharField(max_length=12, blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    region = models.CharField(max_length=40, blank=True)
    # Kept in sync with `teams` so list cards can show a short label without extra joins.
    school_or_club = models.CharField(max_length=160, blank=True)
    teams = models.ManyToManyField(
        "competitions.Participant",
        blank=True,
        related_name="player_profiles",
        help_text=_(
            "School or club sides this player lists. One profile can sit on several competitions."
        ),
    )
    bio = models.TextField(blank=True)
    availability = models.CharField(
        max_length=12, choices=Availability.choices, default=Availability.AVAILABLE
    )
    availability_note = models.CharField(max_length=200, blank=True)
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PRIVATE
    )

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)


class PlayerSport(BaseModel):
    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name="sports")
    sport = models.CharField(max_length=40)
    primary_position = models.CharField(max_length=40, blank=True)
    secondary_positions = models.JSONField(default=list, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_primary", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "sport"], name="uniq_profile_sport")
        ]


class Measurement(BaseModel):
    """One dated body measurement. Rows are kept, so the history is visible."""

    class Source(models.TextChoices):
        SELF = "self", _("Self-reported")
        COACH = "coach", _("Coach")
        OFFICIAL = "official", _("Official")

    profile = models.ForeignKey(
        PlayerProfile, on_delete=models.CASCADE, related_name="measurements"
    )
    kind = models.CharField(max_length=24)
    value = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    text_value = models.CharField(max_length=40, blank=True)
    unit = models.CharField(max_length=12, blank=True)
    measured_on = models.DateField()
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.SELF)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["kind", "-measured_on", "-created_at"]

    @property
    def is_verified(self) -> bool:
        return self.source != self.Source.SELF and self.verified_by_id is not None


class InjuryRecord(BaseModel):
    """Private by default: only the player and guardians see it unless shared."""

    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name="injuries")
    description = models.CharField(max_length=200)
    injured_on = models.DateField(null=True, blank=True)
    recovered_on = models.DateField(null=True, blank=True)
    shared_with_scouts = models.BooleanField(default=False)

    class Meta:
        ordering = ["-injured_on", "-created_at"]


class HighlightVideo(BaseModel):
    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name="videos")
    title = models.CharField(max_length=160)
    url = models.URLField(blank=True, max_length=600)
    media_asset = models.ForeignKey(
        "media_assets.MediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]


class GuardianLink(BaseModel):
    """A parent or legal guardian of a player under the age of consent."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting for the guardian")
        ACTIVE = "active", _("Active")
        REVOKED = "revoked", _("Removed")

    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name="guardians")
    guardian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="guardian_links",
    )
    invited_email = models.EmailField()
    relationship = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ["-created_at"]


class ConsentRecord(BaseModel):
    """Append-only audit of every consent decision: who, when and what was shared."""

    class Action(models.TextChoices):
        GRANTED = "granted", _("Granted")
        REVOKED = "revoked", _("Revoked")

    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name="consents")
    given_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    given_as = models.CharField(max_length=12, help_text=_("guardian or player"))
    action = models.CharField(max_length=10, choices=Action.choices)
    # The highest visibility agreed to, and which sections may be shown.
    visibility = models.CharField(max_length=10, blank=True)
    sections = models.JSONField(default=list, blank=True)
    note = models.CharField(max_length=280, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Consent records are an audit trail and cannot be changed.")
        super().save(*args, **kwargs)


class LeagueSquad(BaseModel):
    """A national-team style selection of the best players in one competition.

    Selectors are the competition's owner and admins. Drafts are theirs alone;
    a published squad is visible to anyone who can see the competition.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")

    competition = models.OneToOneField(
        "competitions.Competition", on_delete=models.CASCADE, related_name="league_squad"
    )
    name = models.CharField(max_length=120, blank=True)
    size = models.PositiveIntegerField(default=23)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    # Players a selector dropped; regenerating never brings them back.
    excluded_users = models.JSONField(default=list, blank=True)
    # Players already told they were selected, so republishing does not repeat it.
    notified_users = models.JSONField(default=list, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="league_squads_selected",
    )

    def __str__(self) -> str:
        return self.name or f"Squad for {self.competition_id}"


class SquadPick(BaseModel):
    """One player in a league squad, with the evidence the pick was made on."""

    squad = models.ForeignKey(LeagueSquad, on_delete=models.CASCADE, related_name="picks")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    roster_member = models.ForeignKey(
        "competitions.RosterMember", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    group_key = models.CharField(max_length=40)
    position_label = models.CharField(max_length=80, blank=True)
    score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    # A snapshot of the numbers behind the pick, so the squad explains itself later.
    evidence = models.JSONField(default=dict, blank=True)
    # Picked by hand: regenerating keeps a locked pick where it is.
    locked = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "-score"]
        constraints = [
            models.UniqueConstraint(fields=["squad", "user"], name="uniq_player_per_squad")
        ]


class ReportExport(BaseModel):
    """Every exported report is logged: who exported what, and when."""

    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    kind = models.CharField(max_length=30)
    profile = models.ForeignKey(
        PlayerProfile, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    competition = models.ForeignKey(
        "competitions.Competition",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    access = models.CharField(max_length=12, blank=True)
    # What else identifies the report: compared profiles, a shortlist, an organisation.
    params = models.JSONField(default=dict, blank=True)
    file_format = models.CharField(max_length=8, default="screen")

    class Meta:
        ordering = ["-created_at"]


class LeagueScout(BaseModel):
    """A scout attached to one league that is open to scouts.

    The league's owner or admins add them. A league scout follows the league and
    helps pick its squad, alongside the league's own admins.
    """

    competition = models.ForeignKey(
        "competitions.Competition", on_delete=models.CASCADE, related_name="league_scouts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scouted_leagues"
    )
    organisation = models.ForeignKey(
        Organisation, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["competition", "user"], name="uniq_scout_per_league")
        ]


class PhysicalTestResult(BaseModel):
    """One physical test result, e.g. a 40 m sprint. Rows are kept for the trend."""

    class Source(models.TextChoices):
        SELF = "self", _("Self-reported")
        COACH = "coach", _("Coach")
        OFFICIAL = "official", _("Official")

    profile = models.ForeignKey(
        PlayerProfile, on_delete=models.CASCADE, related_name="test_results"
    )
    sport = models.CharField(max_length=40)
    test_key = models.CharField(max_length=40)
    value = models.DecimalField(max_digits=9, decimal_places=3)
    unit = models.CharField(max_length=16)
    tested_on = models.DateField()
    venue = models.CharField(max_length=160, blank=True)
    note = models.CharField(max_length=240, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.SELF)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["sport", "test_key", "-tested_on", "-created_at"]
        indexes = [models.Index(fields=["sport", "test_key"])]

    @property
    def is_verified(self) -> bool:
        return self.source != self.Source.SELF and self.verified_by_id is not None


class PlayerStatLine(BaseModel):
    """Cached match stats for one player in one sport, season and competition.

    ``competition`` is null for the player's whole season in that sport. Built by
    the stats job after each completed fixture; never edited by hand.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stat_lines"
    )
    sport = models.CharField(max_length=40)
    season = models.PositiveIntegerField()
    competition = models.ForeignKey(
        "competitions.Competition",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="stat_lines",
    )
    matches = models.PositiveIntegerField(default=0)
    minutes = models.PositiveIntegerField(default=0)
    values = models.JSONField(default=dict, blank=True)
    computed_at = models.DateTimeField()

    class Meta:
        ordering = ["-season", "sport"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "sport", "season", "competition"],
                name="uniq_stat_line",
                nulls_distinct=False,
            )
        ]
        indexes = [models.Index(fields=["sport", "season"])]


class ScoutRating(BaseModel):
    """One scout's dated rating of a player. Never edited, so progress shows over time.

    ``client_id`` is made on the scout's phone, so a rating saved offline and sent
    twice while syncing is still stored once.
    """

    class Mode(models.TextChoices):
        QUICK = "quick", _("Quick: the five areas")
        FULL = "full", _("Full: every attribute")

    client_id = models.UUIDField(unique=True)
    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name="ratings")
    scout = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scout_ratings"
    )
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="ratings"
    )
    sport = models.CharField(max_length=40)
    position = models.CharField(max_length=40, blank=True)
    fixture = models.ForeignKey(
        "fixtures.Fixture", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    mode = models.CharField(max_length=6, choices=Mode.choices, default=Mode.QUICK)
    watched = models.CharField(max_length=6, default="live")
    confidence = models.CharField(max_length=6, default="medium")
    area_scores = models.JSONField(default=dict, blank=True)
    attribute_scores = models.JSONField(default=dict, blank=True)
    current_ability = models.PositiveSmallIntegerField(null=True, blank=True)
    potential = models.PositiveSmallIntegerField(null=True, blank=True)
    recommendation = models.CharField(max_length=12, blank=True)
    # Private to the scout's organisation; never shown to the player.
    notes = models.TextField(blank=True)
    clips = models.JSONField(default=list, blank=True)
    observed_at = models.DateTimeField()

    class Meta:
        ordering = ["-observed_at", "-created_at"]
        indexes = [models.Index(fields=["profile", "organisation", "observed_at"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Ratings are dated records and cannot be changed; add a new one.")
        super().save(*args, **kwargs)


class SavedSearch(BaseModel):
    """A scout's saved talent search; with alerts on, new matches are notified."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_searches"
    )
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    name = models.CharField(max_length=120)
    filters = models.JSONField(default=dict, blank=True)
    alerts = models.BooleanField(default=True)
    # Profiles already known to match, so an alert only names new ones.
    matched_ids = models.JSONField(default=list, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]


class Shortlist(BaseModel):
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="shortlists"
    )
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=280, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organisation", "name"], name="uniq_shortlist_name")
        ]


class ShortlistEntry(BaseModel):
    class Status(models.TextChoices):
        WATCHING = "watching", _("Watching")
        CONTACTED = "contacted", _("Contacted")
        TRIAL_BOOKED = "trial_booked", _("Trial booked")
        SIGNED = "signed", _("Signed")
        REJECTED = "rejected", _("Rejected")

    shortlist = models.ForeignKey(Shortlist, on_delete=models.CASCADE, related_name="entries")
    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.WATCHING)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["shortlist", "profile"], name="uniq_shortlist_entry")
        ]


class ShortlistComment(BaseModel):
    entry = models.ForeignKey(ShortlistEntry, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]


class ShortlistLog(BaseModel):
    """Append-only record of every shortlist change."""

    class Action(models.TextChoices):
        ADDED = "added", _("Added")
        REMOVED = "removed", _("Removed")
        STATUS = "status", _("Status changed")
        ASSIGNED = "assigned", _("Assigned")
        COMMENTED = "commented", _("Commented")
        CONTACTED = "contacted", _("Contact requested")

    shortlist = models.ForeignKey(Shortlist, on_delete=models.CASCADE, related_name="log")
    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name="+")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("The shortlist log is an audit trail and cannot be changed.")
        super().save(*args, **kwargs)


class ContactRequest(BaseModel):
    """A scout asking to get in touch. It goes to the player, or to their guardians if
    the player is under 18. Contact details are never shared by the platform."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting for an answer")
        ACCEPTED = "accepted", _("Accepted")
        DECLINED = "declined", _("Declined")
        WITHDRAWN = "withdrawn", _("Withdrawn")

    profile = models.ForeignKey(
        PlayerProfile, on_delete=models.CASCADE, related_name="contact_requests"
    )
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="contact_requests"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    message = models.TextField()
    to_guardian = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    response = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
