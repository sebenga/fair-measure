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
import threading
import time
import uuid
from collections import deque
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
        if settings.REALTIME_POLLING:
            _remember_event(message)
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
        if settings.JOBS_INLINE:
            # Delayed jobs (demo expiry) are picked up by run_periodic instead.
            if not delay_ms:
                _run_inline(queue, name, data)
            return
        try:
            get_redis().lpush(settings.JOB_INBOX_KEY, message)
        except redis.RedisError:
            reset_redis()
            logger.warning("Job %s/%s dropped: Redis unavailable", queue, name)

    if immediate:
        _send()
    else:
        transaction.on_commit(_send)


# --- In-process fallback ------------------------------------------------------
# A deployment without the Node service (one Render web service) has nobody to
# run queued jobs or relay events. JOBS_INLINE runs jobs on a small thread pool
# here; REALTIME_POLLING keeps recent events so the app can poll for them.

_executor = None
_executor_lock = threading.Lock()
_recent_events: deque[str] = deque(maxlen=500)
_last_periodic = 0.0
PERIODIC_EVERY_SECONDS = 10 * 60


def _job_pool():
    global _executor
    with _executor_lock:
        if _executor is None:
            from concurrent.futures import ThreadPoolExecutor

            _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fm-job")
        return _executor


def _guarded(label: str, task, *args) -> None:
    # A savepoint, so a failed job cannot leave a Postgres transaction aborted.
    try:
        with transaction.atomic():
            task(*args)
    except Exception:
        logger.exception("Inline job %s failed", label)


def _in_pool(label: str, task, *args) -> None:
    from django.db import connections

    try:
        _guarded(label, task, *args)
    finally:
        # Pool threads outlive requests, so nothing else closes their connections.
        connections.close_all()


def _run_inline(queue: str, name: str, data: dict[str, Any]) -> None:
    from .jobs import run_job

    label = f"{queue}/{name}"
    if settings.JOBS_INLINE_SYNC:
        _guarded(label, run_job, queue, name, data)
    else:
        _job_pool().submit(_in_pool, label, run_job, queue, name, data)


def maybe_run_periodic() -> None:
    """Called after requests; runs the worker's repeating jobs at most every ten minutes."""

    global _last_periodic
    if not settings.JOBS_INLINE:
        return
    now = time.monotonic()
    with _executor_lock:
        if _last_periodic and now - _last_periodic < PERIODIC_EVERY_SECONDS:
            return
        _last_periodic = now
    from .jobs import run_periodic

    if settings.JOBS_INLINE_SYNC:
        _guarded("periodic", run_periodic)
    else:
        _job_pool().submit(_in_pool, "periodic", run_periodic)


def _remember_event(message: str) -> None:
    if redis_configured():
        try:
            client = get_redis()
            client.lpush(settings.REALTIME_RECENT_KEY, message)
            client.ltrim(settings.REALTIME_RECENT_KEY, 0, _recent_events.maxlen - 1)
            return
        except redis.RedisError:
            reset_redis()
    _recent_events.appendleft(message)


def recent_events(rooms: set[str], since_ms: int) -> list[dict[str, Any]]:
    """Events newer than `since_ms` for any of `rooms`, oldest first."""

    raw: list[str] = []
    if redis_configured():
        try:
            raw = list(get_redis().lrange(settings.REALTIME_RECENT_KEY, 0, -1))
        except redis.RedisError:
            reset_redis()
            raw = list(_recent_events)
    else:
        raw = list(_recent_events)
    found = []
    for item in raw:
        try:
            envelope = json.loads(item)
        except (TypeError, ValueError):
            continue
        if int(envelope.get("ts") or 0) <= since_ms:
            continue
        if not rooms.intersection(envelope.get("rooms") or []):
            continue
        found.append(
            {
                "id": envelope.get("id"),
                "event": envelope.get("event"),
                "payload": envelope.get("payload") or {},
                "ts": envelope.get("ts"),
            }
        )
    found.sort(key=lambda row: row["ts"])
    return found


class Queues:
    """Queue names, mirrored in realtime/src/queues.ts."""

    MEDIA = "media"
    NOTIFICATIONS = "notifications"
    STANDINGS = "standings"
    SEARCH = "search"
    STATS = "stats"
    SCOUTING = "scouting"
