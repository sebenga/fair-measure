from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.media_assets.models import MediaAsset
from apps.media_assets.serializers import MediaAssetSerializer

from .models import Comment, CommentMedia, Post, PostMedia, Reaction

MAX_ATTACHMENTS = 4


def validate_attachments(value: list, *, user, competition) -> list:
    """Only the uploader may attach an asset, and only to the competition it was uploaded for.

    That stops anyone embedding someone else's private media by guessing an id.
    """

    if not value:
        return value
    if len(value) > MAX_ATTACHMENTS:
        raise serializers.ValidationError(
            f"Attach up to {MAX_ATTACHMENTS} photos or videos at a time."
        )
    if len(set(value)) != len(value):
        raise serializers.ValidationError("The same file is attached twice.")

    assets = {asset.id: asset for asset in MediaAsset.objects.filter(id__in=value, owner=user)}
    missing = [str(item) for item in value if item not in assets]
    if missing:
        raise serializers.ValidationError(
            f"These media assets are not yours or do not exist: {', '.join(missing)}."
        )
    for asset in assets.values():
        if asset.status == MediaAsset.Status.FAILED:
            raise serializers.ValidationError(
                "One of the files failed to upload. Remove it and try again."
            )
        if asset.kind == MediaAsset.Kind.IMAGE and asset.status != MediaAsset.Status.READY:
            raise serializers.ValidationError("A photo is still uploading. Try again in a moment.")
        if asset.competition_id and competition and asset.competition_id != competition.id:
            raise serializers.ValidationError("That file was uploaded to a different competition.")
    return value


class PostMediaSerializer(serializers.ModelSerializer):
    media_asset = MediaAssetSerializer(read_only=True)

    class Meta:
        model = PostMedia
        fields = ["id", "media_asset", "display_order"]


class CommentMediaSerializer(serializers.ModelSerializer):
    media_asset = MediaAssetSerializer(read_only=True)

    class Meta:
        model = CommentMedia
        fields = ["id", "media_asset", "display_order"]


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    media = CommentMediaSerializer(many=True, read_only=True)
    media_asset_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True, default=list
    )
    body = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")
    my_reaction = serializers.SerializerMethodField()
    reaction_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "parent",
            "body",
            "media",
            "media_asset_ids",
            "reply_count",
            "reaction_count",
            "my_reaction",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "reply_count", "created_at", "updated_at"]

    def validate_media_asset_ids(self, value: list) -> list:
        post = self.context.get("post")
        return validate_attachments(
            value,
            user=self.context["request"].user,
            competition=post.competition if post else None,
        )

    def validate(self, attrs: dict) -> dict:
        body = attrs.get("body", getattr(self.instance, "body", "")) or ""
        attrs["body"] = body.strip() if "body" in attrs else body
        has_media = bool(attrs.get("media_asset_ids")) or bool(
            self.instance and self.instance.media.exists()
        )
        if not attrs["body"] and not has_media:
            raise serializers.ValidationError("Write something or attach a photo or video.")
        if self.instance is not None:
            # A comment cannot be moved to another thread once written.
            attrs.pop("parent", None)
        return attrs

    def _sync_media(self, comment: Comment, media_ids: list) -> None:
        CommentMedia.objects.filter(comment=comment).exclude(media_asset_id__in=media_ids).delete()
        existing = set(
            CommentMedia.objects.filter(comment=comment).values_list("media_asset_id", flat=True)
        )
        CommentMedia.objects.bulk_create(
            [
                CommentMedia(comment=comment, media_asset_id=media_id, display_order=index)
                for index, media_id in enumerate(media_ids)
                if media_id not in existing
            ]
        )

    @transaction.atomic
    def create(self, validated_data: dict) -> Comment:
        media_ids = validated_data.pop("media_asset_ids", [])
        comment = Comment.objects.create(**validated_data)
        self._sync_media(comment, media_ids)
        return comment

    @transaction.atomic
    def update(self, instance: Comment, validated_data: dict) -> Comment:
        media_ids = validated_data.pop("media_asset_ids", None)
        comment = super().update(instance, validated_data)
        if media_ids is not None and "media_asset_ids" in self.initial_data:
            self._sync_media(comment, media_ids)
        return comment

    def get_my_reaction(self, obj: Comment) -> str | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        reaction = next((r for r in obj.reactions.all() if r.user_id == request.user.id), None)
        return reaction.kind if reaction else None

    def validate_parent(self, parent: Comment | None) -> Comment | None:
        if parent is None:
            return None
        post = self.context.get("post")
        if post and parent.post_id != post.id:
            raise serializers.ValidationError("That comment belongs to a different post.")
        if parent.parent_id is not None:
            raise serializers.ValidationError(
                "Replies are limited to one level. Reply to the top-level comment instead."
            )
        return parent


class PostSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    my_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "competition",
            "author",
            "body",
            "fixture",
            "participant",
            "is_pinned",
            "is_announcement",
            "media",
            "comment_count",
            "reaction_count",
            "my_reaction",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "competition",
            "author",
            "comment_count",
            "reaction_count",
            "created_at",
            "updated_at",
        ]

    def get_my_reaction(self, obj: Post) -> str | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        reaction = next((r for r in obj.reactions.all() if r.user_id == request.user.id), None)
        return reaction.kind if reaction else None


class PostWriteSerializer(serializers.ModelSerializer):
    media_asset_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True, default=list
    )

    class Meta:
        model = Post
        fields = [
            "id",
            "body",
            "fixture",
            "participant",
            "is_pinned",
            "is_announcement",
            "media_asset_ids",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs: dict) -> dict:
        body = attrs.get("body", getattr(self.instance, "body", "")) or ""
        media_ids = attrs.get("media_asset_ids")
        has_existing_media = bool(self.instance and self.instance.media.exists())

        if not body.strip() and not media_ids and not has_existing_media:
            raise serializers.ValidationError("Add some text or attach a photo or video.")

        competition = self.context["competition"]
        for field in ("fixture", "participant"):
            value = attrs.get(field)
            if value is not None and value.competition_id != competition.id:
                raise serializers.ValidationError(
                    {field: f"That {field} belongs to a different competition."}
                )
        return attrs

    def validate_media_asset_ids(self, value: list) -> list:
        return validate_attachments(
            value,
            user=self.context["request"].user,
            competition=self.context.get("competition"),
        )

    def to_representation(self, instance: Post) -> dict:
        # Writes answer with the full read shape so the client can render the post at once.
        return PostSerializer(instance, context=self.context).data

    def _sync_media(self, post: Post, media_ids: list) -> None:
        PostMedia.objects.filter(post=post).exclude(media_asset_id__in=media_ids).delete()
        existing = set(PostMedia.objects.filter(post=post).values_list("media_asset_id", flat=True))
        PostMedia.objects.bulk_create(
            [
                PostMedia(post=post, media_asset_id=media_id, display_order=index)
                for index, media_id in enumerate(media_ids)
                if media_id not in existing
            ]
        )

    @transaction.atomic
    def create(self, validated_data: dict) -> Post:
        media_ids = validated_data.pop("media_asset_ids", [])
        post = Post.objects.create(**validated_data)
        self._sync_media(post, media_ids)
        return post

    @transaction.atomic
    def update(self, instance: Post, validated_data: dict) -> Post:
        media_ids = validated_data.pop("media_asset_ids", None)
        post = super().update(instance, validated_data)
        if media_ids is not None:
            self._sync_media(post, media_ids)
        return post


class ReactionSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Reaction.Kind.choices, default=Reaction.Kind.LIKE)
