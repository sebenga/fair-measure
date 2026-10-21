"""Fantasy points and market prices, derived from recorded match events.

Points follow official FPL (appearance, goals by position, assists, cards,
saves, clean sheets). The event codes come from whatever the competition
already records — nothing here invents a new score type.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from apps.competitions.models import RosterMember
from apps.fixtures.models import Fixture, PlayerAppearance, PlayerMatchRating, ScoreEvent

from .models import FantasySlot
from .rules import BASE_PRICES

GOAL_CODES = {"goal", "try"}
ASSIST_CODES = {"assist"}
OWN_GOAL_CODES = {"own-goal", "own_goal"}
YELLOW_CODES = {"yellow-card", "yellow"}
RED_CODES = {"red-card", "red"}
SAVE_CODES = {"save"}
PENALTY_SAVE_CODES = {"penalty-save", "pen-save"}

COUNTED = {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}
TWO = Decimal("2")
TENTH = Decimal("0.1")


def classify_slot(position: str) -> str:
    """Map a roster position string onto an FPL shirt slot."""

    text = (position or "").strip().lower().replace("_", "-").replace(" ", "-")
    if not text:
        return FantasySlot.MID

    compact = text.replace("-", "")
    if compact in {"gk", "gkp", "goalkeeper", "keeper", "goalie"} or "goalkeep" in text:
        return FantasySlot.GKP
    if compact in {"st", "cf", "fw", "fwd"} or any(
        token in text for token in ("forward", "striker", "attacker", "centre-forward", "center-forward")
    ):
        return FantasySlot.FWD
    if compact in {"cb", "lb", "rb", "lwb", "rwb", "wb", "def"} or any(
        token in text
        for token in (
            "defend",
            "centre-back",
            "center-back",
            "full-back",
            "fullback",
            "left-back",
            "right-back",
            "wing-back",
            "wingback",
        )
    ):
        return FantasySlot.DEF
    if compact in {"cm", "dm", "am", "cam", "cdm", "lm", "rm", "lw", "rw", "mid"} or any(
        token in text for token in ("midfield", "winger", "wing")
    ):
        return FantasySlot.MID
    return FantasySlot.MID


def _qty(event: ScoreEvent) -> Decimal:
    return Decimal(event.quantity)


def _minutes_for(appearance: PlayerAppearance | None, fixture: Fixture, played: bool) -> int:
    if appearance is not None and appearance.minutes is not None:
        return int(appearance.minutes)
    if played:
        return int(fixture.duration_minutes or 90)
    return 0


def player_match_points(
    *,
    slot: str,
    minutes: int,
    events: Iterable[ScoreEvent],
    conceded: Decimal,
) -> Decimal:
    """Points one player earns in one counted fixture."""

    points = Decimal("0")
    if minutes <= 0:
        return points

    points += Decimal("1")
    if minutes >= 60:
        points += Decimal("1")

    saves = Decimal("0")
    for event in events:
        code = event.scoring_category.code
        amount = _qty(event)
        if code in GOAL_CODES:
            if slot == FantasySlot.FWD:
                points += Decimal("4") * amount
            elif slot == FantasySlot.MID:
                points += Decimal("5") * amount
            else:
                points += Decimal("6") * amount
        elif code in ASSIST_CODES:
            points += Decimal("3") * amount
        elif code in OWN_GOAL_CODES:
            points -= Decimal("2") * amount
        elif code in YELLOW_CODES:
            points -= Decimal("1") * amount
        elif code in RED_CODES:
            points -= Decimal("3") * amount
        elif code in PENALTY_SAVE_CODES:
            points += Decimal("5") * amount
        elif code in SAVE_CODES:
            saves += amount

    if saves >= 3:
        points += (saves // 3)

    if conceded <= 0 and minutes >= 60:
        if slot in {FantasySlot.GKP, FantasySlot.DEF}:
            points += Decimal("4")
        elif slot == FantasySlot.MID:
            points += Decimal("1")

    return points


def season_totals(competition) -> dict[object, dict]:
    """Per-player season points, last-fixture points, and a suggested price."""

    members = list(
        RosterMember.objects.filter(participant__competition=competition, is_active=True)
        .select_related("participant")
    )
    if not members:
        return {}

    by_id = {member.id: member for member in members}
    slots = {member.id: classify_slot(member.position) for member in members}

    fixtures = list(
        Fixture.objects.filter(competition=competition, status__in=COUNTED)
        .prefetch_related("sides")
        .order_by("scheduled_at", "created_at")
    )
    if not fixtures:
        return {
            member.id: {
                "points": Decimal("0"),
                "event_points": Decimal("0"),
                "minutes": 0,
                "slot": slots[member.id],
                "price": BASE_PRICES[slots[member.id]],
            }
            for member in members
        }

    fixture_ids = [fixture.id for fixture in fixtures]
    last_fixture = fixtures[-1]

    conceded: dict[tuple[object, object], Decimal] = {}
    for fixture in fixtures:
        sides = list(fixture.sides.all())
        for side in sides:
            others = [other.score for other in sides if other.id != side.id]
            conceded[(fixture.id, side.participant_id)] = max(others) if others else Decimal("0")

    events_by_player: dict[tuple[object, object], list[ScoreEvent]] = defaultdict(list)
    played: set[tuple[object, object]] = set()
    for event in ScoreEvent.objects.filter(
        fixture_id__in=fixture_ids, player_id__in=by_id
    ).select_related("scoring_category"):
        events_by_player[(event.fixture_id, event.player_id)].append(event)
        played.add((event.fixture_id, event.player_id))

    for rating in PlayerMatchRating.objects.filter(fixture_id__in=fixture_ids, player_id__in=by_id):
        played.add((rating.fixture_id, rating.player_id))

    appearances: dict[tuple[object, object], PlayerAppearance] = {}
    for row in PlayerAppearance.objects.filter(fixture_id__in=fixture_ids, player_id__in=by_id):
        appearances[(row.fixture_id, row.player_id)] = row
        played.add((row.fixture_id, row.player_id))

    totals: dict[object, dict] = {
        member.id: {
            "points": Decimal("0"),
            "event_points": Decimal("0"),
            "minutes": 0,
            "slot": slots[member.id],
            "price": BASE_PRICES[slots[member.id]],
        }
        for member in members
    }

    for member in members:
        slot = slots[member.id]
        season = Decimal("0")
        minutes_total = 0
        last = Decimal("0")
        for fixture in fixtures:
            key = (fixture.id, member.id)
            mins = _minutes_for(appearances.get(key), fixture, key in played)
            minutes_total += mins
            against = conceded.get((fixture.id, member.participant_id), Decimal("0"))
            match_pts = player_match_points(
                slot=slot,
                minutes=mins,
                events=events_by_player.get(key, ()),
                conceded=against,
            )
            season += match_pts
            if fixture.id == last_fixture.id:
                last = match_pts
        totals[member.id]["points"] = season
        totals[member.id]["event_points"] = last
        totals[member.id]["minutes"] = minutes_total
        totals[member.id]["price"] = _price_for(slot, season)

    return totals


def _price_for(slot: str, season_points: Decimal) -> Decimal:
    """Start from the FPL-style floor, then rise with output."""

    bump = (season_points / Decimal("10")).quantize(TENTH, rounding=ROUND_HALF_UP)
    price = BASE_PRICES[slot] + bump
    if price < Decimal("4.0"):
        return Decimal("4.0")
    if price > Decimal("15.0"):
        return Decimal("15.0")
    return price


def money(value: Decimal) -> str:
    return format(value.quantize(TENTH, rounding=ROUND_HALF_UP), "f")


def points_text(value: Decimal) -> str:
    quantized = value.quantize(TENTH, rounding=ROUND_HALF_UP)
    return format(quantized.normalize(), "f")
