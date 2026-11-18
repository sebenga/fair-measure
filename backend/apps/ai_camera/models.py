"""AI camera recordings and human-confirmed event suggestions."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.fixtures.models import Fixture, ScoreEvent


class MatchRecording(BaseModel):
    """Chunked match video stored in object storage (never on Render disks)."""

    class Status(models.TextChoices):
        UPLOADING = "uploading", _("Uploading")
        READY = "ready", _("Ready")
        PROCESSING = "processing", _("Processing")
        DONE = "done", _("Done")
        FAILED = "failed", _("Failed")

    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name="recordings")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="match_recordings",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADING)
    storage_key = models.CharField(max_length=400, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    consent_version = models.CharField(max_length=40, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class RecordingChunk(BaseModel):
    recording = models.ForeignKey(MatchRecording, on_delete=models.CASCADE, related_name="chunks")
    index = models.PositiveIntegerField()
    storage_key = models.CharField(max_length=400)
    bytes = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["recording", "index"], name="uniq_recording_chunk")
        ]


class AiEventSuggestion(BaseModel):
    """AI-proposed match event; never official until a human accepts it."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Accepted")
        REJECTED = "rejected", _("Rejected")
        EDITED = "edited", _("Edited")

    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name="ai_suggestions")
    recording = models.ForeignKey(
        MatchRecording, on_delete=models.SET_NULL, null=True, blank=True, related_name="suggestions"
    )
    event_type = models.CharField(max_length=64)
    timestamp_seconds = models.DecimalField(max_digits=10, decimal_places=2)
    clip_url = models.URLField(blank=True)
    team_side_id = models.UUIDField(null=True, blank=True)
    player_guess_id = models.UUIDField(null=True, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    is_disciplinary = models.BooleanField(
        default=False,
        help_text=_("Cards and score events must never auto-apply."),
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_suggestion_reviews",
    )
    match_event = models.ForeignKey(
        ScoreEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_suggestions",
    )
    provider = models.CharField(max_length=64, blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["timestamp_seconds", "created_at"]
        indexes = [models.Index(fields=["fixture", "status"])]
