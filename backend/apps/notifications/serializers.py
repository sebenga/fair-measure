from rest_framework import serializers

from .models import DeviceToken, Notification, NotificationPreference


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ["id", "token", "platform", "device_name", "is_active", "last_seen_at"]
        read_only_fields = ["id", "last_seen_at"]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "competition",
            "fixture_reminders",
            "score_updates",
            "feed_activity",
            "announcements",
        ]
        read_only_fields = ["id"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "competition",
            "kind",
            "title",
            "body",
            "data",
            "read_at",
            "created_at",
        ]
        read_only_fields = [field for field in fields if field != "read_at"]
