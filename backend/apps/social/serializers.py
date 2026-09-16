from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from apps.accounts.serializers import UserSummarySerializer
from apps.media_assets.models import MediaAsset
from apps.media_assets.serializers import MediaAssetSerializer

from .models import Comment, Post, PostMedia, Reaction


class PostMediaSerializer(serializers.ModelSerializer):
    media_asset = MediaAssetSerializer(read_only=True)

    class Meta:
        model = PostMedia
        fields = ["id", "media_asset", "display_order"]


class CommentSerializer(serializers.ModelSerializer):
    author = UserSummarySerializer(read_only=True)
    my_reaction = serializers.SerializerMethodField()
    reaction_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "parent",
            "body",
            "reply_count",
            "reaction_count",
            "my_reaction",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "reply_count", "created_at", "updated_at"]

    def get_my_reaction(self, obj: Comment) -> str | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        reaction = next(
            (r for r in obj.reactions.all() if r.user_id == request.user.id), None
        )
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
        reaction = next(
            (r for r in obj.reactions.all() if r.user_id == request.user.id), None
        )
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
        if not value:
            return value
        request = self.context["request"]
        # Only the uploader may attach an asset, so nobody can embed someone
        # else's private media by guessing an id.
        owned = set(
            MediaAsset.objects.filter(id__in=value, owner=request.user).values_list(
                "id", flat=True
            )
        )
        missing = [str(item) for item in value if item not in owned]
        if missing:
            raise serializers.ValidationError(
                f"These media assets are not yours or do not exist: {', '.join(missing)}."
            )
        return value

    def _sync_media(self, post: Post, media_ids: list) -> None:
        PostMedia.objects.filter(post=post).exclude(media_asset_id__in=media_ids).delete()
        existing = set(
            PostMedia.objects.filter(post=post).values_list("media_asset_id", flat=True)
        )
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
