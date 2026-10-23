from __future__ import annotations

import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from .bus import get_redis


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
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"

    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except redis.RedisError as exc:
        checks["redis"] = f"error: {exc.__class__.__name__}"

    # Redis is best-effort (live scores, jobs). A miss must not take the
    # web process out of Render's load balancer.
    database_ok = checks["database"] == "ok"
    healthy = database_ok and checks["redis"] == "ok"
    return Response(
        {
            "status": "ok" if healthy else ("degraded" if database_ok else "error"),
            "checks": checks,
            "debug": settings.DEBUG,
        },
        status=status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
