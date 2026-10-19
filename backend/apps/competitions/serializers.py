from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
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
    TeamPick,
    ScoringCategory,
    Stage,
)
from .presets import (
    PRESETS,
    SCORING_LOCKED_MESSAGE,
    apply_preset,
    format_allowed,
    scoring_is_locked,
)


def _validate_game_time(settings: dict, instance) -> None:
    """A time limit, once set, stays set. Overtime can be 0, which removes it."""

    current = (getattr(instance, "settings_json", None) or {}) if instance is not None else {}
    for key in ("time_limit_minutes", "overtime_minutes"):
        if key not in settings and key in current:
            settings[key] = current[key]

    if "time_limit_minutes" in settings:
        try:
            limit = int(settings["time_limit_minutes"])
        except (TypeError, ValueError):
            limit = 0
        if limit < 1:
            raise serializers.ValidationError(
                {"settings_json": "A game needs a time limit of at least 1 minute."}
            )
        settings["time_limit_minutes"] = limit
    if "overtime_minutes" in settings:
        raw = settings["overtime_minutes"]
        try:
            overtime = 0 if raw in (None, "") else int(raw)
        except (TypeError, ValueError):
            overtime = -1
        if overtime < 0:
            raise serializers.ValidationError(
                {"settings_json": "Overtime cannot be negative. Use 0 for no overtime."}
            )
        settings["overtime_minutes"] = overtime


def _apply_game_time_to_unstarted(competition) -> None:
    from apps.fixtures.models import Fixture

    from .presets import default_game_time

    limit, overtime = default_game_time(competition.settings_json)
    competition.fixtures.filter(
        status__in=[Fixture.Status.SCHEDULED, Fixture.Status.POSTPONED]
    ).update(duration_minutes=limit, overtime_minutes=overtime)


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
    elif membership.role != Role.MEMBER:
        raise serializers.ValidationError({field: f"{user.get_full_name()} can't join a team."})

    already = (
        RosterMember.objects.filter(participant__competition=participant.competition, user=user)
        .exclude(participant=participant)
        .exists()
    )
    if already:
        raise serializers.ValidationError(
            {field: "That profile is already on another team in this league."}
        )

    existing = participant.roster.filter(user=user).first()
    if existing is not None:
        if field == "user":
            raise serializers.ValidationError({field: "That member is already on this team."})
        return existing
    return RosterMember.objects.create(
        participant=participant, user=user, name=user.get_full_name()
    )


MIN_TEAM_PLAYERS = 14


def team_entry_mode(competition) -> str | None:
    """How a team competition fills its squads. Unset leaves the older open flow."""
    settings = getattr(competition, "settings_json", None) or {}
    if settings.get("participant_type") in {"individual", "pair"}:
        return None
    mode = settings.get("team_entry")
    if mode in {"pick", "draft"}:
        return mode
    return None


def squad_counts(participant: Participant) -> tuple[int, int]:
    accepted = participant.roster.filter(is_active=True).count()
    pending = participant.picks.filter(status=TeamPick.Status.PENDING).count()
    return accepted, pending


def draft_teams(competition) -> list[Participant]:
    return list(
        competition.participants.filter(kind=Participant.Kind.TEAM, is_active=True)
        .order_by("name")
    )


def next_draft_team(teams: list[Participant]) -> Participant | None:
    """Snake order. A team that already has 14 players (accepted or waiting) is skipped."""
    if not teams:
        return None
    totals = [sum(squad_counts(team)) for team in teams]
    if all(total >= MIN_TEAM_PLAYERS for total in totals):
        return None
    count = len(teams)
    made = sum(totals)
    for step in range(made, made + count * MIN_TEAM_PLAYERS):
        round_no, index = divmod(step, count)
        slot = index if round_no % 2 == 0 else count - 1 - index
        if totals[slot] < MIN_TEAM_PLAYERS:
            return teams[slot]
    return None


def draft_payload(competition) -> dict:
    teams = draft_teams(competition)
    rows = []
    for team in teams:
        accepted, pending = squad_counts(team)
        rows.append(
            {
                "id": str(team.id),
                "name": team.name,
                "accepted": accepted,
                "pending": pending,
                "total": accepted + pending,
            }
        )
    clock = next_draft_team(teams)
    return {
        "squad_size": MIN_TEAM_PLAYERS,
        "on_the_clock": None if clock is None else {"id": str(clock.id), "name": clock.name},
        "teams": rows,
        "complete": bool(teams) and clock is None,
    }


def offer_team_pick(participant: Participant, user, actor) -> TeamPick:
    """Invite a profile onto a team. They are not on the roster until they accept."""
    if participant.kind != Participant.Kind.TEAM:
        raise serializers.ValidationError({"user": "Pick profiles onto a team."})

    membership = Membership.objects.filter(
        competition=participant.competition, user=user
    ).first()
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
                {"user": "An admin can only add themselves to a team."}
            )
    elif membership.role != Role.MEMBER:
        raise serializers.ValidationError({"user": f"{user.get_full_name()} can't join a team."})

    competition_id = participant.competition_id
    if RosterMember.objects.filter(
        participant__competition_id=competition_id, user=user, is_active=True
    ).exists():
        raise serializers.ValidationError(
            {"user": "That profile is already on a team in this league."}
        )

    pending = TeamPick.objects.filter(
        participant__competition_id=competition_id,
        user=user,
        status=TeamPick.Status.PENDING,
    ).first()
    if pending is not None:
        if pending.participant_id == participant.id:
            return pending
        raise serializers.ValidationError(
            {"user": "That profile already has a pick waiting in this league."}
        )

    return TeamPick.objects.create(
        participant=participant,
        user=user,
        invited_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


def accept_team_pick(pick: TeamPick, actor) -> TeamPick:
    if pick.user_id != getattr(actor, "id", None):
        raise PermissionDenied("Only the picked profile can accept.")
    if pick.status != TeamPick.Status.PENDING:
        raise serializers.ValidationError({"status": "This pick is already settled."})
    add_profile_to_team(pick.participant, pick.user, actor, field="user")
    now = timezone.now()
    pick.status = TeamPick.Status.ACCEPTED
    pick.responded_at = now
    pick.save(update_fields=["status", "responded_at", "updated_at"])
    TeamPick.objects.filter(
        participant__competition_id=pick.participant.competition_id,
        user_id=pick.user_id,
        status=TeamPick.Status.PENDING,
    ).update(status=TeamPick.Status.DECLINED, responded_at=now)
    return pick


def decline_team_pick(pick: TeamPick, actor) -> TeamPick:
    if pick.user_id != getattr(actor, "id", None):
        raise PermissionDenied("Only the picked profile can decline.")
    if pick.status != TeamPick.Status.PENDING:
        raise serializers.ValidationError({"status": "This pick is already settled."})
    pick.status = TeamPick.Status.DECLINED
    pick.responded_at = timezone.now()
    pick.save(update_fields=["status", "responded_at", "updated_at"])
    return pick


class TeamPickSerializer(serializers.ModelSerializer):
    user_display_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source="user.email", read_only=True)
    team_name = serializers.CharField(source="participant.name", read_only=True)

    class Meta:
        model = TeamPick
        fields = [
            "id",
            "participant",
            "team_name",
            "user",
            "user_display_name",
            "user_email",
            "status",
            "created_at",
            "responded_at",
        ]
        read_only_fields = [
            "id",
            "participant",
            "team_name",
            "user_display_name",
            "user_email",
            "status",
            "created_at",
            "responded_at",
        ]

    def get_user_display_name(self, obj: TeamPick) -> str:
        return obj.user.get_full_name()


class ParticipantSerializer(serializers.ModelSerializer):
    roster = RosterMemberSerializer(many=True, read_only=True)
    pending_count = serializers.SerializerMethodField()
    pending_user_ids = serializers.SerializerMethodField()
    stage_ids = serializers.PrimaryKeyRelatedField(
        source="stages", many=True, queryset=Stage.objects.all(), required=False
    )
    member_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )
    user = serializers.UUIDField(
        write_only=True,
        required=False,
        help_text="The profile entering, for competitions whose individuals are profiles.",
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
            "pending_count",
            "pending_user_ids",
            "member_ids",
            "user",
        ]
        extra_kwargs = {"name": {"required": False}}

    def _pending_picks(self, obj: Participant):
        cached = getattr(obj, "_prefetched_objects_cache", {}).get("picks")
        if cached is not None:
            return [pick for pick in cached if pick.status == TeamPick.Status.PENDING]
        return list(obj.picks.filter(status=TeamPick.Status.PENDING))

    def get_pending_count(self, obj: Participant) -> int:
        return len(self._pending_picks(obj))

    def get_pending_user_ids(self, obj: Participant) -> list[str]:
        return [str(pick.user_id) for pick in self._pending_picks(obj)]

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
        competition = self.context.get("competition")
        named = bool((attrs.get("name") or "").strip())
        if self.instance is None and "individual" in allowed and "pair" in allowed:
            member_ids = list(dict.fromkeys(attrs.get("member_ids") or []))
            if len(member_ids) == 2:
                if not named:
                    raise serializers.ValidationError({"name": "Name the pair."})
                attrs["kind"] = Participant.Kind.TEAM
                attrs["member_ids"] = member_ids
                return attrs
            attrs["kind"] = Participant.Kind.INDIVIDUAL
            attrs.pop("member_ids", None)
            return _as_profile_entrant(competition, attrs)
        if self.instance is None and entrant_type == "individual":
            attrs["kind"] = Participant.Kind.INDIVIDUAL
            attrs.pop("member_ids", None)
            return _as_profile_entrant(competition, attrs)
        attrs.pop("user", None)
        if self.instance is None and not named:
            raise serializers.ValidationError({"name": "Give the entrant a name."})
        if self.instance is None and entrant_type == "pair":
            attrs["kind"] = Participant.Kind.TEAM
            attrs.pop("member_ids", None)
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
            mode = team_entry_mode(self.context.get("competition"))
            member_ids = list(dict.fromkeys(attrs.get("member_ids") or []))
            if mode == "pick" and creating_team:
                if len(member_ids) < MIN_TEAM_PLAYERS:
                    raise serializers.ValidationError(
                        {
                            "member_ids": (
                                f"A team needs at least {MIN_TEAM_PLAYERS} players."
                            )
                        }
                    )
                attrs["member_ids"] = member_ids
            elif mode == "draft" and member_ids:
                raise serializers.ValidationError(
                    {"member_ids": "Name the team, then draft players onto it."}
                )
            else:
                attrs.pop("member_ids", None)
        return attrs

    def create(self, validated_data: dict) -> Participant:
        member_ids = [str(value) for value in validated_data.pop("member_ids", []) or []]
        entrant_user = validated_data.pop("entrant_user", None)
        validated_data.pop("user", None)
        with transaction.atomic():
            if entrant_user is not None:
                validated_data["managed_by"] = entrant_user
            participant = super().create(validated_data)
            if entrant_user is not None:
                _enter_profile(participant, entrant_user, self.context["request"].user)
            if member_ids:
                actor = self.context["request"].user
                users = {str(user.id): user for user in User.objects.filter(id__in=member_ids)}
                if len(users) != len(set(member_ids)):
                    raise serializers.ValidationError(
                        {"member_ids": "Choose profiles that exist."}
                    )
                for user_id in member_ids:
                    offer_team_pick(participant, users[user_id], actor)
        return participant

    def update(self, instance: Participant, validated_data: dict) -> Participant:
        validated_data.pop("member_ids", None)
        validated_data.pop("user", None)
        return super().update(instance, validated_data)


def _as_profile_entrant(competition, attrs: dict) -> dict:
    """An individual entrant is a profile: its name comes from the profile."""

    attrs["entrant_user"] = _profile_entrant(competition, attrs.pop("user", None))
    attrs["name"] = _entrant_name(competition, attrs["entrant_user"])
    return attrs


def _profile_entrant(competition, user_id):
    """The profile entering an individual competition, once per competition."""

    if not user_id:
        raise serializers.ValidationError({"user": "Search for a profile and choose who is entering."})
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        raise serializers.ValidationError({"user": "Choose a profile that exists."})
    entered = RosterMember.objects.filter(
        participant__competition=competition, user=user
    ).exists() or competition.participants.filter(managed_by=user).exists()
    if entered:
        raise serializers.ValidationError({"user": "That profile is already in this competition."})
    return user


def _entrant_name(competition, user) -> str:
    name = (user.get_full_name() or user.email).strip()
    if competition.participants.filter(name=name).exists():
        name = f"{name} ({user.email})"
    return name[:200]


def _enter_profile(participant: Participant, user, actor) -> RosterMember:
    """Make the profile a member and link it to its entrant so events name them."""

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
                {"user": "An admin can only enter themselves."}
            )
    elif membership.role != Role.MEMBER:
        raise serializers.ValidationError(
            {"user": f"{user.get_full_name()} scores this competition and cannot enter it."}
        )
    return RosterMember.objects.create(
        participant=participant, user=user, name=user.get_full_name() or user.email
    )


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
        if self.instance is None and not attrs.get("user_id") and not attrs.get("email"):
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
    league_points = serializers.DictField(
        child=serializers.DecimalField(max_digits=6, decimal_places=2),
        required=False,
        write_only=True,
        help_text="Custom VS competitions only: table points for a win, draw and loss.",
    )

    participant_type = serializers.ChoiceField(
        choices=["team", "individual"],
        required=False,
        write_only=True,
        help_text="Custom VS competitions only: whether teams or individuals play each other.",
    )

    def validate_league_points(self, value: dict) -> dict:
        unknown = set(value) - {"win", "draw", "loss"}
        if unknown:
            raise serializers.ValidationError("Use win, draw and loss.")
        return value

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
            "league_points",
            "participant_type",
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
        chosen_format = attrs.get("format")
        if chosen_format:
            if self.instance is None:
                preset_key = attrs.get("preset")
                rules = (
                    {"formats_allowed": PRESETS[preset_key].get("formats_allowed")}
                    if preset_key in PRESETS and preset_key != "custom"
                    else None
                )
            else:
                rules = self.instance.settings_json
            if not format_allowed(rules, chosen_format):
                raise serializers.ValidationError(
                    {"format": "This kind of competition does not support that format."}
                )
        settings = attrs.get("settings_json")
        if isinstance(settings, dict):
            _validate_game_time(settings, self.instance)
        return attrs

    def update(self, instance: Competition, validated_data: dict) -> Competition:
        before = (instance.settings_json or {}).copy()
        competition = self._update(instance, validated_data)
        after = competition.settings_json or {}
        if any(
            before.get(key) != after.get(key)
            for key in ("time_limit_minutes", "overtime_minutes")
        ):
            _apply_game_time_to_unstarted(competition)
        return competition

    # Settings that stay editable once the scoring rules are locked. Everything
    # else (score types, targets, bonuses, tie-breaks, ...) belongs to the rules.
    LOCKED_EDITABLE_SETTINGS = (
        "time_limit_minutes",
        "overtime_minutes",
        "team_entry",
        "profile_entrants",
    )

    def _update(self, instance: Competition, validated_data: dict) -> Competition:
        current = dict(instance.settings_json or {})
        new_status = validated_data.get("status")
        started_locks = current.get("lock_when_started") is True
        if (
            started_locks
            and new_status == "draft"
            and instance.status not in (None, "", "draft")
        ):
            raise serializers.ValidationError(
                {"status": "A started competition cannot go back to draft; its rules are locked."}
            )
        if "settings_json" in validated_data:
            incoming = dict(validated_data.get("settings_json") or {})
            if "lock_when_started" in current:
                incoming["lock_when_started"] = current["lock_when_started"]
            else:
                incoming.pop("lock_when_started", None)
            if scoring_is_locked(instance):
                # Start from what is stored so omitted keys are never deleted,
                # then apply only the few settings that may change.
                merged = dict(current)
                for key in self.LOCKED_EDITABLE_SETTINGS:
                    if key in incoming:
                        merged[key] = incoming[key]
                if not started_locks:
                    merged["scoring_locked"] = True
                validated_data["settings_json"] = merged
            else:
                validated_data["settings_json"] = incoming
        return super().update(instance, validated_data)

    @transaction.atomic
    def create(self, validated_data: dict) -> Competition:
        preset_key = validated_data.pop("preset", None)
        custom_categories = validated_data.pop("scoring_categories", None)
        scoring_basis = validated_data.pop("scoring_basis", None)
        league_points = validated_data.pop("league_points", None)
        participant_type = validated_data.pop("participant_type", None)
        user = self.context["request"].user

        versus = preset_key == "custom" and scoring_basis == "results"
        if preset_key == "custom" and not versus:
            scoring_basis = "criteria"
            validated_data["match_weekdays"] = []
            validated_data["format"] = "freeform"
        if versus and validated_data.get("format") in (None, "", "freeform"):
            validated_data["format"] = "league"

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
            if versus:
                points = {"win": 3, "draw": 1, "loss": 0, **(league_points or {})}
                settings["contest_type"] = "head_to_head"
                settings["participant_type"] = participant_type or "team"
                settings["participant_types"] = [settings["participant_type"]]
                if settings["participant_type"] == "individual":
                    settings["profile_entrants"] = True
                settings["league_points"] = {key: float(value) for key, value in points.items()}
                settings["formats_allowed"] = ["league", "knockout", "groups_knockout", "ladder"]
                PointsPolicy.objects.update_or_create(
                    competition=competition,
                    defaults={
                        "win_points": points["win"],
                        "draw_points": points["draw"],
                        "loss_points": points["loss"],
                    },
                )
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
