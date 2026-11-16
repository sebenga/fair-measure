"""League discipline: red-card bans and yellow-card accumulations.

Normal league defaults (FIFA / SAFA style):

- A red card (straight or second yellow) bans the player for the next match.
- Every five yellow cards in the same season bans the player for the next match.

Injured players stay out of team sheets until an organiser clears them.
Automatic suspensions are derived from completed fixtures and written onto
the roster so team profiles and team sheets stay in sync.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.competitions.models import RosterMember

from .cards import RED, YELLOW
from .models import Fixture, ScoreEvent

AUTO_PREFIX = "Automatic · "

DEFAULTS = {
    "enabled": True,
    "yellow_threshold": 5,
    "yellow_ban_matches": 1,
    "red_ban_matches": 1,
}

FINISHED = {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}
OPEN = {
    Fixture.Status.SCHEDULED,
    Fixture.Status.POSTPONED,
    Fixture.Status.LIVE,
}


@dataclass(frozen=True)
class Ban:
    """A suspension served on one team fixture index."""

    index: int
    reason: str


def discipline_config(competition) -> dict:
    """League card-ban rules stored on the competition, with normal defaults."""

    settings = competition.settings_json or {}
    raw = settings.get("discipline")
    if not isinstance(raw, dict):
        has_cards = competition.scoring_categories.filter(code__in=(YELLOW, RED)).exists()
        return {**DEFAULTS, "enabled": has_cards}
    return {**DEFAULTS, **raw}


def _order_key(fixture: Fixture):
    return (fixture.scheduled_at or fixture.created_at, fixture.created_at, str(fixture.id))


def team_fixtures(participant, stage=None) -> list[Fixture]:
    """This team's fixtures in season order, excluding cancelled games."""

    qs = Fixture.objects.filter(
        competition_id=participant.competition_id,
        sides__participant=participant,
    ).exclude(status=Fixture.Status.CANCELLED)
    if stage is not None:
        qs = qs.filter(stage_id=stage.id)
    return sorted(qs.distinct(), key=_order_key)


def next_team_fixture(participant, after: Fixture | None = None, stage=None) -> Fixture | None:
    """The next open fixture this team still has to play."""

    fixtures = team_fixtures(participant, stage=stage if stage is not None else getattr(after, "stage", None))
    started = False if after is None else False
    for fixture in fixtures:
        if after is not None and not started:
            if fixture.id == after.id:
                started = True
            continue
        if fixture.status in OPEN:
            return fixture
    return None


def _card_totals(fixture_ids: list, player_ids: list) -> dict[tuple, dict[str, int]]:
    totals: dict[tuple, dict[str, int]] = {}
    if not fixture_ids or not player_ids:
        return totals
    rows = ScoreEvent.objects.filter(
        fixture_id__in=fixture_ids,
        player_id__in=player_ids,
        scoring_category__code__in=(YELLOW, RED),
    ).values_list("fixture_id", "player_id", "scoring_category__code", "quantity")
    for fixture_id, player_id, code, quantity in rows:
        key = (fixture_id, player_id)
        cards = totals.setdefault(key, {"yellow": 0, "red": 0})
        cards["yellow" if code == YELLOW else "red"] += int(quantity or 1)
    return totals


def bans_for_player(
    fixtures: list[Fixture],
    player_id,
    *,
    yellow_threshold: int,
    yellow_ban_matches: int,
    red_ban_matches: int,
    cards: dict[tuple, dict[str, int]] | None = None,
) -> list[Ban]:
    """Fixture indices where this player must sit out because of earlier cards.

    Bans are earned when a finished match ends, then served on later team
    fixtures in order. A red and a yellow-threshold ban in the same match
    stack across consecutive matches.
    """

    if yellow_threshold < 1:
        yellow_threshold = 5
    yellow_total = 0
    bans: list[Ban] = []
    pending: list[str] = []
    card_map = cards or {}

    for index, fixture in enumerate(fixtures):
        if pending:
            bans.append(Ban(index=index, reason=pending.pop(0)))
        if fixture.status not in FINISHED:
            continue
        row = card_map.get((fixture.id, player_id), {"yellow": 0, "red": 0})
        yellows = row["yellow"]
        reds = row["red"]
        before = yellow_total
        yellow_total += yellows
        prev_bands = before // yellow_threshold
        new_bands = yellow_total // yellow_threshold
        for band in range(prev_bands + 1, new_bands + 1):
            reason = f"{AUTO_PREFIX}{band * yellow_threshold} yellow cards"
            pending.extend([reason] * max(1, yellow_ban_matches))
        if reds:
            pending.extend([f"{AUTO_PREFIX}Red card"] * max(1, red_ban_matches))
    return bans


def suspension_for(fixture: Fixture, player: RosterMember, config: dict | None = None) -> Ban | None:
    """Return the automatic ban that applies to this player in this fixture, if any."""

    rules = config or discipline_config(fixture.competition)
    if not rules.get("enabled"):
        return None
    fixtures = team_fixtures(player.participant, stage=fixture.stage)
    try:
        index = next(i for i, row in enumerate(fixtures) if row.id == fixture.id)
    except StopIteration:
        return None
    finished_ids = [row.id for row in fixtures if row.status in FINISHED]
    cards = _card_totals(finished_ids, [player.id])
    bans = bans_for_player(
        fixtures,
        player.id,
        yellow_threshold=int(rules.get("yellow_threshold") or 5),
        yellow_ban_matches=int(rules.get("yellow_ban_matches") or 1),
        red_ban_matches=int(rules.get("red_ban_matches") or 1),
        cards=cards,
    )
    for ban in bans:
        if ban.index == index:
            return ban
    return None


def effective_availability(
    member: RosterMember, fixture: Fixture, config: dict | None = None
) -> tuple[str, str, object]:
    """Availability used when naming a team sheet for this fixture."""

    if member.availability == RosterMember.Availability.INJURED:
        return member.availability, member.availability_note, member.available_from
    ban = suspension_for(fixture, member, config=config)
    if ban is not None:
        return RosterMember.Availability.SUSPENDED, ban.reason, None
    if member.availability == RosterMember.Availability.SUSPENDED:
        return member.availability, member.availability_note, member.available_from
    return RosterMember.Availability.AVAILABLE, "", None


def is_unavailable_for_sheet(member: RosterMember, fixture: Fixture, config: dict | None = None) -> bool:
    status, _, _ = effective_availability(member, fixture, config=config)
    return status != RosterMember.Availability.AVAILABLE


def sync_roster_discipline(fixture: Fixture) -> None:
    """Refresh automatic suspensions on both squads after a result is settled."""

    config = discipline_config(fixture.competition)
    if not config.get("enabled"):
        return

    for side in fixture.sides.select_related("participant").all():
        participant = side.participant
        upcoming = next_team_fixture(participant, after=fixture, stage=fixture.stage)
        members = list(participant.roster.filter(is_active=True))
        if not members:
            continue
        for member in members:
            if member.availability == RosterMember.Availability.INJURED:
                continue
            auto = (member.availability_note or "").startswith(AUTO_PREFIX)
            ban = suspension_for(upcoming, member, config=config) if upcoming is not None else None
            if ban is not None:
                if member.availability == RosterMember.Availability.AVAILABLE or auto:
                    member.availability = RosterMember.Availability.SUSPENDED
                    member.availability_note = ban.reason
                    member.available_from = None
                    member.save(
                        update_fields=[
                            "availability",
                            "availability_note",
                            "available_from",
                            "updated_at",
                        ]
                    )
            elif auto:
                member.availability = RosterMember.Availability.AVAILABLE
                member.availability_note = ""
                member.available_from = None
                member.save(
                    update_fields=[
                        "availability",
                        "availability_note",
                        "available_from",
                        "updated_at",
                    ]
                )
