"""The internal API the BullMQ workers call back into.

The workers own scheduling, retries and backoff; Django owns the business logic
and the database. Rather than reimplement standings maths or notification rules
in TypeScript, each worker performs an authenticated POST to one of these
endpoints. The logic itself lives in `apps.core.jobs` so a deployment without
the worker can run the same rules in-process.

Access is gated by a bearer token shared out of band (`INTERNAL_API_TOKEN`), and
these routes should not be exposed beyond the private network.
"""

from __future__ import annotations

import hmac
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response

from . import jobs

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


def _unknown(job: str) -> Response:
    logger.info("Ignoring unknown job '%s'", job)
    return Response({"detail": f"Unknown job '{job}'."}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(exclude=True)
@api_view(["POST"])
# The service token is not a JWT; the default authenticators would reject it
# with a 401 before HasInternalToken ever runs.
@authentication_classes([])
@permission_classes([HasInternalToken])
def authorize_rooms(request: Request) -> Response:
    """Decide which Socket.io rooms a user may subscribe to.

    The gateway holds no database connection, so it asks here before joining a
    socket to a room. Without this, anyone with a valid login could subscribe to
    a private competition's live scores by guessing its id.
    """

    user_id = request.data.get("user_id")
    user = User.objects.filter(pk=user_id).first() if jobs.valid_uuids({str(user_id)}) else None
    if user is None:
        return Response({"allowed": []})
    return Response({"allowed": jobs.allowed_rooms(user, request.data.get("rooms") or [])})


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([HasInternalToken])
def recompute_standings(request: Request) -> Response:
    return Response(jobs.recompute_standings(request.data))


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([HasInternalToken])
def dispatch_notification(request: Request) -> Response:
    """Turn a queued notification job into in-app records and FCM pushes."""

    job = request.data.get("job", "")
    try:
        return Response(jobs.dispatch_notification(job, request.data.get("data") or {}))
    except jobs.UnknownJob:
        return _unknown(job)


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([HasInternalToken])
def index_search_document(request: Request) -> Response:
    job = request.data.get("job", "")
    try:
        return Response(jobs.index_search_document(job, request.data.get("data") or {}))
    except jobs.UnknownJob:
        return _unknown(job)


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([HasInternalToken])
def finalize_media(request: Request) -> Response:
    """Poll a video provider for an asset whose webhook never arrived."""

    job = request.data.get("job", "")
    return Response(jobs.finalize_media(job, request.data.get("data") or {}))


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([HasInternalToken])
def recompute_player_stats(request: Request) -> Response:
    """The stats job: rebuild cached player stats for one competition's players."""

    return Response(jobs.recompute_player_stats(request.data))


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([HasInternalToken])
def run_saved_search_alerts(request: Request) -> Response:
    """The scheduled job: tell scouts about players newly matching their saved searches."""

    return Response(jobs.run_saved_search_alerts())
