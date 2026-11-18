"""Swappable vision backends. Render has no GPUs — inference is external."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass
class SuggestedEvent:
    event_type: str
    timestamp_seconds: Decimal
    confidence: Decimal
    team_side_id: str | None = None
    player_guess_id: str | None = None
    clip_url: str = ""
    is_disciplinary: bool = False
    raw: dict | None = None


class VisionProvider(Protocol):
    """Detect players/ball, assign kits, OCR shirt numbers, propose events."""

    name: str

    def process_clip(self, *, storage_key: str, fixture_id: str, kit_colours: dict) -> list[SuggestedEvent]:
        ...


class StubVisionProvider:
    """Deterministic sample suggestions for tests and free-tier dry runs."""

    name = "stub"

    def process_clip(self, *, storage_key: str, fixture_id: str, kit_colours: dict) -> list[SuggestedEvent]:
        # Always emit a non-disciplinary tackle plus a yellow flagged for human review.
        return [
            SuggestedEvent(
                event_type="tackle",
                timestamp_seconds=Decimal("612.0"),
                confidence=Decimal("0.910"),
                clip_url="",
                is_disciplinary=False,
                raw={"storage_key": storage_key, "fixture_id": fixture_id, "kit_colours": kit_colours},
            ),
            SuggestedEvent(
                event_type="yellow",
                timestamp_seconds=Decimal("740.5"),
                confidence=Decimal("0.620"),
                clip_url="",
                is_disciplinary=True,
                raw={"note": "card suggestions never auto-apply"},
            ),
        ]


class HttpVisionProvider:
    """Calls an external GPU host (Modal / Replicate / RunPod / AWS) via env config."""

    name = "http"

    def __init__(self, endpoint: str, api_key: str = "") -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key

    def process_clip(self, *, storage_key: str, fixture_id: str, kit_colours: dict) -> list[SuggestedEvent]:
        import json
        import urllib.request

        payload = json.dumps(
            {"storage_key": storage_key, "fixture_id": fixture_id, "kit_colours": kit_colours}
        ).encode()
        request = urllib.request.Request(
            f"{self.endpoint}/v1/process",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 — operator-configured URL
            data = json.loads(response.read().decode())
        out: list[SuggestedEvent] = []
        for row in data.get("events") or []:
            out.append(
                SuggestedEvent(
                    event_type=str(row.get("event_type") or row.get("type") or "unknown"),
                    timestamp_seconds=Decimal(str(row.get("timestamp_seconds") or 0)),
                    confidence=Decimal(str(row.get("confidence") or 0)),
                    team_side_id=row.get("team_side_id"),
                    player_guess_id=row.get("player_guess_id"),
                    clip_url=str(row.get("clip_url") or ""),
                    is_disciplinary=bool(row.get("is_disciplinary")),
                    raw=row,
                )
            )
        return out


def get_vision_provider() -> VisionProvider:
    from django.conf import settings

    kind = (getattr(settings, "AI_VISION_PROVIDER", None) or "stub").strip().lower()
    if kind in {"", "stub", "none", "off"}:
        return StubVisionProvider()
    endpoint = getattr(settings, "AI_VISION_ENDPOINT", "") or ""
    key = getattr(settings, "AI_API_KEY", "") or ""
    if not endpoint:
        return StubVisionProvider()
    return HttpVisionProvider(endpoint, key)
