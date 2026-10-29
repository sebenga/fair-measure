from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.models import RosterMember
from apps.competitions.views import visible_competitions

from . import scoring, services

TAG = ["Fantasy"]


def _competition(request: Request, competition_pk):
    competition = get_object_or_404(visible_competitions(request.user), pk=competition_pk)
    if not services.available(competition):
        raise ValidationError(services.UNAVAILABLE)
    return competition


class FantasyTeamView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Your fantasy squad in this competition")
    def get(self, request: Request, competition_pk) -> Response:
        competition = _competition(request, competition_pk)
        return Response(services.overview(competition, request.user))

    @extend_schema(
        tags=TAG,
        summary="Save your fantasy squad",
        request=dict,
        responses=dict,
    )
    def put(self, request: Request, competition_pk) -> Response:
        competition = _competition(request, competition_pk)
        services.save_team(
            competition,
            request.user,
            name=str(request.data.get("name") or ""),
            raw_picks=request.data.get("picks") or [],
        )
        return Response(services.overview(competition, request.user))


class FantasyPlayersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Players you can pick, with price and points",
        parameters=[
            OpenApiParameter("q", str, description="Search name or club."),
            OpenApiParameter("slot", str, description="GKP | DEF | MID | FWD"),
            OpenApiParameter("club", str, description="Participant id."),
        ],
    )
    def get(self, request: Request, competition_pk) -> Response:
        competition = _competition(request, competition_pk)
        players = services.market(
            competition,
            query=str(request.query_params.get("q") or ""),
            slot=str(request.query_params.get("slot") or ""),
            club=str(request.query_params.get("club") or ""),
        )
        return Response({"players": players, "count": len(players)})


class PlayerPerformanceView(APIView):
    """Performance points for one roster player: season total and match-by-match lines."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="A player's performance points, per match and for the season",
        description=(
            "FPL-style points from completed and forfeited fixtures. The season total is the "
            "sum of match points. Each match lists its lines (appearance, 60+ minutes, goals by "
            "position, assists, saves, clean sheet, cards, own goals). Captaincy is not applied: "
            "it only doubles a player inside a fantasy squad."
        ),
        responses={
            200: inline_serializer(
                "PlayerPerformance",
                fields={
                    "player_id": serializers.UUIDField(),
                    "name": serializers.CharField(),
                    "number": serializers.IntegerField(allow_null=True),
                    "team_id": serializers.UUIDField(),
                    "team_name": serializers.CharField(),
                    "slot": serializers.CharField(),
                    "slots": serializers.ListField(child=serializers.CharField()),
                    "matches_played": serializers.IntegerField(),
                    "minutes": serializers.IntegerField(),
                    "total_performance_points": serializers.CharField(),
                    "matches": inline_serializer(
                        "PlayerPerformanceMatch",
                        many=True,
                        fields={
                            "fixture_id": serializers.UUIDField(),
                            "label": serializers.CharField(),
                            "played_at": serializers.DateTimeField(allow_null=True),
                            "opponents": serializers.ListField(child=serializers.CharField()),
                            "team_score": serializers.CharField(allow_null=True),
                            "conceded": serializers.CharField(),
                            "minutes": serializers.IntegerField(),
                            "slot": serializers.CharField(),
                            "points": serializers.CharField(),
                            "lines": inline_serializer(
                                "PlayerPerformanceLine",
                                many=True,
                                fields={
                                    "label": serializers.CharField(),
                                    "points": serializers.CharField(),
                                    "each": serializers.CharField(),
                                    "count": serializers.CharField(),
                                    "detail": serializers.CharField(),
                                },
                            ),
                        },
                    ),
                },
            )
        },
    )
    def get(self, request: Request, competition_pk, player_pk) -> Response:
        competition = _competition(request, competition_pk)
        member = get_object_or_404(
            RosterMember.objects.select_related("participant"),
            pk=player_pk,
            participant__competition=competition,
        )
        return Response(scoring.player_performance(competition, member))


class FantasyStandingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Fantasy league table for this competition")
    def get(self, request: Request, competition_pk) -> Response:
        competition = _competition(request, competition_pk)
        rows = services.standings(competition)
        return Response({"rows": rows, "count": len(rows)})


class FantasyAutoPickView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="A legal complete squad, not saved until you confirm")
    def post(self, request: Request, competition_pk) -> Response:
        competition = _competition(request, competition_pk)
        return Response({"picks": services.auto_pick(competition)})
