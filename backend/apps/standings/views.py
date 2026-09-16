from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.models import Stage
from apps.competitions.views import visible_competitions

from .models import StandingRow
from .serializers import StandingRowSerializer
from .services import refresh_standings


class StandingsView(APIView):
    """The league table for a competition, optionally scoped to one stage."""

    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = None

    @extend_schema(
        tags=["Standings"],
        summary="Get the league table",
        parameters=[
            OpenApiParameter("stage", str, description="Limit the table to one stage."),
            OpenApiParameter(
                "refresh",
                bool,
                description="Recompute before returning instead of using the cache.",
            ),
        ],
        responses={200: StandingRowSerializer(many=True)},
    )
    def get(self, request: Request, competition_pk: str) -> Response:
        competition = get_object_or_404(
            visible_competitions(request.user), pk=competition_pk
        )

        stage = None
        if stage_id := request.query_params.get("stage"):
            stage = get_object_or_404(Stage, pk=stage_id, competition=competition)

        rows = StandingRow.objects.filter(
            competition=competition, stage=stage
        ).select_related("participant")

        # An empty cache usually means nothing has been computed yet rather than
        # that the table is genuinely empty, so fill it on first read.
        if request.query_params.get("refresh") in {"1", "true", "yes"} or not rows.exists():
            refresh_standings(competition, stage)
            rows = StandingRow.objects.filter(
                competition=competition, stage=stage
            ).select_related("participant")

        return Response(
            {
                "competition_id": str(competition.id),
                "stage_id": str(stage.id) if stage else None,
                "rows": StandingRowSerializer(rows, many=True).data,
            }
        )
