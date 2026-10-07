from __future__ import annotations

from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.core.permissions import Role, role_in

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
from .presets import PRESETS, SCORING_LOCKED_MESSAGE, apply_preset, scoring_is_locked


def _preset_locks_scoring(preset_key: str | None) -> bool:
    if not preset_key or preset_key == "custom":
        return False
    preset = PRESETS.get(preset_key)
    return bool(preset and preset.get("scoring_locked", True))


def _unique_category_code(competition, base: str) -> str:
    candidate = (base or "score")[:60]
    if competition is None:
        return candidate
    used = set(
        ScoringCategory.objects.filter(competition=competition).values_list("code", flat=True)
    )
    if candidate not in used:
        return candidate
    counter = 2
    while f"{candidate}-{counter}" in used:
        counter += 1
    return f"{candidate}-{counter}"[:60]


class ScoringCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoringCategory
        fields = [
            "id",
            "name",
            "code",
            "description",
            "points",
            "affects_score",
            "display_order",
            "icon",
        ]
        extra_kwargs = {"code": {"required": False, "allow_blank": True}}

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("code"):
            attrs["code"] = slugify(attrs.get("name") or "")[:60] or "score"
        return attrs

    def create(self, validated_data: dict) -> ScoringCategory:
        competition = validated_data.get("competition") or self.context.get("competition")
        validated_data["code"] = _unique_category_code(
            competition, validated_data.get("code") or "score"
        )
        return super().create(validated_data)


class ScoringCategoryWriteSerializer(serializers.Serializer):
    """A scoring row accepted on competition create, before the category has an id."""

    name = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    points = serializers.DecimalField(max_digits=8, decimal_places=2, default=1)
    affects_score = serializers.BooleanField(default=True)
    code = serializers.SlugField(max_length=60, required=False, allow_blank=True)


class RuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = ["id", "name", "description", "display_order"]


class PointsPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PointsPolicy
        fields = [
            "id",
            "win_points",
            "draw_points",
            "loss_points",
            "bonus_win_margin",
            "bonus_win_points",
            "bonus_loss_margin",
            "bonus_loss_points",
            "forfeit_points",
            "tiebreakers",
            "allow_draws",
        ]

    def validate_tiebreakers(self, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise serializers.ValidationError("Tiebreakers must be a list.")
        valid = {choice.value for choice in PointsPolicy.Tiebreaker}
        unknown = [item for item in value if item not in valid]
        if unknown:
            raise serializers.ValidationError(
                f"Unknown tiebreakers: {', '.join(map(str, unknown))}. "
                f"Choose from: {', '.join(sorted(valid))}."
            )
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Tiebreakers must not repeat.")
        return value


class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = [
            "id",
            "name",
            "kind",
            "display_order",
            "starts_on",
            "ends_on",
            "advances_count",
        ]


class RosterMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = RosterMember
        fields = ["id", "name", "number", "position", "user", "is_active"]


class ParticipantSerializer(serializers.ModelSerializer):
    roster = RosterMemberSerializer(many=True, read_only=True)
    stage_ids = serializers.PrimaryKeyRelatedField(
        source="stages", many=True, queryset=Stage.objects.all(), required=False
    )

    class Meta:
        model = Participant
        fields = [
            "id",
            "name",
            "short_name",
            "description",
            "logo_url",
            "managed_by",
            "seed",
            "is_active",
            "metadata",
            "stage_ids",
            "roster",
        ]

    def validate_stage_ids(self, stages: list[Stage]) -> list[Stage]:
        competition = self.context.get("competition")
        if competition and any(stage.competition_id != competition.id for stage in stages):
            raise serializers.ValidationError("Stages must belong to the same competition.")
        return stages


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)

    class Meta:
        model = Membership
        fields = ["id", "user", "user_id", "email", "role", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("user_id") and not attrs.get("email"):
            raise serializers.ValidationError("Provide either user_id or email.")
        return attrs

    def validate_role(self, value: str) -> str:
        # Ownership transfers are a deliberate, separate action.
        if value == Role.OWNER:
            raise serializers.ValidationError(
                "Use the transfer-ownership endpoint to change the owner."
            )
        return value


class CompetitionListSerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    my_role = serializers.SerializerMethodField()
    scoring_basis = serializers.SerializerMethodField()

    class Meta:
        model = Competition
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "sport",
            "logo_url",
            "banner_url",
            "format",
            "status",
            "is_private",
            "starts_on",
            "ends_on",
            "owner",
            "participant_count",
            "my_role",
            "scoring_basis",
            "created_at",
        ]

    def get_my_role(self, obj: Competition) -> str | None:
        request = self.context.get("request")
        return role_in(obj, request.user) if request else None

    def get_scoring_basis(self, obj: Competition) -> str:
        settings = obj.settings_json or {}
        basis = settings.get("scoring_basis")
        if basis in {"results", "criteria"}:
            return basis
        if settings.get("table_mode") == "points":
            return "criteria"
        return "results"


class CompetitionDetailSerializer(CompetitionListSerializer):
    scoring_categories = ScoringCategorySerializer(many=True, read_only=True)
    rules = RuleSerializer(many=True, read_only=True)
    points_policy = PointsPolicySerializer(read_only=True)
    stages = StageSerializer(many=True, read_only=True)
    participants = ParticipantSerializer(many=True, read_only=True)

    class Meta(CompetitionListSerializer.Meta):
        fields = [
            *CompetitionListSerializer.Meta.fields,
            "timezone",
            "match_weekdays",
            "settings_json",
            "scoring_categories",
            "rules",
            "points_policy",
            "stages",
            "participants",
            "updated_at",
        ]


class CompetitionWriteSerializer(serializers.ModelSerializer):
    preset = serializers.ChoiceField(
        choices=sorted(PRESETS.keys()),
        required=False,
        write_only=True,
        help_text=(
            "Optional. Seeds scoring categories, a points policy and rules. "
            "Official presets lock that scoring. Only Custom stays editable."
        ),
    )
    scoring_categories = ScoringCategoryWriteSerializer(
        many=True,
        required=False,
        write_only=True,
        help_text=(
            "Used by Custom competitions. Official presets reject this field "
            "and keep their own scoring."
        ),
    )
    scoring_basis = serializers.ChoiceField(
        choices=["results", "criteria"],
        required=False,
        write_only=True,
        help_text="results scores fixtures as win/draw/loss. criteria sums the scoring criteria.",
    )

    class Meta:
        model = Competition
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "sport",
            "logo_url",
            "banner_url",
            "format",
            "status",
            "is_private",
            "starts_on",
            "ends_on",
            "timezone",
            "match_weekdays",
            "settings_json",
            "preset",
            "scoring_categories",
            "scoring_basis",
        ]
        read_only_fields = ["id", "slug"]

    def validate_match_weekdays(self, value: list[int]) -> list[int]:
        if not isinstance(value, list) or any(
            not isinstance(day, int) or not 0 <= day <= 6 for day in value
        ):
            raise serializers.ValidationError(
                "match_weekdays must be a list of integers 0-6, where 0 is Monday."
            )
        return sorted(set(value))

    def validate(self, attrs: dict) -> dict:
        starts_on = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        ends_on = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if starts_on and ends_on and ends_on < starts_on:
            raise serializers.ValidationError({"ends_on": "End date is before the start date."})
        if self.instance is None and attrs.get("preset") == "custom":
            categories = attrs.get("scoring_categories") or []
            if not any(str(item.get("name", "")).strip() for item in categories):
                raise serializers.ValidationError(
                    {
                        "scoring_categories": (
                            "Define at least one scoring criterion before creating a custom competition."
                        )
                    }
                )
        if self.instance is None and _preset_locks_scoring(attrs.get("preset")):
            if attrs.get("scoring_categories"):
                raise serializers.ValidationError({"scoring_categories": SCORING_LOCKED_MESSAGE})
            if attrs.get("scoring_basis"):
                raise serializers.ValidationError({"scoring_basis": SCORING_LOCKED_MESSAGE})
        return attrs

    def update(self, instance: Competition, validated_data: dict) -> Competition:
        if scoring_is_locked(instance) and "settings_json" in validated_data:
            current = dict(instance.settings_json or {})
            incoming = dict(validated_data.get("settings_json") or {})
            for key in ("preset", "scoring_locked", "table_mode", "scoring_basis"):
                if key in current:
                    incoming[key] = current[key]
            incoming["scoring_locked"] = True
            validated_data["settings_json"] = incoming
        return super().update(instance, validated_data)

    @transaction.atomic
    def create(self, validated_data: dict) -> Competition:
        preset_key = validated_data.pop("preset", None)
        custom_categories = validated_data.pop("scoring_categories", None)
        scoring_basis = validated_data.pop("scoring_basis", None)
        user = self.context["request"].user

        if preset_key and not validated_data.get("sport"):
            validated_data["sport"] = PRESETS[preset_key]["sport"]
        if preset_key and not validated_data.get("format"):
            validated_data["format"] = PRESETS[preset_key]["format"]

        competition = Competition.objects.create(owner=user, **validated_data)
        Membership.objects.create(competition=competition, user=user, role=Role.OWNER)

        if preset_key:
            apply_preset(competition, preset_key)
        else:
            PointsPolicy.objects.create(competition=competition)

        if custom_categories is not None and preset_key in (None, "custom"):
            competition.scoring_categories.all().delete()
            used: set[str] = set()
            rows = []
            for index, item in enumerate(custom_categories):
                base = item.get("code") or slugify(item["name"])[:60] or f"score-{index + 1}"
                code = base
                counter = 2
                while code in used:
                    code = f"{base}-{counter}"
                    counter += 1
                used.add(code)
                rows.append(
                    ScoringCategory(
                        competition=competition,
                        name=item["name"],
                        code=code[:60],
                        description=item.get("description") or "",
                        points=item["points"],
                        affects_score=item.get("affects_score", True),
                        display_order=index,
                    )
                )
            ScoringCategory.objects.bulk_create(rows)

        if scoring_basis and preset_key in (None, "custom"):
            settings = dict(competition.settings_json or {})
            settings["scoring_basis"] = scoring_basis
            settings["table_mode"] = "points" if scoring_basis == "criteria" else "head_to_head"
            competition.settings_json = settings
            competition.save(update_fields=["settings_json", "updated_at"])

        return competition


class ApplyPresetSerializer(serializers.Serializer):
    preset = serializers.ChoiceField(choices=sorted(PRESETS.keys()))
    replace_existing = serializers.BooleanField(
        default=False,
        help_text="Delete current scoring categories and rules before applying.",
    )


class TransferOwnershipSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
