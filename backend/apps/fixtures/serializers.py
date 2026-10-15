from __future__ import annotations

from datetime import time
from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from apps.competitions.models import Participant, ScoringCategory, Stage

from .models import Fixture, FixtureSide, PlayerMatchRating, ScoreEvent


class ParticipantRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = ["id", "name", "short_name", "logo_url"]


class FixtureSideSerializer(serializers.ModelSerializer):
    participant = ParticipantRefSerializer(read_only=True)
    participant_id = serializers.PrimaryKeyRelatedField(
        source="participant", queryset=Participant.objects.all(), write_only=True
    )

    class Meta:
        model = FixtureSide
        fields = [
            "id",
            "participant",
            "participant_id",
            "position",
            "is_home",
            "score",
            "outcome",
            "forfeited",
        ]
        read_only_fields = ["score", "outcome"]


class ScoreEventSerializer(serializers.ModelSerializer):
    scoring_category_name = serializers.CharField(
        source="scoring_category.name", read_only=True
    )
    points = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    participant_id = serializers.UUIDField(source="side.participant_id", read_only=True)
    player_user_id = serializers.SerializerMethodField()
    rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=1,
        required=False,
        write_only=True,
        min_value=Decimal("0"),
        max_value=Decimal("10"),
        help_text="This profile's rating for the fixture, from 0 to 10.",
    )

    class Meta:
        model = ScoreEvent
        fields = [
            "id",
            "side",
            "participant_id",
            "scoring_category",
            "scoring_category_name",
            "quantity",
            "points",
            "minute",
            "period",
            "unit_index",
            "player",
            "player_user_id",
            "player_name",
            "rating",
            "note",
            "occurred_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_player_user_id(self, obj: ScoreEvent):
        player = getattr(obj, "player", None)
        if player is None or player.user_id is None:
            return None
        return player.user_id

    def validate(self, attrs: dict) -> dict:
        fixture = self.context["fixture"]
        side = attrs.get("side") or getattr(self.instance, "side", None)
        category = attrs.get("scoring_category") or getattr(
            self.instance, "scoring_category", None
        )

        if side is not None and side.fixture_id != fixture.id:
            raise serializers.ValidationError({"side": "That side is not in this fixture."})
        if category is not None and category.competition_id != fixture.competition_id:
            raise serializers.ValidationError(
                {
                    "scoring_category": (
                        "That scoring category belongs to a different competition."
                    )
                }
            )

        player = attrs.get("player", getattr(self.instance, "player", None))
        if (
            self.instance is None
            and player is None
            and side is not None
            and side.participant.roster.filter(is_active=True).exists()
        ):
            raise serializers.ValidationError({"player": "Choose the profile who scored."})
        if player is not None and side is not None and player.participant_id != side.participant_id:
            raise serializers.ValidationError(
                {"player": "That player is not on this side's roster."}
            )
        if player is not None and not (attrs.get("player_name") or "").strip():
            attrs["player_name"] = player.name
        if attrs.get("rating") is not None and player is None:
            raise serializers.ValidationError(
                {"rating": "A rating belongs to the profile who played."}
            )
        return attrs

    def _save_rating(self, event: ScoreEvent, rating: Decimal | None) -> None:
        if rating is None or event.player_id is None:
            return
        PlayerMatchRating.objects.update_or_create(
            fixture_id=event.fixture_id,
            player_id=event.player_id,
            defaults={"rating": rating},
        )

    def create(self, validated_data: dict) -> ScoreEvent:
        rating = validated_data.pop("rating", None)
        event = super().create(validated_data)
        self._save_rating(event, rating)
        return event

    def update(self, instance: ScoreEvent, validated_data: dict) -> ScoreEvent:
        rating = validated_data.pop("rating", None)
        event = super().update(instance, validated_data)
        self._save_rating(event, rating)
        return event


class FixtureListSerializer(serializers.ModelSerializer):
    sides = FixtureSideSerializer(many=True, read_only=True)

    class Meta:
        model = Fixture
        fields = [
            "id",
            "competition",
            "stage",
            "round_number",
            "label",
            "scheduled_at",
            "duration_minutes",
            "location",
            "status",
            "sides",
            "started_at",
            "completed_at",
        ]


class PlayerMatchRatingSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="player.name", read_only=True)
    player_user_id = serializers.UUIDField(
        source="player.user_id", read_only=True, allow_null=True
    )

    class Meta:
        model = PlayerMatchRating
        fields = ["id", "player", "player_name", "player_user_id", "rating"]


class FixtureDetailSerializer(FixtureListSerializer):
    events = ScoreEventSerializer(many=True, read_only=True)
    ratings = PlayerMatchRatingSerializer(many=True, read_only=True)
    referees = serializers.SerializerMethodField()

    class Meta(FixtureListSerializer.Meta):
        fields = [
            *FixtureListSerializer.Meta.fields,
            "notes",
            "events",
            "ratings",
            "referees",
            "created_at",
        ]

    def get_referees(self, obj) -> list[dict]:
        rows = obj.referees.all()
        return [
            {
                "id": str(row.user_id),
                "display_name": row.user.get_full_name(),
                "email": row.user.email,
            }
            for row in rows
        ]


class FixtureWriteSerializer(serializers.ModelSerializer):
    sides = FixtureSideSerializer(many=True, required=False)

    class Meta:
        model = Fixture
        fields = [
            "id",
            "stage",
            "round_number",
            "label",
            "scheduled_at",
            "duration_minutes",
            "location",
            "status",
            "notes",
            "sides",
        ]
        read_only_fields = ["id"]

    def validate_sides(self, sides: list[dict]) -> list[dict]:
        competition = self.context["competition"]
        participants = [side["participant"] for side in sides]
        if len({p.id for p in participants}) != len(participants):
            raise serializers.ValidationError("A participant cannot play against itself.")
        for participant in participants:
            if participant.competition_id != competition.id:
                raise serializers.ValidationError(
                    f"'{participant.name}' is not in this competition."
                )
        return sides

    def validate_stage(self, stage: Stage | None) -> Stage | None:
        competition = self.context["competition"]
        if stage is not None and stage.competition_id != competition.id:
            raise serializers.ValidationError("That stage belongs to a different competition.")
        return stage

    @transaction.atomic
    def create(self, validated_data: dict) -> Fixture:
        sides_data = validated_data.pop("sides", [])
        fixture = Fixture.objects.create(**validated_data)
        FixtureSide.objects.bulk_create(
            [
                FixtureSide(
                    fixture=fixture,
                    participant=side["participant"],
                    position=side.get("position", index),
                    is_home=side.get("is_home", index == 0),
                    forfeited=side.get("forfeited", False),
                )
                for index, side in enumerate(sides_data)
            ]
        )
        return fixture

    @transaction.atomic
    def update(self, instance: Fixture, validated_data: dict) -> Fixture:
        sides_data = validated_data.pop("sides", None)
        fixture = super().update(instance, validated_data)

        if sides_data is not None:
            # Replacing the line-up discards recorded events for removed sides,
            # which cascade from FixtureSide.
            keep_ids = []
            for index, side in enumerate(sides_data):
                obj, _ = FixtureSide.objects.update_or_create(
                    fixture=fixture,
                    participant=side["participant"],
                    defaults={
                        "position": side.get("position", index),
                        "is_home": side.get("is_home", index == 0),
                        "forfeited": side.get("forfeited", False),
                    },
                )
                keep_ids.append(obj.id)
            fixture.sides.exclude(id__in=keep_ids).delete()

        fixture.recalculate_scores()
        return fixture


class GenerateFixturesSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=["round_robin", "knockout"], default="round_robin")
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="Defaults to every active participant in the competition.",
    )
    stage_id = serializers.UUIDField(required=False, allow_null=True)
    starts_on = serializers.DateField()
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        help_text="0 is Monday. Defaults to the competition's match_weekdays.",
    )
    kickoff = serializers.TimeField(default=time(hour=15))
    minutes_between_fixtures = serializers.IntegerField(default=0, min_value=0, max_value=1440)
    double_round = serializers.BooleanField(
        default=False, help_text="Play every pairing twice, home and away."
    )
    location = serializers.CharField(required=False, allow_blank=True, default="")
    replace_existing = serializers.BooleanField(
        default=False,
        help_text="Delete existing scheduled fixtures before generating. "
        "Completed fixtures are never deleted.",
    )


class BulkScoreEventSerializer(serializers.Serializer):
    """Record several events at once, e.g. when catching up after a match."""

    events = ScoreEventSerializer(many=True)


class FixtureStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Fixture.Status.choices)


class ScoreAssistSerializer(serializers.Serializer):
    """An admin records either a criterion award or a win/draw/loss result."""

    kind = serializers.ChoiceField(choices=["criterion", "result"])
    participant = serializers.PrimaryKeyRelatedField(
        queryset=Participant.objects.all(), required=False
    )
    scoring_category = serializers.PrimaryKeyRelatedField(
        queryset=ScoringCategory.objects.all(), required=False
    )
    quantity = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, default=Decimal("1")
    )
    home = serializers.PrimaryKeyRelatedField(
        queryset=Participant.objects.all(), required=False
    )
    away = serializers.PrimaryKeyRelatedField(
        queryset=Participant.objects.all(), required=False
    )
    outcome = serializers.ChoiceField(
        choices=["home", "away", "draw"], required=False
    )
    note = serializers.CharField(max_length=280, allow_blank=True, required=False, default="")

    def validate(self, attrs: dict) -> dict:
        competition = self.context["competition"]
        kind = attrs["kind"]
        if kind == "criterion":
            participant = attrs.get("participant")
            category = attrs.get("scoring_category")
            if participant is None or category is None:
                raise serializers.ValidationError(
                    "Choose a participant and a scoring criterion."
                )
            if not attrs.get("note", "").strip():
                raise serializers.ValidationError(
                    {"note": "Describe how these points were accumulated."}
                )
            if participant.competition_id != competition.id:
                raise serializers.ValidationError("That participant is not in this competition.")
            if category.competition_id != competition.id:
                raise serializers.ValidationError("That scoring criterion belongs to another competition.")
            if attrs["quantity"] == 0:
                raise serializers.ValidationError({"quantity": "Enter what was achieved."})
        else:
            home = attrs.get("home")
            away = attrs.get("away")
            if home is None or away is None or not attrs.get("outcome"):
                raise serializers.ValidationError("Choose both sides and a result.")
            if home.id == away.id:
                raise serializers.ValidationError("A participant cannot play against itself.")
            for participant in (home, away):
                if participant.competition_id != competition.id:
                    raise serializers.ValidationError(
                        f"'{participant.name}' is not in this competition."
                    )
        return attrs
