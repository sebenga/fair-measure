from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.views import visible_competitions

from . import services

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
