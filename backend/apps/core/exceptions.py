"""A single, predictable error envelope for every API failure."""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, DjangoValidationError):
        return Response(
            {
                "error": {
                    "code": "validation_error",
                    "message": "The request could not be validated.",
                    "detail": getattr(exc, "message_dict", None) or list(exc.messages),
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, IntegrityError):
        logger.warning("Integrity error on %s: %s", context.get("request"), exc)
        return Response(
            {
                "error": {
                    "code": "conflict",
                    "message": "That change conflicts with existing data.",
                }
            },
            status=status.HTTP_409_CONFLICT,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled API error on %s", context.get("request"))
        return Response(
            {
                "error": {
                    "code": "server_error",
                    "message": "Something went wrong.",
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code = getattr(exc, "default_code", "error")
    detail = response.data
    message = "Request failed."
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
        detail = None
    elif isinstance(detail, list) and detail:
        message = str(detail[0])

    response.data = {"error": {"code": code, "message": message, "detail": detail}}
    return response
