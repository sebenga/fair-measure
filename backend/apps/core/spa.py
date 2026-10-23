"""Serve the Angular app from the same origin as the API."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpRequest, HttpResponse


_API_PREFIXES = ("/api/", "/admin/", "/internal/", "/healthz", "/static/", "/media/")


def spa_index(request: HttpRequest) -> HttpResponse:
    index = Path(settings.SPA_DIR) / "index.html"
    if not index.is_file():
        return HttpResponse("Fair Measure API is up. The web app is still building.", status=503)
    return FileResponse(index.open("rb"), content_type="text/html")


class SpaFallbackMiddleware:
    """Turn unmatched GET routes into index.html so Ionic client routes work."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if response.status_code != 404 or request.method != "GET":
            return response
        if request.path.startswith(_API_PREFIXES):
            return response
        index = Path(settings.SPA_DIR) / "index.html"
        if not index.is_file():
            return response
        return FileResponse(index.open("rb"), content_type="text/html")
