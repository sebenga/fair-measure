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
    school_or_club = models.CharField(max_length=160, blank=True)
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
