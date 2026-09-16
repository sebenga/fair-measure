from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.competitions.models import Competition
from apps.core.models import BaseModel


class DeviceToken(BaseModel):
    """An FCM registration token for one installation of the app."""

    class Platform(models.TextChoices):
        IOS = "ios", _("iOS")
        ANDROID = "android", _("Android")
        WEB = "web", _("Web")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="device_tokens"
    )
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    device_name = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [models.Index(fields=["user", "is_active"])]

    def __str__(self) -> str:
        return f"{self.platform} token for {self.user}"


class NotificationPreference(BaseModel):
    """Per-competition mute settings. Absence of a row means "notify me"."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notification_preferences",
        help_text=_("Null means these are the user's global defaults."),
    )
    fixture_reminders = models.BooleanField(default=True)
    score_updates = models.BooleanField(default=True)
    feed_activity = models.BooleanField(default=True)
    announcements = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "competition"],
                name="uniq_pref_per_competition",
                condition=models.Q(competition__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user"],
                name="uniq_global_pref",
                condition=models.Q(competition__isnull=True),
            ),
        ]


class Notification(BaseModel):
    """An in-app notification, kept so users can see what they missed."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    kind = models.CharField(max_length=60)
    title = models.CharField(max_length=180)
    body = models.CharField(max_length=400, blank=True)
    data = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self) -> str:
        return self.title
