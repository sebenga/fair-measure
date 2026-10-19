from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.competitions.models import Competition
from apps.core.models import BaseModel


class MediaAsset(BaseModel):
    """A photo or video, wherever it happens to live.

    Uploads never pass through Django. The client asks for a signed target, uploads
    straight to R2/S3 or the video provider, and the asset flips to `ready` when
    the client confirms or the provider's webhook arrives. Keeping bytes out of
    the API server is what makes video uploads survivable on a mobile connection.
    """

    class Kind(models.TextChoices):
        IMAGE = "image", _("Image")
        VIDEO = "video", _("Video")

    class Status(models.TextChoices):
        PENDING = "pending", _("Awaiting upload")
        PROCESSING = "processing", _("Processing")
        READY = "ready", _("Ready")
        FAILED = "failed", _("Failed")

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="media_assets"
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="media_assets",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    caption = models.CharField(max_length=280, blank=True)

    # Object storage (images and original files).
    storage_provider = models.CharField(max_length=20, blank=True)
    storage_key = models.CharField(max_length=512, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    # Video provider (Cloudflare Stream or Mux).
    video_provider = models.CharField(max_length=24, blank=True)
    provider_asset_id = models.CharField(max_length=180, blank=True, db_index=True)
    playback_id = models.CharField(max_length=180, blank=True)
    playback_url = models.URLField(blank=True, max_length=600)
    thumbnail_url = models.URLField(blank=True, max_length=600)
    duration_seconds = models.FloatField(null=True, blank=True)

    error_message = models.CharField(max_length=400, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["owner", "status"])]

    def __str__(self) -> str:
        return f"{self.kind} {self.id} ({self.status})"

    @property
    def url(self) -> str:
        if self.kind == self.Kind.VIDEO:
            return self.playback_url
        if self.storage_provider == "local" and self.storage_key:
            from .storage import local_url

            return local_url(self.storage_key)
        if self.storage_key and settings.STORAGE_PUBLIC_BASE_URL:
            return f"{settings.STORAGE_PUBLIC_BASE_URL.rstrip('/')}/{self.storage_key}"
        return ""


MEDIA_STATUS_CHOICES = MediaAsset.Status.choices
MEDIA_KIND_CHOICES = MediaAsset.Kind.choices
