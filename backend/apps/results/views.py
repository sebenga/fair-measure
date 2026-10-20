"""API for officials, events, result sheets and the amendment log."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.views import visible_competitions
from apps.core.bus import competition_room, fixture_room, publish_event
from apps.core.permissions import Role, has_at_least

from . import services
from .calculators import statuses_for
from .models import CompetitionOfficial, ResultAmendment

User = get_user_model()
TAG = ["Results"]


def _competition(request: Request, pk):
    return get_object_or_404(visible_competitions(request.user), pk=pk)


def _fixture(request: Request, pk):
    from apps.fixtures.models import Fixture

    fixture = get_object_or_404(
        Fixture.objects.select_related("competition"),
        pk=pk,
        competition__in=visible_competitions(request.user),
    )
    if not services.result_type_of(fixture.competition):
        raise ValidationError(
            "This competition records results with score events, not a result sheet."
        )
    return fixture


def _person(user) -> str:
    if user is None:
        return ""
    return user.get_full_name() or user.display_name or ""


def _official_rows(competition) -> list[dict]:
    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "name": _person(row.user),
            "title": row.title,
            "title_label": row.get_title_display(),
        }
        for row in CompetitionOfficial.objects.filter(competition=competition).select_related(
            "user"
        )
    ]


class OfficialsView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(tags=TAG, summary="Stewards, judges, ground jury and vets", responses=dict)
    def get(self, request: Request, pk) -> Response:
        competition = _competition(request, pk)
        return Response(
            {
                "officials": _official_rows(competition),
                "required": services.officials_required(competition),
                "titles": [
                    {"key": key, "label": label} for key, label in CompetitionOfficial.Title.choices
                ],
                "can_manage": has_at_least(competition, request.user, Role.ADMIN),
                "i_am_official": services.is_official(competition, request.user),
            }
        )

    @extend_schema(
        tags=TAG, summary="Appoint an official (owner and admins)", request=dict, responses=dict
    )
    def post(self, request: Request, pk) -> Response:
        competition = _competition(request, pk)
        if not has_at_least(competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only the owner and admins appoint officials.")
        person = User.objects.filter(pk=request.data.get("user"), is_active=True).first()
        if person is None:
            raise ValidationError({"user": "Choose a profile on Fair Measure."})
        title = request.data.get("title") or CompetitionOfficial.Title.STEWARD
        if title not in CompetitionOfficial.Title.values:
            raise ValidationError({"title": "Choose one of the official titles."})
        _, created = CompetitionOfficial.objects.get_or_create(
            competition=competition,
            user=person,
            title=title,
            defaults={"appointed_by": request.user},
        )
        if not created:
            raise ValidationError({"user": "They already hold that role here."})
        return Response({"officials": _official_rows(competition)}, status=status.HTTP_201_CREATED)


class OfficialDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Remove an official", request=None, responses=dict)
    def delete(self, request: Request, pk, official_id) -> Response:
        competition = _competition(request, pk)
        if not has_at_least(competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only the owner and admins remove officials.")
        get_object_or_404(CompetitionOfficial, pk=official_id, competition=competition).delete()
        return Response({"officials": _official_rows(competition)})


class EventCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Create an event (race, class, ride) with its entrants",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, pk) -> Response:
        competition = _competition(request, pk)
        if not services.result_type_of(competition):
            raise ValidationError("This competition schedules matches, not events.")
        if not has_at_least(competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only the owner and admins create events.")
        label = str(request.data.get("label") or "").strip()
        if not label:
            raise ValidationError({"label": "Name the event."})
        config = request.data.get("config")
        if config is not None:
            config = services.clean_event_config(competition, config)
        fixture = services.create_event(
            competition,
            label=label,
            scheduled_at=request.data.get("scheduled_at") or None,
            participant_ids=request.data.get("participant_ids") or None,
            actor=request.user,
        )
        if config:
            sheet = fixture.result_sheet
            sheet.config = config
            sheet.save(update_fields=["config", "updated_at"])
        return Response(_sheet_payload(fixture, request.user), status=status.HTTP_201_CREATED)


def _riders(participant, config: dict) -> list[str]:
    """Who rides for a team entrant: its roster, or numbered places up to the team size."""

    size = int(config.get("team_size") or 0)
    if not size:
        return []
    names = list(
        participant.roster.filter(is_active=True).order_by("number", "name").values_list("name", flat=True)
    )[:size]
    return names + [f"Rider {index}" for index in range(len(names) + 1, size + 1)]


def _combination(participant) -> dict | None:
    combo = getattr(participant, "combination", None)
    if combo is None:
        return None
    return {
        "horse_id": str(combo.horse_id),
        "horse": combo.horse.name,
        "rider": combo.rider_label,
        "trainer": combo.trainer_label,
    }


def _sheet_payload(fixture, viewer) -> dict:
    from apps.horses.models import Combination  # noqa: F401 - reverse relation below

    services.ensure_sheet(fixture)
    entries = services.recompute(fixture)
    sheet = fixture.result_sheet
    competition = fixture.competition
    config = services.sheet_config(fixture)
    settings = competition.settings_json or {}
    rows = []
    for entry in sorted(entries, key=lambda item: item.breakdown.get("order", 0)):
        participant = entry.side.participant
        rows.append(
            {
                "side_id": str(entry.side_id),
                "participant_id": str(participant.id),
                "name": participant.name,
                "combination": _combination(participant),
                "riders": _riders(participant, config),
                "data": entry.data,
                "status": entry.status,
                "status_reason": entry.status_reason,
                "computed_status": entry.computed_status,
                "effective_status": entry.effective_status,
                "welfare_locked": entry.welfare_locked,
                "rank": entry.rank,
                "primary": str(entry.primary) if entry.primary is not None else None,
                "breakdown": entry.breakdown,
            }
        )
    amendments = [
        {
            "id": str(row.id),
            "action": row.action,
            "action_label": row.get_action_display(),
            "reason": row.reason,
            "actor": _person(row.actor),
            "entrant": row.side.participant.name if row.side_id and row.side else "",
            "before": row.before,
            "after": row.after,
            "created_at": row.created_at,
        }
        for row in ResultAmendment.objects.filter(fixture=fixture).select_related(
            "actor", "side__participant"
        )[:100]
    ]
    return {
        "fixture": {
            "id": str(fixture.id),
            "competition_id": str(competition.id),
            "label": fixture.label,
            "status": fixture.status,
            "scheduled_at": fixture.scheduled_at,
        },
        "result_type": services.result_type_of(competition),
        "config": config,
        "statuses": statuses_for(config),
        "placing_points": settings.get("placing_points") or [],
        "final": sheet.is_final,
        "finalised_at": sheet.finalised_at,
        "finalised_by": _person(sheet.finalised_by),
        "permissions": {
            "can_record": services.can_record(fixture, viewer)
            or services.can_decide(competition, viewer),
            "can_decide": services.can_decide(competition, viewer),
            "officials_required": services.officials_required(competition),
        },
        "entries": rows,
        "amendments": amendments,
    }


def _broadcast(fixture) -> None:
    publish_event(
        "fixture.updated",
        {"fixture_id": str(fixture.id), "competition_id": str(fixture.competition_id)},
        [competition_room(fixture.competition_id), fixture_room(fixture.id)],
    )


class ResultSheetView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=TAG, summary="An event's result sheet, ranking and amendment log", responses=dict
    )
    def get(self, request: Request, pk) -> Response:
        return Response(_sheet_payload(_fixture(request, pk), request.user))

    @extend_schema(
        tags=TAG,
        summary="Save results (provisional, or an official amendment with a reason)",
        description=(
            "Body: {entries: [{side, data}], config?: {...event settings}, reason?}. "
            "Once the result is final, only officials may change it and a reason is required."
        ),
        request=dict,
        responses=dict,
    )
    def put(self, request: Request, pk) -> Response:
        fixture = _fixture(request, pk)
        services.save_results(
            fixture,
            request.data.get("entries") or [],
            request.user,
            reason=str(request.data.get("reason") or ""),
            config=request.data.get("config"),
        )
        _broadcast(fixture)
        return Response(_sheet_payload(fixture, request.user))


class ResultStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Eliminate, retire, withdraw or disqualify an entrant (officials)",
        description="Body: {side, status, reason, welfare?}. A welfare elimination is final.",
        request=dict,
        responses=dict,
    )
    def post(self, request: Request, pk) -> Response:
        fixture = _fixture(request, pk)
        services.set_status(
            fixture,
            request.data.get("side"),
            str(request.data.get("status") or ""),
            request.user,
            reason=str(request.data.get("reason") or ""),
            welfare=bool(request.data.get("welfare")),
        )
        _broadcast(fixture)
        return Response(_sheet_payload(fixture, request.user))


class ResultFinaliseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG, summary="Finalise the result (officials)", request=dict, responses=dict
    )
    def post(self, request: Request, pk) -> Response:
        fixture = _fixture(request, pk)
        services.finalise(fixture, request.user, reason=str(request.data.get("reason") or ""))
        _broadcast(fixture)
        return Response(_sheet_payload(fixture, request.user))


class CombinationStatsView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=TAG,
        summary="Series results per horse, rider or trainer",
        parameters=[OpenApiParameter("by", str, description="horse | rider | trainer")],
        responses=dict,
    )
    def get(self, request: Request, pk) -> Response:
        competition = _competition(request, pk)
        by = request.query_params.get("by") or "horse"
        if by not in {"horse", "rider", "trainer"}:
            raise ValidationError({"by": "Use horse, rider or trainer."})
        return Response({"by": by, "rows": services.combination_stats(competition, by)})
