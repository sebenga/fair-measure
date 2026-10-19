"""Horse registry API and combination entrants."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.models import Participant
from apps.competitions.views import visible_competitions
from apps.core.permissions import Role, has_at_least

from .models import Combination, Horse

User = get_user_model()
TAG = ["Horses"]


class HorseSerializer(serializers.ModelSerializer):
    trainer_label = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    owner_ids = serializers.PrimaryKeyRelatedField(
        source="owners", many=True, queryset=User.objects.filter(is_active=True), required=False
    )

    class Meta:
        model = Horse
        fields = [
            "id",
            "name",
            "registration_number",
            "fei_id",
            "breed",
            "sex",
            "colour",
            "foaled_on",
            "owner_ids",
            "owner_names",
            "trainer",
            "trainer_name",
            "trainer_label",
            "photo_url",
            "status",
            "can_edit",
            "created_at",
        ]
        read_only_fields = ["id", "trainer_label", "can_edit", "created_at"]

    def get_trainer_label(self, obj: Horse) -> str:
        if obj.trainer_id:
            return obj.trainer.get_full_name() or obj.trainer.display_name
        return obj.trainer_name

    def get_can_edit(self, obj: Horse) -> bool:
        request = self.context.get("request")
        return obj.can_edit(request.user) if request else False

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Give the horse's name.")
        return value


def _record(horse: Horse) -> dict:
    from apps.results.services import counted_entries

    starts = wins = seconds = thirds = 0
    competitions = set()
    for combo in horse.combinations.select_related("participant__competition"):
        competition = combo.participant.competition
        for entry, _ in counted_entries(competition):
            if entry.side.participant_id != combo.participant_id:
                continue
            competitions.add(competition.name)
            starts += 1
            wins += entry.rank == 1
            seconds += entry.rank == 2
            thirds += entry.rank == 3
    return {
        "starts": starts,
        "wins": wins,
        "seconds": seconds,
        "thirds": thirds,
        "competitions": sorted(competitions),
    }


class HorseListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Horses: mine by default, or search the registry",
        parameters=[
            OpenApiParameter("q", str, description="Search every active horse by name or number.")
        ],
        responses=HorseSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        query = (request.query_params.get("q") or "").strip()
        if query:
            horses = Horse.objects.filter(status=Horse.Status.ACTIVE).filter(
                Q(name__icontains=query)
                | Q(registration_number__iexact=query)
                | Q(fei_id__iexact=query)
            )[:30]
        else:
            horses = (
                Horse.objects.filter(
                    Q(created_by=request.user) | Q(owners=request.user) | Q(trainer=request.user)
                )
                .distinct()
                .order_by("name")
            )
        return Response(HorseSerializer(horses, many=True, context={"request": request}).data)

    @extend_schema(
        tags=TAG,
        summary="Register a horse",
        request=HorseSerializer,
        responses={201: HorseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = HorseSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        horse = serializer.save(created_by=request.user)
        return Response(
            HorseSerializer(horse, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class HorseDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="A horse and its record", responses=dict)
    def get(self, request: Request, pk) -> Response:
        horse = get_object_or_404(Horse, pk=pk)
        data = HorseSerializer(horse, context={"request": request}).data
        return Response({**data, "record": _record(horse)})

    @extend_schema(
        tags=TAG,
        summary="Edit a horse (registrar, owners, trainer)",
        request=HorseSerializer,
        responses=HorseSerializer,
    )
    def patch(self, request: Request, pk) -> Response:
        horse = get_object_or_404(Horse, pk=pk)
        if not horse.can_edit(request.user):
            raise PermissionDenied("Only the horse's owners, trainer or registrar can edit it.")
        serializer = HorseSerializer(
            horse, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


def _person(user_id):
    if not user_id:
        return None
    person = User.objects.filter(pk=user_id, is_active=True).first()
    if person is None:
        raise ValidationError("That profile was not found.")
    return person


class CombinationCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Enter a combination: a horse with its rider (and trainer)",
        description="Body: {horse, rider? (user id) | rider_name, trainer? | trainer_name?}.",
        request=dict,
        responses={201: dict},
    )
    @transaction.atomic
    def post(self, request: Request, pk) -> Response:
        competition = get_object_or_404(visible_competitions(request.user), pk=pk)
        if not has_at_least(competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only the owner and admins add entrants.")
        if (competition.settings_json or {}).get("participant_type") != "combination":
            raise ValidationError(
                "This competition's entrants are not horse-and-rider combinations."
            )
        horse = get_object_or_404(Horse, pk=request.data.get("horse"))
        if horse.status != Horse.Status.ACTIVE:
            raise ValidationError({"horse": "A retired horse cannot be entered."})
        rider = _person(request.data.get("rider"))
        rider_name = str(request.data.get("rider_name") or "").strip()
        if rider is None and not rider_name:
            raise ValidationError({"rider": "Choose the rider, or type their name."})
        trainer = _person(request.data.get("trainer"))
        trainer_name = str(request.data.get("trainer_name") or "").strip()
        if (
            Combination.objects.filter(participant__competition=competition, horse=horse)
            .filter(Q(rider=rider) if rider else Q(rider_name__iexact=rider_name))
            .exists()
        ):
            raise ValidationError("That horse and rider are already entered.")
        rider_label = (rider.get_full_name() or rider.display_name) if rider else rider_name
        name = str(request.data.get("name") or f"{horse.name} / {rider_label}")[:200]
        if competition.participants.filter(name=name).exists():
            raise ValidationError({"name": "An entrant already has that name."})
        participant = Participant.objects.create(
            competition=competition,
            name=name,
            kind=Participant.Kind.INDIVIDUAL,
            managed_by=rider,
        )
        combo = Combination.objects.create(
            participant=participant,
            horse=horse,
            rider=rider,
            rider_name="" if rider else rider_name,
            trainer=trainer,
            trainer_name="" if trainer else trainer_name,
        )
        return Response(
            {
                "participant_id": str(participant.id),
                "name": participant.name,
                "horse": horse.name,
                "rider": combo.rider_label,
                "trainer": combo.trainer_label,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(tags=TAG, summary="The competition's combinations", responses=dict)
    def get(self, request: Request, pk) -> Response:
        competition = get_object_or_404(visible_competitions(request.user), pk=pk)
        rows = Combination.objects.filter(participant__competition=competition).select_related(
            "participant", "horse", "rider", "trainer"
        )
        return Response(
            [
                {
                    "participant_id": str(row.participant_id),
                    "name": row.participant.name,
                    "horse_id": str(row.horse_id),
                    "horse": row.horse.name,
                    "rider": row.rider_label,
                    "trainer": row.trainer_label,
                }
                for row in rows
            ]
        )
