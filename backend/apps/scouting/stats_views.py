"""Scouting Phase 3 API: a player's stats, physical test results and percentiles."""

from __future__ import annotations

from datetime import date

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import attributes, catalog, stats
from .models import PhysicalTestResult, PlayerProfile, PlayerSport, PlayerStatLine, ScoutingRole
from .services import access_level, coaches_player

TAG = ["Scouting"]


def _player_competitions(profile: PlayerProfile):
    """Competitions the player is in, as a roster member or as an entrant."""

    from apps.competitions.models import Competition

    return Competition.objects.filter(
        Q(participants__roster__user=profile.user, participants__roster__is_active=True)
        | Q(participants__managed_by=profile.user)
    ).distinct()


def test_source(user, profile: PlayerProfile) -> str | None:
    """How a result this user records is labelled, or None if they may not record one."""

    if not user or not user.is_authenticated:
        return None
    if coaches_player(user, profile):
        return PhysicalTestResult.Source.COACH
    from apps.core.permissions import Role, has_at_least
    from apps.results.models import CompetitionOfficial

    for competition in _player_competitions(profile):
        if CompetitionOfficial.objects.filter(competition=competition, user=user).exists():
            return PhysicalTestResult.Source.OFFICIAL
        if has_at_least(competition, user, Role.ADMIN):
            return PhysicalTestResult.Source.OFFICIAL
    if profile.user_id == user.id:
        return PhysicalTestResult.Source.SELF
    return None


def _visible_profile(request: Request, pk) -> tuple[PlayerProfile, str]:
    profile = get_object_or_404(PlayerProfile, pk=pk)
    access = access_level(profile, request.user)
    if access is None and test_source(request.user, profile) in (
        None,
        PhysicalTestResult.Source.SELF,
    ):
        raise NotFound("No profile found.")
    return profile, access or "scout"


def _sports_for(profile: PlayerProfile) -> list[str]:
    keys = list(
        PlayerSport.objects.filter(profile=profile)
        .order_by("-is_primary")
        .values_list("sport", flat=True)
    )
    keys += [
        sport
        for sport in PlayerStatLine.objects.filter(user=profile.user)
        .values_list("sport", flat=True)
        .distinct()
        if sport not in keys
    ]
    return [key for key in keys if key in catalog.SPORTS]


class ProfileStatsView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=TAG,
        summary="A player's match stats, physical tests and percentiles",
        description=(
            "Stats come from the competition engine and are cached by the stats job after "
            "each completed fixture. Percentiles compare the player with visible players in "
            f"the same sport, position, age group and gender category, and are hidden below "
            f"{stats.MIN_SAMPLE} players."
        ),
        parameters=[
            OpenApiParameter("sport", str, description="Catalogue sport key (default: primary)"),
            OpenApiParameter("season", int, description="Season year (default: latest)"),
            OpenApiParameter("competition", str, description="One competition id (default: all)"),
        ],
        responses=dict,
    )
    def get(self, request: Request, pk) -> Response:
        profile, _access = _visible_profile(request, pk)
        if not PlayerStatLine.objects.filter(user=profile.user).exists():
            stats.recompute_user(profile.user)  # first view before the job has run
        sports = _sports_for(profile)
        sport = request.query_params.get("sport") or (sports[0] if sports else "")
        if sport and sport not in catalog.SPORTS:
            raise ValidationError({"sport": "That sport is not in the scouting catalogue."})
        lines = PlayerStatLine.objects.filter(user=profile.user, sport=sport)
        seasons = sorted({line.season for line in lines}, reverse=True)
        try:
            season = int(
                request.query_params.get("season") or (seasons[0] if seasons else date.today().year)
            )
        except ValueError as error:
            raise ValidationError({"season": "Use a year, e.g. 2026."}) from error
        competition_id = request.query_params.get("competition") or None
        season_lines = lines.filter(season=season)
        line = season_lines.filter(competition_id=competition_id).first()
        definitions = {
            row["key"]: row for row in (catalog.sport_catalogue(sport) or {}).get("match_stats", [])
        }
        peers = stats.cohort(profile, sport) if sport else []
        ranks = (
            stats.stat_percentiles(profile, sport, season, line.values, peers)
            if line and not competition_id
            else {}
        )
        rows = []
        for key, definition in definitions.items():
            entry = (line.values if line else {}).get(key) or {}
            rows.append(
                {
                    **{
                        field: definition.get(field)
                        for field in ("key", "label", "per", "unit", "formula", "source", "better")
                    },
                    "value": entry.get("value"),
                    "per_match": entry.get("per_match"),
                    "percentile": (ranks.get(key) or {}).get("percentile"),
                    "sample": (ranks.get(key) or {}).get("sample", 0),
                }
            )
        history = [
            {
                "season": row.season,
                "matches": row.matches,
                "values": {key: (value or {}).get("value") for key, value in row.values.items()},
            }
            for row in lines.filter(competition=None).order_by("season")
        ]
        competitions = [
            {"id": str(row.competition_id), "name": row.competition.name}
            for row in season_lines.exclude(competition=None).select_related("competition")
        ]
        return Response(
            {
                "profile_id": str(profile.id),
                "name": f"{profile.first_name} {profile.last_name}".strip(),
                "sports": [{"key": key, "label": catalog.SPORTS[key]["label"]} for key in sports],
                "sport": sport,
                "seasons": seasons,
                "season": season,
                "competitions": competitions,
                "competition": competition_id,
                "line": {
                    "matches": line.matches if line else 0,
                    "minutes": line.minutes if line else 0,
                    "computed_at": line.computed_at if line else None,
                },
                "stats": rows,
                "history": history,
                "tests": stats.test_summary(profile, sport, peers) if sport else [],
                "percentile_minimum": stats.MIN_SAMPLE,
                "cohort": len(peers),
                "can_record_tests": test_source(request.user, profile) is not None,
            }
        )


def _validate_test(data: dict, profile: PlayerProfile) -> tuple[str, dict]:
    sport = str(data.get("sport") or "")
    definitions = (attributes.SPORT_ATTRIBUTES.get(sport) or {}).get("physical_tests") or []
    definition = next((row for row in definitions if row["key"] == data.get("test_key")), None)
    if sport not in catalog.SPORTS:
        raise ValidationError({"sport": "Choose a sport from the catalogue."})
    if definition is None:
        raise ValidationError({"test_key": "Choose one of this sport's physical tests."})
    unit = str(data.get("unit") or definition["unit"])
    if unit != definition["unit"]:
        raise ValidationError(
            {"unit": f"{definition['label']} is recorded in {definition['unit']}."}
        )
    return sport, definition


class ProfileTestsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="A player's physical test results", responses=dict)
    def get(self, request: Request, pk) -> Response:
        profile, _ = _visible_profile(request, pk)
        rows = PhysicalTestResult.objects.filter(profile=profile)
        if sport := request.query_params.get("sport"):
            rows = rows.filter(sport=sport)
        return Response(
            [
                {**stats.result_row(row), "sport": row.sport, "test_key": row.test_key}
                for row in rows
            ]
        )

    @extend_schema(
        tags=TAG,
        summary="Record a physical test result",
        description=(
            "A coach of the player's team or an official or admin of one of the player's "
            "competitions records a verified result. A player may add their own, which is "
            "labelled self-reported."
        ),
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, pk) -> Response:
        profile = get_object_or_404(PlayerProfile, pk=pk)
        source = test_source(request.user, profile)
        if source is None:
            raise PermissionDenied(
                "Only the player's coach, an official or the player can record a test."
            )
        sport, definition = _validate_test(request.data, profile)
        try:
            value = round(float(request.data.get("value")), 3)
        except (TypeError, ValueError) as error:
            raise ValidationError({"value": "Give the result as a number."}) from error
        if value < 0:
            raise ValidationError({"value": "A result cannot be negative."})
        try:
            tested_on = date.fromisoformat(
                str(request.data.get("tested_on") or date.today().isoformat())
            )
        except ValueError as error:
            raise ValidationError({"tested_on": "Use a date like 2026-10-19."}) from error
        if tested_on > date.today():
            raise ValidationError({"tested_on": "The test date is in the future."})
        verified = source != PhysicalTestResult.Source.SELF
        row = PhysicalTestResult.objects.create(
            profile=profile,
            sport=sport,
            test_key=definition["key"],
            value=value,
            unit=definition["unit"],
            tested_on=tested_on,
            venue=str(request.data.get("venue") or "")[:160],
            note=str(request.data.get("note") or "")[:240],
            source=source,
            verified_by=request.user if verified else None,
            recorded_by=request.user,
        )
        return Response(
            {
                **stats.result_row(row),
                "sport": row.sport,
                "test_key": row.test_key,
                "test": definition["label"],
            },
            status=status.HTTP_201_CREATED,
        )


class TestResultDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Remove a test result I recorded", responses={204: None})
    def delete(self, request: Request, pk) -> Response:
        row = get_object_or_404(PhysicalTestResult, pk=pk)
        if row.recorded_by_id != request.user.id:
            raise PermissionDenied("Only the person who recorded a result can remove it.")
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecordablePlayersView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Players I can record a verified test for (my teams and competitions)",
        responses=dict,
    )
    def get(self, request: Request) -> Response:
        from apps.competitions.models import RosterMember
        from apps.core.permissions import Role
        from apps.results.models import CompetitionOfficial

        teams = set(
            ScoutingRole.objects.filter(
                user=request.user, role=ScoutingRole.Role.COACH, team__isnull=False
            ).values_list("team_id", flat=True)
        )
        competitions = set(
            CompetitionOfficial.objects.filter(user=request.user).values_list(
                "competition_id", flat=True
            )
        ) | set(
            request.user.memberships.filter(role__in=[Role.OWNER, Role.ADMIN]).values_list(
                "competition_id", flat=True
            )
        )
        members = RosterMember.objects.filter(
            Q(participant_id__in=teams) | Q(participant__competition_id__in=competitions),
            is_active=True,
            user__isnull=False,
        ).select_related("participant")
        team_of = {}
        for member in members:
            team_of.setdefault(member.user_id, member.participant.name)
        rows = []
        for profile in PlayerProfile.objects.filter(user_id__in=team_of).order_by(
            "first_name", "last_name"
        )[:300]:
            rows.append(
                {
                    "profile_id": str(profile.id),
                    "name": f"{profile.first_name} {profile.last_name}".strip(),
                    "team": team_of.get(profile.user_id, ""),
                    "sports": [
                        {"key": sport, "label": catalog.SPORTS[sport]["label"]}
                        for sport in _sports_for(profile)
                    ],
                }
            )
        mine = PlayerProfile.objects.filter(user=request.user).first()
        return Response(
            {
                "players": rows,
                "self": {
                    "profile_id": str(mine.id),
                    "sports": [
                        {"key": key, "label": catalog.SPORTS[key]["label"]}
                        for key in _sports_for(mine)
                    ],
                }
                if mine
                else None,
            }
        )
