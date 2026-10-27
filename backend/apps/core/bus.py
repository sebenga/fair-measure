"""The bridge between Django and the Node realtime/worker service.

Django never imports Socket.io or BullMQ. Instead it uses Redis in two ways:

* **Realtime events** are PUBLISHed to a pub/sub channel. The Socket.io gateway
  subscribes and fans each message out to the rooms named in the payload.
* **Background jobs** are LPUSHed onto a durable list. A small bridge in the Node
  service BRPOPs from that list and hands the job to the right BullMQ queue.

A list is used for jobs rather than pub/sub so that nothing is lost when the
worker is restarting. Both helpers are fire-and-forget: a Redis outage degrades
realtime and background processing but must never fail the user's API request.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

import redis
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def redis_configured() -> bool:
    """False when REDIS_URL is missing or still the local default on Render."""

    url = (settings.REDIS_URL or "").strip()
    if not url:
        return False
    if "localhost" in url or "127.0.0.1" in url:
        return not bool(os.environ.get("RENDER"))
    return True


def reset_redis() -> None:
    global _client
    if _client is None:
        return
    try:
        _client.close()
    except Exception:
        pass
    _client = None


def _from_url() -> redis.Redis:
    import ssl

    kwargs: dict = {
        "decode_responses": True,
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "retry_on_timeout": True,
        "health_check_interval": 30,
    }
    url = settings.REDIS_URL
    # Render Key Value is TLS (rediss://). Their cert chain is not always in
    # the slim image, so we verify the host but not a custom CA.
    if url.startswith("rediss://"):
        kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
    return redis.Redis.from_url(url, **kwargs)


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = _from_url()
    return _client


# --- Rooms ------------------------------------------------------------------
# Room names are the contract with the Socket.io gateway; both sides build them
# through these helpers so the strings can never drift apart.


def competition_room(competition_id: Any) -> str:
    return f"competition:{competition_id}"


def fixture_room(fixture_id: Any) -> str:
    return f"fixture:{fixture_id}"


def games_room(games_id: Any) -> str:
    return f"games:{games_id}"


def user_room(user_id: Any) -> str:
    return f"user:{user_id}"


# --- Realtime events --------------------------------------------------------


def publish_event(
    event: str,
    payload: dict[str, Any],
    rooms: list[str],
    *,
    immediate: bool = False,
) -> None:
    """Broadcast `event` to every socket in `rooms`.

    Deferred to transaction commit by default so subscribers never receive an
    event describing a row that was subsequently rolled back.
    """

    message = json.dumps(
        {
            "id": str(uuid.uuid4()),
            "event": event,
            "rooms": rooms,
            "payload": payload,
            "ts": int(time.time() * 1000),
        },
        default=str,
    )

    def _send() -> None:
        try:
            get_redis().publish(settings.REALTIME_EVENT_CHANNEL, message)
        except redis.RedisError:
            reset_redis()
            logger.warning("Realtime event %s dropped: Redis unavailable", event)

    if immediate:
        _send()
    else:
        transaction.on_commit(_send)


# --- Background jobs --------------------------------------------------------


def enqueue_job(
    queue: str,
    name: str,
    data: dict[str, Any],
    *,
    delay_ms: int | None = None,
    attempts: int = 3,
    immediate: bool = False,
) -> None:
    """Hand a job to a BullMQ queue via the Node-side bridge."""

    message = json.dumps(
        {
            "id": str(uuid.uuid4()),
            "queue": queue,
            "name": name,
            "data": data,
            "opts": {
                "attempts": attempts,
                **({"delay": delay_ms} if delay_ms else {}),
            },
        },
        default=str,
    )

    def _send() -> None:
        try:
            get_redis().lpush(settings.JOB_INBOX_KEY, message)
        except redis.RedisError:
            reset_redis()
            logger.warning("Job %s/%s dropped: Redis unavailable", queue, name)

    if immediate:
        _send()
    else:
        transaction.on_commit(_send)


class Queues:
    """Queue names, mirrored in realtime/src/queues.ts."""

    MEDIA = "media"
    NOTIFICATIONS = "notifications"
    STANDINGS = "standings"
    SEARCH = "search"
    STATS = "stats"
    SCOUTING = "scouting"
