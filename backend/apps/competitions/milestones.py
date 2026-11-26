"""Named, recurring points milestones for custom (criteria) competitions.

Admins set ``settings_json.points_milestones`` to a list of
``{id, name, interval}``. Each definition fires every time an entrant's
standings total crosses another multiple of its interval (50, 100, 150…).

Legacy ``points_milestone_interval`` is migrated into a single named entry.
"""

from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from apps.standings.models import StandingRow

ZERO = Decimal("0")
NAME_MAX = 80
INTERVAL_MAX = 100_000
MILESTONES_MAX = 20


def _slug_id(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40] or "milestone"
    return f"{base}-{uuid.uuid4().hex[:8]}"


def list_milestones(competition_or_settings) -> list[dict]:
    """Return normalized milestone defs for a competition or settings dict."""
    if hasattr(competition_or_settings, "settings_json"):
        settings = competition_or_settings.settings_json or {}
    else:
        settings = competition_or_settings or {}
    return _read_milestones(settings)


def milestones_enabled(competition) -> bool:
    return bool(list_milestones(competition))


def milestone_interval(competition) -> int | None:
    """Smallest interval when milestones exist (compat helper)."""
    items = list_milestones(competition)
    if not items:
        return None
    return min(int(item["interval"]) for item in items)


def normalize_milestone_settings(settings: dict) -> None:
    """Validate/normalize ``points_milestones``; migrate legacy interval."""
    from rest_framework.exceptions import ValidationError

    raw_list = settings.get("points_milestones", None)
    legacy = settings.get("points_milestone_interval", None)

    if raw_list is None and legacy not in (None, "", False, 0, "0"):
        # Migrate old single-interval setting into a named recurring milestone.
        try:
            value = int(legacy)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"points_milestone_interval": "Milestone points must be a whole number."}
            ) from exc
        if value > 0:
            raw_list = [{"name": "Milestone", "interval": value}]
        else:
            raw_list = []

    if raw_list in (None, "", False):
        settings.pop("points_milestones", None)
        settings.pop("points_milestone_interval", None)
        return

    if not isinstance(raw_list, list):
        raise ValidationError({"points_milestones": "Milestones must be a list."})

    if len(raw_list) > MILESTONES_MAX:
        raise ValidationError(
            {"points_milestones": f"At most {MILESTONES_MAX} milestones."}
        )

    cleaned: list[dict] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_list):
        if not isinstance(item, dict):
            raise ValidationError(
                {"points_milestones": f"Milestone {index + 1} must be an object."}
            )
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValidationError(
                {"points_milestones": f"Milestone {index + 1} needs a name."}
            )
        if len(name) > NAME_MAX:
            raise ValidationError(
                {
                    "points_milestones": (
                        f"Milestone names must be {NAME_MAX} characters or fewer."
                    )
                }
            )
        try:
            interval = int(item.get("interval"))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {
                    "points_milestones": (
                        f"“{name}” needs a whole-number points interval."
                    )
                }
            ) from exc
        if interval < 1 or interval > INTERVAL_MAX:
            raise ValidationError(
                {
                    "points_milestones": (
                        f"“{name}” interval must be between 1 and {INTERVAL_MAX}."
                    )
                }
            )
        mid = str(item.get("id") or "").strip() or _slug_id(name)
        if mid in seen_ids:
            mid = _slug_id(name)
        seen_ids.add(mid)
        cleaned.append({"id": mid, "name": name, "interval": interval})

    settings.pop("points_milestone_interval", None)
    if cleaned:
        settings["points_milestones"] = cleaned
    else:
        settings.pop("points_milestones", None)


def _read_milestones(settings: dict) -> list[dict]:
    raw = settings.get("points_milestones")
    if isinstance(raw, list) and raw:
        out: list[dict] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            try:
                interval = int(item.get("interval"))
            except (TypeError, ValueError):
                continue
            if not name or interval < 1:
                continue
            mid = str(item.get("id") or "").strip() or _slug_id(name)
            out.append({"id": mid, "name": name, "interval": interval})
        return out

    # Legacy single interval → virtual named milestone (read path).
    legacy = settings.get("points_milestone_interval")
    if legacy in (None, "", False, 0, "0"):
        return []
    try:
        value = int(legacy)
    except (TypeError, ValueError):
        return []
    if value < 1:
        return []
    return [{"id": "legacy", "name": "Milestone", "interval": value}]


def standing_points(competition, participant_id) -> Decimal:
    """Current overall table points for a participant (0 if no row yet)."""
    row = (
        StandingRow.objects.filter(
            competition=competition,
            participant_id=participant_id,
            stage__isnull=True,
        )
        .only("points")
        .first()
    )
    return row.points if row is not None else ZERO


def standing_points_map(competition, participant_ids: Iterable) -> dict[str, Decimal]:
    ids = [str(pid) for pid in participant_ids]
    if not ids:
        return {}
    rows = StandingRow.objects.filter(
        competition=competition,
        participant_id__in=ids,
        stage__isnull=True,
    ).only("participant_id", "points")
    found = {str(row.participant_id): row.points for row in rows}
    return {pid: found.get(pid, ZERO) for pid in ids}


def crossed_milestone_values(before: Decimal, after: Decimal, interval: int) -> list[int]:
    """Multiples of `interval` newly reached when points move from before → after."""
    if interval <= 0 or after <= before:
        return []
    first = (int(before) // interval + 1) * interval
    last = (int(after) // interval) * interval
    if last < first:
        return []
    return list(range(first, last + 1, interval))


def milestone_payloads(
    *,
    competition,
    before: dict[str, Decimal],
    participants: dict[str, object],
) -> list[dict]:
    """Build celebration payloads for every named milestone that was crossed."""
    defs = list_milestones(competition)
    if not defs or not before:
        return []

    after = standing_points_map(competition, before.keys())
    payloads: list[dict] = []
    for participant_id, old_points in before.items():
        new_points = after.get(participant_id, ZERO)
        participant = participants.get(participant_id)
        entrant = getattr(participant, "name", None) or "Entrant"
        for definition in defs:
            interval = int(definition["interval"])
            for mark in crossed_milestone_values(old_points, new_points, interval):
                payloads.append(
                    {
                        "participant_id": str(participant_id),
                        "participant_name": entrant,
                        "milestone_id": definition["id"],
                        "milestone_name": definition["name"],
                        "milestone": mark,
                        "points": str(new_points),
                        "interval": interval,
                    }
                )
    # Stable order: by point mark, then name.
    payloads.sort(key=lambda row: (row["milestone"], row["milestone_name"]))
    return payloads


def snapshot_before(
    competition, participant_ids: Iterable[UUID | str]
) -> dict[str, Decimal]:
    """Capture standings points before an award, when milestones are enabled."""
    if not milestones_enabled(competition):
        return {}
    return standing_points_map(competition, participant_ids)
