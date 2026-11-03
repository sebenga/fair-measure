from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.jobs import valid_uuids

from .services import COMPETITIONS_INDEX, PARTICIPANTS_INDEX, POSTS_INDEX, search

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
        if competition_id := request.query_params.get("competition"):
            filters = f'competition_id = "{competition_id}"'

        results = {}
        for label, index_name in targets.items():
            # Competitions are not scoped by competition_id, so skip the filter there.
            index_filter = "" if index_name == COMPETITIONS_INDEX else filters
            hits = search(index_name, query, filters=index_filter, limit=limit)
            if index_name == COMPETITIONS_INDEX:
                hits = _released_only(hits)
            results[label] = hits

        return Response({"query": query, "results": results})


def _released_only(hits: list[dict]) -> list[dict]:
    """The index can lag behind a release switch, so check the database."""

    from apps.competitions.models import Competition
    from apps.competitions.views import released_competitions

    ids = valid_uuids({hit.get("id") for hit in hits})
    allowed = {
        str(pk)
        for pk in Competition.objects.filter(released_competitions(), pk__in=ids).values_list(
            "pk", flat=True
        )
    }
    return [hit for hit in hits if str(hit.get("id")) in allowed]
