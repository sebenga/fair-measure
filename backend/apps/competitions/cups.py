"""Named cups on a league. Only one cup runs at a time."""

from __future__ import annotations

from rest_framework import serializers

from apps.fixtures.models import Fixture

from .engine import round_winners
from .models import Competition, Stage

OPEN_STATUSES = {
    Fixture.Status.SCHEDULED,
    Fixture.Status.LIVE,
    Fixture.Status.POSTPONED,
}


def normalize_cup_entries(raw, *, strict: bool = True) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()
    if not isinstance(raw, list):
        raw = []
    for item in raw:
        name = item.get("name") if isinstance(item, dict) else item
        cup_id = item.get("id") if isinstance(item, dict) else None
        name = " ".join(str(name or "").split())
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            if strict:
                raise serializers.ValidationError(
                    {"cups": f'"{name}" is already used. Cup names must be unique.'}
                )
            continue
        seen.add(key)
        entry: dict = {"name": name[:120]}
        if cup_id:
            entry["id"] = str(cup_id)
        entries.append(entry)
    return entries


def normalize_cup_names(raw, *, strict: bool = True) -> list[str]:
    return [entry["name"] for entry in normalize_cup_entries(raw, strict=strict)]


def cup_names_for(competition: Competition) -> list[str]:
    settings = getattr(competition, "settings_json", None) or {}
    names = normalize_cup_names(settings.get("cups"), strict=False)
    if names:
        return names
    existing = list(
        competition.stages.filter(kind=Stage.Kind.KNOCKOUT).order_by("display_order").values_list("name", flat=True)
    )
    return existing or ["Cup"]


def persist_cup_names(competition: Competition, names: list[str] | None = None) -> list[str]:
    resolved = names if names is not None else cup_names_for(competition)
    if not resolved:
        resolved = ["Cup"]
    settings = dict(competition.settings_json or {})
    settings["cups"] = resolved
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])
    return resolved


def sync_named_cups(competition: Competition, entries: list[dict] | None = None) -> list[Stage]:
    """Create, rename, or drop unused knockout stages so they match the cup list."""

    resolved = entries if entries is not None else [{"name": name} for name in cup_names_for(competition)]
    if not resolved:
        resolved = [{"name": "Cup"}]
    persist_cup_names(competition, [entry["name"] for entry in resolved])
    existing = list(competition.stages.filter(kind=Stage.Kind.KNOCKOUT).order_by("display_order", "created_at"))
    by_id = {str(stage.id): stage for stage in existing}
    by_key = {stage.name.casefold(): stage for stage in existing}
    used: set = set()
    cups: list[Stage] = []
    for index, entry in enumerate(resolved):
        stage = None
        cup_id = entry.get("id")
        if cup_id and cup_id in by_id:
            stage = by_id[cup_id]
        elif entry["name"].casefold() in by_key:
            stage = by_key[entry["name"].casefold()]
        order = index + 1
        if stage is None:
            stage = Stage.objects.create(
                competition=competition,
                name=entry["name"],
                kind=Stage.Kind.KNOCKOUT,
                display_order=order,
            )
        else:
            updates = []
            if stage.name != entry["name"]:
                stage.name = entry["name"]
                updates.append("name")
            if stage.display_order != order:
                stage.display_order = order
                updates.append("display_order")
            if updates:
                updates.append("updated_at")
                stage.save(update_fields=updates)
        used.add(stage.id)
        cups.append(stage)
    leftovers = [stage for stage in existing if stage.id not in used]
    for stage in leftovers:
        if stage.fixtures.exists():
            raise serializers.ValidationError(
                {"cups": f'"{stage.name}" already has fixtures. Keep that cup or finish it first.'}
            )
        stage.delete()
    return cups


def ensure_league_and_cup_stages(competition: Competition) -> tuple[Stage, list[Stage]]:
    league = competition.stages.filter(kind=Stage.Kind.LEAGUE).order_by("display_order").first()
    if league is None:
        league = Stage.objects.create(
            competition=competition, name="League", kind=Stage.Kind.LEAGUE, display_order=0
        )
    names = persist_cup_names(competition)
    existing = list(competition.stages.filter(kind=Stage.Kind.KNOCKOUT).order_by("display_order", "created_at"))
    by_key = {stage.name.casefold(): stage for stage in existing}
    cups: list[Stage] = []
    for index, name in enumerate(names):
        stage = by_key.pop(name.casefold(), None)
        order = index + 1
        if stage is None:
            stage = Stage.objects.create(
                competition=competition,
                name=name,
                kind=Stage.Kind.KNOCKOUT,
                display_order=order,
            )
        else:
            updates = []
            if stage.name != name:
                stage.name = name
                updates.append("name")
            if stage.display_order != order:
                stage.display_order = order
                updates.append("display_order")
            if updates:
                updates.append("updated_at")
                stage.save(update_fields=updates)
        cups.append(stage)
    return league, cups


def cup_is_complete(stage: Stage) -> bool:
    fixtures = list(stage.fixtures.all())
    if not fixtures:
        return False
    latest = max(fixture.round_number or 1 for fixture in fixtures)
    current = [fixture for fixture in fixtures if (fixture.round_number or 1) == latest]
    if any(fixture.status not in {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT} for fixture in current):
        return False
    winners = round_winners(current)
    return winners is not None and len(winners) < 2


def cup_is_running(stage: Stage) -> bool:
    if stage.fixtures.filter(status__in=OPEN_STATUSES).exists():
        return True
    if stage.fixtures.exists() and not cup_is_complete(stage):
        return True
    return False


def running_cup_stage(competition: Competition) -> Stage | None:
    for stage in competition.stages.filter(kind=Stage.Kind.KNOCKOUT).order_by("display_order", "created_at"):
        if cup_is_running(stage):
            return stage
    return None


def active_cup_stage(competition: Competition) -> Stage | None:
    running = running_cup_stage(competition)
    if running is not None:
        return running
    _, cups = ensure_league_and_cup_stages(competition)
    for stage in cups:
        if not stage.fixtures.exists():
            return stage
    return cups[-1] if cups else None


def assert_cups_are_sequential(competition: Competition, starting: Stage | None = None) -> None:
    running = [
        stage
        for stage in competition.stages.filter(kind=Stage.Kind.KNOCKOUT).order_by("display_order")
        if cup_is_running(stage) and (starting is None or stage.id != starting.id)
    ]
    if running:
        names = ", ".join(stage.name for stage in running)
        raise serializers.ValidationError(
            f"{names} is still running. Only one cup can run at a time."
        )
