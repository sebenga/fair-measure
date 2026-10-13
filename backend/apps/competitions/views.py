from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Prefetch, Q, QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.bus import Queues, competition_room, enqueue_job, publish_event
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
)
from .presets import PRESETS, SCORING_LOCKED_MESSAGE, apply_preset, public_preset, scoring_is_locked
from .serializers import (
    ApplyPresetSerializer,
    CompetitionDetailSerializer,
    CompetitionListSerializer,
    CompetitionWriteSerializer,
    MembershipSerializer,
    ParticipantSerializer,
    add_profile_to_team,
    PointsPolicySerializer,
    RosterMemberSerializer,
    RuleSerializer,
    ScoringCategorySerializer,
    StageSerializer,
    TransferOwnershipSerializer,
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
                "scoring_categories", "rules", "stages", "participants__roster"
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

        latest = (
            Fixture.objects.filter(competition=competition)
            .order_by("-round_number")
            .values_list("round_number", flat=True)
            .first()
        )
        if latest is None:
            raise ValidationError("There is no round to advance.")
        current = list(
            Fixture.objects.filter(competition=competition, round_number=latest).order_by(
                "created_at"
            )
        )
        winners = round_winners(current)
        if not winners:
            raise ValidationError("Every match in this round needs a winner first.")
        if len(winners) < 2:
            return Response({"advanced": False, "detail": "The bracket is complete."})

        pairs, bye = pair_advancers(winners)
        created = []
        with transaction.atomic():
            for home_id, away_id in pairs:
                fixture = Fixture.objects.create(
                    competition=competition,
                    round_number=(latest or 0) + 1,
                    status=Fixture.Status.SCHEDULED,
                )
                FixtureSide.objects.create(
                    fixture=fixture, participant_id=home_id, position=0, is_home=True
                )
                FixtureSide.objects.create(
                    fixture=fixture, participant_id=away_id, position=1, is_home=False
                )
                created.append(str(fixture.id))
            if bye is not None and pairs:
                # A bye waits in the following round against the next winner.
                fixture = Fixture.objects.create(
                    competition=competition,
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

    def _assert_can_write(self) -> None:
        participant = self.get_participant()
        if participant.managed_by_id == self.request.user.id:
            return
        if not has_at_least(participant.competition, self.request.user, Role.ADMIN):
            raise PermissionDenied("You cannot change this roster.")

    def perform_create(self, serializer) -> None:
        self._assert_can_write()
        participant = self.get_participant()
        member = serializer.validated_data.get("user")
        if participant.kind == Participant.Kind.TEAM:
            if member is None:
                raise ValidationError({"user": "A team is made up of profiles."})
            serializer.instance = add_profile_to_team(
                participant, member, self.request.user, field="user"
            )
            return
        serializer.save(participant=participant)

    def perform_update(self, serializer) -> None:
        self._assert_can_write()
        serializer.save()

    def perform_destroy(self, instance) -> None:
        self._assert_can_write()
        participant = instance.participant
        if (
            participant.kind == Participant.Kind.TEAM
            and participant.roster.filter(is_active=True).count() <= 2
        ):
            raise ValidationError("A team keeps at least two profiles.")
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
