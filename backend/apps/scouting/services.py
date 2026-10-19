"""Age rules, roles and the privacy decisions every scouting endpoint relies on."""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from . import catalog
from .models import (
    ConsentRecord,
    GuardianLink,
    Organisation,
    PlayerProfile,
    ScoutingRole,
)

VISIBILITY_RANK = {
    PlayerProfile.Visibility.PRIVATE: 0,
    PlayerProfile.Visibility.SCOUTS: 1,
    PlayerProfile.Visibility.PUBLIC: 2,
}

SCOUT_ROLES = {ScoutingRole.Role.SCOUT, ScoutingRole.Role.SCOUT_ADMIN}


# --- Age ---------------------------------------------------------------------


def today() -> date:
    return timezone.localdate()


def age_on(date_of_birth: date | None, on: date) -> int | None:
    if date_of_birth is None:
        return None
    years = on.year - date_of_birth.year
    if (on.month, on.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


def age_group(date_of_birth: date | None, on: date | None = None) -> dict | None:
    """Age groups use the age on 1 January of the season, the usual junior-sport cut-off."""

    if date_of_birth is None:
        return None
    reference = on or today()
    season_age = age_on(date_of_birth, date(reference.year, 1, 1))
    for group in catalog.AGE_GROUPS:
        if group["under"] is None or season_age < group["under"]:
            return {"key": group["key"], "label": group["label"]}
    return None


def is_minor(profile: PlayerProfile, on: date | None = None) -> bool:
    """Unknown age is treated as a minor: nothing is shown until we know."""

    age = age_on(profile.date_of_birth, on or today())
    return age is None or age < catalog.AGE_OF_CONSENT


# --- Roles -------------------------------------------------------------------


def roles_of(user) -> set[str]:
    if not user or not user.is_authenticated:
        return set()
    return set(ScoutingRole.objects.filter(user=user).values_list("role", flat=True))


def is_scout(user) -> bool:
    return bool(roles_of(user) & SCOUT_ROLES)


def scout_organisations(user) -> list[Organisation]:
    return list(
        Organisation.objects.filter(roles__user=user, roles__role__in=SCOUT_ROLES).distinct()
    )


def is_scout_admin_of(user, organisation: Organisation) -> bool:
    if user.is_staff:
        return True
    return ScoutingRole.objects.filter(
        user=user, organisation=organisation, role=ScoutingRole.Role.SCOUT_ADMIN
    ).exists()


def grant_role(user, role: str, *, organisation=None, team=None, granted_by=None) -> ScoutingRole:
    existing = ScoutingRole.objects.filter(
        user=user, role=role, organisation=organisation, team=team
    ).first()
    if existing:
        return existing
    return ScoutingRole.objects.create(
        user=user, role=role, organisation=organisation, team=team, granted_by=granted_by
    )


def coaches_player(user, profile: PlayerProfile) -> bool:
    """A coach of a team the player is on (an active roster member)."""

    if not user or not user.is_authenticated:
        return False
    from apps.competitions.models import RosterMember

    teams = ScoutingRole.objects.filter(
        user=user, role=ScoutingRole.Role.COACH, team__isnull=False
    ).values_list("team_id", flat=True)
    return RosterMember.objects.filter(
        participant_id__in=list(teams), user=profile.user, is_active=True
    ).exists()


# --- Consent and visibility --------------------------------------------------


def is_guardian_of(user, profile: PlayerProfile) -> bool:
    if not user or not user.is_authenticated:
        return False
    return GuardianLink.objects.filter(
        profile=profile, guardian=user, status=GuardianLink.Status.ACTIVE
    ).exists()


def active_consent(profile: PlayerProfile) -> ConsentRecord | None:
    """The latest guardian decision, if it is a grant from a still-active guardian."""

    latest = (
        ConsentRecord.objects.filter(profile=profile, given_as="guardian")
        .order_by("-created_at")
        .first()
    )
    if latest is None or latest.action != ConsentRecord.Action.GRANTED:
        return None
    if not is_guardian_of(latest.given_by, profile):
        return None
    return latest


def effective_visibility(profile: PlayerProfile, on: date | None = None) -> str:
    """What scouts and the public actually get, after the age and consent rules."""

    chosen = profile.visibility
    if profile.date_of_birth is None:
        return PlayerProfile.Visibility.PRIVATE
    if not is_minor(profile, on):
        return chosen
    consent = active_consent(profile)
    if consent is None:
        return PlayerProfile.Visibility.PRIVATE
    allowed = consent.visibility or PlayerProfile.Visibility.PRIVATE
    return min(chosen, allowed, key=lambda value: VISIBILITY_RANK.get(value, 0))


def shared_sections(profile: PlayerProfile) -> set[str]:
    """Adults share everything they made visible; minors share what was consented."""

    required = {item["key"] for item in catalog.CONSENT_SECTIONS if item["required"]}
    if not is_minor(profile):
        return catalog.keys(catalog.CONSENT_SECTIONS)
    consent = active_consent(profile)
    if consent is None:
        return set()
    return required | (set(consent.sections) & catalog.keys(catalog.CONSENT_SECTIONS))


def access_level(profile: PlayerProfile, viewer) -> str | None:
    """`owner`, `guardian`, `scout`, `public`, or None when the viewer may not see it."""

    if viewer and viewer.is_authenticated:
        if profile.user_id == viewer.id:
            return "owner"
        if is_guardian_of(viewer, profile):
            return "guardian"
    visibility = effective_visibility(profile)
    if visibility == PlayerProfile.Visibility.PUBLIC:
        if (
            viewer
            and viewer.is_authenticated
            and (is_scout(viewer) or coaches_player(viewer, profile))
        ):
            return "scout"
        return "public"
    if visibility == PlayerProfile.Visibility.SCOUTS and (
        is_scout(viewer) or coaches_player(viewer, profile)
    ):
        return "scout"
    return None


def scouting_leagues(user):
    """Competitions whose owners opened them to scouts, as far as this user may see them.

    Scouts see every open league, private ones included: opening a league to scouts
    is the owner's consent to that. Everyone else sees open leagues they could
    already see.
    """

    from apps.competitions.models import Competition
    from apps.competitions.views import visible_competitions

    leagues = Competition.objects.filter(open_to_scouts=True).select_related("owner")
    if is_scout(user):
        return leagues
    return leagues.filter(pk__in=visible_competitions(user).values("pk"))


def is_league_scout(competition, user) -> bool:
    if not user or not user.is_authenticated:
        return False
    from .models import LeagueScout

    return LeagueScout.objects.filter(competition=competition, user=user).exists()


MAX_PROFILE_TEAMS = 12


def roster_team_ids(user) -> set:
    """Active team (not individual) sides a person is listed on."""

    if not user:
        return set()
    from apps.competitions.models import RosterMember

    return set(
        RosterMember.objects.filter(
            user=user, is_active=True, participant__kind="team"
        ).values_list("participant_id", flat=True)
    )


def team_payload(participant, *, from_roster: bool = False) -> dict:
    return {
        "id": str(participant.id),
        "name": participant.name,
        "competition_id": str(participant.competition_id),
        "competition": participant.competition.name,
        "sport": participant.competition.sport,
        "from_roster": from_roster,
    }


def affiliated_teams(profile: PlayerProfile) -> list[dict]:
    """Claimed school/club sides plus any team the player is actually rostered on.

    Roster rows cannot be dropped from the talent profile; they change in the
    competition itself. A player can still claim extra sides in other competitions.
    """

    from apps.competitions.models import Participant

    roster = roster_team_ids(profile.user_id)
    claimed = {team.id: team for team in profile.teams.select_related("competition").all()}
    missing = roster - set(claimed)
    if missing:
        for team in Participant.objects.filter(pk__in=missing).select_related("competition"):
            claimed[team.id] = team
    rows = [
        team_payload(team, from_roster=team.id in roster)
        for team in sorted(
            claimed.values(), key=lambda team: (team.name.lower(), team.competition.name.lower())
        )
    ]
    return rows


def school_or_club_label(teams: list[dict], fallback: str = "") -> str:
    names: list[str] = []
    seen: set[str] = set()
    for team in teams:
        if team["name"] not in seen:
            seen.add(team["name"])
            names.append(team["name"])
    return ", ".join(names)[:160] or fallback


def visible_profiles(viewer):
    """Every profile the viewer may open. Evaluated in Python because consent is per row."""

    candidates = (
        PlayerProfile.objects.exclude(visibility=PlayerProfile.Visibility.PRIVATE)
        .select_related("user")
        .prefetch_related("sports", "teams__competition")
    )
    return [
        profile for profile in candidates if access_level(profile, viewer) in {"scout", "public"}
    ]


def record_consent(
    profile: PlayerProfile,
    *,
    by,
    given_as: str,
    action: str,
    visibility: str = "",
    sections: list[str] | None = None,
    note: str = "",
) -> ConsentRecord:
    return ConsentRecord.objects.create(
        profile=profile,
        given_by=by,
        given_as=given_as,
        action=action,
        visibility=visibility,
        sections=list(sections or []),
        note=note,
    )
