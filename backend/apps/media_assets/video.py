"""Video providers behind one interface: Cloudflare Stream or Mux.

Both work the same way from our side. We ask for a one-time direct-upload URL,
hand it to the client, and the provider tells us over a webhook when the asset
has finished encoding. `get_video_provider()` picks the implementation from
settings so callers never name a vendor.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests
from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError

REQUEST_TIMEOUT = 15


@dataclass(slots=True)
class DirectUpload:
    upload_url: str
    provider_asset_id: str
    provider: str


@dataclass(slots=True)
class VideoStatus:
    ready: bool
    failed: bool
    playback_id: str = ""
    playback_url: str = ""
    thumbnail_url: str = ""
    duration_seconds: float | None = None
    error_message: str = ""


class VideoProvider(ABC):
    name: str

    @abstractmethod
    def create_direct_upload(self, *, max_duration_seconds: int, metadata: dict) -> DirectUpload:
        ...

    @abstractmethod
    def get_status(self, provider_asset_id: str) -> VideoStatus:
        ...

    @abstractmethod
    def delete(self, provider_asset_id: str) -> None:
        ...

    @abstractmethod
    def verify_webhook(self, body: bytes, headers: dict) -> bool:
        ...

    @abstractmethod
    def parse_webhook(self, payload: dict) -> tuple[str, VideoStatus] | None:
        """Return (provider_asset_id, status) for events we care about."""


class CloudflareStreamProvider(VideoProvider):
    name = "cloudflare_stream"

    @property
    def _base_url(self) -> str:
        return (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{settings.CLOUDFLARE_ACCOUNT_ID}/stream"
        )

    @property
    def _headers(self) -> dict[str, str]:
        if not settings.CLOUDFLARE_ACCOUNT_ID or not settings.CLOUDFLARE_STREAM_API_TOKEN:
            raise ValidationError(
                "Cloudflare Stream is not configured. Set CLOUDFLARE_ACCOUNT_ID and "
                "CLOUDFLARE_STREAM_API_TOKEN."
            )
        return {"Authorization": f"Bearer {settings.CLOUDFLARE_STREAM_API_TOKEN}"}

    def create_direct_upload(self, *, max_duration_seconds: int, metadata: dict) -> DirectUpload:
        response = requests.post(
            f"{self._base_url}/direct_upload",
            headers=self._headers,
            json={
                "maxDurationSeconds": max_duration_seconds,
                "requireSignedURLs": False,
                "meta": {key: str(value) for key, value in metadata.items()},
            },
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            raise APIException(f"Cloudflare Stream rejected the upload request: {response.text}")

        result = response.json()["result"]
        return DirectUpload(
            upload_url=result["uploadURL"],
            provider_asset_id=result["uid"],
            provider=self.name,
        )

    def get_status(self, provider_asset_id: str) -> VideoStatus:
        response = requests.get(
            f"{self._base_url}/{provider_asset_id}",
            headers=self._headers,
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            return VideoStatus(ready=False, failed=True, error_message=response.text[:400])
        return self._to_status(response.json()["result"])

    def _to_status(self, result: dict) -> VideoStatus:
        state = (result.get("status") or {}).get("state", "")
        uid = result.get("uid", "")
        return VideoStatus(
            ready=state == "ready",
            failed=state == "error",
            playback_id=uid,
            playback_url=(result.get("playback") or {}).get("hls", ""),
            thumbnail_url=result.get("thumbnail", ""),
            duration_seconds=result.get("duration"),
            error_message=(result.get("status") or {}).get("errorReasonText", ""),
        )

    def delete(self, provider_asset_id: str) -> None:
        requests.delete(
            f"{self._base_url}/{provider_asset_id}",
            headers=self._headers,
            timeout=REQUEST_TIMEOUT,
        )

    def verify_webhook(self, body: bytes, headers: dict) -> bool:
        secret = settings.CLOUDFLARE_STREAM_WEBHOOK_SECRET
        if not secret:
            return False

        # Header format: "time=1234567890,sig1=<hex hmac of 'time.body'>"
        signature_header = headers.get("Webhook-Signature", "")
        parts = dict(
            piece.split("=", 1) for piece in signature_header.split(",") if "=" in piece
        )
        timestamp, signature = parts.get("time"), parts.get("sig1")
        if not timestamp or not signature:
            return False

        # Reject replays of an old, validly signed request.
        if abs(time.time() - int(timestamp)) > 300:
            return False

        expected = hmac.new(
            secret.encode(),
            f"{timestamp}.{body.decode()}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, payload: dict) -> tuple[str, VideoStatus] | None:
        uid = payload.get("uid")
        if not uid:
            return None
        return uid, self._to_status(payload)


class MuxProvider(VideoProvider):
    name = "mux"
    _base_url = "https://api.mux.com"

    @property
    def _auth(self) -> tuple[str, str]:
        if not settings.MUX_TOKEN_ID or not settings.MUX_TOKEN_SECRET:
            raise ValidationError(
                "Mux is not configured. Set MUX_TOKEN_ID and MUX_TOKEN_SECRET."
            )
        return settings.MUX_TOKEN_ID, settings.MUX_TOKEN_SECRET

    def create_direct_upload(self, *, max_duration_seconds: int, metadata: dict) -> DirectUpload:
        response = requests.post(
            f"{self._base_url}/video/v1/uploads",
            auth=self._auth,
            json={
                "cors_origin": "*",
                "new_asset_settings": {
                    "playback_policy": ["public"],
                    "passthrough": metadata.get("media_asset_id", ""),
                },
            },
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            raise APIException(f"Mux rejected the upload request: {response.text}")

        data = response.json()["data"]
        # Mux returns an upload id now and an asset id later, over the webhook.
        return DirectUpload(
            upload_url=data["url"], provider_asset_id=data["id"], provider=self.name
        )

    def get_status(self, provider_asset_id: str) -> VideoStatus:
        response = requests.get(
            f"{self._base_url}/video/v1/assets/{provider_asset_id}",
            auth=self._auth,
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            return VideoStatus(ready=False, failed=True, error_message=response.text[:400])
        return self._to_status(response.json()["data"])

    def _to_status(self, data: dict) -> VideoStatus:
        status = data.get("status", "")
        playback_ids = data.get("playback_ids") or []
        playback_id = playback_ids[0]["id"] if playback_ids else ""
        return VideoStatus(
            ready=status == "ready",
            failed=status == "errored",
            playback_id=playback_id,
            playback_url=(
                f"https://stream.mux.com/{playback_id}.m3u8" if playback_id else ""
            ),
            thumbnail_url=(
                f"https://image.mux.com/{playback_id}/thumbnail.jpg" if playback_id else ""
            ),
            duration_seconds=data.get("duration"),
            error_message=str((data.get("errors") or {}).get("messages", ""))[:400],
        )

    def delete(self, provider_asset_id: str) -> None:
        requests.delete(
            f"{self._base_url}/video/v1/assets/{provider_asset_id}",
            auth=self._auth,
            timeout=REQUEST_TIMEOUT,
        )

    def verify_webhook(self, body: bytes, headers: dict) -> bool:
        secret = settings.MUX_WEBHOOK_SECRET
        if not secret:
            return False

        # Header format: "t=<timestamp>,v1=<hex hmac of 't.body'>"
        parts = dict(
            piece.split("=", 1)
            for piece in headers.get("Mux-Signature", "").split(",")
            if "=" in piece
        )
        timestamp, signature = parts.get("t"), parts.get("v1")
        if not timestamp or not signature:
            return False
        if abs(time.time() - int(timestamp)) > 300:
            return False

        expected = hmac.new(
            secret.encode(), f"{timestamp}.{body.decode()}".encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, payload: dict) -> tuple[str, VideoStatus] | None:
        event_type = payload.get("type", "")
        data = payload.get("data") or {}

        if event_type == "video.upload.asset_created":
            # Bridges the upload id we stored to the asset id we will poll.
            return data.get("id", ""), VideoStatus(
                ready=False, failed=False, playback_id=data.get("asset_id", "")
            )
        if event_type.startswith("video.asset."):
            return data.get("id", ""), self._to_status(data)
        return None


_PROVIDERS: dict[str, type[VideoProvider]] = {
    CloudflareStreamProvider.name: CloudflareStreamProvider,
    MuxProvider.name: MuxProvider,
}


def get_video_provider(name: str | None = None) -> VideoProvider:
    key = name or settings.VIDEO_PROVIDER
    provider_class = _PROVIDERS.get(key)
    if provider_class is None:
        raise ValidationError(
            f"Unknown video provider '{key}'. Choose one of: {', '.join(_PROVIDERS)}."
        )
    return provider_class()
