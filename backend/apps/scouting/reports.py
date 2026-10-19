"""Player scouting reports, built only from stored data.

The profile part is the same privacy-shaped view a scout or the public gets, so a
report never shows more than the profile screen would. League numbers come from
competitions the viewer can see, and each carries its date.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from apps.core.permissions import Role, has_at_least

from .models import LeagueSquad, PlayerProfile, SquadPick
from .serializers import ScoutProfileSerializer
from .services import is_league_scout, scouting_leagues


def _fmt(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f")


def _selection_for(competition, user_id, viewer) -> dict | None:
    squad = LeagueSquad.objects.filter(competition=competition).first()
    if squad is None:
        return None
    is_selector = has_at_least(competition, viewer, Role.ADMIN) or is_league_scout(
        competition, viewer
    )
    if squad.status != LeagueSquad.Status.PUBLISHED and not is_selector:
        return None
    pick = SquadPick.objects.filter(squad=squad, user_id=user_id).first()
    if pick is None:
        return None
    return {
        "squad": squad.name or f"{competition.name} squad",
        "status": squad.status,
        "group": pick.group_key,
        "position": pick.position_label,
        "score": format(pick.score, "f") if pick.score is not None else None,
        "summary": pick.evidence.get("summary", []),
        "published_at": squad.published_at,
    }


def league_record(profile: PlayerProfile, viewer) -> list[dict]:
    from apps.competitions.models import RosterMember
    from apps.fixtures.models import Fixture, FixtureSide, PlayerMatchRating, ScoreEvent

    # Only leagues whose owners opened them to scouts feed a scouting report.
    visible = scouting_leagues(viewer)
    entries = (
        RosterMember.objects.filter(user=profile.user, participant__competition__in=visible)
        .select_related("participant__competition")
        .order_by("-participant__competition__created_at")
    )
    finished = [Fixture.Status.COMPLETED, Fixture.Status.FORFEIT]
    rows: list[dict] = []
    seen: set = set()
    for entry in entries:
        competition = entry.participant.competition
        if competition.id in seen:
            continue
        seen.add(competition.id)

        sides = FixtureSide.objects.filter(
            participant=entry.participant, fixture__status__in=finished
        ).values_list("outcome", flat=True)
        record = {"won": 0, "drawn": 0, "lost": 0}
        for outcome in sides:
            key = {"win": "won", "draw": "drawn", "loss": "lost"}.get(outcome)
            if key:
                record[key] += 1

        ratings = list(
            PlayerMatchRating.objects.filter(fixture__competition=competition, player=entry)
            .select_related("fixture")
            .order_by("fixture__scheduled_at", "created_at")
        )
        events = list(
            ScoreEvent.objects.filter(fixture__competition=competition, player=entry)
            .select_related("scoring_category", "fixture")
            .order_by("created_at")
        )
        stats: dict[str, dict] = {}
        for event in events:
            bucket = stats.setdefault(
                event.scoring_category.code,
                {
                    "label": event.scoring_category.name,
                    "count": Decimal("0"),
                    "points": Decimal("0"),
                    "first": event.created_at,
                    "last": event.created_at,
                },
            )
            bucket["count"] += event.quantity
            bucket["points"] += event.points
            bucket["last"] = event.created_at

        average = (
            sum((row.rating for row in ratings), Decimal("0")) / len(ratings) if ratings else None
        )
        rows.append(
            {
                "competition_id": str(competition.id),
                "competition": competition.name,
                "sport": competition.sport,
                "team": entry.participant.name,
                "position": entry.position,
                "number": entry.number,
                "games": sum(record.values()),
                "record": record,
                "avg_rating": _fmt(average),
                "ratings": [
                    {
                        "fixture": row.fixture.label or "Fixture",
                        "date": row.fixture.scheduled_at or row.created_at,
                        "rating": format(row.rating, "f"),
                    }
                    for row in ratings
                ],
                "stats": [
                    {
                        "key": key,
                        "label": bucket["label"],
                        "count": format(bucket["count"].normalize(), "f"),
                        "points": format(bucket["points"].normalize(), "f"),
                        "first": bucket["first"],
                        "last": bucket["last"],
                    }
                    for key, bucket in stats.items()
                ],
                "selection": _selection_for(competition, profile.user_id, viewer),
            }
        )
    return rows


def coverage(profile_view: dict, leagues: list[dict]) -> list[dict]:
    measurements = profile_view.get("measurements") or []
    verified = sum(1 for item in measurements if item.get("verified"))
    ratings = sum(len(row["ratings"]) for row in leagues)
    tagged = sum(1 for row in leagues for stat in row["stats"])
    return [
        {
            "key": "positions",
            "label": "Sport and positions",
            "available": bool(profile_view.get("sports")),
        },
        {
            "key": "physical",
            "label": "Physical measurements",
            "available": bool(measurements),
            "note": f"{verified} of {len(measurements)} verified by a coach or official"
            if measurements
            else "None shared",
        },
        {
            "key": "ratings",
            "label": "Match ratings",
            "available": ratings > 0,
            "note": f"{ratings} rated game(s)" if ratings else "No games rated yet",
        },
        {
            "key": "stats",
            "label": "Scoring stats",
            "available": tagged > 0,
            "note": "From score events tagged to this player in leagues open to scouts"
            if tagged
            else "No score events tagged to this player in leagues open to scouts yet",
        },
        {
            "key": "videos",
            "label": "Highlight videos",
            "available": bool(profile_view.get("videos")),
        },
        {
            "key": "scout_ratings",
            "label": "Scout ratings",
            "available": False,
            "note": "Scout ratings are not recorded on Fair Measure yet",
        },
    ]


def headline(profile_view: dict, leagues: list[dict]) -> list[str]:
    lines: list[str] = []
    for row in leagues:
        selection = row.get("selection")
        if selection and selection["status"] == LeagueSquad.Status.PUBLISHED:
            lines.append(
                f"Selected for the {selection['squad']} ({selection['position'] or 'squad'})"
            )
    all_ratings = [Decimal(item["rating"]) for row in leagues for item in row["ratings"]]
    if all_ratings:
        average = sum(all_ratings, Decimal("0")) / len(all_ratings)
        lines.append(
            f"Average match rating {_fmt(average)} across {len(all_ratings)} rated game(s)"
        )
    games = sum(row["games"] for row in leagues)
    if games:
        lines.append(f"{games} completed game(s) for their team(s) across {len(leagues)} league(s)")
    primary = next(iter(profile_view.get("sports") or []), None)
    if primary:
        position = primary.get("primary_position_label")
        lines.append(f"{primary['sport_label']}{' · ' + position if position else ''}")
    return lines


def player_report(profile: PlayerProfile, viewer, access: str) -> dict:
    # Owners and guardians get the report a scout would get, so they can check it.
    shaped_as = "scout" if access in {"owner", "guardian"} else access
    profile_view = ScoutProfileSerializer(profile, context={"access": shaped_as}).data
    leagues = league_record(profile, viewer)
    return {
        "kind": "player_scouting_report",
        "generated_at": timezone.now(),
        "access": access,
        "shaped_as": shaped_as,
        "profile": profile_view,
        "headline": headline(profile_view, leagues),
        "leagues": leagues,
        "coverage": coverage(profile_view, leagues),
    }
