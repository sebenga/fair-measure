from __future__ import annotations

from rest_framework import serializers

from . import catalog
from .models import (
    ConsentRecord,
    GuardianLink,
    HighlightVideo,
    InjuryRecord,
    Measurement,
    Organisation,
    PlayerProfile,
    PlayerSport,
    ScoutingRole,
)
from .services import (
    MAX_PROFILE_TEAMS,
    account_name,
    active_consent,
    affiliated_teams,
    age_group,
    age_on,
    date_of_birth_of,
    effective_visibility,
    is_minor,
    roster_team_ids,
    school_or_club_label,
    shared_sections,
    today,
)


class OrganisationSerializer(serializers.ModelSerializer):
    my_role = serializers.SerializerMethodField()
    scout_count = serializers.SerializerMethodField()

    class Meta:
        model = Organisation
        fields = ["id", "name", "kind", "region", "logo_url", "my_role", "scout_count"]
        read_only_fields = ["id", "my_role", "scout_count"]

    def validate_region(self, value: str) -> str:
        if value and value not in catalog.keys(catalog.REGIONS):
            raise serializers.ValidationError("Choose a region from the list.")
        return value

    def get_my_role(self, obj: Organisation) -> str | None:
        request = self.context.get("request")
        if not request:
            return None
        role = (
            obj.roles.filter(user=request.user, role__in=["scout_admin", "scout"])
            .order_by("role")
            .values_list("role", flat=True)
            .first()
        )
        return role

    def get_scout_count(self, obj: Organisation) -> int:
        return obj.roles.filter(role__in=["scout", "scout_admin"]).count()


class ScoutingRoleSerializer(serializers.ModelSerializer):
    organisation_name = serializers.CharField(
        source="organisation.name", default=None, read_only=True
    )
    team_name = serializers.CharField(source="team.name", default=None, read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = ScoutingRole
        fields = [
            "id",
            "role",
            "organisation",
            "organisation_name",
            "team",
            "team_name",
            "user",
            "user_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_name(self, obj: ScoutingRole) -> str:
        return obj.user.display_name or obj.user.get_full_name()


class OrganisationMemberWriteSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=False)
    email = serializers.EmailField(required=False)
    role = serializers.ChoiceField(choices=["scout", "scout_admin"], default="scout")

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("user_id") and not attrs.get("email"):
            raise serializers.ValidationError("Give a user_id or an email address.")
        return attrs


class CoachRoleSerializer(serializers.Serializer):
    team = serializers.UUIDField(help_text="The competition entrant (team) you coach.")


class PlayerSportSerializer(serializers.ModelSerializer):
    sport_label = serializers.SerializerMethodField()
    primary_position_label = serializers.SerializerMethodField()

    class Meta:
        model = PlayerSport
        fields = [
            "id",
            "sport",
            "sport_label",
            "primary_position",
            "primary_position_label",
            "secondary_positions",
            "is_primary",
        ]
        read_only_fields = ["id", "sport_label", "primary_position_label"]

    def validate(self, attrs: dict) -> dict:
        sport_key = attrs.get("sport", getattr(self.instance, "sport", None))
        if catalog.sport(sport_key) is None:
            raise serializers.ValidationError({"sport": "That sport is not in the catalogue."})
        positions = catalog.position_keys(sport_key)
        primary = attrs.get("primary_position", getattr(self.instance, "primary_position", ""))
        if primary and primary not in positions:
            raise serializers.ValidationError(
                {"primary_position": "Choose a position from this sport's list."}
            )
        secondary = (
            attrs.get("secondary_positions", getattr(self.instance, "secondary_positions", []))
            or []
        )
        if not isinstance(secondary, list) or any(item not in positions for item in secondary):
            raise serializers.ValidationError(
                {"secondary_positions": "Choose positions from this sport's list."}
            )
        attrs["secondary_positions"] = [
            item for item in dict.fromkeys(secondary) if item != primary
        ]
        return attrs

    def get_sport_label(self, obj: PlayerSport) -> str:
        return (catalog.sport(obj.sport) or {}).get("label", obj.sport)

    def get_primary_position_label(self, obj: PlayerSport) -> str:
        entry = catalog.sport(obj.sport) or {}
        return next(
            (
                item["label"]
                for item in entry.get("positions", [])
                if item["key"] == obj.primary_position
            ),
            obj.primary_position,
        )


class MeasurementSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()
    verified = serializers.BooleanField(source="is_verified", read_only=True)
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Measurement
        fields = [
            "id",
            "kind",
            "label",
            "value",
            "text_value",
            "unit",
            "measured_on",
            "source",
            "verified",
            "verified_by_name",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "label",
            "unit",
            "source",
            "verified",
            "verified_by_name",
            "created_at",
        ]

    def validate(self, attrs: dict) -> dict:
        spec = catalog.measurement(attrs.get("kind", ""))
        if spec is None:
            raise serializers.ValidationError({"kind": "Unknown measurement."})
        if spec["kind"] == "number":
            value = attrs.get("value")
            if value is None or value <= 0:
                raise serializers.ValidationError({"value": "Enter a positive number."})
            attrs["text_value"] = ""
            attrs["unit"] = spec["unit"]
        else:
            choice = (attrs.get("text_value") or "").strip().lower()
            if choice not in spec["choices"]:
                raise serializers.ValidationError(
                    {"text_value": f"Choose one of: {', '.join(spec['choices'])}."}
                )
            attrs["text_value"] = choice
            attrs["value"] = None
            attrs["unit"] = ""
        if attrs["measured_on"] > today():
            raise serializers.ValidationError({"measured_on": "The date cannot be in the future."})
        return attrs

    def get_label(self, obj: Measurement) -> str:
        return (catalog.measurement(obj.kind) or {}).get("label", obj.kind)

    def get_verified_by_name(self, obj: Measurement) -> str:
        if not obj.is_verified:
            return ""
        return obj.verified_by.display_name or obj.verified_by.get_full_name()


class InjurySerializer(serializers.ModelSerializer):
    class Meta:
        model = InjuryRecord
        fields = ["id", "description", "injured_on", "recovered_on", "shared_with_scouts"]
        read_only_fields = ["id"]


class HighlightVideoSerializer(serializers.ModelSerializer):
    playback_url = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = HighlightVideo
        fields = ["id", "title", "url", "media_asset", "playback_url", "status", "created_at"]
        read_only_fields = ["id", "playback_url", "status", "created_at"]

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("url") and not attrs.get("media_asset"):
            raise serializers.ValidationError("Add a video link or upload a video.")
        asset = attrs.get("media_asset")
        request = self.context.get("request")
        if asset is not None and request and asset.owner_id != request.user.id:
            raise serializers.ValidationError({"media_asset": "Use a video you uploaded."})
        return attrs

    def get_playback_url(self, obj: HighlightVideo) -> str:
        if obj.media_asset_id:
            return obj.media_asset.url
        return obj.url

    def get_status(self, obj: HighlightVideo) -> str:
        return obj.media_asset.status if obj.media_asset_id else "ready"


class GuardianLinkSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="profile.full_name", read_only=True)
    player_age_group = serializers.SerializerMethodField()
    profile_id = serializers.UUIDField(source="profile.id", read_only=True)
    guardian_name = serializers.SerializerMethodField()

    class Meta:
        model = GuardianLink
        fields = [
            "id",
            "profile_id",
            "player_name",
            "player_age_group",
            "invited_email",
            "relationship",
            "status",
            "guardian_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_player_age_group(self, obj: GuardianLink) -> str | None:
        group = age_group(obj.profile.date_of_birth)
        return group["label"] if group else None

    def get_guardian_name(self, obj: GuardianLink) -> str:
        if obj.guardian_id is None:
            return ""
        return obj.guardian.display_name or obj.guardian.get_full_name()


class GuardianInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    relationship = serializers.CharField(max_length=40, required=False, allow_blank=True)


class ConsentDecisionSerializer(serializers.Serializer):
    visibility = serializers.ChoiceField(
        choices=[PlayerProfile.Visibility.SCOUTS, PlayerProfile.Visibility.PUBLIC]
    )
    sections = serializers.ListField(child=serializers.CharField(), required=False)
    note = serializers.CharField(max_length=280, required=False, allow_blank=True)

    def validate_sections(self, value: list[str]) -> list[str]:
        known = catalog.keys(catalog.CONSENT_SECTIONS)
        unknown = [item for item in value if item not in known]
        if unknown:
            raise serializers.ValidationError(f"Unknown sections: {', '.join(unknown)}.")
        required = [item["key"] for item in catalog.CONSENT_SECTIONS if item["required"]]
        return list(dict.fromkeys([*required, *value]))


class ConsentRecordSerializer(serializers.ModelSerializer):
    given_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ConsentRecord
        fields = [
            "id",
            "given_by_name",
            "given_as",
            "action",
            "visibility",
            "sections",
            "note",
            "created_at",
        ]
        read_only_fields = fields

    def get_given_by_name(self, obj: ConsentRecord) -> str:
        if obj.given_by_id is None:
            return ""
        return obj.given_by.display_name or obj.given_by.get_full_name()


def _latest_measurements(profile: PlayerProfile) -> list[Measurement]:
    seen: dict[str, Measurement] = {}
    for item in profile.measurements.select_related("verified_by").order_by(
        "kind", "-measured_on", "-created_at"
    ):
        seen.setdefault(item.kind, item)
    return list(seen.values())


class PlayerProfileSerializer(serializers.ModelSerializer):
    """The owner's (and guardian's) full view, and the shape used to edit it."""

    age = serializers.SerializerMethodField()
    age_group = serializers.SerializerMethodField()
    is_minor = serializers.SerializerMethodField()
    effective_visibility = serializers.SerializerMethodField()
    consent_status = serializers.SerializerMethodField()
    sports = PlayerSportSerializer(many=True, read_only=True)
    teams = serializers.SerializerMethodField()
    team_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text=(
            "School or club sides on Fair Measure. A player can list several, "
            "including in different competitions."
        ),
    )
    measurements = serializers.SerializerMethodField()
    measurement_history = MeasurementSerializer(source="measurements", many=True, read_only=True)
    injuries = InjurySerializer(many=True, read_only=True)
    videos = HighlightVideoSerializer(many=True, read_only=True)
    guardians = GuardianLinkSerializer(many=True, read_only=True)
    access = serializers.SerializerMethodField()

    class Meta:
        model = PlayerProfile
        fields = [
            "id",
            "first_name",
            "last_name",
            "photo_url",
            "date_of_birth",
            "age",
            "age_group",
            "is_minor",
            "gender_category",
            "nationality",
            "region",
            "school_or_club",
            "teams",
            "team_ids",
            "bio",
            "availability",
            "availability_note",
            "visibility",
            "effective_visibility",
            "consent_status",
            "sports",
            "measurements",
            "measurement_history",
            "injuries",
            "videos",
            "guardians",
            "access",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "age",
            "age_group",
            "is_minor",
            "school_or_club",
            "teams",
            "effective_visibility",
            "consent_status",
            "sports",
            "measurements",
            "measurement_history",
            "injuries",
            "videos",
            "guardians",
            "access",
            "updated_at",
        ]
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": True},
        }

    def validate_gender_category(self, value: str) -> str:
        if value and value not in catalog.keys(catalog.GENDER_CATEGORIES):
            raise serializers.ValidationError("Choose a category from the list.")
        return value

    def validate_region(self, value: str) -> str:
        if value and value not in catalog.keys(catalog.REGIONS):
            raise serializers.ValidationError("Choose a region from the list.")
        return value

    def validate_date_of_birth(self, value):
        if value and value > today():
            raise serializers.ValidationError("The date of birth cannot be in the future.")
        return value

    def validate_team_ids(self, value: list) -> list:
        if len(value) > MAX_PROFILE_TEAMS:
            raise serializers.ValidationError(
                f"A profile can list up to {MAX_PROFILE_TEAMS} teams."
            )
        if len(set(value)) != len(value):
            raise serializers.ValidationError("The same team is listed twice.")
        if not value:
            return value

        from apps.competitions.models import Participant
        from apps.competitions.views import visible_competitions

        teams = {
            team.id: team
            for team in Participant.objects.filter(
                pk__in=value, kind=Participant.Kind.TEAM, is_active=True
            ).select_related("competition")
        }
        missing = [str(item) for item in value if item not in teams]
        if missing:
            raise serializers.ValidationError(
                "Choose school or club sides that exist on Fair Measure."
            )

        request = self.context.get("request")
        user = request.user if request else None
        visible = set(visible_competitions(user).values_list("id", flat=True)) if user else set()
        roster = roster_team_ids(user)
        blocked = [
            team.name
            for team in teams.values()
            if team.competition_id not in visible and team.id not in roster
        ]
        if blocked:
            raise serializers.ValidationError(
                f"These teams are not available to you: {', '.join(blocked)}."
            )
        return value

    def get_teams(self, obj: PlayerProfile) -> list[dict]:
        return affiliated_teams(obj)

    def create(self, validated_data: dict) -> PlayerProfile:
        team_ids = validated_data.pop("team_ids", [])
        user = validated_data.get("user")
        if user is not None:
            given, family = account_name(user)
            if not validated_data.get("first_name"):
                validated_data["first_name"] = given or (user.email or "Player").split("@")[0][:80]
            validated_data.setdefault("last_name", family)
            if user.date_of_birth and not validated_data.get("date_of_birth"):
                validated_data["date_of_birth"] = user.date_of_birth
            if user.avatar_url and not validated_data.get("photo_url"):
                validated_data["photo_url"] = user.avatar_url
            if user.bio and not validated_data.get("bio"):
                validated_data["bio"] = user.bio
            if user.country and not validated_data.get("nationality"):
                validated_data["nationality"] = user.country
        profile = super().create(validated_data)
        self._set_teams(profile, team_ids)
        self._sync_account(profile, validated_data)
        return profile

    def update(self, instance: PlayerProfile, validated_data: dict) -> PlayerProfile:
        team_ids = validated_data.pop("team_ids", None)
        profile = super().update(instance, validated_data)
        if team_ids is not None:
            self._set_teams(profile, team_ids)
        self._sync_account(profile, validated_data)
        return profile

    def _sync_account(self, profile: PlayerProfile, validated_data: dict) -> None:
        user = profile.user
        mapping = {
            "first_name": "given_name",
            "last_name": "family_name",
            "date_of_birth": "date_of_birth",
            "photo_url": "avatar_url",
            "bio": "bio",
            "nationality": "country",
        }
        changed: list[str] = []
        for src, dest in mapping.items():
            if src not in validated_data:
                continue
            value = validated_data[src]
            if getattr(user, dest) != value:
                setattr(user, dest, value)
                changed.append(dest)
        if changed:
            user.save(update_fields=changed)

    def to_representation(self, instance: PlayerProfile) -> dict:
        data = super().to_representation(instance)
        user = instance.user
        given, family = account_name(user)
        data["first_name"] = given or instance.first_name
        data["last_name"] = family or instance.last_name
        data["date_of_birth"] = user.date_of_birth or instance.date_of_birth
        data["photo_url"] = user.avatar_url or instance.photo_url
        data["bio"] = user.bio or instance.bio
        if user.country:
            data["nationality"] = user.country
        return data

    def _set_teams(self, profile: PlayerProfile, team_ids: list) -> None:
        profile.teams.set(team_ids)
        profile.school_or_club = school_or_club_label(affiliated_teams(profile))
        profile.save(update_fields=["school_or_club", "updated_at"])

    def get_age(self, obj: PlayerProfile) -> int | None:
        return age_on(date_of_birth_of(obj), today())

    def get_age_group(self, obj: PlayerProfile) -> dict | None:
        return age_group(date_of_birth_of(obj))

    def get_is_minor(self, obj: PlayerProfile) -> bool:
        return is_minor(obj)

    def get_effective_visibility(self, obj: PlayerProfile) -> str:
        return effective_visibility(obj)

    def get_consent_status(self, obj: PlayerProfile) -> dict:
        born = date_of_birth_of(obj)
        if not is_minor(obj) and born is not None:
            return {"needed": False, "granted": True, "visibility": None, "sections": []}
        consent = active_consent(obj)
        return {
            "needed": True,
            "granted": consent is not None,
            "visibility": consent.visibility if consent else None,
            "sections": consent.sections if consent else [],
            "missing_date_of_birth": born is None,
        }

    def get_measurements(self, obj: PlayerProfile) -> list[dict]:
        return MeasurementSerializer(_latest_measurements(obj), many=True).data

    def get_access(self, obj: PlayerProfile) -> str:
        return self.context.get("access", "owner")


class ScoutProfileSerializer(serializers.Serializer):
    """What a scout or the public may see. Contact details are never included."""

    def to_representation(self, profile: PlayerProfile) -> dict:
        access = self.context.get("access", "public")
        sections = shared_sections(profile)
        group = age_group(date_of_birth_of(profile))
        user = profile.user
        given, family = account_name(user)
        teams = affiliated_teams(profile)
        data: dict = {
            "id": str(profile.id),
            "first_name": given or profile.first_name,
            "last_name": family or profile.last_name,
            "photo_url": user.avatar_url or profile.photo_url,
            "age_group": group,
            "gender_category": profile.gender_category,
            "nationality": profile.nationality,
            "region": profile.region,
            "teams": teams,
            "school_or_club": school_or_club_label(teams, profile.school_or_club),
            "bio": user.bio or profile.bio,
            "access": access,
            "contact": "Contact this player through Fair Measure; details are never shared.",
            "sports": PlayerSportSerializer(profile.sports.all(), many=True).data,
            "measurements": [],
            "videos": [],
            "injuries": [],
            "availability": None,
            "updated_at": profile.updated_at,
        }
        # Exact age only for scouts; the public sees the age group.
        if access == "scout":
            data["age"] = age_on(date_of_birth_of(profile), today())
        if "physical" in sections:
            data["measurements"] = MeasurementSerializer(
                _latest_measurements(profile), many=True
            ).data
        if "videos" in sections:
            data["videos"] = HighlightVideoSerializer(profile.videos.all(), many=True).data
        if "availability" in sections:
            data["availability"] = {
                "status": profile.availability,
                "note": profile.availability_note,
            }
        if access == "scout":
            data["injuries"] = InjurySerializer(
                profile.injuries.filter(shared_with_scouts=True), many=True
            ).data
        return data


class ProfileCardSerializer(serializers.Serializer):
    """A compact row for lists."""

    def to_representation(self, profile: PlayerProfile) -> dict:
        primary = next(iter(profile.sports.all()), None)
        given, family = account_name(profile.user)
        group = age_group(date_of_birth_of(profile))
        teams = affiliated_teams(profile)
        return {
            "id": str(profile.id),
            "name": " ".join(part for part in (given, family) if part) or profile.full_name,
            "photo_url": profile.user.avatar_url or profile.photo_url,
            "age_group": group["label"] if group else None,
            "region": profile.region,
            "teams": teams,
            "school_or_club": school_or_club_label(teams, profile.school_or_club),
            "sport": PlayerSportSerializer(primary).data if primary else None,
        }
