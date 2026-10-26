"""The internal API the BullMQ workers call back into.

The workers own scheduling, retries and backoff; Django owns the business logic
and the database. Rather than reimplement standings maths or notification rules
in TypeScript, each worker performs an authenticated POST to one of these
endpoints. That keeps a single definition of every rule.

Access is gated by a bearer token shared out of band (`INTERNAL_API_TOKEN`), and
these routes should not be exposed beyond the private network.
"""

from __future__ import annotations

import hmac
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)
User = get_user_model()


class HasInternalToken(BasePermission):
    message = "A valid internal service token is required."

    def has_permission(self, request: Request, view) -> bool:
        expected = settings.INTERNAL_API_TOKEN
        if not expected:
            return False
        header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return hmac.compare_digest(header[len(prefix) :], expected)


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([HasInternalToken])
def authorize_rooms(request: Request) -> Response:
    """Decide which Socket.io rooms a user may subscribe to.

    The gateway holds no database connection, so it asks here before joining a
    socket to a room. Without this, anyone with a valid login could subscribe to
    a private competition's live scores by guessing its id.
    """

    from apps.competitions.models import Competition
    from apps.core.permissions import role_in
    from apps.fixtures.models import Fixture

    user = User.objects.filter(pk=request.data.get("user_id")).first()
    requested = request.data.get("rooms") or []
    if user is None or not isinstance(requested, list):
        return Response({"allowed": []})

    # Resolve every room to the competition that governs it, in two queries.
    competition_ids: set[str] = set()
    fixture_ids: set[str] = set()
    for room in requested:
        if not isinstance(room, str) or ":" not in room:
            continue
        kind, _, identifier = room.partition(":")
        if kind == "competition":
            competition_ids.add(identifier)
        elif kind == "fixture":
            fixture_ids.add(identifier)

    # Room identifiers arrive as strings, so both maps are keyed by string to
    # avoid silent misses against UUID objects.
    fixture_to_competition = {
        str(fixture_id): str(competition_id)
        for fixture_id, competition_id in Fixture.objects.filter(
            id__in=fixture_ids
        ).values_list("id", "competition_id")
    }
    competitions = {
        str(competition.id): competition
        for competition in Competition.objects.filter(
            id__in=competition_ids | set(fixture_to_competition.values())
        )
    }

    allowed = []
    for room in requested:
        if not isinstance(room, str) or ":" not in room:
            continue
        kind, _, identifier = room.partition(":")

        if kind == "user":
            if identifier == str(user.id):
                allowed.append(room)
            continue

        if kind == "games":
            from apps.games.views import visible_games

            if visible_games(user).filter(pk=identifier).exists():
                allowed.append(room)
            continue

        if kind == "competition":
            competition = competitions.get(identifier)
        elif kind == "fixture":
            competition_id = fixture_to_competition.get(identifier)
            competition = competitions.get(competition_id) if competition_id else None
        else:
            continue

        if competition is None:
            continue
        if not competition.is_private or role_in(competition, user) is not None:
            allowed.append(room)

    return Response({"allowed": allowed})


@extend_schema(exclude=True)
@api_view(["POST"])
# The service token is not a JWT; the default authenticators would reject it
# with a 401 before HasInternalToken ever runs.
@authentication_classes([])
@permission_classes([HasInternalToken])
def recompute_standings(request: Request) -> Response:
    from apps.competitions.models import Competition, Stage
    from apps.core.bus import competition_room, publish_event
    from apps.standings.services import refresh_standings

    competition = get_object_or_404(Competition, pk=request.data.get("competition_id"))

    stage = None
    if stage_id := request.data.get("stage_id"):
        stage = get_object_or_404(Stage, pk=stage_id, competition=competition)

    rows = refresh_standings(competition, stage)

    publish_event(
        "standings.updated",
        {
            "competition_id": str(competition.id),
            "stage_id": str(stage.id) if stage else None,
            "rows": [
                {
                    "position": row.position,
                    "participant_id": str(row.participant_id),
                    "played": row.played,
                    "points": str(row.points),
                    "score_difference": str(row.score_difference),
                }
                for row in rows
            ],
        },
        [competition_room(competition.id)],
        immediate=True,
    )
    return Response({"rows": len(rows)})


@extend_schema(exclude=True)
@api_view(["POST"])
# The service token is not a JWT; the default authenticators would reject it
# with a 401 before HasInternalToken ever runs.
@authentication_classes([])
@permission_classes([HasInternalToken])
def dispatch_notification(request: Request) -> Response:
    """Turn a queued notification job into in-app records and FCM pushes."""

    from apps.competitions.models import Competition
    from apps.notifications.services import notify_users
    from apps.social.models import Comment, Post

    job = request.data.get("job", "")
    data = request.data.get("data") or {}

    if job == "announcement":
        post = get_object_or_404(
            Post.objects.select_related("competition", "author"), pk=data.get("post_id")
        )
        recipients = User.objects.filter(
            memberships__competition=post.competition
        ).exclude(pk=post.author_id)
        sent = notify_users(
            recipients,
            kind="announcement",
            title=f"{post.competition.name}: announcement",
            body=post.body[:180],
            competition=post.competition,
            category="announcements",
            data={"post_id": str(post.id), "competition_id": str(post.competition_id)},
        )
        return Response({"sent": sent})

    if job == "comment-reply":
        comment = get_object_or_404(
            Comment.objects.select_related("post__competition", "author", "parent__author"),
            pk=data.get("comment_id"),
        )
        # Notify the post author, and the parent comment's author for a reply.
        recipient_ids = {comment.post.author_id}
        if comment.parent_id:
            recipient_ids.add(comment.parent.author_id)
        recipient_ids.discard(comment.author_id)

        sent = notify_users(
            User.objects.filter(pk__in=recipient_ids),
            kind="comment",
            title=f"{comment.author.get_full_name()} replied",
            body=comment.body[:180],
            competition=comment.post.competition,
            category="feed_activity",
            data={"post_id": str(comment.post_id), "comment_id": str(comment.id)},
        )
        return Response({"sent": sent})

    if job == "competition-invite":
        competition = get_object_or_404(Competition, pk=data.get("competition_id"))
        sent = notify_users(
            User.objects.filter(pk=data.get("user_id")),
            kind="invite",
            title=f"You were added to {competition.name}",
            body=f"{data.get('invited_by', 'An admin')} added you to the competition.",
            competition=competition,
            category="announcements",
            data={"competition_id": str(competition.id)},
        )
        return Response({"sent": sent})

    if job in {"fixtures-published", "fixture-reminder"}:
        competition = get_object_or_404(Competition, pk=data.get("competition_id"))
        recipients = User.objects.filter(memberships__competition=competition)
        title = (
            f"{competition.name}: fixtures published"
            if job == "fixtures-published"
            else f"{competition.name}: match starting soon"
        )
        sent = notify_users(
            recipients,
            kind=job,
            title=title,
            body=data.get("body", ""),
            competition=competition,
            category="fixture_reminders",
            data={"competition_id": str(competition.id), **data},
        )
        return Response({"sent": sent})

    logger.info("Ignoring unknown notification job '%s'", job)
    return Response({"detail": f"Unknown job '{job}'."}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(exclude=True)
@api_view(["POST"])
# The service token is not a JWT; the default authenticators would reject it
# with a 401 before HasInternalToken ever runs.
@authentication_classes([])
@permission_classes([HasInternalToken])
def index_search_document(request: Request) -> Response:
    from apps.competitions.models import Competition, Participant
    from apps.search import services as search_services
    from apps.social.models import Post

    job = request.data.get("job", "")
    data = request.data.get("data") or {}

    if job == "purge-demos":
        from apps.competitions.demo import delete_demo_if_expired, purge_expired_demos

        if data.get("competition_id"):
            deleted = delete_demo_if_expired(data["competition_id"])
            return Response({"purged": True, "deleted": deleted})
        return Response({"purged": True, "count": purge_expired_demos()})
    if job == "index-competition":
        competition = get_object_or_404(Competition, pk=data.get("competition_id"))
        search_services.index_documents(
            search_services.COMPETITIONS_INDEX,
            [search_services.competition_document(competition)],
        )
    elif job == "index-participant":
        participant = get_object_or_404(Participant, pk=data.get("participant_id"))
        search_services.index_documents(
            search_services.PARTICIPANTS_INDEX,
            [search_services.participant_document(participant)],
        )
    elif job == "index-post":
        post = get_object_or_404(Post.objects.select_related("author"), pk=data.get("post_id"))
        search_services.index_documents(
            search_services.POSTS_INDEX, [search_services.post_document(post)]
        )
    else:
        return Response(
            {"detail": f"Unknown job '{job}'."}, status=status.HTTP_400_BAD_REQUEST
        )

    return Response({"indexed": True})


@extend_schema(exclude=True)
@api_view(["POST"])
# The service token is not a JWT; the default authenticators would reject it
# with a 401 before HasInternalToken ever runs.
@authentication_classes([])
@permission_classes([HasInternalToken])
def finalize_media(request: Request) -> Response:
    """Poll a video provider for an asset whose webhook never arrived."""

    from apps.core.bus import publish_event, user_room
    from apps.media_assets.models import MediaAsset
    from apps.media_assets.video import get_video_provider

    job = request.data.get("job", "")
    data = request.data.get("data") or {}

    if job == "delete-remote-asset":
        from apps.media_assets.storage import delete_object

        if data.get("storage_key"):
            try:
                delete_object(data["storage_key"])
            except Exception as exc:
                logger.warning("Could not delete object %s: %s", data["storage_key"], exc)
        if data.get("provider_asset_id") and data.get("video_provider"):
            try:
                get_video_provider(data["video_provider"]).delete(data["provider_asset_id"])
            except Exception as exc:
                logger.warning("Could not delete remote video: %s", exc)
        return Response({"deleted": True})

    asset = get_object_or_404(MediaAsset, pk=data.get("media_asset_id"))

    if asset.kind == MediaAsset.Kind.VIDEO and asset.provider_asset_id:
        video_status = get_video_provider(asset.video_provider).get_status(
            asset.provider_asset_id
        )
        if video_status.ready:
            asset.status = MediaAsset.Status.READY
            asset.playback_id = video_status.playback_id
            asset.playback_url = video_status.playback_url
            asset.thumbnail_url = video_status.thumbnail_url
            asset.duration_seconds = video_status.duration_seconds
            asset.ready_at = timezone.now()
            asset.save()
        elif video_status.failed:
            asset.status = MediaAsset.Status.FAILED
            asset.error_message = video_status.error_message[:400]
            asset.save(update_fields=["status", "error_message"])

    publish_event(
        "media.updated",
        {"media_asset_id": str(asset.id), "status": asset.status},
        [user_room(asset.owner_id)],
        immediate=True,
    )
    return Response({"status": asset.status})


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([HasInternalToken])
def recompute_player_stats(request: Request) -> Response:
    """The stats job: rebuild cached player stats for one competition's players."""

    from apps.competitions.models import Competition
    from apps.scouting.stats import recompute_competition

    competition = get_object_or_404(Competition, pk=request.data.get("competition_id"))
    return Response({"rows": recompute_competition(competition)})


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([HasInternalToken])
def run_saved_search_alerts(request: Request) -> Response:
    """The scheduled job: tell scouts about players newly matching their saved searches."""

    from apps.scouting.discovery_views import run_saved_search_alerts as run

    return Response({"alerts": run()})
