"""Closes the API of a feature that has not been released yet, for every account."""

from __future__ import annotations

import re

from django.http import JsonResponse

from .services import feature_is_live

_UUID = r"[0-9a-fA-F-]{36}"
_SCOUT_TOOLS = (
    "search|compare|shortlists|saved-searches|contact-requests|reports|organisations"
    "|ratings|tests|leagues|profiles"
)

FEATURE_PATHS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^/api/v1/games(/|$)"), "games"),
    (re.compile(rf"^/api/v1/scouting/({_SCOUT_TOOLS})(/|$)"), "scouting"),
    (re.compile(rf"^/api/v1/competitions/{_UUID}/fantasy(/|$)"), "fantasy"),
]


def feature_for_path(path: str) -> str | None:
    for pattern, feature in FEATURE_PATHS:
        if pattern.match(path):
            return feature
    return None


class FeatureReleaseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        feature = feature_for_path(request.path)
        if feature and not feature_is_live(feature):
            return JsonResponse(
                {"error": "not_released", "detail": "This part of Fair Measure is not open yet."},
                status=404,
            )
        return self.get_response(request)
