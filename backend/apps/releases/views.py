from __future__ import annotations

from django.db.models import Count, Q
from django.db.models.fields.json import KT
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.models import Competition
from apps.competitions.presets import PRESETS, public_preset

from .models import Release
from .services import (
    FEATURES,
    can_clear_leagues,
    feature_is_live,
    feature_map,
    is_platform_admin,
    set_live,
    sport_is_live,
)

COMPETITION_LIMIT = 100


class IsPlatformAdmin(BasePermission):
    message = "Only the platform admin can change what is released."

    def has_permission(self, request, view) -> bool:
        return is_platform_admin(request.user)


class CanClearLeagues(BasePermission):
    message = "Only the platform owner can clear every competition."

    def has_permission(self, request, view) -> bool:
        return can_clear_leagues(request.user)


class ReleaseStateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Platform"], summary="Features open to the public")
    def get(self, request: Request) -> Response:
        return Response(
            {
                "features": feature_map(),
                "platform_admin": is_platform_admin(request.user),
                "clear_leagues": can_clear_leagues(request.user),
            }
        )


def _preset_counts() -> dict[str, int]:
    rows = (
        Competition.objects.annotate(preset=KT("settings_json__preset"))
        .values("preset")
        .annotate(total=Count("id"))
    )
    return {row["preset"]: row["total"] for row in rows if row["preset"]}


def _catalogue() -> dict:
    counts = _preset_counts()
    sports = []
    for key, preset in PRESETS.items():
        row = public_preset(key, preset)
        sports.append(
            {
                "key": key,
                "label": row["label"],
                "icon": row["icon"],
                "kind": row["kind"],
                "group": row["group"] or row["kind"],
                "group_label": row["group_label"] or "Competition types",
                "family_label": row.get("family_label") or "",
                "live": sport_is_live(key),
                "competitions": counts.get(key, 0),
            }
        )
    features = [
        {
            "key": row["key"],
            "label": row["label"],
            "description": row["description"],
            "live": feature_is_live(row["key"]),
        }
        for row in FEATURES
    ]
    return {"features": features, "sports": sports}


class ReleaseUpdateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Release.Kind.choices)
    keys = serializers.ListField(child=serializers.CharField(max_length=80), min_length=1)
    live = serializers.BooleanField()

    def validate(self, attrs: dict) -> dict:
        if attrs["kind"] == Release.Kind.SPORT:
            known = set(PRESETS)
        else:
            known = {row["key"] for row in FEATURES}
        unknown = sorted(set(attrs["keys"]) - known)
        if unknown:
            raise serializers.ValidationError({"keys": f"Unknown: {', '.join(unknown[:5])}"})
        return attrs


class ReleaseAdminView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(tags=["Platform"], summary="Every sport and feature with its release state")
    def get(self, request: Request) -> Response:
        return Response(_catalogue())

    @extend_schema(
        tags=["Platform"],
        summary="Release or hide sports or features",
        request=ReleaseUpdateSerializer,
    )
    def post(self, request: Request) -> Response:
        serializer = ReleaseUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        set_live(data["kind"], list(dict.fromkeys(data["keys"])), data["live"], request.user)
        return Response(_catalogue())


def _competition_row(competition: Competition) -> dict:
    preset_key = (competition.settings_json or {}).get("preset") or ""
    preset = PRESETS.get(preset_key)
    return {
        "id": str(competition.id),
        "name": competition.name,
        "sport": competition.sport,
        "preset": preset_key,
        "preset_label": preset["label"] if preset else "",
        "sport_live": sport_is_live(preset_key) if preset else True,
        "status": competition.status,
        "is_private": competition.is_private,
        "platform_hidden": competition.platform_hidden,
        "owner": competition.owner.display_name or competition.owner.email,
        "participants": getattr(competition, "participant_total", 0),
        "created_at": competition.created_at.isoformat(),
    }


class CompetitionAdminListView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(tags=["Platform"], summary="Every competition, with its platform visibility")
    def get(self, request: Request) -> Response:
        rows = Competition.objects.select_related("owner").annotate(
            participant_total=Count("participants", distinct=True)
        )
        query = (request.query_params.get("search") or "").strip()
        if query:
            rows = rows.filter(
                Q(name__icontains=query)
                | Q(sport__icontains=query)
                | Q(owner__display_name__icontains=query)
                | Q(owner__email__icontains=query)
            )
        if request.query_params.get("hidden") in {"1", "true", "yes"}:
            rows = rows.filter(platform_hidden=True)
        rows = rows.order_by("-created_at")
        total = rows.count()
        return Response(
            {
                "count": total,
                "results": [_competition_row(row) for row in rows[:COMPETITION_LIMIT]],
            }
        )


class CompetitionVisibilitySerializer(serializers.Serializer):
    platform_hidden = serializers.BooleanField()


class CompetitionAdminDetailView(APIView):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        tags=["Platform"],
        summary="Hide a competition from the public, or show it again",
        request=CompetitionVisibilitySerializer,
    )
    def patch(self, request: Request, pk: str) -> Response:
        competition = get_object_or_404(
            Competition.objects.select_related("owner").annotate(
                participant_total=Count("participants", distinct=True)
            ),
            pk=pk,
        )
        serializer = CompetitionVisibilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        competition.platform_hidden = serializer.validated_data["platform_hidden"]
        competition.save(update_fields=["platform_hidden", "updated_at"])
        return Response(_competition_row(competition))


CLEAR_PHRASE = "CLEAR ALL LEAGUES"


class ClearCompetitionsSerializer(serializers.Serializer):
    confirm = serializers.CharField()

    def validate_confirm(self, value: str) -> str:
        if value.strip() != CLEAR_PHRASE:
            raise serializers.ValidationError(f'Type "{CLEAR_PHRASE}" to confirm.')
        return value


class ClearCompetitionsView(APIView):
    permission_classes = [CanClearLeagues]

    @extend_schema(
        tags=["Platform"],
        summary="Delete every competition on the platform",
        description=f'Irreversible. The body must carry confirm: "{CLEAR_PHRASE}".',
        request=ClearCompetitionsSerializer,
        responses={200: dict},
    )
    def post(self, request: Request) -> Response:
        ClearCompetitionsSerializer(data=request.data).is_valid(raise_exception=True)
        from apps.competitions.reset import clear_all_competitions

        return Response({"cleared": clear_all_competitions(by=request.user)})
