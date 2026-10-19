"""Saving, finalising and amending performance results, with the audit trail."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.permissions import Role, has_at_least

from .calculators import ResultDataError, _serial, evaluate, statuses_for
from .models import CompetitionOfficial, EntryResult, ResultAmendment, ResultSheet

MERGED_KEYS = {"time_allowed", "time_limit"}


def result_type_of(competition) -> str | None:
    return (competition.settings_json or {}).get("result_type") or None


def officials_required(competition) -> bool:
    return bool((competition.settings_json or {}).get("official_results"))


def is_official(competition, user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return CompetitionOfficial.objects.filter(competition=competition, user=user).exists()


def can_record(fixture, user) -> bool:
    """Who may enter provisional results: officials, admins, the event's referee, scorers."""

    from apps.fixtures.views import user_can_score_fixture

    return is_official(fixture.competition, user) or user_can_score_fixture(fixture, user)


def can_decide(competition, user) -> bool:
    """Who may finalise, amend, disqualify or eliminate."""

    if is_official(competition, user):
        return True
    if officials_required(competition):
        return False
    return has_at_least(competition, user, Role.ADMIN)


def assert_can_decide(competition, user) -> None:
    if not can_decide(competition, user):
        if officials_required(competition):
            raise PermissionDenied(
                "Only this competition's stewards, judges or ground jury can do that."
            )
        raise PermissionDenied("Only officials or admins can do that.")


def sheet_config(fixture) -> dict:
    """The preset's result config with this event's own settings on top."""

    settings = fixture.competition.settings_json or {}
    config = dict(settings.get("result_config") or {})
    config.setdefault("statuses", settings.get("statuses") or statuses_for(config))
    sheet = getattr(fixture, "result_sheet", None)
    for key, value in ((sheet.config if sheet else {}) or {}).items():
        if key in MERGED_KEYS and isinstance(value, dict):
            config[key] = {**(config.get(key) or {}), **value}
        else:
            config[key] = value
    if config.get("table") and not config.get("events"):
        from .tables import COMBINED_EVENT_TABLES

        config["events"] = COMBINED_EVENT_TABLES.get(config["table"], [])
    return config


def ensure_sheet(fixture) -> ResultSheet:
    sheet, _ = ResultSheet.objects.get_or_create(fixture=fixture)
    for side in fixture.sides.all():
        EntryResult.objects.get_or_create(side=side)
    fixture.result_sheet = sheet
    return sheet


def _snapshot(entry: EntryResult) -> dict:
    return {
        "data": entry.data,
        "status": entry.status,
        "status_reason": entry.status_reason,
        "rank": entry.rank,
        "primary": str(entry.primary) if entry.primary is not None else None,
    }


def recompute(fixture) -> list[EntryResult]:
    """Run the preset's calculator over every entrant and cache the ranking."""

    from apps.fixtures.models import FixtureSide

    result_type = result_type_of(fixture.competition)
    ensure_sheet(fixture)
    config = sheet_config(fixture)
    sides = list(fixture.sides.select_related("entry_result"))
    entries = {side.id: side.entry_result.data for side in sides}
    overrides = {
        side.id: (side.entry_result.status, side.entry_result.status_reason)
        for side in sides
        if side.entry_result.status
    }
    try:
        ranked = evaluate(result_type, entries, config, overrides)
    except ResultDataError as error:
        raise ValidationError({"results": str(error)}) from error

    updated = []
    for side in sides:
        rank, order, outcome = ranked[side.id]
        entry = side.entry_result
        entry.computed_status = "" if entry.status else outcome.status
        entry.rank = rank
        entry.primary = (
            outcome.primary.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
            if outcome.primary is not None
            else None
        )
        entry.breakdown = {
            **_serial(outcome.breakdown),
            "order": order,
            "status_reason": entry.status_reason or outcome.status_reason,
        }
        updated.append(entry)
        side.score = (
            entry.primary.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if entry.primary is not None
            else Decimal("0")
        )
        if rank == 1:
            side.outcome = FixtureSide.Outcome.WIN
        elif rank is not None or entry.effective_status:
            side.outcome = FixtureSide.Outcome.LOSS
        else:
            side.outcome = FixtureSide.Outcome.PENDING
    EntryResult.objects.bulk_update(
        updated, ["computed_status", "rank", "primary", "breakdown", "updated_at"]
    )
    FixtureSide.objects.bulk_update(sides, ["score", "outcome"])
    return updated


def _refresh_if_counted(fixture) -> None:
    if fixture.is_counted:
        from apps.standings.services import refresh_standings

        refresh_standings(fixture.competition)


def _log(fixture, actor, action, *, side=None, reason="", before=None, after=None) -> None:
    ResultAmendment.objects.create(
        fixture=fixture,
        side=side,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        reason=reason[:500],
        before=before or {},
        after=after or {},
    )


@transaction.atomic
def save_results(fixture, rows: list[dict], actor, *, reason: str = "", config: dict | None = None):
    """Store raw inputs. Once a result is final, only officials may change it, with a reason."""

    sheet = ensure_sheet(fixture)
    competition = fixture.competition
    if sheet.is_final:
        assert_can_decide(competition, actor)
        if not reason.strip():
            raise ValidationError({"reason": "Give a reason for amending a final result."})
    elif not (can_record(fixture, actor) or can_decide(competition, actor)):
        raise PermissionDenied("You cannot record results for this event.")

    if config is not None:
        if not isinstance(config, dict):
            raise ValidationError({"config": "Event settings must be an object."})
        if not (can_decide(competition, actor) or has_at_least(competition, actor, Role.ADMIN)):
            raise PermissionDenied("Only officials or admins change an event's settings.")
        before = dict(sheet.config)
        sheet.config = {**sheet.config, **config}
        sheet.save(update_fields=["config", "updated_at"])
        if sheet.is_final:
            _log(
                fixture,
                actor,
                ResultAmendment.Action.AMENDED,
                reason=reason,
                before={"config": before},
                after={"config": sheet.config},
            )

    sides = {str(side.id): side for side in fixture.sides.select_related("entry_result")}
    changed = []
    for row in rows or []:
        side = sides.get(str(row.get("side")))
        if side is None:
            raise ValidationError({"side": "That entrant is not in this event."})
        entry = side.entry_result
        data = row.get("data") or {}
        if not isinstance(data, dict):
            raise ValidationError({"data": "Result data must be an object."})
        if entry.welfare_locked:
            raise ValidationError(
                {"side": f"{side.participant.name} was eliminated on welfare grounds. That stands."}
            )
        if data == entry.data:
            continue
        before = _snapshot(entry)
        entry.data = data
        entry.save(update_fields=["data", "updated_at"])
        changed.append((side, before))

    entries = recompute(fixture)
    if sheet.is_final:
        by_side = {entry.side_id: entry for entry in entries}
        for side, before in changed:
            _log(
                fixture,
                actor,
                ResultAmendment.Action.AMENDED,
                side=side,
                reason=reason,
                before=before,
                after=_snapshot(by_side[side.id]),
            )
        _refresh_if_counted(fixture)
    return entries


@transaction.atomic
def set_status(fixture, side_id, status: str, actor, *, reason: str, welfare: bool = False):
    """An official eliminates, retires, withdraws or disqualifies an entrant (or clears it)."""

    competition = fixture.competition
    assert_can_decide(competition, actor)
    if not reason.strip():
        raise ValidationError({"reason": "Give a reason. Every decision is logged."})
    ensure_sheet(fixture)
    side = fixture.sides.select_related("entry_result").filter(pk=side_id).first()
    if side is None:
        raise ValidationError({"side": "That entrant is not in this event."})
    entry = side.entry_result
    if entry.welfare_locked:
        raise ValidationError({"status": "A welfare elimination cannot be overridden in the app."})
    config = sheet_config(fixture)
    allowed = {item["code"] for item in statuses_for(config)}
    for extra in ("failed_status", "elimination_status", "inspection_status"):
        if config.get(extra):
            allowed.add(config[extra])
    if status and status not in allowed:
        raise ValidationError({"status": f"Use one of: {', '.join(sorted(allowed))}."})
    if welfare and not status:
        raise ValidationError({"status": "A welfare elimination needs a status such as EL."})

    before = _snapshot(entry)
    entry.status = status
    entry.status_reason = reason[:280]
    entry.welfare_locked = bool(welfare)
    entry.save(update_fields=["status", "status_reason", "welfare_locked", "updated_at"])
    entries = recompute(fixture)
    after = _snapshot(next(item for item in entries if item.side_id == side.id))
    _log(
        fixture,
        actor,
        ResultAmendment.Action.WELFARE if welfare else ResultAmendment.Action.STATUS,
        side=side,
        reason=reason,
        before=before,
        after=after,
    )
    _refresh_if_counted(fixture)
    return entries


@transaction.atomic
def finalise(fixture, actor, *, reason: str = ""):
    from apps.fixtures.models import Fixture

    competition = fixture.competition
    assert_can_decide(competition, actor)
    sheet = ensure_sheet(fixture)
    entries = recompute(fixture)
    pending = [
        entry.side.participant.name
        for entry in entries
        if entry.rank is None and not entry.effective_status
    ]
    if pending:
        raise ValidationError(
            {"results": f"Still waiting for a result for: {', '.join(sorted(pending))}."}
        )
    already = sheet.is_final
    sheet.finalised_at = timezone.now()
    sheet.finalised_by = actor
    sheet.save(update_fields=["finalised_at", "finalised_by", "updated_at"])
    fixture.status = Fixture.Status.COMPLETED
    fixture.completed_at = fixture.completed_at or timezone.now()
    fixture.save(update_fields=["status", "completed_at", "updated_at"])
    if not already:
        _log(
            fixture,
            actor,
            ResultAmendment.Action.FINALISED,
            reason=reason,
            after={
                "ranking": [
                    {
                        "entrant": entry.side.participant.name,
                        "rank": entry.rank,
                        "status": entry.effective_status,
                    }
                    for entry in sorted(entries, key=lambda item: item.breakdown.get("order", 0))
                ]
            },
        )
    _refresh_if_counted(fixture)
    return entries


@transaction.atomic
def create_event(competition, *, label: str, scheduled_at=None, participant_ids=None, actor=None):
    """One event (a race, a class, a ride) with every chosen entrant in it."""

    from apps.fixtures.models import Fixture, FixtureSide

    participants = competition.participants.filter(is_active=True)
    if participant_ids:
        participants = participants.filter(id__in=participant_ids)
    participants = list(participants.order_by("seed", "name"))
    if not participants:
        raise ValidationError({"participant_ids": "Add entrants before creating an event."})
    fixture = Fixture.objects.create(
        competition=competition,
        label=label[:160],
        scheduled_at=scheduled_at,
        status=Fixture.Status.SCHEDULED,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    FixtureSide.objects.bulk_create(
        [
            FixtureSide(fixture=fixture, participant=participant, position=index)
            for index, participant in enumerate(participants)
        ]
    )
    ensure_sheet(fixture)
    return fixture


# --- Series and combination statistics -----------------------------------------


def placing_points_for(settings: dict, rank: int, tied: int) -> Decimal:
    table = [Decimal(str(value)) for value in settings.get("placing_points") or []]
    if not table or rank < 1:
        return Decimal("0")
    if (settings.get("dead_heat_points") or "full") == "shared" and tied > 1:
        shares = table[rank - 1 : rank - 1 + tied]
        return sum(shares, Decimal("0")) / tied if shares else Decimal("0")
    return table[rank - 1] if rank <= len(table) else Decimal("0")


def counted_entries(competition):
    """Every entrant's result in finalised events, with how many shared their place."""

    from apps.fixtures.models import Fixture

    entries = list(
        EntryResult.objects.filter(
            side__fixture__competition=competition,
            side__fixture__status__in=[Fixture.Status.COMPLETED, Fixture.Status.FORFEIT],
        ).select_related("side__participant", "side__fixture")
    )
    ties: dict = {}
    for entry in entries:
        if entry.rank is not None:
            key = (entry.side.fixture_id, entry.rank)
            ties[key] = ties.get(key, 0) + 1
    return [(entry, ties.get((entry.side.fixture_id, entry.rank), 1)) for entry in entries]


def combination_stats(competition, by: str) -> list[dict]:
    """Starts, wins, seconds, thirds and points per horse, rider or trainer."""

    from apps.horses.models import Combination

    settings = competition.settings_json or {}
    combos = {
        combo.participant_id: combo
        for combo in Combination.objects.filter(
            participant__competition=competition
        ).select_related("horse", "rider", "trainer")
    }
    table: dict = {}
    for entry, tied in counted_entries(competition):
        combo = combos.get(entry.side.participant_id)
        if combo is None:
            continue
        if by == "horse":
            key, label = f"horse:{combo.horse_id}", combo.horse.name
        elif by == "trainer":
            label = combo.trainer_label
            if not label:
                continue
            key = f"trainer:{combo.trainer_id or label.lower()}"
        else:
            label = combo.rider_label
            if not label:
                continue
            key = f"rider:{combo.rider_id or label.lower()}"
        row = table.setdefault(
            key,
            {
                "key": key,
                "name": label,
                "starts": 0,
                "wins": 0,
                "seconds": 0,
                "thirds": 0,
                "points": Decimal("0"),
                "statuses": 0,
            },
        )
        row["starts"] += 1
        if entry.rank == 1:
            row["wins"] += 1
        elif entry.rank == 2:
            row["seconds"] += 1
        elif entry.rank == 3:
            row["thirds"] += 1
        if entry.rank is None:
            row["statuses"] += 1
        else:
            row["points"] += placing_points_for(settings, entry.rank, tied)
    rows = sorted(
        table.values(),
        key=lambda row: (
            -row["wins"],
            -row["seconds"],
            -row["thirds"],
            -row["points"],
            row["name"].lower(),
        ),
    )
    return [{**row, "points": format(row["points"].normalize(), "f")} for row in rows]
