from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.models import Competition, Membership, Stage
from apps.competitions.serializers import MIN_TEAM_PLAYERS, team_entry_mode
from apps.competitions.views import visible_competitions
from apps.core.bus import (
    Queues,
    competition_room,
    enqueue_job,
    fixture_room,
    publish_event,
)
from apps.core.permissions import Role, has_at_least

from .models import Fixture, FixtureReferee, PlayerMatchRating, ScoreEvent
from .serializers import (
    BulkScoreEventSerializer,
    FixtureDetailSerializer,
    FixtureListSerializer,
    FixtureStatusSerializer,
    FixtureWriteSerializer,
    GenerateFixturesSerializer,
    ScoreAssistSerializer,
    ScoreEventSerializer,
)


def user_can_score_fixture(fixture: Fixture, user) -> bool:
    """Owners and admins can score any game. A named referee scores that game.

    Until a game has a referee, a league scorer can still record it.
    """
    if has_at_least(fixture.competition, user, Role.ADMIN):
        return True
    if fixture.referees.filter(user=user).exists():
        return True
    if fixture.referees.exists():
        return False
    return has_at_least(fixture.competition, user, Role.SCORER)


from .services import ScheduleOptions, award_criterion, generate_knockout, generate_round_robin, record_result


def _fixture_payload(fixture: Fixture) -> dict:
    """The compact shape pushed over Socket.io when a score changes."""

    return {
        "fixture_id": str(fixture.id),
        "competition_id": str(fixture.competition_id),
        "status": fixture.status,
        "sides": [
            {
                "id": str(side.id),
                "participant_id": str(side.participant_id),
                "name": side.participant.name,
                "score": str(side.score),
                "outcome": side.outcome,
            }
            for side in fixture.sides.select_related("participant")
        ],
    }


@extend_schema_view(
    list=extend_schema(
        tags=["Fixtures"],
        summary="List fixtures",
        parameters=[
            OpenApiParameter("status", str, description="scheduled | live | completed | ..."),
            OpenApiParameter("stage", str, description="Filter by stage id."),
            OpenApiParameter("participant", str, description="Filter by participant id."),
            OpenApiParameter("upcoming", bool, description="Only fixtures still to be played."),
        ],
    ),
    retrieve=extend_schema(tags=["Fixtures"], summary="Get a fixture with its event timeline"),
    create=extend_schema(tags=["Fixtures"], summary="Create a fixture"),
    partial_update=extend_schema(tags=["Fixtures"], summary="Update a fixture"),
    destroy=extend_schema(tags=["Fixtures"], summary="Delete a fixture"),
)
class FixtureViewSet(viewsets.ModelViewSet):
    # Real filtering happens in get_queryset(); this is the base the schema
    # generator and DRF's router introspect for the model and lookup type.
    queryset = Fixture.objects.none()
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_fields = ["status", "stage", "round_number"]
    ordering_fields = ["scheduled_at", "round_number", "created_at"]

    def get_competition(self) -> Competition:
        if not hasattr(self, "_competition"):
            self._competition = get_object_or_404(
                visible_competitions(self.request.user), pk=self.kwargs["competition_pk"]
            )
        return self._competition

    def get_serializer_context(self) -> dict:
        return {**super().get_serializer_context(), "competition": self.get_competition()}

    def get_queryset(self):
        queryset = (
            Fixture.objects.filter(competition=self.get_competition())
            .select_related("stage")
            .prefetch_related("sides__participant")
        )
        params = self.request.query_params
        if participant_id := params.get("participant"):
            queryset = queryset.filter(sides__participant_id=participant_id)
        if params.get("upcoming") in {"1", "true", "yes"}:
            queryset = queryset.filter(
                status__in=[Fixture.Status.SCHEDULED, Fixture.Status.LIVE]
            )
        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                "events__scoring_category",
                "events__player",
                "ratings__player",
                "referees__user",
            )
        return queryset.distinct()

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return FixtureWriteSerializer
        if self.action == "retrieve":
            return FixtureDetailSerializer
        return FixtureListSerializer

    def _assert_can_score(self) -> None:
        if not user_can_score_fixture(self.get_object(), self.request.user):
            raise PermissionDenied("You need to be an admin or this game's referee to score it.")

    def _assert_is_admin(self) -> None:
        if not has_at_least(self.get_competition(), self.request.user, Role.ADMIN):
            raise PermissionDenied("Only competition admins can do that.")

    def perform_create(self, serializer) -> None:
        self._assert_is_admin()
        serializer.save(
            competition=self.get_competition(), created_by=self.request.user
        )
        self._broadcast(serializer.instance, "fixture.created")

    def perform_update(self, serializer) -> None:
        self._assert_can_score()
        serializer.save()
        self._broadcast(serializer.instance, "fixture.updated")

    def perform_destroy(self, instance: Fixture) -> None:
        self._assert_is_admin()
        competition_id = instance.competition_id
        fixture_id = instance.id
        instance.delete()
        publish_event(
            "fixture.deleted",
            {"fixture_id": str(fixture_id), "competition_id": str(competition_id)},
            [competition_room(competition_id)],
        )
        enqueue_job(Queues.STANDINGS, "recompute", {"competition_id": str(competition_id)})

    def _broadcast(self, fixture: Fixture, event: str) -> None:
        publish_event(
            event,
            _fixture_payload(fixture),
            [competition_room(fixture.competition_id), fixture_room(fixture.id)],
        )
        if fixture.is_counted:
            enqueue_job(
                Queues.STANDINGS,
                "recompute",
                {"competition_id": str(fixture.competition_id)},
            )

    @extend_schema(
        tags=["Fixtures"],
        summary="Generate a fixture list",
        description=(
            "Builds a round-robin or knockout schedule across the competition's "
            "match weekdays, starting from the given date."
        ),
        request=GenerateFixturesSerializer,
        responses={201: FixtureListSerializer(many=True)},
    )
    @action(detail=False, methods=["post"])
    def generate(self, request: Request, competition_pk: str | None = None) -> Response:
        self._assert_is_admin()
        competition = self.get_competition()

        serializer = GenerateFixturesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        participants_qs = competition.participants.filter(is_active=True)
        if data.get("participant_ids"):
            participants_qs = participants_qs.filter(id__in=data["participant_ids"])
        participants = list(participants_qs.order_by("seed", "name"))

        if len(participants) < 2:
            raise ValidationError("Add at least two participants before generating fixtures.")

        if team_entry_mode(competition) in {"pick", "draft"}:
            short = [
                participant.name
                for participant in participants
                if participant.roster.filter(is_active=True).count() < MIN_TEAM_PLAYERS
            ]
            if short:
                names = ", ".join(short)
                raise ValidationError(
                    f"Each team needs {MIN_TEAM_PLAYERS} accepted players before a schedule. Still short: {names}."
                )

        stage = None
        if data.get("stage_id"):
            stage = get_object_or_404(Stage, pk=data["stage_id"], competition=competition)

        options = ScheduleOptions(
            starts_on=data["starts_on"],
            weekdays=data.get("weekdays") or competition.match_weekdays or [],
            kickoff=data["kickoff"],
            minutes_between_fixtures=data["minutes_between_fixtures"],
            double_round=data["double_round"],
            location=data.get("location", ""),
            stage=stage,
        )

        with transaction.atomic():
            if data["replace_existing"]:
                # Completed fixtures carry results, so they are left alone.
                competition.fixtures.filter(
                    status__in=[Fixture.Status.SCHEDULED, Fixture.Status.POSTPONED]
                ).delete()

            if data["method"] == "knockout":
                created = generate_knockout(competition, participants, options)
            else:
                created = generate_round_robin(competition, participants, options)

        publish_event(
            "fixtures.generated",
            {"competition_id": str(competition.id), "count": len(created)},
            [competition_room(competition.id)],
        )
        enqueue_job(
            Queues.NOTIFICATIONS,
            "fixtures-published",
            {"competition_id": str(competition.id), "count": len(created)},
        )

        queryset = (
            Fixture.objects.filter(id__in=[f.id for f in created])
            .prefetch_related("sides__participant")
            .order_by("scheduled_at", "round_number")
        )
        return Response(
            FixtureListSerializer(queryset, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Fixtures"],
        summary="Change a fixture's status",
        request=FixtureStatusSerializer,
        responses={200: FixtureDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request: Request, **kwargs) -> Response:
        self._assert_can_score()
        fixture = self.get_object()

        serializer = FixtureStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        with transaction.atomic():
            fixture.status = new_status
            if new_status == Fixture.Status.LIVE and fixture.started_at is None:
                fixture.started_at = timezone.now()
            if new_status in {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}:
                fixture.completed_at = timezone.now()
                fixture.recalculate_scores()
            fixture.save(update_fields=["status", "started_at", "completed_at", "updated_at"])

        self._broadcast(fixture, f"fixture.{new_status}")
        return Response(FixtureDetailSerializer(fixture).data)


@extend_schema_view(
    list=extend_schema(tags=["Scoring"], summary="List a fixture's score events"),
    create=extend_schema(tags=["Scoring"], summary="Record a score event"),
    partial_update=extend_schema(tags=["Scoring"], summary="Correct a score event"),
    destroy=extend_schema(tags=["Scoring"], summary="Remove a score event"),
)
class ScoreEventViewSet(viewsets.ModelViewSet):
    queryset = ScoreEvent.objects.none()
    serializer_class = ScoreEventSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_fixture(self) -> Fixture:
        if not hasattr(self, "_fixture"):
            self._fixture = get_object_or_404(
                Fixture.objects.select_related("competition"),
                pk=self.kwargs["fixture_pk"],
                competition__in=visible_competitions(self.request.user),
            )
        return self._fixture

    def get_serializer_context(self) -> dict:
        return {**super().get_serializer_context(), "fixture": self.get_fixture()}

    def get_queryset(self):
        return ScoreEvent.objects.filter(fixture=self.get_fixture()).select_related(
            "scoring_category", "player", "side__participant"
        )

    def _assert_can_score(self) -> None:
        if not user_can_score_fixture(self.get_fixture(), self.request.user):
            raise PermissionDenied("You need to be an admin or this game's referee to score it.")

    def _after_change(self, event_name: str, extra: dict | None = None) -> None:
        fixture = self.get_fixture()
        fixture.refresh_from_db()
        payload = {**_fixture_payload(fixture), **(extra or {})}
        publish_event(
            event_name,
            payload,
            [competition_room(fixture.competition_id), fixture_room(fixture.id)],
        )
        if fixture.is_counted:
            enqueue_job(
                Queues.STANDINGS,
                "recompute",
                {"competition_id": str(fixture.competition_id)},
            )

    def perform_create(self, serializer) -> None:
        self._assert_can_score()
        fixture = self.get_fixture()
        with transaction.atomic():
            serializer.save(fixture=fixture, recorded_by=self.request.user)
            fixture.recalculate_scores()
        self._after_change("score.recorded", {"event_id": str(serializer.instance.id)})

    def perform_update(self, serializer) -> None:
        self._assert_can_score()
        with transaction.atomic():
            serializer.save()
            self.get_fixture().recalculate_scores()
        self._after_change("score.corrected", {"event_id": str(serializer.instance.id)})

    def perform_destroy(self, instance: ScoreEvent) -> None:
        self._assert_can_score()
        event_id = str(instance.id)
        with transaction.atomic():
            instance.delete()
            self.get_fixture().recalculate_scores()
        self._after_change("score.removed", {"event_id": event_id})

    @extend_schema(
        tags=["Scoring"],
        summary="Record several score events at once",
        request=BulkScoreEventSerializer,
        responses={201: ScoreEventSerializer(many=True)},
    )
    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk(self, request: Request, **kwargs) -> Response:
        self._assert_can_score()
        fixture = self.get_fixture()

        serializer = BulkScoreEventSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        pending_ratings = []
        rows = []
        for item in serializer.validated_data["events"]:
            rating = item.pop("rating", None)
            event = ScoreEvent(fixture=fixture, recorded_by=request.user, **item)
            rows.append(event)
            pending_ratings.append((event, rating))

        with transaction.atomic():
            created = ScoreEvent.objects.bulk_create(rows)
            for event, rating in pending_ratings:
                if rating is None or event.player_id is None:
                    continue
                PlayerMatchRating.objects.update_or_create(
                    fixture=fixture,
                    player_id=event.player_id,
                    defaults={"rating": rating},
                )
            fixture.recalculate_scores()

        self._after_change("score.recorded", {"count": len(created)})
        return Response(
            ScoreEventSerializer(created, many=True).data, status=status.HTTP_201_CREATED
        )


class ScoreAssistView(APIView):
    """Lets a scorer award criteria or record a win, draw, or loss."""

    permission_classes = [IsAuthenticated]

    def _competition(self, request: Request, competition_pk: str) -> Competition:
        competition = get_object_or_404(visible_competitions(request.user), pk=competition_pk)
        if not has_at_least(competition, request.user, Role.SCORER):
            raise PermissionDenied("Only a scorer, admin, or owner can record scores.")
        return competition

    def _publish_table(self, competition: Competition) -> None:
        publish_event(
            "standings.updated",
            {"competition_id": str(competition.id)},
            [competition_room(competition.id)],
        )

    @extend_schema(tags=["Scoring"], summary="Recent scoring entries for administrators")
    def get(self, request: Request, competition_pk: str) -> Response:
        competition = self._competition(request, competition_pk)
        events = (
            ScoreEvent.objects.filter(fixture__competition=competition)
            .select_related("scoring_category", "side__participant")
            .order_by("-created_at")[:40]
        )
        return Response(
            [
                {
                    "id": str(event.id),
                    "participant_id": str(event.side.participant_id),
                    "participant_name": event.side.participant.name,
                    "criterion": event.scoring_category.name,
                    "description": event.scoring_category.description,
                    "quantity": str(event.quantity),
                    "awarded": str(event.points),
                    "note": event.note,
                    "created_at": event.created_at,
                }
                for event in events
            ]
        )

    @extend_schema(
        tags=["Scoring"],
        summary="Award a scoring criterion or record a win, draw, or loss",
        request=ScoreAssistSerializer,
        responses={201: dict},
    )
    def post(self, request: Request, competition_pk: str) -> Response:
        competition = self._competition(request, competition_pk)
        serializer = ScoreAssistSerializer(
            data=request.data, context={"competition": competition}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            if data["kind"] == "criterion":
                event = award_criterion(
                    competition=competition,
                    participant=data["participant"],
                    category=data["scoring_category"],
                    quantity=data["quantity"],
                    note=data["note"].strip(),
                    user=request.user,
                )
                self._publish_table(competition)
                return Response(
                    {
                        "id": str(event.id),
                        "awarded": str(event.points),
                        "note": event.note,
                    },
                    status=status.HTTP_201_CREATED,
                )
            fixture = record_result(
                competition=competition,
                home=data["home"],
                away=data["away"],
                outcome=data["outcome"],
                note=data.get("note", "").strip(),
                user=request.user,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        self._publish_table(competition)
        return Response({"id": str(fixture.id), "label": fixture.label}, status=status.HTTP_201_CREATED)


class FixtureRefereeView(APIView):
    permission_classes = [IsAuthenticated]

    def _fixture(self, request: Request, competition_pk, fixture_pk) -> Fixture:
        return get_object_or_404(
            Fixture.objects.select_related("competition"),
            pk=fixture_pk,
            competition_id=competition_pk,
            competition__in=visible_competitions(request.user),
        )

    def post(self, request: Request, competition_pk, fixture_pk):
        fixture = self._fixture(request, competition_pk, fixture_pk)
        if not has_at_least(fixture.competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only an admin can choose the referee.")
        user_id = request.data.get("user")
        if not user_id:
            raise ValidationError({"user": "Choose a profile."})
        user = get_object_or_404(get_user_model(), pk=user_id)
        if not Membership.objects.filter(competition=fixture.competition, user=user).exists():
            Membership.objects.create(
                competition=fixture.competition,
                user=user,
                role=Role.MEMBER,
                invited_by=request.user,
            )
        FixtureReferee.objects.get_or_create(fixture=fixture, user=user)
        fixture = Fixture.objects.prefetch_related("referees__user").get(pk=fixture.pk)
        return Response(FixtureDetailSerializer(fixture).data, status=status.HTTP_201_CREATED)

    def delete(self, request: Request, competition_pk, fixture_pk):
        fixture = self._fixture(request, competition_pk, fixture_pk)
        if not has_at_least(fixture.competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only an admin can change the referee.")
        user_id = request.query_params.get("user")
        if not user_id:
            raise ValidationError({"user": "Choose a referee to remove."})
        FixtureReferee.objects.filter(fixture=fixture, user_id=user_id).delete()
        fixture = Fixture.objects.prefetch_related("referees__user").get(pk=fixture.pk)
        return Response(FixtureDetailSerializer(fixture).data)
