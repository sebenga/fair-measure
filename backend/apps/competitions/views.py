from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from decimal import Decimal

from django.db.models import Count, Prefetch, Q, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.bus import Queues, competition_room, enqueue_job, publish_event
from apps.fixtures.models import Fixture, PlayerMatchRating, ScoreEvent
from apps.core.permissions import (
    IsCompetitionAdminOrReadOnly,
    Role,
    has_at_least,
)

from .models import (
    Competition,
    Membership,
    Participant,
    PointsPolicy,
    RosterMember,
    Rule,
    ScoringCategory,
    Stage,
    TeamPick,
)
from .presets import PRESETS, SCORING_LOCKED_MESSAGE, apply_preset, public_preset, scoring_is_locked
from .serializers import (
    squad_size_for,
    ApplyPresetSerializer,
    CompetitionDetailSerializer,
    CompetitionListSerializer,
    CompetitionWriteSerializer,
    MembershipSerializer,
    ParticipantSerializer,
    TeamPickSerializer,
    accept_team_pick,
    decline_team_pick,
    draft_payload,
    next_draft_team,
    offer_team_pick,
    team_entry_mode,
    PointsPolicySerializer,
    RosterMemberSerializer,
    RuleSerializer,
    ScoringCategorySerializer,
    StageSerializer,
    TransferOwnershipSerializer,
    NextSeasonSerializer,
)

User = get_user_model()


def visible_competitions(user) -> QuerySet[Competition]:
    """Public competitions, plus any private ones the user belongs to."""

    queryset = Competition.objects.select_related("owner")
    if not user or not user.is_authenticated:
        return queryset.filter(is_private=False)
    return queryset.filter(
        Q(is_private=False) | Q(owner=user) | Q(memberships__user=user)
    ).distinct()


@extend_schema_view(
    list=extend_schema(
        tags=["Competitions"],
        summary="List competitions you can see",
        parameters=[
            OpenApiParameter(
                "sport", str, description="Filter by type, e.g. rugby, KPIs, cleaning."
            ),
            OpenApiParameter("status", str, description="draft | active | completed | archived"),
            OpenApiParameter("mine", bool, description="Only competitions you are a member of."),
            OpenApiParameter("search", str, description="Search name, description and sport."),
        ],
    ),
    retrieve=extend_schema(tags=["Competitions"], summary="Get one competition in full"),
    create=extend_schema(tags=["Competitions"], summary="Create a competition"),
    partial_update=extend_schema(tags=["Competitions"], summary="Update a competition"),
    update=extend_schema(tags=["Competitions"], summary="Replace a competition"),
    destroy=extend_schema(tags=["Competitions"], summary="Delete a competition"),
)
class CompetitionViewSet(viewsets.ModelViewSet):
    queryset = Competition.objects.none()
    permission_classes = [IsAuthenticatedOrReadOnly, IsCompetitionAdminOrReadOnly]
    lookup_field = "pk"
    filterset_fields = ["sport", "status", "format", "is_private"]
    search_fields = ["name", "description", "sport"]
    ordering_fields = ["created_at", "name", "starts_on"]
    # An explicit default keeps pagination stable across pages.
    ordering = ["-created_at"]

    def get_queryset(self) -> QuerySet[Competition]:
        queryset = visible_competitions(self.request.user).annotate(
            participant_count=Count("participants", distinct=True)
        )
        if self.request.query_params.get("mine") in {"1", "true", "yes"}:
            queryset = queryset.filter(
                Q(owner=self.request.user) | Q(memberships__user=self.request.user)
            ).distinct()
        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                "scoring_categories",
                "rules",
                "stages",
                "participants__roster",
                "participants__picks",
            ).select_related("points_policy")
        return queryset

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return CompetitionWriteSerializer
        if self.action == "retrieve":
            return CompetitionDetailSerializer
        return CompetitionListSerializer

    def perform_destroy(self, instance: Competition) -> None:
        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("Only the owner can delete a competition.")
        # A logged point protects its scoring category so that criterion cannot
        # be removed on its own. Deleting the league removes that history too.
        from apps.fixtures.models import ScoreEvent

        with transaction.atomic():
            ScoreEvent.objects.filter(scoring_category__competition=instance).delete()
            instance.delete()

    @extend_schema(
        tags=["Competitions"],
        summary="List starting points for a competition",
        responses={200: dict},
    )
    @action(detail=False, methods=["get"], permission_classes=[])
    def presets(self, request: Request) -> Response:
        return Response([public_preset(key, preset) for key, preset in PRESETS.items()])

    @extend_schema(
        tags=["Competitions"],
        summary="Apply a starting-point preset to an existing competition",
        request=ApplyPresetSerializer,
        responses={200: CompetitionDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="apply-preset")
    def apply_preset(self, request: Request, pk: str | None = None) -> Response:
        competition = self.get_object()
        serializer = ApplyPresetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if scoring_is_locked(competition):
            raise PermissionDenied(SCORING_LOCKED_MESSAGE)

        with transaction.atomic():
            if serializer.validated_data["replace_existing"]:
                competition.scoring_categories.all().delete()
                competition.rules.all().delete()
            apply_preset(competition, serializer.validated_data["preset"])

        competition.refresh_from_db()
        return Response(
            CompetitionDetailSerializer(competition, context=self.get_serializer_context()).data
        )

    @extend_schema(
        tags=["Competitions"],
        summary="Advance knockout winners into the next round",
        responses={201: dict},
    )
    @action(detail=True, methods=["post"], url_path="advance")
    def advance(self, request: Request, pk: str | None = None) -> Response:
        from apps.fixtures.models import Fixture, FixtureSide

        from .engine import pair_advancers, round_winners

        competition = self.get_object()
        if not has_at_least(competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only competition admins can advance a bracket.")
        if competition.format not in {"knockout", "league_knockout"}:
            raise ValidationError("Only knockout competitions have a bracket to advance.")

        cup_stage = None
        if competition.format == "league_knockout":
            cup_stage = competition.stages.filter(kind="knockout").order_by("display_order").first()
        cup_fixtures = Fixture.objects.filter(competition=competition)
        if cup_stage is not None:
            cup_fixtures = cup_fixtures.filter(stage=cup_stage)

        latest = (
            cup_fixtures.order_by("-round_number")
            .values_list("round_number", flat=True)
            .first()
        )
        if latest is None:
            raise ValidationError("There is no round to advance.")
        current = list(
            cup_fixtures.filter(round_number=latest).order_by("created_at")
        )
        winners = round_winners(current)
        if not winners:
            raise ValidationError("Every match in this round needs a winner first.")
        if len(winners) < 2:
            return Response({"advanced": False, "detail": "The bracket is complete."})

        reserved = list((competition.settings_json or {}).get("cup_slot_datetimes") or [])
        raw_kickoff = reserved.pop(0) if reserved else None
        next_kickoff = parse_datetime(raw_kickoff) if isinstance(raw_kickoff, str) else raw_kickoff
        pairs, bye = pair_advancers(winners)
        created = []
        with transaction.atomic():
            for home_id, away_id in pairs:
                fixture = Fixture.objects.create(
                    competition=competition,
                    stage=cup_stage,
                    round_number=(latest or 0) + 1,
                    label=f"Cup round {(latest or 0) + 1}",
                    scheduled_at=next_kickoff,
                    status=Fixture.Status.SCHEDULED,
                )
                FixtureSide.objects.create(
                    fixture=fixture, participant_id=home_id, position=0, is_home=True
                )
                FixtureSide.objects.create(
                    fixture=fixture, participant_id=away_id, position=1, is_home=False
                )
                created.append(str(fixture.id))
            if reserved or next_kickoff is not None:
                settings = dict(competition.settings_json or {})
                settings["cup_slot_datetimes"] = reserved
                competition.settings_json = settings
                competition.save(update_fields=["settings_json", "updated_at"])
            if bye is not None and pairs:
                # A bye waits in the following round against the next winner.
                fixture = Fixture.objects.create(
                    competition=competition,
                    stage=cup_stage,
                    round_number=(latest or 0) + 1,
                    label="Bye",
                    status=Fixture.Status.COMPLETED,
                )
                side = FixtureSide.objects.create(
                    fixture=fixture, participant_id=bye, position=0, is_home=True
                )
                side.outcome = FixtureSide.Outcome.WIN
                side.save(update_fields=["outcome", "updated_at"])
                created.append(str(fixture.id))

        return Response(
            {"advanced": True, "round_number": (latest or 0) + 1, "fixtures": created},
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Competitions"],
        summary="Transfer ownership to another member",
        request=TransferOwnershipSerializer,
        responses={200: CompetitionDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="transfer-ownership")
    def transfer_ownership(self, request: Request, pk: str | None = None) -> Response:
        competition = self.get_object()
        if competition.owner_id != request.user.id:
            raise PermissionDenied("Only the current owner can transfer ownership.")

        serializer = TransferOwnershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_owner = get_object_or_404(User, pk=serializer.validated_data["user_id"])

        with transaction.atomic():
            previous_owner_id = competition.owner_id
            competition.owner = new_owner
            competition.save(update_fields=["owner"])
            Membership.objects.update_or_create(
                competition=competition, user=new_owner, defaults={"role": Role.OWNER}
            )
            Membership.objects.filter(
                competition=competition, user_id=previous_owner_id
            ).update(role=Role.ADMIN)

        publish_event(
            "competition.updated",
            {"competition_id": str(competition.id), "owner_id": str(new_owner.id)},
            [competition_room(competition.id)],
        )
        return Response(
            CompetitionDetailSerializer(competition, context=self.get_serializer_context()).data
        )

    @extend_schema(
        tags=["Competitions"],
        summary="Join a public competition",
        request=None,
        responses={201: MembershipSerializer},
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request: Request, pk: str | None = None) -> Response:
        competition = get_object_or_404(visible_competitions(request.user), pk=pk)
        if competition.is_private:
            raise PermissionDenied("This competition is invite only.")

        membership, created = Membership.objects.get_or_create(
            competition=competition, user=request.user, defaults={"role": Role.MEMBER}
        )
        return Response(
            MembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Competitions"],
        summary="Schedule the next season or a knockout after the current one finishes",
        request=NextSeasonSerializer,
        responses={201: dict},
    )
    @action(detail=True, methods=["post"], url_path="next-season")
    def next_season(self, request: Request, pk: str | None = None) -> Response:
        competition = self.get_object()
        if not has_at_least(competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only competition admins can schedule the next season.")

        serializer = NextSeasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from .season import schedule_next

        stage, created = schedule_next(
            competition,
            kind=data["kind"],
            starts_on=data["starts_on"],
            kickoff=data["kickoff"],
            weekdays=data.get("weekdays"),
            minutes_between_fixtures=data["minutes_between_fixtures"],
            double_round=data["double_round"],
            location=data.get("location", ""),
            advance=data.get("advance"),
        )
        competition.refresh_from_db()
        publish_event(
            "fixtures.generated",
            {"competition_id": str(competition.id), "count": len(created), "stage_id": str(stage.id)},
            [competition_room(competition.id)],
        )
        publish_event(
            "competition.updated",
            {"competition_id": str(competition.id)},
            [competition_room(competition.id)],
        )
        enqueue_job(
            Queues.NOTIFICATIONS,
            "fixtures-published",
            {"competition_id": str(competition.id), "count": len(created)},
        )
        from apps.fixtures.serializers import FixtureListSerializer

        queryset = (
            Fixture.objects.filter(id__in=[item.id for item in created])
            .prefetch_related("sides__participant")
            .order_by("scheduled_at", "round_number")
        )
        return Response(
            {
                "stage": StageSerializer(stage).data,
                "fixtures": FixtureListSerializer(queryset, many=True).data,
                "competition": CompetitionDetailSerializer(
                    competition, context=self.get_serializer_context()
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(tags=["Competitions"], summary="Leave a competition", request=None)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def leave(self, request: Request, pk: str | None = None) -> Response:
        competition = get_object_or_404(visible_competitions(request.user), pk=pk)
        if competition.owner_id == request.user.id:
            raise ValidationError("Transfer ownership before leaving your own competition.")
        Membership.objects.filter(competition=competition, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CompetitionScopedViewSet(viewsets.ModelViewSet):
    """Base for everything nested under /competitions/{competition_pk}/."""

    permission_classes = [IsAuthenticatedOrReadOnly, IsCompetitionAdminOrReadOnly]
    minimum_write_role = Role.ADMIN

    def get_competition(self) -> Competition:
        if not hasattr(self, "_competition"):
            self._competition = get_object_or_404(
                visible_competitions(self.request.user),
                pk=self.kwargs["competition_pk"],
            )
        return self._competition

    def get_serializer_context(self) -> dict:
        return {**super().get_serializer_context(), "competition": self.get_competition()}

    def get_queryset(self):
        return self.queryset.filter(competition=self.get_competition())

    def _assert_can_write(self) -> None:
        if not has_at_least(self.get_competition(), self.request.user, self.minimum_write_role):
            raise PermissionDenied(
                f"You need {self.minimum_write_role} access to change this competition."
            )

    def perform_create(self, serializer) -> None:
        self._assert_can_write()
        serializer.save(competition=self.get_competition())
        self._announce("created", serializer.instance)

    def perform_update(self, serializer) -> None:
        self._assert_can_write()
        serializer.save()
        self._announce("updated", serializer.instance)

    def perform_destroy(self, instance) -> None:
        self._assert_can_write()
        instance.delete()

    def _announce(self, verb: str, instance) -> None:
        competition = self.get_competition()
        publish_event(
            f"{self.basename}.{verb}",
            {"competition_id": str(competition.id), "id": str(instance.id)},
            [competition_room(competition.id)],
        )


@extend_schema_view(
    list=extend_schema(tags=["Scoring"], summary="List a competition's scoring categories"),
    create=extend_schema(tags=["Scoring"], summary="Add a scoring category"),
    partial_update=extend_schema(tags=["Scoring"], summary="Update a scoring category"),
    destroy=extend_schema(tags=["Scoring"], summary="Delete a scoring category"),
)
class ScoringCategoryViewSet(CompetitionScopedViewSet):
    queryset = ScoringCategory.objects.all()
    serializer_class = ScoringCategorySerializer
    basename = "scoring_category"

    def _assert_scoring_editable(self) -> None:
        if scoring_is_locked(self.get_competition()):
            raise PermissionDenied(SCORING_LOCKED_MESSAGE)

    def perform_create(self, serializer) -> None:
        self._assert_scoring_editable()
        super().perform_create(serializer)

    def perform_update(self, serializer) -> None:
        self._assert_scoring_editable()
        super().perform_update(serializer)

    def perform_destroy(self, instance: ScoringCategory) -> None:
        self._assert_can_write()
        self._assert_scoring_editable()
        if instance.score_events.exists():
            raise ValidationError(
                "This category has recorded events. Set its points to 0 instead of "
                "deleting it, so past results stay accurate."
            )
        instance.delete()


@extend_schema_view(
    list=extend_schema(tags=["Rules"], summary="List a competition's rules"),
    create=extend_schema(tags=["Rules"], summary="Add a rule"),
    partial_update=extend_schema(tags=["Rules"], summary="Update a rule"),
    destroy=extend_schema(tags=["Rules"], summary="Delete a rule"),
)
class RuleViewSet(CompetitionScopedViewSet):
    queryset = Rule.objects.all()
    serializer_class = RuleSerializer
    basename = "rule"

    def _assert_rules_editable(self) -> None:
        if scoring_is_locked(self.get_competition()):
            raise PermissionDenied(SCORING_LOCKED_MESSAGE)

    def perform_create(self, serializer) -> None:
        self._assert_rules_editable()
        super().perform_create(serializer)

    def perform_update(self, serializer) -> None:
        self._assert_rules_editable()
        super().perform_update(serializer)

    def perform_destroy(self, instance: Rule) -> None:
        self._assert_can_write()
        self._assert_rules_editable()
        instance.delete()


@extend_schema_view(
    list=extend_schema(tags=["Competitions"], summary="List a competition's stages"),
    create=extend_schema(tags=["Competitions"], summary="Add a stage"),
)
class StageViewSet(CompetitionScopedViewSet):
    queryset = Stage.objects.all()
    serializer_class = StageSerializer
    basename = "stage"


@extend_schema_view(
    list=extend_schema(tags=["Participants"], summary="List participants"),
    create=extend_schema(tags=["Participants"], summary="Add a participant"),
    partial_update=extend_schema(tags=["Participants"], summary="Update a participant"),
    destroy=extend_schema(tags=["Participants"], summary="Remove a participant"),
)
class ParticipantViewSet(CompetitionScopedViewSet):
    queryset = Participant.objects.prefetch_related(
        Prefetch("roster", queryset=RosterMember.objects.select_related("user")),
        Prefetch("picks", queryset=TeamPick.objects.select_related("user")),
        "stages",
    )
    serializer_class = ParticipantSerializer
    basename = "participant"
    search_fields = ["name", "short_name"]

    def perform_create(self, serializer) -> None:
        self._assert_can_write()
        serializer.save(competition=self.get_competition())
        enqueue_job(
            Queues.SEARCH,
            "index-participant",
            {"participant_id": str(serializer.instance.id)},
        )
        self._announce("created", serializer.instance)


@extend_schema(
    tags=["Participants"],
    parameters=[
        OpenApiParameter(
            "competition_pk", OpenApiTypes.UUID, OpenApiParameter.PATH
        ),
        OpenApiParameter(
            "participant_pk", OpenApiTypes.UUID, OpenApiParameter.PATH
        ),
    ],
)
@extend_schema_view(
    list=extend_schema(summary="List a participant's roster"),
    create=extend_schema(summary="Add a roster member"),
)
class RosterMemberViewSet(viewsets.ModelViewSet):
    queryset = RosterMember.objects.none()
    serializer_class = RosterMemberSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_participant(self) -> Participant:
        return get_object_or_404(
            Participant.objects.select_related("competition"),
            pk=self.kwargs["participant_pk"],
            competition__in=visible_competitions(self.request.user),
        )

    def get_queryset(self):
        return RosterMember.objects.filter(participant=self.get_participant()).select_related("user")

    def get_serializer_context(self) -> dict:
        context = super().get_serializer_context()
        if "participant_pk" in self.kwargs:
            context["participant"] = self.get_participant()
        return context

    def _assert_can_write(self) -> None:
        participant = self.get_participant()
        if participant.managed_by_id == self.request.user.id:
            return
        if not has_at_least(participant.competition, self.request.user, Role.ADMIN):
            raise PermissionDenied("You cannot change this roster.")

    def perform_create(self, serializer) -> None:
        self._assert_can_write()
        participant = self.get_participant()
        if participant.kind == Participant.Kind.TEAM:
            raise ValidationError(
                {"user": "Pick the profile and wait for them to accept."}
            )
        serializer.save(participant=participant)

    def perform_update(self, serializer) -> None:
        self._assert_can_write()
        serializer.save()

    def perform_destroy(self, instance) -> None:
        self._assert_can_write()
        instance.delete()


@extend_schema_view(
    list=extend_schema(tags=["Members"], summary="List competition members"),
    create=extend_schema(tags=["Members"], summary="Invite a member by user id or email"),
    partial_update=extend_schema(tags=["Members"], summary="Change a member's role"),
    destroy=extend_schema(tags=["Members"], summary="Remove a member"),
)
class MembershipViewSet(CompetitionScopedViewSet):
    queryset = Membership.objects.select_related("user")
    serializer_class = MembershipSerializer
    basename = "membership"

    def perform_create(self, serializer) -> None:
        self._assert_can_write()
        competition = self.get_competition()
        data = serializer.validated_data

        if data.get("user_id"):
            user = get_object_or_404(User, pk=data["user_id"])
        else:
            user = User.objects.filter(email__iexact=data["email"]).first()
            if user is None:
                raise ValidationError(
                    {"email": "No Fair Measure account uses that email address yet."}
                )

        if Membership.objects.filter(competition=competition, user=user).exists():
            raise ValidationError("That person is already a member.")

        membership = Membership.objects.create(
            competition=competition,
            user=user,
            role=data.get("role", Role.MEMBER),
            invited_by=self.request.user,
        )
        serializer.instance = membership

        enqueue_job(
            Queues.NOTIFICATIONS,
            "competition-invite",
            {
                "user_id": str(user.id),
                "competition_id": str(competition.id),
                "competition_name": competition.name,
                "invited_by": self.request.user.get_full_name(),
            },
        )

    def perform_destroy(self, instance: Membership) -> None:
        self._assert_can_write()
        if instance.role == Role.OWNER:
            raise ValidationError("Transfer ownership before removing the owner.")
        instance.delete()

    def perform_update(self, serializer) -> None:
        self._assert_can_write()
        if serializer.instance.role == Role.OWNER:
            raise ValidationError("Transfer ownership before changing the owner's role.")
        serializer.save()


@extend_schema_view(
    get=extend_schema(tags=["Scoring"], summary="Get the points policy"),
    patch=extend_schema(tags=["Scoring"], summary="Update the points policy"),
)
class PointsPolicyView(generics.RetrieveUpdateAPIView):
    """A competition has exactly one points policy, so this is a singleton resource."""

    serializer_class = PointsPolicySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    http_method_names = ["get", "patch", "head", "options"]

    def get_competition(self) -> Competition:
        return get_object_or_404(
            visible_competitions(self.request.user), pk=self.kwargs["competition_pk"]
        )

    def get_object(self) -> PointsPolicy:
        policy, _ = PointsPolicy.objects.get_or_create(competition=self.get_competition())
        return policy

    def perform_update(self, serializer) -> None:
        competition = self.get_competition()
        if not has_at_least(competition, self.request.user, Role.ADMIN):
            raise PermissionDenied("Only competition admins can change the points policy.")
        if scoring_is_locked(competition):
            raise PermissionDenied(SCORING_LOCKED_MESSAGE)
        serializer.save()

        # Every row of the league table is derived from this policy.
        enqueue_job(Queues.STANDINGS, "recompute", {"competition_id": str(competition.id)})
        publish_event(
            "standings.stale",
            {"competition_id": str(competition.id)},
            [competition_room(competition.id)],
        )


class PlayerLeagueProfileView(APIView):
    """Bio, scoring timeline and per-game ratings for one profile in one league."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Competitions"], summary="A profile's bio, league stats and timeline")
    def get(self, request: Request, competition_pk, user_pk) -> Response:
        competition = get_object_or_404(visible_competitions(request.user), pk=competition_pk)
        person = get_object_or_404(User, pk=user_pk, is_active=True)
        roster = (
            RosterMember.objects.filter(participant__competition=competition, user=person)
            .select_related("participant")
            .first()
        )
        events = list(
            ScoreEvent.objects.filter(fixture__competition=competition, player__user=person)
            .select_related("scoring_category", "fixture", "side__participant")
            .order_by("-created_at")
        )
        ratings = PlayerMatchRating.objects.filter(
            fixture__competition=competition, player__user=person
        ).select_related("fixture")
        totals: dict[str, dict] = {}
        for event in events:
            code = event.scoring_category.code
            bucket = totals.setdefault(
                code,
                {
                    "category": event.scoring_category.name,
                    "count": Decimal("0"),
                    "points": Decimal("0"),
                    "affects_score": event.scoring_category.affects_score,
                },
            )
            bucket["count"] += event.quantity
            bucket["points"] += event.points
        return Response(
            {
                "profile": {
                    "id": str(person.id),
                    "display_name": person.get_full_name(),
                    "avatar_url": person.avatar_url,
                    "bio": person.bio,
                    "headline": person.headline,
                    "city": person.city,
                    "country": person.country,
                    "experience": person.experience,
                    "education": person.education,
                    "skills": person.skills,
                    "languages": person.languages,
                },
                "team": (
                    None
                    if roster is None
                    else {"id": str(roster.participant_id), "name": roster.participant.name}
                ),
                "totals": [
                    {
                        "category": bucket["category"],
                        "code": code,
                        "count": format(bucket["count"], "f"),
                        "points": format(bucket["points"], "f"),
                        "affects_score": bucket["affects_score"],
                    }
                    for code, bucket in totals.items()
                ],
                "timeline": [
                    {
                        "id": str(event.id),
                        "fixture_id": str(event.fixture_id),
                        "fixture_label": event.fixture.label or "Fixture",
                        "minute": event.minute,
                        "period": event.period,
                        "category": event.scoring_category.name,
                        "quantity": format(event.quantity, "f"),
                        "points": format(event.points, "f"),
                        "team": event.side.participant.name,
                        "occurred_at": event.occurred_at,
                        "created_at": event.created_at,
                    }
                    for event in events
                ],
                "ratings": [
                    {
                        "fixture_id": str(rating.fixture_id),
                        "fixture_label": rating.fixture.label or "Fixture",
                        "rating": format(rating.rating, "f"),
                        "scheduled_at": rating.fixture.scheduled_at,
                    }
                    for rating in ratings.order_by("-created_at")
                ],
            }
        )


def _visible_competition(request: Request, competition_pk):
    competition = get_object_or_404(Competition, pk=competition_pk)
    if not visible_competitions(request.user).filter(pk=competition.pk).exists():
        raise PermissionDenied("You cannot see this competition.")
    return competition


def _can_manage_team(request: Request, participant: Participant) -> bool:
    if participant.managed_by_id == request.user.id:
        return True
    return has_at_least(participant.competition, request.user, Role.ADMIN)


class TeamPickListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, competition_pk, participant_pk):
        competition = _visible_competition(request, competition_pk)
        participant = get_object_or_404(Participant, pk=participant_pk, competition=competition)
        picks = (
            TeamPick.objects.filter(participant=participant)
            .select_related("user", "participant__competition")
            .order_by("-created_at")
        )
        return Response(TeamPickSerializer(picks, many=True).data)

    def post(self, request: Request, competition_pk, participant_pk):
        competition = _visible_competition(request, competition_pk)
        participant = get_object_or_404(Participant, pk=participant_pk, competition=competition)
        if not _can_manage_team(request, participant):
            raise PermissionDenied("You cannot pick players for this team.")
        if team_entry_mode(competition) == "draft":
            needed = squad_size_for(competition)
            if participant.roster.filter(is_active=True).count() < needed:
                raise ValidationError(
                    {
                        "team_entry": (
                            f"Draft this team to {needed} players first. "
                            "Then you can add more as it grows."
                        )
                    }
                )
        user_id = request.data.get("user")
        if not user_id:
            raise ValidationError({"user": "Choose a profile."})
        user = get_object_or_404(get_user_model(), pk=user_id)
        pick = offer_team_pick(participant, user, request.user)
        return Response(TeamPickSerializer(pick).data, status=status.HTTP_201_CREATED)


def _pending_picks_for(user, competition=None):
    picks = TeamPick.objects.filter(user=user, status=TeamPick.Status.PENDING).select_related(
        "user", "participant__competition"
    )
    if competition is not None:
        picks = picks.filter(participant__competition=competition)
    return picks.order_by("-created_at")


def _own_team_pick(user, competition_pk, pick_pk) -> TeamPick:
    """The invited player can always answer their own pick, even on a private league."""

    return get_object_or_404(
        TeamPick.objects.select_related("participant__competition", "user"),
        pk=pick_pk,
        participant__competition_id=competition_pk,
        user=user,
    )


class MyPendingTeamPickListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request):
        return Response(TeamPickSerializer(_pending_picks_for(request.user), many=True).data)


class MyTeamPickListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, competition_pk):
        competition = _visible_competition(request, competition_pk)
        return Response(TeamPickSerializer(_pending_picks_for(request.user, competition), many=True).data)


class TeamPickAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, competition_pk, pick_pk):
        pick = _own_team_pick(request.user, competition_pk, pick_pk)
        accept_team_pick(pick, request.user)
        pick.refresh_from_db()
        return Response(TeamPickSerializer(pick).data)


class TeamPickDeclineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, competition_pk, pick_pk):
        pick = TeamPick.objects.select_related("participant__competition", "user").filter(
            pk=pick_pk, participant__competition_id=competition_pk
        ).first()
        if pick is None:
            raise PermissionDenied("You cannot see this competition.")
        if pick.user_id == request.user.id:
            decline_team_pick(pick, request.user)
        elif _can_manage_team(request, pick.participant):
            _visible_competition(request, competition_pk)
            if pick.status != TeamPick.Status.PENDING:
                raise ValidationError({"status": "This pick is already settled."})
            pick.status = TeamPick.Status.DECLINED
            pick.responded_at = timezone.now()
            pick.save(update_fields=["status", "responded_at", "updated_at"])
        else:
            raise PermissionDenied("Only the picked profile can decline.")
        pick.refresh_from_db()
        return Response(TeamPickSerializer(pick).data)


class TeamDraftView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, competition_pk):
        competition = _visible_competition(request, competition_pk)
        if team_entry_mode(competition) != "draft":
            raise ValidationError({"team_entry": "This competition picks teams directly."})
        return Response(draft_payload(competition))

    def post(self, request: Request, competition_pk):
        competition = _visible_competition(request, competition_pk)
        if team_entry_mode(competition) != "draft":
            raise ValidationError({"team_entry": "This competition picks teams directly."})
        if not has_at_least(competition, request.user, Role.ADMIN):
            raise PermissionDenied("You cannot run the draft.")
        user_id = request.data.get("user")
        if not user_id:
            raise ValidationError({"user": "Choose a profile to draft."})
        needed = squad_size_for(competition)
        team = next_draft_team(
            list(
                competition.participants.filter(kind=Participant.Kind.TEAM, is_active=True).order_by(
                    "name"
                )
            ),
            needed,
        )
        if team is None:
            raise ValidationError({"user": f"Every team already has {needed} players."})
        user = get_object_or_404(get_user_model(), pk=user_id)
        pick = offer_team_pick(team, user, request.user)
        return Response(
            {"pick": TeamPickSerializer(pick).data, **draft_payload(competition)},
            status=status.HTTP_201_CREATED,
        )
