from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

PERSONAL_FIELDS = [
    "given_name",
    "family_name",
    "date_of_birth",
    "id_number",
    "phone",
    "city",
    "country",
    "headline",
    "website",
    "experience",
    "education",
    "skills",
    "languages",
]


class OptionalDateField(serializers.DateField):
    """A date that may be left blank. An empty string is stored as no date."""

    def to_internal_value(self, value):
        if value in (None, ""):
            return None
        return super().to_internal_value(value)


class UserSerializer(serializers.ModelSerializer):
    date_of_birth = OptionalDateField(allow_null=True, required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "display_name",
            "avatar_url",
            "bio",
            *PERSONAL_FIELDS,
            "email_verified",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "email_verified", "date_joined"]
        extra_kwargs = {
            name: {"required": False, "allow_blank": True}
            for name in PERSONAL_FIELDS
            if name != "date_of_birth"
        }

    def validate_date_of_birth(self, value):
        if value and value > timezone.localdate():
            raise serializers.ValidationError("Date of birth is in the future.")
        return value


class ProfileSerializer(serializers.ModelSerializer):
    """A person who can be picked when a team is created."""

    class Meta:
        model = User
        fields = ["id", "display_name", "email", "avatar_url", "bio", "headline"]


class UserSummarySerializer(serializers.ModelSerializer):
    """The lightweight shape embedded in posts, comments and memberships."""

    class Meta:
        model = User
        fields = ["id", "display_name", "avatar_url"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "password"]
        read_only_fields = ["id"]

    def validate_email(self, value: str) -> str:
        normalized = User.objects.normalize_email(value).lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return normalized

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data: dict):
        return User.objects.create_user(**validated_data)


class FairMeasureTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds profile claims so the client and the Socket.io gateway can avoid a round trip."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["display_name"] = user.display_name
        return token

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class GoogleAuthSerializer(serializers.Serializer):
    """Exchanges a Google ID token (from the Ionic/Capacitor client) for our own JWTs."""

    id_token = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(style={"input_type": "password"})
    new_password = serializers.CharField(min_length=8, style={"input_type": "password"})

    def validate_current_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value: str) -> str:
        validate_password(value, self.context["request"].user)
        return value
