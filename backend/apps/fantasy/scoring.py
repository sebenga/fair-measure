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
from apps.fixtures.played import lineup_position_by_match, lineup_positions

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


def slots_from_positions(positions: list[str], fallback: str = "") -> list[str]:
    """Fantasy shirts this player can fill, most-played line first.

    One player can be both DEF and MID. They stay one person — the same id
    appears in both lists.
    """

    slots: list[str] = []
    for label in positions:
        slot = classify_slot(label)
        if slot not in slots:
            slots.append(slot)
    if not slots:
        slots.append(classify_slot(fallback))
    return slots


def _qty(event: ScoreEvent) -> Decimal:
    return Decimal(event.quantity)


def _minutes_for(appearance: PlayerAppearance | None, fixture: Fixture, played: bool) -> int:
    if appearance is not None and appearance.minutes is not None:
        return int(appearance.minutes)
    if played:
        return int(fixture.duration_minutes or 90)
    return 0


GOAL_POINTS = {
    FantasySlot.GKP: Decimal("6"),
    FantasySlot.DEF: Decimal("6"),
    FantasySlot.MID: Decimal("5"),
    FantasySlot.FWD: Decimal("4"),
}
CLEAN_SHEET_POINTS = {
    FantasySlot.GKP: Decimal("4"),
    FantasySlot.DEF: Decimal("4"),
    FantasySlot.MID: Decimal("1"),
    FantasySlot.FWD: Decimal("0"),
}
# Labels match RULES_PUBLIC["scoring"] so the breakdown reads like the rules page.
SLOT_GROUP = {
    FantasySlot.GKP: "GK/DEF",
    FantasySlot.DEF: "GK/DEF",
    FantasySlot.MID: "MID",
    FantasySlot.FWD: "FWD",
}


def _line(label: str, each: Decimal, count: Decimal) -> dict:
    detail = f"× {points_text(count)}" if count != 1 else ""  # noqa: RUF001
    return {"label": label, "each": each, "count": count, "points": each * count, "detail": detail}


def match_breakdown(
    *,
    slot: str,
    minutes: int,
    events: Iterable[ScoreEvent],
    conceded: Decimal,
) -> dict:
    """One player's points in one counted fixture, line by line.

    Shots, tackles and other stat-only codes are ignored: they are player stats,
    not fantasy actions. Captaincy is applied to a squad, never here.
    """

    lines: list[dict] = []
    if minutes > 0:
        lines.append(_line("Appearance", Decimal("1"), Decimal("1")))
        if minutes >= 60:
            lines.append(_line("60+ minutes", Decimal("1"), Decimal("1")))

        counts: dict[str, Decimal] = defaultdict(Decimal)
        for event in events:
            code = event.scoring_category.code
            for key, codes in (
                ("goal", GOAL_CODES),
                ("assist", ASSIST_CODES),
                ("own_goal", OWN_GOAL_CODES),
                ("yellow", YELLOW_CODES),
                ("red", RED_CODES),
                ("penalty_save", PENALTY_SAVE_CODES),
                ("save", SAVE_CODES),
            ):
                if code in codes:
                    counts[key] += _qty(event)
                    break

        if counts["goal"]:
            label = f"Goal ({SLOT_GROUP.get(slot, 'MID')})"
            each = GOAL_POINTS.get(slot, GOAL_POINTS[FantasySlot.MID])
            lines.append(_line(label, each, counts["goal"]))
        if counts["assist"]:
            lines.append(_line("Assist", Decimal("3"), counts["assist"]))
        if counts["penalty_save"]:
            lines.append(_line("Penalty save", Decimal("5"), counts["penalty_save"]))
        if counts["save"] >= 3:
            line = _line("3 saves", Decimal("1"), counts["save"] // 3)
            line["detail"] = f"{points_text(counts['save'])} saves"
            lines.append(line)
        if conceded <= 0 and minutes >= 60 and CLEAN_SHEET_POINTS.get(slot):
            label = f"Clean sheet ({SLOT_GROUP.get(slot, 'MID')})"
            lines.append(_line(label, CLEAN_SHEET_POINTS[slot], Decimal("1")))
        if counts["own_goal"]:
            lines.append(_line("Own goal", Decimal("-2"), counts["own_goal"]))
        if counts["yellow"]:
            lines.append(_line("Yellow card", Decimal("-1"), counts["yellow"]))
        if counts["red"]:
            lines.append(_line("Red card", Decimal("-3"), counts["red"]))

    return {
        "minutes": max(int(minutes), 0),
        "slot": slot,
        "points": sum((line["points"] for line in lines), Decimal("0")),
        "lines": lines,
    }


def player_match_points(
    *,
    slot: str,
    minutes: int,
    events: Iterable[ScoreEvent],
    conceded: Decimal,
) -> Decimal:
    """Points one player earns in one counted fixture."""

    return match_breakdown(slot=slot, minutes=minutes, events=events, conceded=conceded)["points"]


def _match_rows(competition, members: list[RosterMember]) -> tuple[dict, list[Fixture], dict]:
    """Every counted fixture for these players, with one match breakdown each.

    Returns (slots by player, counted fixtures oldest first, rows by player).
    A row is {"fixture", "side", "conceded", "breakdown"}; a fixture the player
    did not appear in still has a row, worth 0.
    """

    by_id = {member.id: member for member in members}
    shirts = lineup_positions(competition, by_id)
    match_shirts = lineup_position_by_match(competition, by_id)
    slots = {
        member.id: slots_from_positions(shirts.get(member.id, []), member.position)
        for member in members
    }

    fixtures = list(
        Fixture.objects.filter(competition=competition, status__in=COUNTED)
        .prefetch_related("sides__participant")
        .order_by("scheduled_at", "created_at")
    )
    if not fixtures:
        return slots, [], {member.id: [] for member in members}

    fixture_ids = [fixture.id for fixture in fixtures]

    # Conceded = the best opposing score, so multi-way fixtures still have one figure.
    conceded: dict[tuple[object, object], Decimal] = {}
    sides_by_fixture: dict[object, dict[object, object]] = {}
    for fixture in fixtures:
        sides = list(fixture.sides.all())
        sides_by_fixture[fixture.id] = {side.participant_id: side for side in sides}
        for side in sides:
            others = [other.score for other in sides if other.id != side.id]
            conceded[(fixture.id, side.participant_id)] = max(others) if others else Decimal("0")

    events_by_player: dict[tuple[object, object], list[ScoreEvent]] = defaultdict(list)
    appeared: set[tuple[object, object]] = set()
    for event in ScoreEvent.objects.filter(
        fixture_id__in=fixture_ids, player_id__in=by_id
    ).select_related("scoring_category"):
        events_by_player[(event.fixture_id, event.player_id)].append(event)
        appeared.add((event.fixture_id, event.player_id))

    for rating in PlayerMatchRating.objects.filter(fixture_id__in=fixture_ids, player_id__in=by_id):
        appeared.add((rating.fixture_id, rating.player_id))

    appearances: dict[tuple[object, object], PlayerAppearance] = {}
    for row in PlayerAppearance.objects.filter(fixture_id__in=fixture_ids, player_id__in=by_id):
        appearances[(row.fixture_id, row.player_id)] = row
        appeared.add((row.fixture_id, row.player_id))

    rows: dict[object, list[dict]] = {}
    for member in members:
        primary = slots[member.id][0]
        member_rows = []
        for fixture in fixtures:
            key = (fixture.id, member.id)
            shirt = match_shirts.get(key)
            member_rows.append(
                {
                    "fixture": fixture,
                    "side": sides_by_fixture[fixture.id].get(member.participant_id),
                    "conceded": conceded.get((fixture.id, member.participant_id), Decimal("0")),
                    "breakdown": match_breakdown(
                        slot=classify_slot(shirt) if shirt else primary,
                        minutes=_minutes_for(appearances.get(key), fixture, key in appeared),
                        events=events_by_player.get(key, ()),
                        conceded=conceded.get((fixture.id, member.participant_id), Decimal("0")),
                    ),
                }
            )
        rows[member.id] = member_rows
    return slots, fixtures, rows


def season_totals(competition) -> dict[object, dict]:
    """Per-player season points, last-fixture points, and a suggested price.

    The season total is the sum of the player's match points.
    """

    members = list(
        RosterMember.objects.filter(participant__competition=competition, is_active=True)
        .select_related("participant")
    )
    if not members:
        return {}

    slots, fixtures, rows = _match_rows(competition, members)
    totals: dict[object, dict] = {}
    for member in members:
        primary = slots[member.id][0]
        member_rows = rows.get(member.id, [])
        season = sum((row["breakdown"]["points"] for row in member_rows), Decimal("0"))
        totals[member.id] = {
            "points": season,
            "event_points": member_rows[-1]["breakdown"]["points"] if member_rows else Decimal("0"),
            "minutes": sum(row["breakdown"]["minutes"] for row in member_rows),
            "slot": primary,
            "slots": slots[member.id],
            "price": _price_for(primary, season) if fixtures else BASE_PRICES[primary],
        }
    return totals


def player_performance(competition, member: RosterMember) -> dict:
    """One player's season total and the breakdown of every counted match they played."""

    slots, _fixtures, rows = _match_rows(competition, [member])
    member_rows = rows.get(member.id, [])
    played = [row for row in member_rows if row["breakdown"]["minutes"] > 0]
    total = sum((row["breakdown"]["points"] for row in member_rows), Decimal("0"))
    matches = []
    for row in played:
        fixture = row["fixture"]
        side = row["side"]
        opponents = [
            other.participant.name
            for other in fixture.sides.all()
            if side is None or other.id != side.id
        ]
        breakdown = row["breakdown"]
        matches.append(
            {
                "fixture_id": str(fixture.id),
                "label": fixture.label,
                "played_at": (fixture.completed_at or fixture.scheduled_at),
                "opponents": opponents,
                "team_score": points_text(Decimal(side.score)) if side is not None else None,
                "conceded": points_text(row["conceded"]),
                "minutes": breakdown["minutes"],
                "slot": breakdown["slot"],
                "points": points_text(breakdown["points"]),
                "lines": [
                    {
                        "label": line["label"],
                        "points": points_text(line["points"]),
                        "each": points_text(line["each"]),
                        "count": points_text(line["count"]),
                        "detail": line["detail"],
                    }
                    for line in breakdown["lines"]
                ],
            }
        )
    return {
        "player_id": str(member.id),
        "name": member.name,
        "number": member.number,
        "team_id": str(member.participant_id),
        "team_name": member.participant.name,
        "slot": slots[member.id][0],
        "slots": slots[member.id],
        "matches_played": len(played),
        "minutes": sum(row["breakdown"]["minutes"] for row in member_rows),
        "total_performance_points": points_text(total),
        "matches": matches,
    }


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
