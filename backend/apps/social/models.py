"""The competition feed: posts, threaded comments, reactions and attachments."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.competitions.models import Competition, Participant
from apps.core.models import BaseModel, SoftDeleteModel
from apps.fixtures.models import Fixture
from apps.media_assets.models import MediaAsset


class Post(BaseModel, SoftDeleteModel):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    body = models.TextField(blank=True)
    # Optional context: a post can be attached to a match or a team.
    fixture = models.ForeignKey(
        Fixture, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts"
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    is_pinned = models.BooleanField(default=False)
    is_announcement = models.BooleanField(
        default=False, help_text=_("Announcements notify every member.")
    )

    # Denormalised counters. The feed shows them on every row, so recomputing
    # them per request would mean two extra aggregates per post.
    comment_count = models.PositiveIntegerField(default=0)
    reaction_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["competition", "-created_at"]),
            models.Index(fields=["fixture"]),
        ]

    def __str__(self) -> str:
        return f"{self.author} · {self.body[:40]}"


class PostMedia(BaseModel):
    """Ordered attachments on a post."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="media")
    media_asset = models.ForeignKey(
        MediaAsset, on_delete=models.CASCADE, related_name="post_attachments"
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]
        constraints = [
            models.UniqueConstraint(fields=["post", "media_asset"], name="uniq_media_per_post")
        ]


class Comment(BaseModel, SoftDeleteModel):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    # Self-referencing for replies. Kept to one level in the API so threads stay
    # readable on a phone.
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    body = models.TextField(blank=True)
    reply_count = models.PositiveIntegerField(default=0)
    reaction_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["post", "created_at"])]

    def __str__(self) -> str:
        return f"{self.author} · {self.body[:40]}"


class CommentMedia(BaseModel):
    """Ordered photos and clips attached to a comment or reply."""

    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="media")
    media_asset = models.ForeignKey(
        MediaAsset, on_delete=models.CASCADE, related_name="comment_attachments"
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["comment", "media_asset"], name="uniq_media_per_comment"
            )
        ]


class Reaction(BaseModel):
    class Kind(models.TextChoices):
        LIKE = "like", _("Like")
        LOVE = "love", _("Love")
        LAUGH = "laugh", _("Laugh")
        WOW = "wow", _("Wow")
        CLAP = "clap", _("Clap")

    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, null=True, blank=True, related_name="reactions"
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, null=True, blank=True, related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.LIKE)

    class Meta:
        constraints = [
            # One reaction per user per target; changing it is an update.
            models.UniqueConstraint(
                fields=["post", "user"],
                name="uniq_post_reaction_per_user",
                condition=models.Q(post__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["comment", "user"],
                name="uniq_comment_reaction_per_user",
                condition=models.Q(comment__isnull=False),
            ),
            models.CheckConstraint(
                condition=models.Q(post__isnull=False) ^ models.Q(comment__isnull=False),
                name="reaction_targets_exactly_one",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.kind}"


REACTION_KIND_CHOICES = Reaction.Kind.choices
