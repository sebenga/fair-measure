from __future__ import annotations

import uuid

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import (
    COMPETITIONS_INDEX,
    PARTICIPANTS_INDEX,
    POSTS_INDEX,
    only_public_hits,
    search,
)

INDEXES = {
    "competitions": COMPETITIONS_INDEX,
    "participants": PARTICIPANTS_INDEX,
    "posts": POSTS_INDEX,
}


class SearchView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Search"],
        summary="Search competitions, participants and posts",
        description=(
            "Backed by Meilisearch when SEARCH_ENABLED is on, and by a Postgres "
            "substring match otherwise, so the endpoint behaves the same either way."
        ),
        parameters=[
            OpenApiParameter("q", str, required=True, description="The search text."),
            OpenApiParameter(
                "type",
                str,
                description="competitions | participants | posts. Defaults to all three.",
            ),
            OpenApiParameter("competition", str, description="Scope to one competition."),
            OpenApiParameter("limit", int, description="Results per type, max 50."),
        ],
        responses={200: dict},
    )
    def get(self, request: Request) -> Response:
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response({"query": "", "results": {}})

        limit = min(int(request.query_params.get("limit") or 20), 50)
        requested = request.query_params.get("type")
        targets = (
            {requested: INDEXES[requested]} if requested in INDEXES else INDEXES
        )

        filters = ""
        if raw_competition_id := request.query_params.get("competition"):
            try:
                competition_id = str(uuid.UUID(str(raw_competition_id)))
            except (ValueError, TypeError, AttributeError):
                competition_id = ""
            if competition_id:
                filters = f'competition_id = "{competition_id}"'

        results = {}
        for label, index_name in targets.items():
            # Competitions are not scoped by competition_id, so skip the filter there.
            index_filter = "" if index_name == COMPETITIONS_INDEX else filters
            results[label] = search(index_name, query, filters=index_filter, limit=limit)

        return Response({"query": query, "results": only_public_hits(results)})
