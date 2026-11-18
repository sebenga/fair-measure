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
from apps.competitions.serializers import squad_size_for, team_entry_mode
from apps.competitions.views import visible_competitions
from apps.core.bus import (
    Queues,
    competition_room,
    enqueue_job,
    fixture_room,
    publish_event,
)
from apps.core.permissions import Role, has_at_least

from .models import Fixture, FixtureReferee, ScoreEvent
from .serializers import (
    BulkScoreEventSerializer,
    FixtureDetailSerializer,
    FixtureListSerializer,
    FixtureStatusSerializer,
    FixtureWriteSerializer,
    GenerateFixturesSerializer,
    ScoreAssistSerializer,
    ScoreEventSerializer,
    save_minutes,
)


def user_can_score_fixture(fixture: Fixture, user) -> bool:
    """Live scoring is referee-only; after full time admins may file corrections."""

    from .officials import user_can_score_fixture as _can

    return _can(fixture, user)


def _assert_can_finalise(fixture: Fixture, user) -> None:
    """Where officials sign off results, only they may end a game."""

    from apps.results.services import assert_can_decide, officials_required

    if officials_required(fixture.competition):
        assert_can_decide(fixture.competition, user)


def _scores(fixture: Fixture) -> dict:
    return {
        side.participant.name: {"score": str(side.score), "outcome": side.outcome}
        for side in fixture.sides.select_related("participant")
    }


def _official_reason(fixture: Fixture, request: Request) -> str | None:
    """In competitions whose results are official, a counted match changes only by an
    official, and only with a reason. Returns the reason, or None when no rule applies."""

    from apps.results.services import assert_can_decide, officials_required

    if not officials_required(fixture.competition) or not fixture.is_counted:
        return None
    assert_can_decide(fixture.competition, request.user)
    reason = str(
        request.data.get("amendment_reason") or request.query_params.get("amendment_reason") or ""
    ).strip()
    if not reason:
        raise ValidationError({"amendment_reason": "Give a reason for amending a final result."})
    return reason


def _log_amendment(fixture: Fixture, request: Request, reason: str, before: dict, action="amended"):
    from apps.results.models import ResultAmendment

    ResultAmendment.objects.create(
        fixture=fixture,
        actor=request.user,
        action=action,
        reason=reason[:500],
        before=before,
        after=_scores(fixture),
    )


def _results_changed(fixture: Fixture) -> None:
    """Tell listeners (such as Games medals) the counted results may have moved."""

    from apps.core.signals import results_changed

    results_changed.send(sender=Fixture, competition=fixture.competition)


def _assert_ready_for_kickoff(fixture: Fixture) -> None:
    problems = fixture.kickoff_problems()
    if problems:
        raise ValidationError(" ".join(problems))


from apps.competitions.presets import format_allowed

from .services import (
    ScheduleOptions,
    award_criterion,
    award_criterion_round,
    generate_knockout,
    generate_league_and_knockout,
    generate_round_robin,
    record_result,
)


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
            .prefetch_related(
                "sides__participant",
                "sides__lineup__entries",
                "referees",
                "events__scoring_category",
                "ratings__player",
            )
        )
        params = self.request.query_params
        if participant_id := params.get("participant"):
            queryset = queryset.filter(sides__participant_id=participant_id)
        if params.get("upcoming") in {"1", "true", "yes"}:
            queryset = queryset.filter(status__in=[Fixture.Status.SCHEDULED, Fixture.Status.LIVE])
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
            raise PermissionDenied(
                "Only the appointed referee (or a delegated official) can run this match."
            )

    def _assert_is_admin(self) -> None:
        if not has_at_least(self.get_competition(), self.request.user, Role.ADMIN):
            raise PermissionDenied("Only competition admins can do that.")

    def perform_create(self, serializer) -> None:
        self._assert_is_admin()
        serializer.save(competition=self.get_competition(), created_by=self.request.user)
        self._broadcast(serializer.instance, "fixture.created")

    def perform_update(self, serializer) -> None:
        # Match clock / duration stays an admin setup concern; live scoring is referee-only.
        if {"duration_minutes", "overtime_minutes"} & set(serializer.validated_data):
            self._assert_is_admin()
        else:
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
        _results_changed(fixture)
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
        from apps.competitions.demo import demo_is_active

        if demo_is_active(competition):
            # The demo schedules itself; a second run would lay another season on top.
            raise ValidationError(
                "This demo already has its whole schedule. Create your own competition to "
                "generate one."
            )

        serializer = GenerateFixturesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        participants_qs = competition.participants.filter(is_active=True)
        if data.get("participant_ids"):
            participants_qs = participants_qs.filter(id__in=data["participant_ids"])
        participants = list(participants_qs.order_by("seed", "name"))

        if len(participants) < 2:
            raise ValidationError("Add at least two participants before generating fixtures.")

        if data["method"] == "knockout":
            scheduled_as = "knockout"
        elif data["method"] == "league_knockout":
            scheduled_as = "league_knockout"
        else:
            scheduled_as = "league"
        if not format_allowed(competition.settings_json, scheduled_as):
            raise ValidationError(
                f"This kind of competition cannot be scheduled as a {scheduled_as.replace('_', ' ')}."
            )

        if team_entry_mode(competition) in {"pick", "draft"}:
            needed = squad_size_for(competition)
            short = [
                participant.name
                for participant in participants
                if participant.roster.filter(is_active=True).count() < needed
            ]
            if short:
                names = ", ".join(short)
                needed_as = "accepted" if team_entry_mode(competition) == "pick" else "drafted"
                raise ValidationError(
                    f"Each team needs {needed} {needed_as} players before a schedule. Still short: {names}."
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
            cup_every_league_rounds=data.get("cup_every_league_rounds") or 0,
        )
        if data.get("cups") is not None:
            from apps.competitions.cups import normalize_cup_names, persist_cup_names

            persist_cup_names(competition, normalize_cup_names(data["cups"]))

        with transaction.atomic():
            # Postgres runs requests in parallel, so a double tap or an entrant removed
            # mid-request would otherwise point fixtures at rows that no longer exist.
            type(competition).objects.select_for_update().filter(pk=competition.pk).first()
            still_there = set(
                competition.participants.filter(
                    is_active=True, pk__in=[row.pk for row in participants]
                ).values_list("pk", flat=True)
            )
            participants = [row for row in participants if row.pk in still_there]
            if len(participants) < 2:
                raise ValidationError("Add at least two participants before generating fixtures.")
            if data["replace_existing"]:
                # Completed fixtures carry results, so they are left alone.
                competition.fixtures.filter(
                    status__in=[Fixture.Status.SCHEDULED, Fixture.Status.POSTPONED]
                ).delete()

            if data["method"] == "knockout":
                created = generate_knockout(competition, participants, options)
            elif data["method"] == "league_knockout":
                created = generate_league_and_knockout(competition, participants, options)
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
        from apps.results.services import is_official

        fixture = self.get_object()
        if not is_official(fixture.competition, request.user):
            self._assert_can_score()

        serializer = FixtureStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        if new_status == Fixture.Status.LIVE and fixture.status == Fixture.Status.SCHEDULED:
            _assert_ready_for_kickoff(fixture)
        if new_status == Fixture.Status.COMPLETED and fixture.status == Fixture.Status.LIVE:
            from .phases import assert_can_complete

            assert_can_complete(fixture)
        self._change_status(fixture, request, new_status)
        return Response(FixtureDetailSerializer(fixture).data)

    def _change_status(self, fixture: Fixture, request: Request, new_status: str) -> None:
        """Move a fixture to a new status: officials, amendment log, feed posts and season end."""

        from apps.results.services import assert_can_decide, officials_required

        official = officials_required(fixture.competition)
        reopening = fixture.is_counted and new_status not in {
            Fixture.Status.COMPLETED,
            Fixture.Status.CONFIRMED,
            Fixture.Status.FORFEIT,
        }
        reason = ""
        if official and (
            new_status
            in {Fixture.Status.COMPLETED, Fixture.Status.CONFIRMED, Fixture.Status.FORFEIT}
            or reopening
        ):
            # Only the officials finalise or reopen a result.
            assert_can_decide(fixture.competition, request.user)
            if reopening:
                reason = str(request.data.get("amendment_reason") or "").strip()
                if not reason:
                    raise ValidationError(
                        {"amendment_reason": "Give a reason for reopening a final result."}
                    )
        before = _scores(fixture) if official else {}

        with transaction.atomic():
            fixture.status = new_status
            if reopening:
                # A reopened result is corrected by hand, outside the half-by-half flow.
                fixture.phase = ""
                fixture.confirmed_at = None
                fixture.confirmed_by = None
            if new_status == Fixture.Status.LIVE and fixture.started_at is None:
                fixture.started_at = timezone.now()
            if new_status in {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}:
                fixture.completed_at = timezone.now()
                fixture.recalculate_scores()
                # Phase 1: auto sign-off so standings and season close keep working.
                # Phase 2 replaces this with an explicit referee match-card action
                # that moves status to confirmed.
                fixture.confirmed_at = timezone.now()
                fixture.confirmed_by = request.user
            fixture.save(
                update_fields=[
                    "status",
                    "phase",
                    "started_at",
                    "completed_at",
                    "confirmed_at",
                    "confirmed_by",
                    "updated_at",
                ]
            )
            if new_status in {
                Fixture.Status.LIVE,
                Fixture.Status.COMPLETED,
                Fixture.Status.CONFIRMED,
            }:
                from .matchday import sync_minutes

                sync_minutes(fixture)
            if official and (
                new_status
                in {Fixture.Status.COMPLETED, Fixture.Status.CONFIRMED, Fixture.Status.FORFEIT}
                or reopening
            ):
                _log_amendment(
                    fixture,
                    request,
                    reason,
                    before,
                    action="reopened" if reopening else "finalised",
                )

        self._broadcast(fixture, f"fixture.{new_status}")
        if new_status == Fixture.Status.LIVE:
            from apps.social.live import publish_kickoff

            publish_kickoff(fixture)
        if (
            new_status
            in {Fixture.Status.COMPLETED, Fixture.Status.CONFIRMED, Fixture.Status.FORFEIT}
            or reopening
        ):
            from .discipline import sync_roster_discipline

            sync_roster_discipline(fixture)
        if new_status in {
            Fixture.Status.COMPLETED,
            Fixture.Status.CONFIRMED,
            Fixture.Status.FORFEIT,
        }:
            from apps.social.live import publish_full_time

            publish_full_time(fixture)
            from apps.competitions.season import maybe_finish_competition

            if maybe_finish_competition(fixture.competition):
                publish_event(
                    "competition.updated",
                    {"competition_id": str(fixture.competition_id)},
                    [competition_room(fixture.competition_id)],
                )

    @extend_schema(
        tags=["Fixtures"],
        summary="Move a timed game on: kick off, end a half, start the second half, end the game",
        request=dict,
        responses={200: FixtureDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="phase")
    def phase(self, request: Request, **kwargs) -> Response:
        from . import phases

        fixture = self.get_object()
        self._assert_can_score()
        action_name = str(request.data.get("action") or "")
        with transaction.atomic():
            fixture = Fixture.objects.select_for_update().get(pk=fixture.pk)
            target = phases.next_phase(fixture, action_name)
            if action_name == "kick_off":
                _assert_ready_for_kickoff(fixture)
            if target == phases.FULL_TIME:
                _assert_can_finalise(fixture, request.user)
            fixture.phase = target
            fixture.save(update_fields=["phase", "updated_at"])
        if action_name == "kick_off":
            self._change_status(fixture, request, Fixture.Status.LIVE)
        elif target == phases.FULL_TIME:
            self._change_status(fixture, request, Fixture.Status.COMPLETED)
        else:
            self._broadcast(fixture, "fixture.updated")
        fixture.refresh_from_db()
        return Response(FixtureDetailSerializer(fixture).data)

    @extend_schema(
        tags=["Fixtures"],
        summary="Record a penalty shootout kick, or undo the last one",
        request=dict,
        responses={200: FixtureDetailSerializer},
    )
    @action(detail=True, methods=["post", "delete"], url_path="shootout")
    def shootout(self, request: Request, **kwargs) -> Response:
        from . import phases

        fixture = self.get_object()
        self._assert_can_score()
        with transaction.atomic():
            fixture = Fixture.objects.select_for_update().get(pk=fixture.pk)
            if request.method == "DELETE":
                phases.undo_kick(fixture)
            else:
                _assert_can_finalise(fixture, request.user)
                phases.add_kick(
                    fixture,
                    str(request.data.get("side") or ""),
                    str(request.data.get("player") or ""),
                    bool(request.data.get("scored")),
                )
            decided = phases.shootout_winner(fixture) is not None
            if decided:
                fixture.phase = phases.FULL_TIME
                fixture.save(update_fields=["phase", "updated_at"])
        if decided:
            self._change_status(fixture, request, Fixture.Status.COMPLETED)
        else:
            self._broadcast(fixture, "fixture.updated")
        fixture.refresh_from_db()
        return Response(FixtureDetailSerializer(fixture).data)

    @extend_schema(
        tags=["Fixtures"],
        summary="Referee signs the digital match card and confirms the result",
        request=dict,
        responses={200: FixtureDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request: Request, **kwargs) -> Response:
        from .officials import accepted_referee, log_match_action

        fixture = self.get_object()
        referee = accepted_referee(fixture)
        is_ref = referee is not None and referee.user_id == request.user.id
        if not is_ref and not has_at_least(fixture.competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only the accepted referee (or an admin stand-in) can sign the match card.")
        notes = str(request.data.get("notes") or "").strip()
        with transaction.atomic():
            fixture = Fixture.objects.select_for_update().get(pk=fixture.pk)
            if fixture.status not in {
                Fixture.Status.COMPLETED,
                Fixture.Status.LIVE,
                Fixture.Status.CONFIRMED,
            }:
                raise ValidationError({"status": "Confirm the match after full time."})
            if fixture.status == Fixture.Status.LIVE:
                fixture.phase = "full_time"
                fixture.completed_at = timezone.now()
            fixture.mark_confirmed(user=request.user, notes=notes)
            log_match_action(
                fixture=fixture,
                user=request.user,
                action="match.confirmed",
                detail=notes,
                source="referee" if is_ref else "admin",
            )
        from apps.competitions.season import maybe_finish_competition

        maybe_finish_competition(fixture.competition)
        enqueue_job(
            Queues.STANDINGS,
            "recompute",
            {"competition_id": str(fixture.competition_id)},
        )
        self._broadcast(fixture, "fixture.confirmed")
        fixture.refresh_from_db()
        return Response(FixtureDetailSerializer(fixture).data)

    @extend_schema(
        tags=["Fixtures"],
        summary="Raise or resolve a dispute on a confirmed match",
        request=dict,
        responses={200: dict},
    )
    @action(detail=True, methods=["post"], url_path="dispute")
    def dispute(self, request: Request, **kwargs) -> Response:
        from datetime import timedelta

        from .models import MatchDispute
        from .officials import log_match_action

        fixture = self.get_object()
        action_name = str(request.data.get("action") or "raise")
        if action_name == "raise":
            if fixture.status not in {Fixture.Status.CONFIRMED, Fixture.Status.COMPLETED}:
                raise ValidationError({"status": "Only a finished match can be disputed."})
            window_hours = int(
                (fixture.competition.settings_json or {}).get("dispute_window_hours") or 24
            )
            signed = fixture.confirmed_at or fixture.completed_at or fixture.updated_at
            if signed and timezone.now() - signed > timedelta(hours=window_hours):
                raise ValidationError({"reason": f"The {window_hours}h dispute window has closed."})
            reason = str(request.data.get("reason") or "").strip()
            if len(reason) < 8:
                raise ValidationError({"reason": "Explain why you are disputing the result."})
            if not has_at_least(fixture.competition, request.user, Role.MEMBER):
                raise PermissionDenied("Only competition members can raise a dispute.")
            row = MatchDispute.objects.create(
                fixture=fixture, raised_by=request.user, reason=reason[:4000]
            )
            fixture.status = Fixture.Status.DISPUTED
            fixture.save(update_fields=["status", "updated_at"])
            log_match_action(
                fixture=fixture,
                user=request.user,
                action="match.disputed",
                detail=reason,
                payload={"dispute_id": str(row.id)},
            )
            return Response({"id": str(row.id), "status": row.status}, status=status.HTTP_201_CREATED)

        if action_name == "resolve":
            if not has_at_least(fixture.competition, request.user, Role.ADMIN):
                raise PermissionDenied("Only an admin can resolve a dispute.")
            dispute_id = request.data.get("dispute_id")
            row = get_object_or_404(MatchDispute, pk=dispute_id, fixture=fixture)
            decision = str(request.data.get("decision") or "").strip()
            if decision not in {MatchDispute.Status.UPHELD, MatchDispute.Status.REJECTED}:
                raise ValidationError({"decision": "Choose upheld or rejected."})
            row.status = decision
            row.resolved_by = request.user
            row.resolution_note = str(request.data.get("note") or "")[:4000]
            row.resolved_at = timezone.now()
            row.save()
            fixture.status = (
                Fixture.Status.SCHEDULED
                if decision == MatchDispute.Status.UPHELD
                else Fixture.Status.CONFIRMED
            )
            if fixture.status == Fixture.Status.CONFIRMED and fixture.confirmed_at is None:
                fixture.confirmed_at = timezone.now()
            fixture.save(update_fields=["status", "confirmed_at", "updated_at"])
            log_match_action(
                fixture=fixture,
                user=request.user,
                action="match.dispute_resolved",
                detail=decision,
                payload={"dispute_id": str(row.id)},
            )
            return Response({"id": str(row.id), "status": row.status})

        raise ValidationError({"action": "Use raise or resolve."})


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
            raise PermissionDenied(
                "Only the appointed referee (or a delegated official) can record live events."
            )

    def _after_change(self, event_name: str, extra: dict | None = None) -> None:
        fixture = self.get_fixture()
        fixture.refresh_from_db()
        if fixture.is_counted:
            _results_changed(fixture)
            from .discipline import sync_roster_discipline

            sync_roster_discipline(fixture)
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
        from .officials import LIVE_STATUSES, assert_can_live_score, log_match_action

        fixture = self.get_fixture()
        reason = _official_reason(fixture, self.request)
        source = str(self.request.data.get("source") or "").strip()
        if fixture.status in LIVE_STATUSES or fixture.status == Fixture.Status.POSTPONED:
            assert_can_live_score(fixture, self.request.user)
            if not source:
                source = ScoreEvent.Source.REFEREE
        elif reason is None:
            self._assert_can_score()
            if has_at_least(fixture.competition, self.request.user, Role.ADMIN) and not fixture.referees.filter(
                user=self.request.user, status=FixtureReferee.Status.ACCEPTED
            ).exists():
                source = ScoreEvent.Source.ADMIN_CORRECTION
                if not reason and not str(self.request.data.get("note") or "").strip():
                    raise ValidationError(
                        {"note": "Admin corrections need a short reason in the note."}
                    )
        before = _scores(fixture) if reason else {}
        went_live = fixture.status == Fixture.Status.SCHEDULED
        if went_live:
            _assert_ready_for_kickoff(fixture)
        with transaction.atomic():
            event = serializer.save(
                fixture=fixture,
                recorded_by=self.request.user,
                source=source or ScoreEvent.Source.REFEREE,
            )
            from .cards import reconcile_cards

            reconcile_cards(fixture, event.player_id)
            if went_live:
                fixture.status = Fixture.Status.LIVE
                if fixture.started_at is None:
                    fixture.started_at = timezone.now()
                fixture.save(update_fields=["status", "started_at", "updated_at"])
            fixture.recalculate_scores()
            if reason:
                _log_amendment(fixture, self.request, reason, before)
            log_match_action(
                fixture=fixture,
                user=self.request.user,
                action="event.recorded",
                detail=str(event.scoring_category_id),
                source=event.source,
                payload={"event_id": str(event.id)},
            )
        self._after_change("score.recorded", {"event_id": str(serializer.instance.id)})
        if went_live:
            from apps.social.live import publish_kickoff

            publish_kickoff(fixture)
        from apps.social.live import publish_score_event

        publish_score_event(serializer.instance)

    def perform_update(self, serializer) -> None:
        fixture = self.get_fixture()
        reason = _official_reason(fixture, self.request)
        if reason is None:
            self._assert_can_score()
        before = _scores(fixture) if reason else {}
        with transaction.atomic():
            serializer.save()
            from .cards import reconcile_cards

            reconcile_cards(fixture, serializer.instance.player_id)
            fixture.recalculate_scores()
            if reason:
                _log_amendment(fixture, self.request, reason, before)
        self._after_change("score.corrected", {"event_id": str(serializer.instance.id)})

    def perform_destroy(self, instance: ScoreEvent) -> None:
        fixture = self.get_fixture()
        reason = _official_reason(fixture, self.request)
        if reason is None:
            self._assert_can_score()
        before = _scores(fixture) if reason else {}
        event_id = str(instance.id)
        with transaction.atomic():
            player_id = instance.player_id
            instance.delete()
            from .cards import reconcile_cards

            reconcile_cards(fixture, player_id)
            fixture.recalculate_scores()
            if reason:
                _log_amendment(fixture, self.request, reason, before)
        self._after_change("score.removed", {"event_id": event_id})

    @extend_schema(
        tags=["Scoring"],
        summary="Record several score events at once",
        request=BulkScoreEventSerializer,
        responses={201: ScoreEventSerializer(many=True)},
    )
    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk(self, request: Request, **kwargs) -> Response:
        fixture = self.get_fixture()
        reason = _official_reason(fixture, request)
        if reason is None:
            self._assert_can_score()
        before = _scores(fixture) if reason else {}
        went_live = fixture.status == Fixture.Status.SCHEDULED
        if fixture.status == Fixture.Status.SCHEDULED:
            _assert_ready_for_kickoff(fixture)

        serializer = BulkScoreEventSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        pending_minutes = []
        rows = []
        for item in serializer.validated_data["events"]:
            item.pop("rating", None)
            minutes = item.pop("minutes", None)
            event = ScoreEvent(fixture=fixture, recorded_by=request.user, **item)
            rows.append(event)
            pending_minutes.append((event, minutes))

        with transaction.atomic():
            created = ScoreEvent.objects.bulk_create(rows)
            for event, minutes in pending_minutes:
                save_minutes(event, minutes)
            from .cards import reconcile_cards

            for event in created:
                reconcile_cards(fixture, event.player_id)
            fixture.recalculate_scores()
            if reason:
                _log_amendment(fixture, request, reason, before)

        self._after_change("score.recorded", {"count": len(created)})
        if went_live:
            from apps.social.live import publish_kickoff

            publish_kickoff(fixture)
        from apps.social.live import publish_score_event

        for event in created:
            publish_score_event(event)
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
                    "fixture_id": str(event.fixture_id),
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
        serializer = ScoreAssistSerializer(data=request.data, context={"competition": competition})
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
            if data["kind"] == "criterion_round":
                result = award_criterion_round(
                    competition=competition,
                    category=data["scoring_category"],
                    entries=data["entries"],
                    note=data["note"].strip(),
                    user=request.user,
                )
                self._publish_table(competition)
                return Response(
                    {
                        "count": result["count"],
                        "awarded": str(result["awarded"]),
                        "note": data["note"].strip(),
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
        return Response(
            {"id": str(fixture.id), "label": fixture.label}, status=status.HTTP_201_CREATED
        )


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
        from .officials import appoint_official, log_match_action

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
        role = str(request.data.get("role") or FixtureReferee.Role.REFEREE)
        stand_in = bool(request.data.get("stand_in"))
        note = str(request.data.get("note") or "")
        if stand_in and not note.strip():
            note = "Admin stand-in appointment."
        official = appoint_official(
            fixture=fixture,
            user=user,
            role=role,
            appointed_by=request.user,
            stand_in=stand_in,
            note=note,
        )
        # Stand-ins appointed by admin are accepted immediately so the match can start.
        if stand_in and official.status != FixtureReferee.Status.ACCEPTED:
            official.status = FixtureReferee.Status.ACCEPTED
            official.responded_at = timezone.now()
            official.save(update_fields=["status", "responded_at", "updated_at"])
        log_match_action(
            fixture=fixture,
            user=request.user,
            action="official.appointed",
            detail=f"{role} → {user.get_full_name() or user.email}",
            source="admin",
            payload={"official_id": str(official.id), "stand_in": stand_in},
        )
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


class RefereeAppointmentRespondView(APIView):
    """Accept or decline an appointment as the appointed official."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, appointment_pk) -> Response:
        from .officials import log_match_action, respond_to_appointment

        official = get_object_or_404(
            FixtureReferee.objects.select_related("fixture", "user"), pk=appointment_pk
        )
        accept = bool(request.data.get("accept", True))
        respond_to_appointment(official, user=request.user, accept=accept)
        log_match_action(
            fixture=official.fixture,
            user=request.user,
            action="official.accepted" if accept else "official.declined",
            detail=official.role,
            source="referee",
        )
        return Response(
            {
                "id": str(official.id),
                "status": official.status,
                "fixture_id": str(official.fixture_id),
                "role": official.role,
            }
        )


class RefereeDashboardView(APIView):
    """Upcoming appointments, today's matches, and reports waiting for sign-off."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from django.utils.timezone import localdate

        today = localdate()
        rows = (
            FixtureReferee.objects.filter(user=request.user)
            .select_related("fixture", "fixture__competition")
            .order_by("fixture__scheduled_at", "created_at")
        )
        pending = []
        upcoming = []
        today_matches = []
        to_sign = []
        for row in rows:
            fixture = row.fixture
            item = {
                "appointment_id": str(row.id),
                "fixture_id": str(fixture.id),
                "competition_id": str(fixture.competition_id),
                "competition": fixture.competition.name,
                "label": fixture.label or str(fixture),
                "role": row.role,
                "status": row.status,
                "scheduled_at": fixture.scheduled_at,
                "fixture_status": fixture.status,
            }
            if row.status == FixtureReferee.Status.INVITED:
                pending.append(item)
            if row.status != FixtureReferee.Status.ACCEPTED:
                continue
            if fixture.status in {Fixture.Status.SCHEDULED, Fixture.Status.LIVE}:
                upcoming.append(item)
                if fixture.scheduled_at and fixture.scheduled_at.date() == today:
                    today_matches.append(item)
            if fixture.status == Fixture.Status.COMPLETED and fixture.confirmed_at is None:
                to_sign.append(item)
            elif fixture.status == Fixture.Status.COMPLETED and row.role == FixtureReferee.Role.REFEREE:
                # Phase 1 auto-confirms; still list recent completed for the report.
                if fixture.confirmed_by_id == request.user.id or fixture.confirmed_at:
                    to_sign.append({**item, "signed": True})
        return Response(
            {
                "pending": pending,
                "upcoming": upcoming,
                "today": today_matches,
                "reports": to_sign[:40],
            }
        )
