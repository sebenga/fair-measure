from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.accounts.serializers import UserSummarySerializer
from apps.core.permissions import Role, role_in

User = get_user_model()

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
    return bool(preset and preset.get("scoring_locked", preset.get("locked", True)))


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
        if self.instance is None and not attrs.get("code"):
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
    user_display_name = serializers.SerializerMethodField()

    class Meta:
        model = RosterMember
        fields = ["id", "name", "number", "position", "user", "user_display_name", "is_active"]
        read_only_fields = ["user_display_name"]

    def get_user_display_name(self, obj: RosterMember) -> str:
        if obj.user_id is None:
            return ""
        return obj.user.get_full_name()


def add_profile_to_team(participant: Participant, user, actor, field: str = "member_ids") -> RosterMember:
    """Put a profile on a team.

    Members can be added by an admin. An owner or admin can add only their own
    profile, and only to one team in the league.
    """
    membership = Membership.objects.filter(competition=participant.competition, user=user).first()
    if membership is None:
        invited_by = actor if getattr(actor, "is_authenticated", False) else None
        Membership.objects.create(
            competition=participant.competition,
            user=user,
            role=Role.MEMBER,
            invited_by=invited_by,
        )
    elif membership.role in (Role.OWNER, Role.ADMIN):
        if getattr(actor, "id", None) != user.id:
            raise serializers.ValidationError(
                {field: "An admin can only add themselves to a team."}
            )
        already = (
            RosterMember.objects.filter(participant__competition=participant.competition, user=user)
            .exclude(participant=participant)
            .exists()
        )
        if already:
            raise serializers.ValidationError(
                {field: "An admin can only be on one team in a league."}
            )
    elif membership.role != Role.MEMBER:
        raise serializers.ValidationError({field: f"{user.get_full_name()} can't join a team."})

    existing = participant.roster.filter(user=user).first()
    if existing is not None:
        if field == "user":
            raise serializers.ValidationError({field: "That member is already on this team."})
        return existing
    return RosterMember.objects.create(
        participant=participant, user=user, name=user.get_full_name()
    )


class ParticipantSerializer(serializers.ModelSerializer):
    roster = RosterMemberSerializer(many=True, read_only=True)
    stage_ids = serializers.PrimaryKeyRelatedField(
        source="stages", many=True, queryset=Stage.objects.all(), required=False
    )
    member_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    class Meta:
        model = Participant
        fields = [
            "id",
            "kind",
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
            "member_ids",
        ]

    def validate_stage_ids(self, stages: list[Stage]) -> list[Stage]:
        competition = self.context.get("competition")
        if competition and any(stage.competition_id != competition.id for stage in stages):
            raise serializers.ValidationError("Stages must belong to the same competition.")
        return stages

    def _allowed_entrants(self) -> list[str]:
        competition = self.context.get("competition")
        settings = getattr(competition, "settings_json", None) or {}
        allowed = list(settings.get("participant_types") or [])
        primary = settings.get("participant_type") or "team"
        if primary not in allowed:
            allowed.insert(0, primary)
        return allowed or ["team"]

    def _entrant_type(self) -> str:
        return self._allowed_entrants()[0]

    def validate(self, attrs: dict) -> dict:
        entrant_type = self._entrant_type()
        allowed = self._allowed_entrants()
        if self.instance is None and "individual" in allowed and "pair" in allowed:
            member_ids = list(dict.fromkeys(attrs.get("member_ids") or []))
            if len(member_ids) == 2:
                attrs["kind"] = Participant.Kind.TEAM
                attrs["member_ids"] = member_ids
                return attrs
            attrs["kind"] = Participant.Kind.INDIVIDUAL
            attrs.pop("member_ids", None)
            return attrs
        if self.instance is None and entrant_type == "individual":
            attrs["kind"] = Participant.Kind.INDIVIDUAL
            attrs.pop("member_ids", None)
            return attrs
        if self.instance is None and entrant_type == "pair":
            attrs["kind"] = Participant.Kind.TEAM
            member_ids = list(dict.fromkeys(attrs.get("member_ids") or []))
            if len(member_ids) != 2:
                raise serializers.ValidationError(
                    {"member_ids": "A pair is two profiles."}
                )
            attrs["member_ids"] = member_ids
            return attrs
        if self.instance is None:
            if attrs.get("kind") == Participant.Kind.INDIVIDUAL:
                raise serializers.ValidationError({"kind": "Add a team instead of a player."})
            attrs["kind"] = Participant.Kind.TEAM
        kind = attrs.get("kind")
        if kind is None and self.instance is not None:
            kind = self.instance.kind
        creating_team = self.instance is None and kind == Participant.Kind.TEAM
        converting = (
            self.instance is not None
            and kind == Participant.Kind.TEAM
            and self.instance.kind != Participant.Kind.TEAM
        )
        if creating_team or converting:
            member_ids = list(dict.fromkeys(attrs.get("member_ids") or []))
            if len(member_ids) < 2:
                raise serializers.ValidationError(
                    {"member_ids": "A team is created from at least two profiles."}
                )
            attrs["member_ids"] = member_ids
        return attrs

    def create(self, validated_data: dict) -> Participant:
        member_ids = validated_data.pop("member_ids", [])
        with transaction.atomic():
            participant = super().create(validated_data)
            if participant.kind == Participant.Kind.TEAM:
                self._attach_profiles(participant, member_ids)
        return participant

    def update(self, instance: Participant, validated_data: dict) -> Participant:
        member_ids = validated_data.pop("member_ids", [])
        with transaction.atomic():
            participant = super().update(instance, validated_data)
            if member_ids and participant.kind == Participant.Kind.TEAM:
                self._attach_profiles(participant, member_ids)
        return participant

    def _attach_profiles(self, participant: Participant, member_ids: list) -> None:
        users = list(User.objects.filter(id__in=member_ids))
        if len(users) != len(set(member_ids)):
            raise serializers.ValidationError({"member_ids": "Choose profiles that exist."})
        actor = getattr(self.context.get("request"), "user", None)
        for user in users:
            add_profile_to_team(participant, user, actor)


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)
    member_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "user_id", "email", "member_email", "role", "created_at"]
        read_only_fields = ["id", "member_email", "created_at"]

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
                raise PermissionDenied(SCORING_LOCKED_MESSAGE)
            if attrs.get("scoring_basis"):
                raise PermissionDenied(SCORING_LOCKED_MESSAGE)
        return attrs

    def update(self, instance: Competition, validated_data: dict) -> Competition:
        if scoring_is_locked(instance) and "settings_json" in validated_data:
            current = dict(instance.settings_json or {})
            incoming = dict(validated_data.get("settings_json") or {})
            for key in (
                "preset",
                "scoring_locked",
                "locked",
                "table_mode",
                "scoring_basis",
                "contest_type",
                "participant_type",
                "match_structure",
                "win_condition",
                "draw_allowed",
                "draw_resolution",
                "league_points",
                "tiebreakers",
                "accumulation_ranking",
                "description",
            ):
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

        if preset_key == "custom":
            scoring_basis = "criteria"
            validated_data["match_weekdays"] = []
            validated_data["format"] = "freeform"

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

        if custom_categories is not None and (
            preset_key in (None, "custom") or not _preset_locks_scoring(preset_key)
        ):
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
