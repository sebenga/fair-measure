"""Load the player market, save a squad, and rank managers."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.competitions.models import RosterMember

from .models import FantasyPick, FantasySlot, FantasyTeam
from .rules import (
    BUDGET,
    RULES_PUBLIC,
    SLOT_QUOTAS,
    SQUAD_SIZE,
    STARTERS,
    VALID_FORMATIONS,
    formation_of,
    max_per_club_for,
    validate_picks,
)
from .scoring import classify_slot, money, points_text, season_totals, slots_from_positions

UNAVAILABLE = "Fantasy is only for team sports such as soccer and rugby."


def available(competition) -> bool:
    """Fantasy needs club rosters: soccer, rugby and other team-sport leagues."""

    settings = competition.settings_json or {}
    if (settings.get("participant_type") or "team") != "team":
        return False
    if settings.get("scoring_basis") == "criteria" or settings.get("table_mode") == "points":
        return False
    return True


def pool_members(competition):
    return (
        RosterMember.objects.filter(participant__competition=competition, is_active=True)
        .select_related("participant", "user")
        .order_by("participant__name", "number", "name")
    )


def market(competition, *, query: str = "", slot: str = "", club: str = "") -> list[dict]:
    members = list(pool_members(competition))
    totals = season_totals(competition)
    rows = []
    needle = query.strip().lower()
    for member in members:
        stats = totals.get(member.id) or {}
        member_slots = list(stats.get("slots") or slots_from_positions([], member.position))
        member_slot = stats.get("slot") or member_slots[0]
        if slot and slot not in member_slots:
            continue
        if club and str(member.participant_id) != club:
            continue
        if needle and needle not in member.name.lower() and needle not in member.participant.name.lower():
            continue
        price = stats.get("price") or Decimal("4.5")
        rows.append(_player_payload(member, member_slot, member_slots, stats, price))
    rows.sort(key=lambda row: (-Decimal(row["points"]), Decimal(row["price"]), row["name"].lower()))
    return rows


def _player_payload(
    member: RosterMember, slot: str, slots: list[str], stats: dict, price: Decimal
) -> dict:
    return {
        "id": str(member.id),
        "name": member.name,
        "number": member.number,
        "position": member.position,
        "slot": slot,
        "slots": slots,
        "team_id": str(member.participant_id),
        "team_name": member.participant.name,
        "team_short": member.participant.short_name or member.participant.name[:3].upper(),
        "user_id": str(member.user_id) if member.user_id else None,
        "price": money(price),
        "points": points_text(stats.get("points") or Decimal("0")),
        "event_points": points_text(stats.get("event_points") or Decimal("0")),
    }


def parse_picks(competition, raw_picks) -> list[dict]:
    if not isinstance(raw_picks, list):
        raise ValidationError({"picks": "Send the squad as a list of picks."})

    members = {str(member.id): member for member in pool_members(competition)}
    totals = season_totals(competition)
    parsed = []
    for index, item in enumerate(raw_picks):
        if not isinstance(item, dict):
            raise ValidationError({"picks": "Each pick needs a player id."})
        player_id = str(item.get("player") or "")
        member = members.get(player_id)
        if member is None:
            raise ValidationError({"picks": f"Player {player_id or index} is not in this competition."})
        stats = totals.get(member.id) or {}
        allowed = list(stats.get("slots") or slots_from_positions([], member.position))
        slot = str(item.get("slot") or (allowed[0] if allowed else classify_slot(member.position)))
        if slot not in FantasySlot.values:
            raise ValidationError({"picks": f"{member.name} has an unknown position."})
        if slot not in allowed:
            raise ValidationError(
                {"picks": f"{member.name} has not played as a {slot} in this competition."}
            )
        price = stats.get("price") or Decimal("4.5")
        parsed.append(
            {
                "player": member,
                "slot": slot,
                "is_starter": bool(item.get("is_starter", True)),
                "is_captain": bool(item.get("is_captain", False)),
                "is_vice": bool(item.get("is_vice", False)),
                "bench_order": int(item.get("bench_order") or 0),
                "price": price,
            }
        )
    return parsed


def is_complete(picks: list[dict]) -> bool:
    if len(picks) != SQUAD_SIZE:
        return False
    if Counter(pick["slot"] for pick in picks) != Counter(SLOT_QUOTAS):
        return False
    starters = [pick for pick in picks if pick["is_starter"]]
    if len(starters) != STARTERS or formation_of(starters) is None:
        return False
    return sum(1 for pick in picks if pick["is_captain"]) == 1 and sum(
        1 for pick in picks if pick["is_vice"]
    ) == 1


@transaction.atomic
def save_team(competition, user, *, name: str, raw_picks) -> FantasyTeam:
    picks = parse_picks(competition, raw_picks)
    complete = is_complete(picks)
    validate_picks(
        picks,
        complete=complete,
        club_count=competition.participants.count(),
    )

    label = (name or "").strip()[:80] or f"{user.display_name}'s XI"
    team, _ = FantasyTeam.objects.get_or_create(
        competition=competition,
        user=user,
        defaults={"name": label},
    )
    if name and team.name != label:
        team.name = label
        team.save(update_fields=["name", "updated_at"])

    team.picks.all().delete()
    FantasyPick.objects.bulk_create(
        [
            FantasyPick(
                team=team,
                player=pick["player"],
                slot=pick["slot"],
                is_starter=pick["is_starter"],
                is_captain=pick["is_captain"],
                is_vice=pick["is_vice"],
                bench_order=pick["bench_order"],
                price=pick["price"],
            )
            for pick in picks
        ]
    )
    return team


def team_payload(team: FantasyTeam, totals: dict | None = None) -> dict:
    totals = totals if totals is not None else season_totals(team.competition)
    picks = list(team.picks.select_related("player__participant"))
    rows = []
    spent = Decimal("0")
    points = Decimal("0")
    event_points = Decimal("0")
    captain_id = None
    vice_id = None
    played = set()
    for pick in picks:
        stats = totals.get(pick.player_id) or {}
        player_pts = stats.get("points") or Decimal("0")
        player_event = stats.get("event_points") or Decimal("0")
        if (stats.get("minutes") or 0) > 0:
            played.add(pick.player_id)
        spent += pick.price
        if pick.is_captain:
            captain_id = pick.player_id
        if pick.is_vice:
            vice_id = pick.player_id
        rows.append(
            {
                **_player_payload(
                    pick.player,
                    pick.slot,
                    list(stats.get("slots") or slots_from_positions([], pick.player.position)),
                    stats,
                    pick.price,
                ),
                "pick_id": str(pick.id),
                "is_starter": pick.is_starter,
                "is_captain": pick.is_captain,
                "is_vice": pick.is_vice,
                "bench_order": pick.bench_order,
            }
        )

    multiplier_id = captain_id if captain_id in played or vice_id is None else vice_id
    for pick in picks:
        if not pick.is_starter:
            continue
        stats = totals.get(pick.player_id) or {}
        player_pts = stats.get("points") or Decimal("0")
        player_event = stats.get("event_points") or Decimal("0")
        factor = Decimal("2") if pick.player_id == multiplier_id else Decimal("1")
        points += player_pts * factor
        event_points += player_event * factor

    parsed = [
        {
            "player": pick.player,
            "slot": pick.slot,
            "is_starter": pick.is_starter,
            "is_captain": pick.is_captain,
            "is_vice": pick.is_vice,
            "bench_order": pick.bench_order,
            "price": pick.price,
        }
        for pick in picks
    ]
    starters = [pick for pick in parsed if pick["is_starter"]]
    shape = formation_of(starters)
    return {
        "id": str(team.id),
        "name": team.name,
        "manager": {
            "id": str(team.user_id),
            "display_name": team.user.display_name,
        },
        "complete": is_complete(parsed),
        "budget_used": money(spent),
        "budget_remaining": money(BUDGET - spent),
        "points": points_text(points),
        "event_points": points_text(event_points),
        "formation": "-".join(str(n) for n in shape) if shape else "",
        "picks": rows,
    }


def standings(competition) -> list[dict]:
    totals = season_totals(competition)
    teams = list(
        FantasyTeam.objects.filter(competition=competition)
        .select_related("user")
        .prefetch_related("picks__player__participant")
    )
    rows = [team_payload(team, totals) for team in teams]
    rows.sort(key=lambda row: (-Decimal(row["points"]), -Decimal(row["event_points"]), row["name"].lower()))
    ranked = []
    for index, row in enumerate(rows, start=1):
        ranked.append(
            {
                "rank": index,
                "team_id": row["id"],
                "name": row["name"],
                "manager": row["manager"],
                "complete": row["complete"],
                "points": row["points"],
                "event_points": row["event_points"],
            }
        )
    return ranked


def auto_pick(competition) -> list[dict]:
    """Cheapest legal complete squad, preferring players who have scored."""

    available = market(competition)
    if len(available) < SQUAD_SIZE:
        raise ValidationError(
            {"detail": f"Need at least {SQUAD_SIZE} rostered players before auto-pick can fill a squad."}
        )

    by_slot: dict[str, list[dict]] = defaultdict(list)
    for player in available:
        for shirt in player.get("slots") or [player["slot"]]:
            by_slot[shirt].append(player)

    chosen: list[dict] = []
    used_ids: set[str] = set()
    club_counts: Counter[str] = Counter()
    club_limit = max_per_club_for(len({player["team_id"] for player in available}))
    still_need = dict(SLOT_QUOTAS)
    # Take one shirt from each slot in turn so three-from-a-club does not
    # fill up on defenders before any forwards are picked.
    while any(still_need.values()):
        progressed = False
        for slot, remaining in list(still_need.items()):
            if remaining <= 0:
                continue
            options = sorted(
                by_slot.get(slot, []),
                key=lambda row: (Decimal(row["price"]), -Decimal(row["points"]), row["name"].lower()),
            )
            pick = next(
                (
                    player
                    for player in options
                    if player["id"] not in used_ids and club_counts[player["team_id"]] < club_limit
                ),
                None,
            )
            if pick is None:
                continue
            used_ids.add(pick["id"])
            club_counts[pick["team_id"]] += 1
            chosen.append({**pick, "slot": slot})
            still_need[slot] -= 1
            progressed = True
        if not progressed:
            missing = next(slot for slot, left in still_need.items() if left)
            raise ValidationError(
                {"detail": f"Not enough {missing} players to fill a squad (need {SLOT_QUOTAS[missing]})."}
            )

    # Start a 4-4-2: 1 GK, 4 DEF, 4 MID, 2 FWD — the most forgiving shape.
    starter_quota = {
        FantasySlot.GKP: 1,
        FantasySlot.DEF: 4,
        FantasySlot.MID: 4,
        FantasySlot.FWD: 2,
    }
    starters: list[str] = []
    for slot, count in starter_quota.items():
        slot_picks = [player for player in chosen if player["slot"] == slot]
        slot_picks.sort(key=lambda row: (-Decimal(row["points"]), Decimal(row["price"])))
        starters.extend(player["id"] for player in slot_picks[:count])

    captain = max(chosen, key=lambda row: Decimal(row["points"]))
    vice_options = [player for player in chosen if player["id"] != captain["id"]]
    vice = max(vice_options, key=lambda row: Decimal(row["points"])) if vice_options else captain

    bench_cursor = {FantasySlot.GKP: 0, FantasySlot.DEF: 0, FantasySlot.MID: 0, FantasySlot.FWD: 0}
    picks = []
    for player in chosen:
        starting = player["id"] in starters
        order = 0
        if not starting:
            bench_cursor[player["slot"]] += 1
            order = bench_cursor[player["slot"]]
        picks.append(
            {
                "player": player["id"],
                "slot": player["slot"],
                "is_starter": starting,
                "is_captain": player["id"] == captain["id"],
                "is_vice": player["id"] == vice["id"],
                "bench_order": order,
            }
        )
    return picks


def overview(competition, user) -> dict:
    totals = season_totals(competition)
    team = (
        FantasyTeam.objects.filter(competition=competition, user=user)
        .select_related("user")
        .prefetch_related("picks__player__participant")
        .first()
    )
    ranks = standings(competition)
    mine = next((row for row in ranks if row["manager"]["id"] == str(user.id)), None)
    payload = team_payload(team, totals) if team else None
    if payload and mine:
        payload["rank"] = mine["rank"]
        payload["managers"] = len(ranks)
    return {
        "rules": {
            **RULES_PUBLIC,
            "max_per_club": max_per_club_for(competition.participants.count()),
        },
        "player_count": pool_members(competition).count(),
        "team": payload,
        "standings": ranks[:8],
        "valid_formations": ["-".join(str(n) for n in shape) for shape in sorted(VALID_FORMATIONS)],
    }
