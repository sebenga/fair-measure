from __future__ import annotations

import os
from pathlib import Path

import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from .bus import get_redis, redis_configured, reset_redis


def _authorized_health(request: Request) -> bool:
    expected = getattr(settings, "HEALTH_KEY", "") or ""
    if not expected:
        return False
    return request.headers.get("X-Health-Key") == expected


def _ping_redis() -> str:
    if not redis_configured():
        return "skipped"
    try:
        get_redis().ping()
        return "ok"
    except redis.RedisError:
        reset_redis()
        try:
            get_redis().ping()
            return "ok"
        except redis.RedisError:
            return "error"


@extend_schema(
    summary="Liveness and dependency check",
    description="Reports whether Postgres and Redis are reachable.",
    responses={200: dict, 503: dict},
    auth=[],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request: Request) -> Response:
    checks = {"database": "unknown", "redis": "unknown"}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    checks["redis"] = _ping_redis()

    database_ok = checks["database"] == "ok"
    redis_ok = checks["redis"] in {"ok", "skipped"}
    healthy = database_ok and checks["redis"] == "ok"
    body: dict = {
        "status": "ok" if healthy else ("degraded" if database_ok else "error"),
    }
    if _authorized_health(request):
        body["checks"] = checks
        body["debug"] = settings.DEBUG
    elif not redis_ok and database_ok:
        body["status"] = "degraded"

    return Response(
        body,
        status=status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@extend_schema(
    summary="Build identity",
    responses={200: dict},
    auth=[],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def version(request: Request) -> Response:
    built_at = os.environ.get("BUILD_TIME") or ""
    stamp = Path("/app/.build-time")
    if not built_at and stamp.is_file():
        built_at = stamp.read_text(encoding="utf-8").strip()
    return Response(
        {
            "commit": os.environ.get("RENDER_GIT_COMMIT")
            or os.environ.get("GIT_COMMIT")
            or "",
            "built_at": built_at,
        }
    )
