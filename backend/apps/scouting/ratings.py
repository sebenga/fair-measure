"""Scout ratings: validation, the offline-safe create, and organisation averages.

A rating is a dated record. Area scores in a full rating are the mean of the
attributes rated in that area unless the scout set the area score directly.
An organisation's view of a player uses each of its scouts' latest rating,
weighted by that rating's confidence.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import attributes, catalog
from .models import HighlightVideo, Organisation, PlayerProfile, PlayerSport, ScoutRating
from .services import access_level, is_scout, scout_organisations

SCALE_MIN, SCALE_MAX = attributes.SCALE["min"], attributes.SCALE["max"]
CONFIDENCE_KEYS = set(attributes.CONFIDENCE_WEIGHTS)
WATCHED_KEYS = {row["key"] for row in attributes.WATCHED}
RECOMMENDATION_KEYS = {row["key"] for row in attributes.RECOMMENDATIONS}
MAX_CLIPS = 10


def _score(value, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValidationError({field: f"Rate from {SCALE_MIN} to {SCALE_MAX}."}) from error
    if (
        str(value).strip() not in {str(number), f"{number}.0"}
        or not SCALE_MIN <= number <= SCALE_MAX
    ):
        raise ValidationError({field: f"Rate from {SCALE_MIN} to {SCALE_MAX} in whole numbers."})
    return number


def player_fixtures(profile: PlayerProfile, limit: int = 15) -> list:
    """Recent and upcoming fixtures of the player's teams, newest first."""

    from apps.fixtures.models import Fixture

    return list(
        Fixture.objects.filter(
            Q(
                sides__participant__roster__user=profile.user,
                sides__participant__roster__is_active=True,
            )
            | Q(sides__participant__managed_by=profile.user)
        )
        .exclude(status__in=[Fixture.Status.CANCELLED])
        .select_related("competition")
        .prefetch_related("sides__participant")
        .distinct()
        .order_by("-scheduled_at", "-created_at")[:limit]
    )


def _organisation_for(user, data: dict) -> Organisation:
    mine = scout_organisations(user)
    if not mine:
        raise PermissionDenied("Join a scouting organisation before rating players.")
    wanted = data.get("organisation")
    if wanted:
        found = next((row for row in mine if str(row.id) == str(wanted)), None)
        if found is None:
            raise PermissionDenied("You do not scout for that organisation.")
        return found
    if len(mine) > 1:
        raise ValidationError({"organisation": "Choose which organisation this rating is for."})
    return mine[0]


def validate(user, data: dict) -> dict:
    """Clean a rating from the app. Raises ValidationError or PermissionDenied."""

    if not is_scout(user):
        raise PermissionDenied("Only scouts rate players.")
    try:
        client_id = uuid.UUID(str(data.get("client_id")))
    except (TypeError, ValueError) as error:
        raise ValidationError({"client_id": "Each rating needs the id the app gave it."}) from error
    profile = PlayerProfile.objects.filter(pk=data.get("profile")).first()
    if profile is None or access_level(profile, user) not in {"scout"}:
        raise ValidationError({"profile": "That player is not visible to scouts."})
    organisation = _organisation_for(user, data)

    sports = {row.sport: row for row in PlayerSport.objects.filter(profile=profile)}
    sport = str(data.get("sport") or next(iter(sports), ""))
    if sport not in sports or sport not in catalog.SPORTS:
        raise ValidationError({"sport": "Rate the player in one of the sports on their profile."})
    position = str(data.get("position") or sports[sport].primary_position or "")
    if position and position not in catalog.position_keys(sport):
        raise ValidationError({"position": "That position is not in this sport's catalogue."})

    mode = str(data.get("mode") or ScoutRating.Mode.QUICK)
    if mode not in ScoutRating.Mode.values:
        raise ValidationError({"mode": "Choose quick or full."})
    confidence = str(data.get("confidence") or "medium")
    if confidence not in CONFIDENCE_KEYS:
        raise ValidationError({"confidence": "Choose low, medium or high."})
    watched = str(data.get("watched") or "live")
    if watched not in WATCHED_KEYS:
        raise ValidationError({"watched": "Choose live or video."})

    area_scores = {}
    for key, value in (data.get("area_scores") or {}).items():
        if value in (None, ""):
            continue  # skipped
        if key not in attributes.AREA_KEYS:
            raise ValidationError({"area_scores": f"{key} is not one of the five areas."})
        area_scores[key] = _score(value, f"area_scores.{key}")

    attribute_scores = {}
    if mode == ScoutRating.Mode.FULL:
        allowed = {
            row["key"]: row
            for row in catalog.attributes_for(sport)
            if not row.get("applies_to_positions")
            or not position
            or position in row["applies_to_positions"]
        }
        for key, value in (data.get("attribute_scores") or {}).items():
            if value in (None, ""):
                continue  # skipped
            if key not in allowed:
                raise ValidationError(
                    {"attribute_scores": f"{key} is not rated for this sport and position."}
                )
            attribute_scores[key] = _score(value, f"attribute_scores.{key}")
    elif data.get("attribute_scores"):
        raise ValidationError({"attribute_scores": "Quick mode rates the five areas only."})

    grades = {}
    for field in ("current_ability", "potential"):
        if data.get(field) not in (None, ""):
            grades[field] = _score(data[field], field)
    recommendation = str(data.get("recommendation") or "")
    if recommendation and recommendation not in RECOMMENDATION_KEYS:
        raise ValidationError({"recommendation": "Choose Monitor, Trial, Sign or Not for us."})
    if not (area_scores or attribute_scores or grades or recommendation):
        raise ValidationError("Rate at least one area, attribute or overall grade.")

    fixture = None
    if data.get("fixture"):
        fixture = next(
            (row for row in player_fixtures(profile, 200) if str(row.id) == str(data["fixture"])),
            None,
        )
        if fixture is None:
            raise ValidationError({"fixture": "That fixture is not one the player played in."})

    clips = []
    videos = {str(row.id): row for row in HighlightVideo.objects.filter(profile=profile)}
    for item in (data.get("clips") or [])[: MAX_CLIPS + 1]:
        if len(clips) == MAX_CLIPS:
            raise ValidationError({"clips": f"Add up to {MAX_CLIPS} clips."})
        video_id = str(item.get("video") or "")
        url = str(item.get("url") or "").strip()
        if video_id and video_id not in videos:
            raise ValidationError({"clips": "That video is not on the player's profile."})
        if not video_id and not url.startswith(("https://", "http://")):
            raise ValidationError({"clips": "A clip needs one of the player's videos or a link."})
        try:
            at = int(item.get("at_seconds") or 0)
        except (TypeError, ValueError) as error:
            raise ValidationError({"clips": "Give the clip time in seconds."}) from error
        if at < 0:
            raise ValidationError({"clips": "A clip time cannot be negative."})
        clips.append(
            {
                "video": video_id or None,
                "title": videos[video_id].title if video_id else "",
                "url": url[:600],
                "at_seconds": at,
                "note": str(item.get("note") or "")[:200],
            }
        )

    observed_at = timezone.now()
    if data.get("observed_at"):
        parsed = parse_datetime(str(data["observed_at"]))
        if parsed is None:
            raise ValidationError({"observed_at": "Use an ISO date and time."})
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        if parsed > timezone.now() + timedelta(minutes=10):
            raise ValidationError({"observed_at": "The rating time is in the future."})
        observed_at = parsed

    return {
        "client_id": client_id,
        "profile": profile,
        "organisation": organisation,
        "sport": sport,
        "position": position,
        "fixture": fixture,
        "mode": mode,
        "watched": watched,
        "confidence": confidence,
        "area_scores": area_scores,
        "attribute_scores": attribute_scores,
        "current_ability": grades.get("current_ability"),
        "potential": grades.get("potential"),
        "recommendation": recommendation,
        "notes": str(data.get("notes") or "")[:4000],
        "clips": clips,
        "observed_at": observed_at,
    }


def submit(user, data: dict) -> tuple[ScoutRating, bool]:
    """Store a rating once. A repeat of the same client_id returns the first copy."""

    existing = (
        ScoutRating.objects.filter(client_id=data.get("client_id")).first()
        if data.get("client_id")
        else None
    )
    if existing is not None:
        if existing.scout_id != user.id:
            raise ValidationError({"client_id": "That rating id is already used."})
        return existing, False
    clean = validate(user, data)
    try:
        with transaction.atomic():
            return ScoutRating.objects.create(scout=user, **clean), True
    except IntegrityError:
        # Two sync attempts raced; the other one stored it.
        return ScoutRating.objects.get(client_id=clean["client_id"]), False


def area_values(rating: ScoutRating) -> dict[str, float]:
    """Each area's score for one rating: set directly, or the mean of its attributes."""

    values = {key: float(value) for key, value in rating.area_scores.items()}
    if rating.attribute_scores:
        areas = {row["key"]: row["area"] for row in catalog.attributes_for(rating.sport)}
        grouped: dict[str, list[int]] = defaultdict(list)
        for key, value in rating.attribute_scores.items():
            if key in areas:
                grouped[areas[key]].append(value)
        for area, scores in grouped.items():
            values.setdefault(area, round(sum(scores) / len(scores), 2))
    return values


def _weighted(pairs: list[tuple[float, int]]) -> float | None:
    total = sum(weight for _, weight in pairs)
    if not total:
        return None
    return round(sum(value * weight for value, weight in pairs) / total, 2)


def summary(profile: PlayerProfile, organisation: Organisation, sport: str | None = None) -> dict:
    """The organisation's view: each scout's latest rating, weighted by confidence."""

    ratings = ScoutRating.objects.filter(profile=profile, organisation=organisation)
    if sport:
        ratings = ratings.filter(sport=sport)
    latest: dict = {}
    for rating in ratings.order_by("-observed_at", "-created_at"):
        latest.setdefault(rating.scout_id, rating)
    areas: dict[str, list] = defaultdict(list)
    grades: dict[str, list] = defaultdict(list)
    recommendations: dict[str, int] = defaultdict(int)
    for rating in latest.values():
        weight = attributes.CONFIDENCE_WEIGHTS.get(rating.confidence, 1)
        for area, value in area_values(rating).items():
            areas[area].append((value, weight))
        for field in ("current_ability", "potential"):
            if getattr(rating, field) is not None:
                grades[field].append((getattr(rating, field), weight))
        if rating.recommendation:
            recommendations[rating.recommendation] += 1
    progress = [
        {
            "observed_at": rating.observed_at,
            "scout": rating.scout.display_name if rating.scout_id else "",
            "average": round(sum(values.values()) / len(values), 2)
            if (values := area_values(rating))
            else None,
            "current_ability": rating.current_ability,
            "potential": rating.potential,
        }
        for rating in ratings.select_related("scout").order_by("observed_at", "created_at")
    ]
    return {
        "organisation": {"id": str(organisation.id), "name": organisation.name},
        "scouts": len(latest),
        "ratings": ratings.count(),
        "areas": [
            {
                "key": area["key"],
                "label": area["label"],
                "average": _weighted(areas.get(area["key"], [])),
                "scouts": len(areas.get(area["key"], [])),
            }
            for area in attributes.AREAS
        ],
        "current_ability": _weighted(grades.get("current_ability", [])),
        "potential": _weighted(grades.get("potential", [])),
        "recommendations": [
            {"key": row["key"], "label": row["label"], "count": recommendations.get(row["key"], 0)}
            for row in attributes.RECOMMENDATIONS
        ],
        "progress": progress,
    }


def rating_row(rating: ScoutRating) -> dict:
    return {
        "id": str(rating.id),
        "client_id": str(rating.client_id),
        "profile": str(rating.profile_id),
        "scout": {"id": str(rating.scout_id), "name": rating.scout.display_name},
        "organisation": str(rating.organisation_id),
        "sport": rating.sport,
        "position": rating.position,
        "fixture": (
            {
                "id": str(rating.fixture_id),
                "label": rating.fixture.label,
                "competition": rating.fixture.competition.name,
            }
            if rating.fixture_id
            else None
        ),
        "mode": rating.mode,
        "watched": rating.watched,
        "confidence": rating.confidence,
        "area_scores": rating.area_scores,
        "attribute_scores": rating.attribute_scores,
        "areas": area_values(rating),
        "current_ability": rating.current_ability,
        "potential": rating.potential,
        "recommendation": rating.recommendation,
        "notes": rating.notes,
        "clips": rating.clips,
        "observed_at": rating.observed_at,
        "synced_at": rating.created_at,
    }
