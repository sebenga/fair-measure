"""Serve the Angular app from the same origin as the API."""

from __future__ import annotations

import mimetypes
import secrets
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse

_MACHINE_PREFIXES = (
    "/api/",
    "/admin/",
    "/internal/",
    "/socket.io",
    "/static/",
    "/media/",
)
_MACHINE_EXACT = {"/api", "/healthz", "/ngsw.json"}
_ASSET_SUFFIXES = (
    ".js",
    ".css",
    ".map",
    ".json",
    ".webmanifest",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".txt",
)


def is_machine_path(path: str) -> bool:
    if path in _MACHINE_EXACT:
        return True
    return path.startswith(_MACHINE_PREFIXES)


def is_asset_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith(_ASSET_SUFFIXES) or lowered.startswith("/assets/") or lowered.startswith("/svg/")


def json_not_found() -> JsonResponse:
    return JsonResponse({"error": "not_found"}, status=404)


def serve_spa_asset(path: str) -> FileResponse | None:
    """Serve a built file from SPA_DIR (manifest, JS, CSS) without falling back to index.html."""

    relative = path.lstrip("/")
    if not relative or relative == "index.html" or ".." in relative:
        return None
    root = Path(settings.SPA_DIR).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    content_type, _ = mimetypes.guess_type(str(candidate))
    if candidate.suffix == ".webmanifest":
        content_type = "application/manifest+json"
    return FileResponse(candidate.open("rb"), content_type=content_type or "application/octet-stream")


def not_found(request: HttpRequest, exception=None) -> HttpResponse:
    """URL-resolver 404s: JSON for APIs, a plain 404 for pages (SPA middleware may replace it)."""

    if is_machine_path(request.path) or is_asset_path(request.path):
        return json_not_found()
    return HttpResponse("Not found", status=404, content_type="text/plain")


def _index_path() -> Path:
    return Path(settings.SPA_DIR) / "index.html"


def spa_index(request: HttpRequest) -> HttpResponse:
    index = _index_path()
    if not index.is_file():
        return HttpResponse("Fair Measure API is up. The web app is still building.", status=503)
    html = index.read_text(encoding="utf-8")
    nonce = secrets.token_urlsafe(16)
    html = html.replace("{{CSP_NONCE}}", nonce)
    response = HttpResponse(html, content_type="text/html")
    response["Content-Security-Policy"] = getattr(
        settings, "CONTENT_SECURITY_POLICY", "default-src 'self'"
    ).format(nonce=nonce)
    return response


class SpaFallbackMiddleware:
    """Client routes get index.html. APIs, sockets and missing assets stay 404."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if response.status_code != 404:
            return response
        if is_machine_path(request.path) or is_asset_path(request.path):
            if request.method == "GET":
                served = serve_spa_asset(request.path)
                if served is not None:
                    return served
            if response.get("Content-Type", "").startswith("text/html"):
                return json_not_found()
            return response
        if request.method != "GET":
            return response
        index = _index_path()
        if not index.is_file():
            return response
        html = index.read_text(encoding="utf-8")
        nonce = secrets.token_urlsafe(16)
        html = html.replace("{{CSP_NONCE}}", nonce)
        fallback = HttpResponse(html, content_type="text/html")
        fallback["Content-Security-Policy"] = getattr(
            settings, "CONTENT_SECURITY_POLICY", "default-src 'self'"
        ).format(nonce=nonce)
        return fallback
