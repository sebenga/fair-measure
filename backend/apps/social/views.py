from __future__ import annotations

from django.db import transaction
from django.db.models import F, Prefetch
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response

from apps.competitions.models import Competition
from apps.competitions.views import visible_competitions
from apps.core.bus import Queues, competition_room, enqueue_job, publish_event
from apps.core.pagination import FeedPagination
from apps.core.permissions import Role, has_at_least

from .access import takes_part
from .models import Comment, Post, Reaction
from .serializers import (
    CommentSerializer,
    PostSerializer,
    PostWriteSerializer,
    ReactionSerializer,
)


class ReactionMixin:
    """Shared react/unreact behaviour for posts and comments."""

    reaction_field: str  # "post" or "comment"
    count_field = "reaction_count"

    def _toggle_reaction(self, target, request: Request) -> Response:
        serializer = ReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kind = serializer.validated_data["kind"]

        lookup = {self.reaction_field: target, "user": request.user}

        with transaction.atomic():
            existing = Reaction.objects.filter(**lookup).first()

            if existing and existing.kind == kind:
                # Reacting with the same emoji again removes the reaction.
                existing.delete()
                type(target).objects.filter(pk=target.pk).update(
                    **{self.count_field: F(self.count_field) - 1}
                )
                result, created = None, False
            elif existing:
                existing.kind = kind
                existing.save(update_fields=["kind"])
                result, created = kind, False
            else:
                Reaction.objects.create(**lookup, kind=kind)
                type(target).objects.filter(pk=target.pk).update(
                    **{self.count_field: F(self.count_field) + 1}
                )
                result, created = kind, True

        target.refresh_from_db(fields=[self.count_field])
        return Response(
            {
                "my_reaction": result,
                self.count_field: getattr(target, self.count_field),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Feed"],
        summary="Read a competition's feed",
        parameters=[
            OpenApiParameter("fixture", str, description="Only posts about one fixture."),
            OpenApiParameter("participant", str, description="Only posts about one participant."),
            OpenApiParameter("has_media", bool, description="Only posts with attachments."),
        ],
    ),
    retrieve=extend_schema(tags=["Feed"], summary="Get a single post"),
    create=extend_schema(tags=["Feed"], summary="Write a post"),
    partial_update=extend_schema(tags=["Feed"], summary="Edit a post"),
    destroy=extend_schema(tags=["Feed"], summary="Delete a post"),
)
class PostViewSet(ReactionMixin, viewsets.ModelViewSet):
    queryset = Post.objects.none()
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = FeedPagination
    reaction_field = "post"

    def get_competition(self) -> Competition:
        if not hasattr(self, "_competition"):
            self._competition = get_object_or_404(
                visible_competitions(self.request.user), pk=self.kwargs["competition_pk"]
            )
        return self._competition

    def get_serializer_context(self) -> dict:
        return {**super().get_serializer_context(), "competition": self.get_competition()}

    def get_queryset(self):
        queryset = (
            Post.objects.filter(competition=self.get_competition())
            .alive()
            .select_related("author", "competition", "fixture")
            .prefetch_related("media__media_asset", "fixture__sides__participant")
        )

        if self.request.user.is_authenticated:
            # Narrowed to the caller so `my_reaction` costs one query for the
            # whole page instead of one per post.
            queryset = queryset.prefetch_related(
                Prefetch("reactions", queryset=Reaction.objects.filter(user=self.request.user))
            )

        params = self.request.query_params
        if fixture_id := params.get("fixture"):
            queryset = queryset.filter(fixture_id=fixture_id)
        if participant_id := params.get("participant"):
            queryset = queryset.filter(participant_id=participant_id)
        if params.get("has_media") in {"1", "true", "yes"}:
            queryset = queryset.filter(media__isnull=False).distinct()
        if kind := params.get("kind"):
            queryset = queryset.filter(kind=kind)

        return queryset

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PostWriteSerializer
        return PostSerializer

    def _assert_member(self) -> None:
        if not takes_part(self.get_competition(), self.request.user):
            raise PermissionDenied("Only people in this competition can post and react.")

    def perform_create(self, serializer) -> None:
        self._assert_member()
        competition = self.get_competition()

        if serializer.validated_data.get("is_announcement") and not has_at_least(
            competition, self.request.user, Role.ADMIN
        ):
            raise PermissionDenied("Only admins can post announcements.")

        kind = (
            Post.Kind.COMPETITION
            if serializer.validated_data.get("is_announcement")
            else Post.Kind.PROFILE
        )
        serializer.save(competition=competition, author=self.request.user, kind=kind)
        post = serializer.instance

        publish_event(
            "post.created",
            {
                "competition_id": str(competition.id),
                "post_id": str(post.id),
                "author_id": str(self.request.user.id),
            },
            [competition_room(competition.id)],
        )
        enqueue_job(Queues.SEARCH, "index-post", {"post_id": str(post.id)})
        if post.is_announcement:
            enqueue_job(
                Queues.NOTIFICATIONS,
                "announcement",
                {"competition_id": str(competition.id), "post_id": str(post.id)},
            )

    def perform_update(self, serializer) -> None:
        post = self.get_object()
        if post.author_id != self.request.user.id and not has_at_least(
            self.get_competition(), self.request.user, Role.ADMIN
        ):
            raise PermissionDenied("You can only edit your own posts.")
        serializer.save()

    def perform_destroy(self, instance: Post) -> None:
        if instance.author_id != self.request.user.id and not has_at_least(
            self.get_competition(), self.request.user, Role.ADMIN
        ):
            raise PermissionDenied("You can only delete your own posts.")
        # Soft delete keeps the comment thread's history intact for moderation.
        instance.soft_delete()
        publish_event(
            "post.deleted",
            {"competition_id": str(instance.competition_id), "post_id": str(instance.id)},
            [competition_room(instance.competition_id)],
        )

    @extend_schema(
        tags=["Feed"],
        summary="React to a post, or remove your reaction",
        description="Sending the same reaction twice removes it.",
        request=ReactionSerializer,
        responses={200: dict, 201: dict},
    )
    @action(detail=True, methods=["post"])
    def react(self, request: Request, **kwargs) -> Response:
        self._assert_member()
        return self._toggle_reaction(self.get_object(), request)


@extend_schema_view(
    list=extend_schema(
        tags=["Feed"],
        summary="Public Discover feed",
        description="Recent posts from competitions you can see, for the mixed Discover stream.",
        parameters=[
            OpenApiParameter("has_media", bool, description="Only posts with photos or videos."),
            OpenApiParameter("kind", str, description="profile | competition | live"),
        ],
    ),
)
class DiscoverPostViewSet(viewsets.ReadOnlyModelViewSet):
    """Cross-league posts for Discover — updates, comments, photos and clips."""

    serializer_class = PostSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = FeedPagination
    queryset = Post.objects.none()

    def get_queryset(self):
        queryset = (
            Post.objects.filter(competition__in=visible_competitions(self.request.user))
            .alive()
            .select_related("author", "competition", "fixture")
            .prefetch_related("media__media_asset", "fixture__sides__participant")
        )
        if self.request.user.is_authenticated:
            queryset = queryset.prefetch_related(
                Prefetch("reactions", queryset=Reaction.objects.filter(user=self.request.user))
            )
        if self.request.query_params.get("has_media") in {"1", "true", "yes"}:
            queryset = queryset.filter(media__isnull=False).distinct()
        if kind := self.request.query_params.get("kind"):
            queryset = queryset.filter(kind=kind)
        return queryset


@extend_schema_view(
    list=extend_schema(tags=["Feed"], summary="List a post's comments"),
    create=extend_schema(tags=["Feed"], summary="Comment on a post"),
    partial_update=extend_schema(tags=["Feed"], summary="Edit a comment"),
    destroy=extend_schema(tags=["Feed"], summary="Delete a comment"),
)
class CommentViewSet(ReactionMixin, viewsets.ModelViewSet):
    queryset = Comment.objects.none()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    reaction_field = "comment"

    def get_post(self) -> Post:
        if not hasattr(self, "_post"):
            self._post = get_object_or_404(
                Post.objects.alive().select_related("competition"),
                pk=self.kwargs["post_pk"],
                competition__in=visible_competitions(self.request.user),
            )
        return self._post

    def get_serializer_context(self) -> dict:
        return {**super().get_serializer_context(), "post": self.get_post()}

    def get_queryset(self):
        queryset = (
            Comment.objects.filter(post=self.get_post())
            .alive()
            .select_related("author")
            .prefetch_related("media__media_asset")
        )

        # Top-level only by default; replies are fetched per comment.
        if self.action == "list" and self.request.query_params.get("parent") is None:
            queryset = queryset.filter(parent__isnull=True)
        elif parent_id := self.request.query_params.get("parent"):
            queryset = queryset.filter(parent_id=parent_id)

        if self.request.user.is_authenticated:
            queryset = queryset.prefetch_related(
                Prefetch("reactions", queryset=Reaction.objects.filter(user=self.request.user))
            )
        return queryset

    def _assert_member(self) -> None:
        if not takes_part(self.get_post().competition, self.request.user):
            raise PermissionDenied("Only people in this competition can comment and react.")

    def perform_create(self, serializer) -> None:
        self._assert_member()
        post = self.get_post()

        with transaction.atomic():
            serializer.save(post=post, author=self.request.user)
            comment = serializer.instance
            Post.objects.filter(pk=post.pk).update(comment_count=F("comment_count") + 1)
            if comment.parent_id:
                Comment.objects.filter(pk=comment.parent_id).update(
                    reply_count=F("reply_count") + 1
                )

        publish_event(
            "comment.created",
            {
                "competition_id": str(post.competition_id),
                "post_id": str(post.id),
                "comment_id": str(comment.id),
                "parent_id": str(comment.parent_id) if comment.parent_id else None,
                "author_id": str(self.request.user.id),
            },
            [competition_room(post.competition_id)],
        )
        enqueue_job(
            Queues.NOTIFICATIONS,
            "comment-reply",
            {
                "post_id": str(post.id),
                "comment_id": str(comment.id),
                "actor_id": str(self.request.user.id),
            },
        )

    def perform_update(self, serializer) -> None:
        comment = self.get_object()
        if comment.author_id != self.request.user.id:
            raise PermissionDenied("You can only edit your own comments.")
        serializer.save()

    def perform_destroy(self, instance: Comment) -> None:
        post = self.get_post()
        if instance.author_id != self.request.user.id and not has_at_least(
            post.competition, self.request.user, Role.ADMIN
        ):
            raise PermissionDenied("You can only delete your own comments.")

        with transaction.atomic():
            instance.soft_delete()
            Post.objects.filter(pk=post.pk, comment_count__gt=0).update(
                comment_count=F("comment_count") - 1
            )
            if instance.parent_id:
                Comment.objects.filter(pk=instance.parent_id, reply_count__gt=0).update(
                    reply_count=F("reply_count") - 1
                )

        publish_event(
            "comment.deleted",
            {
                "competition_id": str(post.competition_id),
                "post_id": str(post.id),
                "comment_id": str(instance.id),
                "parent_id": str(instance.parent_id) if instance.parent_id else None,
            },
            [competition_room(post.competition_id)],
        )

    @extend_schema(
        tags=["Feed"],
        summary="React to a comment, or remove your reaction",
        request=ReactionSerializer,
        responses={200: dict, 201: dict},
    )
    @action(detail=True, methods=["post"])
    def react(self, request: Request, **kwargs) -> Response:
        self._assert_member()
        return self._toggle_reaction(self.get_object(), request)
