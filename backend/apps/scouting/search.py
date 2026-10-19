"""Talent search over the profiles a scout may see.

Every filter is data from the catalogue (positions, tests, stats, areas), so the
search never names a sport. It starts from ``visible_profiles``, which already
hides private profiles and under-18s without guardian consent.
"""

from __future__ import annotations

from rest_framework.exceptions import ValidationError

from . import attributes, catalog, ratings, stats
from .models import HighlightVideo, PhysicalTestResult, PlayerProfile, PlayerStatLine
from .services import age_group, scout_organisations, visible_profiles

OPS = {
    "lt": lambda left, right: left < right,
    "lte": lambda left, right: left <= right,
    "gt": lambda left, right: left > right,
    "gte": lambda left, right: left >= right,
    "eq": lambda left, right: left == right,
}
SIMPLE_KEYS = {"q", "sport", "position", "age_group", "gender", "region", "level", "has_video"}
LIST_KEYS = {"tests", "stats", "percentiles", "areas"}
RATING_KEYS = {"areas", "potential_min", "current_min", "recommendation"}
ALL_KEYS = SIMPLE_KEYS | LIST_KEYS | RATING_KEYS


def _number(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValidationError({field: "Give a number."}) from error


def clean(filters: dict) -> dict:
    """Check a filter set against the catalogue; returns a tidy copy."""

    if not isinstance(filters, dict):
        raise ValidationError({"filters": "Filters must be an object."})
    unknown = set(filters) - ALL_KEYS
    if unknown:
        raise ValidationError({"filters": f"Unknown filters: {', '.join(sorted(unknown))}."})
    out: dict = {}
    sport = str(filters.get("sport") or "")
    if sport and sport not in catalog.SPORTS:
        raise ValidationError({"sport": "Choose a sport from the catalogue."})
    if sport:
        out["sport"] = sport
    if filters.get("q"):
        out["q"] = str(filters["q"]).strip().lower()[:80]
    if filters.get("position"):
        if not sport or filters["position"] not in catalog.position_keys(sport):
            raise ValidationError({"position": "Choose a sport, then one of its positions."})
        out["position"] = filters["position"]
    if filters.get("age_group"):
        if filters["age_group"] not in catalog.keys(catalog.AGE_GROUPS):
            raise ValidationError({"age_group": "Unknown age group."})
        out["age_group"] = filters["age_group"]
    if filters.get("gender"):
        if filters["gender"] not in catalog.keys(catalog.GENDER_CATEGORIES):
            raise ValidationError({"gender": "Unknown gender category."})
        out["gender"] = filters["gender"]
    if filters.get("region"):
        if filters["region"] not in catalog.keys(catalog.REGIONS):
            raise ValidationError({"region": "Unknown region."})
        out["region"] = filters["region"]
    if filters.get("level"):
        if filters["level"] not in attributes.LEVEL_RANK:
            raise ValidationError({"level": "Unknown competition level."})
        out["level"] = filters["level"]
    if filters.get("has_video"):
        out["has_video"] = True

    needs_sport = [key for key in ("tests", "stats", "percentiles") if filters.get(key)]
    if needs_sport and not sport:
        raise ValidationError({needs_sport[0]: "Choose a sport for test and stat filters."})
    extra = attributes.SPORT_ATTRIBUTES.get(sport) or {}
    test_keys = {row["key"] for row in extra.get("physical_tests") or []}
    stat_keys = {row["key"] for row in extra.get("match_stats") or []}
    for field, allowed in (("tests", test_keys), ("stats", stat_keys)):
        rows = []
        for row in filters.get(field) or []:
            if row.get("key") not in allowed:
                raise ValidationError(
                    {field: f"{row.get('key')} is not one of this sport's {field}."}
                )
            if row.get("op") not in OPS:
                raise ValidationError({field: "Use lt, lte, gt, gte or eq."})
            rows.append(
                {"key": row["key"], "op": row["op"], "value": _number(row.get("value"), field)}
            )
        if rows:
            out[field] = rows
    percentiles = []
    for row in filters.get("percentiles") or []:
        if row.get("key") not in test_keys | stat_keys:
            raise ValidationError(
                {"percentiles": f"{row.get('key')} is not a test or stat of this sport."}
            )
        percentiles.append({"key": row["key"], "min": _number(row.get("min"), "percentiles")})
    if percentiles:
        out["percentiles"] = percentiles
    areas = []
    for row in filters.get("areas") or []:
        if row.get("key") not in attributes.AREA_KEYS:
            raise ValidationError({"areas": f"{row.get('key')} is not one of the five areas."})
        areas.append({"key": row["key"], "min": _number(row.get("min"), "areas")})
    if areas:
        out["areas"] = areas
    for field in ("potential_min", "current_min"):
        if filters.get(field) not in (None, ""):
            out[field] = _number(filters[field], field)
    if filters.get("recommendation"):
        if filters["recommendation"] not in {row["key"] for row in attributes.RECOMMENDATIONS}:
            raise ValidationError({"recommendation": "Unknown recommendation."})
        out["recommendation"] = filters["recommendation"]
    return out


def player_level(profile: PlayerProfile) -> str | None:
    """The highest level among the competitions the player's teams play in."""

    from django.db.models import Q

    from apps.competitions.models import Competition

    levels = [
        (competition.settings_json or {}).get("level")
        for competition in Competition.objects.filter(
            Q(participants__roster__user=profile.user, participants__roster__is_active=True)
            | Q(participants__managed_by=profile.user)
        ).distinct()
    ]
    ranked = [level for level in levels if level in attributes.LEVEL_RANK]
    return max(ranked, key=attributes.LEVEL_RANK.get) if ranked else None


def best_test(profile: PlayerProfile, sport: str, key: str) -> float | None:
    definition = next(
        (
            row
            for row in (attributes.SPORT_ATTRIBUTES.get(sport) or {}).get("physical_tests") or []
            if row["key"] == key
        ),
        None,
    )
    values = list(
        PhysicalTestResult.objects.filter(profile=profile, sport=sport, test_key=key).values_list(
            "value", flat=True
        )
    )
    if not values or definition is None:
        return None
    return float(min(values) if definition["better"] == "lower" else max(values))


def latest_line(profile: PlayerProfile, sport: str) -> PlayerStatLine | None:
    return (
        PlayerStatLine.objects.filter(user=profile.user, sport=sport, competition=None)
        .order_by("-season")
        .first()
    )


def _recommendation(summary: dict) -> str | None:
    top = max(summary["recommendations"], key=lambda row: row["count"])
    return top["key"] if top["count"] else None


def run(user, filters: dict, *, limit: int = 200) -> list[dict]:
    """Profiles matching every filter, each with the facts the filters looked at."""

    filters = clean(filters)
    sport = filters.get("sport")
    organisation = None
    if RATING_KEYS & set(filters):
        mine = scout_organisations(user)
        if not mine:
            raise ValidationError({"filters": "Join a scouting organisation to filter by ratings."})
        organisation = mine[0]
    results = []
    for profile in visible_profiles(user):
        if profile.user_id == user.id:
            continue
        sports = {row.sport: row for row in profile.sports.all()}
        if sport and sport not in sports:
            continue
        if filters.get("position") and sports[sport].primary_position != filters["position"]:
            if filters["position"] not in (sports[sport].secondary_positions or []):
                continue
        if filters.get("q") and filters["q"] not in profile.full_name.lower():
            continue
        group = (age_group(profile.date_of_birth) or {}).get("key")
        if filters.get("age_group") and group != filters["age_group"]:
            continue
        if filters.get("gender") and profile.gender_category != filters["gender"]:
            continue
        if filters.get("region") and profile.region != filters["region"]:
            continue
        facts: dict = {}
        if filters.get("level"):
            level = player_level(profile)
            if (
                level is None
                or attributes.LEVEL_RANK[level] < attributes.LEVEL_RANK[filters["level"]]
            ):
                continue
            facts["level"] = level
        if filters.get("has_video"):
            if not HighlightVideo.objects.filter(profile=profile).exists():
                continue
            facts["has_video"] = True

        failed = False
        for row in filters.get("tests") or []:
            value = best_test(profile, sport, row["key"])
            if value is None or not OPS[row["op"]](value, row["value"]):
                failed = True
                break
            facts.setdefault("tests", {})[row["key"]] = value
        if failed:
            continue
        line = (
            latest_line(profile, sport)
            if (filters.get("stats") or filters.get("percentiles"))
            else None
        )
        for row in filters.get("stats") or []:
            value = ((line.values if line else {}).get(row["key"]) or {}).get("value")
            if value is None or not OPS[row["op"]](value, row["value"]):
                failed = True
                break
            facts.setdefault("stats", {})[row["key"]] = value
        if failed:
            continue
        if filters.get("percentiles"):
            peers = stats.cohort(profile, sport)
            stat_ranks = (
                stats.stat_percentiles(profile, sport, line.season, line.values, peers)
                if line
                else {}
            )
            test_ranks = {row["key"]: row for row in stats.test_summary(profile, sport, peers)}
            for row in filters["percentiles"]:
                rank = (stat_ranks.get(row["key"]) or test_ranks.get(row["key"]) or {}).get(
                    "percentile"
                )
                if rank is None or rank < row["min"]:
                    failed = True
                    break
                facts.setdefault("percentiles", {})[row["key"]] = rank
            if failed:
                continue
        if organisation is not None:
            summary = ratings.summary(profile, organisation, sport)
            areas = {row["key"]: row["average"] for row in summary["areas"]}
            for row in filters.get("areas") or []:
                if areas.get(row["key"]) is None or areas[row["key"]] < row["min"]:
                    failed = True
                    break
            for field, key in (("potential_min", "potential"), ("current_min", "current_ability")):
                if field in filters and (summary[key] is None or summary[key] < filters[field]):
                    failed = True
            if (
                filters.get("recommendation")
                and _recommendation(summary) != filters["recommendation"]
            ):
                failed = True
            if failed:
                continue
            facts["areas"] = {key: value for key, value in areas.items() if value is not None}
            facts["potential"] = summary["potential"]
            facts["recommendation"] = _recommendation(summary)
        results.append({"profile": profile, "facts": facts})
        if len(results) >= limit:
            break
    return results
