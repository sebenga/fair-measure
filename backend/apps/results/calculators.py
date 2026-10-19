"""Turn one event's raw inputs into a ranking, from preset data alone.

Each result type is a small, pure function: entrant data plus the preset's
`result_config` in, an `Outcome` out. Ranking then works the same for every type:
finishers by their sort key (equal keys share the place), then everyone with a
status such as EL or DQ, in the order the preset lists those statuses. Nothing
here names a sport; penalty values, phases, judges and time rules are all data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

ZERO = Decimal("0")
BIG = Decimal("999999")

DEFAULT_STATUSES: list[dict] = [
    {"code": "EL", "label": "Eliminated"},
    {"code": "RT", "label": "Retired"},
    {"code": "WD", "label": "Withdrawn"},
    {"code": "DNF", "label": "Did not finish"},
    {"code": "DQ", "label": "Disqualified"},
]


class ResultDataError(ValueError):
    """The submitted inputs do not fit the preset's result type."""


@dataclass
class Outcome:
    # "" means the entrant finished (or has not been scored yet, when key is None).
    status: str = ""
    status_reason: str = ""
    primary: Decimal | None = None
    key: tuple | None = None
    breakdown: dict = field(default_factory=dict)

    @property
    def finished(self) -> bool:
        return not self.status and self.key is not None


def dec(value, *, name: str = "value") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ResultDataError(f"{name} must be a number.") from error


def _count(value, *, name: str) -> int:
    if value in (None, ""):
        return 0
    try:
        count = int(value)
    except (TypeError, ValueError) as error:
        raise ResultDataError(f"{name} must be a whole number.") from error
    if count < 0:
        raise ResultDataError(f"{name} cannot be negative.")
    return count


def _q(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def statuses_for(config: dict) -> list[dict]:
    return list(config.get("statuses") or DEFAULT_STATUSES)


# --- Penalty sheets (shared by faults_then_time and penalty_total_lowest) ----


def _penalty_items(items: list[dict], sheet: dict) -> tuple[Decimal, Decimal, str, dict]:
    """Faults, extra seconds, the elimination reason (if any), and a per-item breakdown."""

    faults = ZERO
    seconds = ZERO
    eliminated = ""
    detail: dict = {}
    for item in items:
        key = item["key"]
        raw = sheet.get(key)
        if item.get("per_obstacle"):
            per = raw or {}
            if not isinstance(per, dict):
                raise ResultDataError(f"{item['label']} is counted per obstacle.")
            scale = [dec(value) for value in item.get("scale") or [item.get("faults", 0)]]
            stop = item.get("eliminate_at")
            item_faults = ZERO
            total = 0
            for obstacle, count_value in per.items():
                count = _count(count_value, name=f"{item['label']} at {obstacle}")
                total += count
                if stop and count >= int(stop):
                    eliminated = eliminated or f"{item['label']} ({count} at obstacle {obstacle})"
                    continue
                item_faults += sum(scale[: min(count, len(scale))], ZERO)
                if count > len(scale):
                    item_faults += scale[-1] * (count - len(scale))
            limit_total = item.get("eliminate_total_at")
            if limit_total and total >= int(limit_total):
                eliminated = eliminated or f"{item['label']} ({total} on the course)"
            faults += item_faults
            detail[key] = {"count": total, "faults": str(item_faults)}
            continue

        count = _count(raw, name=item["label"])
        if not count:
            continue
        stop = item.get("eliminate_at")
        if stop and count >= int(stop):
            eliminated = eliminated or item["label"]
        # Only the occurrences before the eliminating one cost faults.
        charged = min(count, int(stop) - 1) if stop else count
        item_faults = dec(item.get("faults", 0)) * charged
        faults += item_faults
        seconds += dec(item.get("penalty_seconds", 0)) * charged
        detail[key] = {"count": count, "faults": str(item_faults)}
    return faults, seconds, eliminated, detail


def _time_faults(
    time_value, allowed, rule: dict, limit=None
) -> tuple[Decimal, Decimal | None, str]:
    """Time penalties for one round or phase, and the time itself."""

    if time_value in (None, ""):
        return ZERO, None, ""
    taken = dec(time_value, name="Time")
    if taken < 0:
        raise ResultDataError("Time cannot be negative.")
    if allowed in (None, ""):
        return ZERO, taken, ""
    allowed = dec(allowed, name="Time allowed")
    hard_limit = None
    if limit not in (None, ""):
        hard_limit = dec(limit, name="Time limit")
    elif rule.get("limit_factor"):
        hard_limit = allowed * dec(rule["limit_factor"])
    if hard_limit is not None and taken > hard_limit:
        return ZERO, taken, "Exceeded the time limit"
    over = taken - allowed
    if over <= 0:
        return ZERO, taken, ""
    per = dec(rule.get("per_seconds") or 1)
    units = over / per
    if rule.get("commenced", True):
        units = Decimal(math.ceil(units))
    penalty = dec(rule.get("penalty", rule.get("fault", 1)))
    return units * penalty, taken, ""


# --- finishing_order -------------------------------------------------------


def finishing_order(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    position = data.get("position")
    if position in (None, ""):
        return Outcome()
    place = _count(position, name="Position")
    if place < 1:
        raise ResultDataError("Positions start at 1.")
    keep = {name: data[name] for name in config.get("record_fields") or [] if name in data}
    return Outcome(primary=Decimal(place), key=(place,), breakdown=keep)


# --- faults_then_time --------------------------------------------------------


def _round_result(sheet: dict, round_key: str, config: dict) -> dict:
    faults, extra_seconds, eliminated, detail = _penalty_items(config.get("penalties") or [], sheet)
    allowed = (config.get("time_allowed") or {}).get(round_key)
    limit = (config.get("time_limit") or {}).get(round_key)
    time_faults, taken, time_problem = _time_faults(
        sheet.get("time"), allowed, config.get("time") or {}, limit
    )
    eliminated = eliminated or time_problem
    total = faults + time_faults
    return {
        "faults": total,
        "obstacle_faults": faults,
        "time_faults": time_faults,
        "time": taken,
        "adjusted_time": (taken + extra_seconds) if taken is not None else None,
        "eliminated": eliminated,
        "detail": detail,
    }


def faults_then_time(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    rounds_data = data.get("rounds") or {}
    rounds = config.get("rounds") or [{"key": "round", "label": "Round"}]
    counted = [item for item in rounds if not item.get("decides")]
    played = {}
    for item in rounds:
        sheet = rounds_data.get(item["key"])
        if sheet:
            played[item["key"]] = _round_result(sheet, item["key"], config)
    if not all(item["key"] in played for item in counted):
        return Outcome(breakdown={"rounds": _serial(played)})
    eliminated = next(
        (
            played[item["key"]]["eliminated"]
            for item in counted
            if played[item["key"]]["eliminated"]
        ),
        "",
    )
    if eliminated:
        return Outcome(
            status=config.get("elimination_status", "EL"),
            status_reason=eliminated,
            breakdown={"rounds": _serial(played)},
        )
    faults = sum((played[item["key"]]["faults"] for item in counted), ZERO)
    last = played[counted[-1]["key"]]
    time_value = (
        last["adjusted_time"] if config.get("ranking") == "time_plus_penalties" else last["time"]
    )
    time_value = time_value if time_value is not None else BIG
    if config.get("ranking") == "time_plus_penalties":
        key = (time_value,)
        primary = time_value
    else:
        key = (faults, time_value)
        primary = faults
    return Outcome(
        primary=primary,
        key=key,
        breakdown={"faults": str(faults), "time": str(time_value), "rounds": _serial(played)},
    )


def faults_then_time_context(outcomes: dict, entries: dict, config: dict) -> None:
    """A deciding round (jump-off) separates only those level on the first place."""

    deciders = [item for item in config.get("rounds") or [] if item.get("decides") == "first"]
    if not deciders or config.get("ranking") == "time_plus_penalties":
        return
    decider = deciders[0]["key"]
    finishers = {entry_id: outcome for entry_id, outcome in outcomes.items() if outcome.finished}
    if not finishers:
        return
    best = min(outcome.key[0] for outcome in finishers.values())
    level = [entry_id for entry_id, outcome in finishers.items() if outcome.key[0] == best]
    if len(level) < 2:
        for outcome in finishers.values():
            outcome.key = (1, *outcome.key)
        return
    for entry_id, outcome in finishers.items():
        if entry_id not in level:
            outcome.key = (1, *outcome.key)
            continue
        sheet = ((entries[entry_id] or {}).get("rounds") or {}).get(decider)
        if not sheet:
            # Level for first but not yet through the deciding round.
            outcome.key = (0, 1, BIG, BIG)
            continue
        result = _round_result(sheet, decider, config)
        outcome.breakdown.setdefault("rounds", {})[decider] = _serial({decider: result})[decider]
        if result["eliminated"]:
            outcome.key = (0, 1, BIG, BIG)
            outcome.breakdown["decider"] = (
                f"Eliminated in the deciding round: {result['eliminated']}"
            )
            continue
        time_value = result["time"] if result["time"] is not None else BIG
        outcome.key = (0, 0, result["faults"], time_value)
        outcome.breakdown["decider"] = {"faults": str(result["faults"]), "time": str(time_value)}


# --- penalty_total_lowest ------------------------------------------------------


def penalty_total_lowest(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    inspections = data.get("inspections") or {}
    for item in config.get("inspections") or []:
        if str(inspections.get(item["key"]) or "").lower() == "fail":
            return Outcome(
                status=config.get("inspection_status", "EL"),
                status_reason=f"Failed {item['label']}",
            )
    phases_data = data.get("phases") or {}
    phases = config.get("phases") or []
    totals: dict[str, dict] = {}
    for phase in phases:
        sheet = phases_data.get(phase["key"])
        if sheet in (None, {}):
            return Outcome(breakdown={"phases": totals})
        if phase.get("input") == "percentage":
            percentage = dec(sheet.get("percentage"), name=f"{phase['label']} percentage")
            if not ZERO <= percentage <= 100:
                raise ResultDataError(f"{phase['label']} percentage must be between 0 and 100.")
            base = dec(phase.get("from_percentage", 100))
            factor = dec(phase.get("multiplier", 1))
            penalty = _q((base - percentage) * factor, int(phase.get("decimals", 1)))
            totals[phase["key"]] = {"penalties": penalty, "time": None}
            continue
        faults, _, eliminated, detail = _penalty_items(phase.get("penalties") or [], sheet)
        allowed = (config.get("time_allowed") or {}).get(phase["key"])
        limit = (config.get("time_limit") or {}).get(phase["key"])
        time_faults, taken, problem = _time_faults(
            sheet.get("time"), allowed, phase.get("time") or {}, limit
        )
        eliminated = eliminated or problem
        if eliminated:
            return Outcome(
                status=config.get("elimination_status", "EL"),
                status_reason=f"{phase['label']}: {eliminated}",
                breakdown={"phases": _serial(totals)},
            )
        totals[phase["key"]] = {
            "penalties": faults + time_faults,
            "jumping": faults,
            "time_penalties": time_faults,
            "time": taken,
            "detail": detail,
        }
    total = sum((row["penalties"] for row in totals.values()), ZERO)
    key: list = [total]
    for rule in config.get("tiebreakers") or []:
        kind, _, phase_key = str(rule).partition(":")
        row = totals.get(phase_key) or {}
        if kind == "phase":
            key.append(row.get("penalties", BIG))
        elif kind == "phase_jumping":
            key.append(row.get("jumping", BIG))
        elif kind == "phase_time":
            key.append(row.get("time") if row.get("time") is not None else BIG)
    return Outcome(
        primary=total, key=tuple(key), breakdown={"total": str(total), "phases": _serial(totals)}
    )


# --- judged_percentage ---------------------------------------------------------


def judged_percentage(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    errors_rule = config.get("errors") or {}
    errors = _count(data.get("errors"), name="Errors")
    stop = errors_rule.get("eliminate_at")
    if stop and errors >= int(stop):
        return Outcome(
            status=config.get("elimination_status", "EL"),
            status_reason=f"{errors} errors of course",
        )
    sheet = config.get("sheet") or []
    if not sheet:
        raise ResultDataError("This result type needs a test sheet in the preset.")
    max_mark = dec(config.get("max_mark", 10))
    step = dec(config.get("mark_step", "0.5"))
    places = int(config.get("decimals", 3))
    marks = data.get("marks") or {}
    judges = list(config.get("judges") or marks.keys())
    if not judges:
        return Outcome()
    deductions = sum(
        (dec(value) for value in (errors_rule.get("deduct_points") or [])[:errors]), ZERO
    )
    weights = {key: dec(value) for key, value in (config.get("section_weights") or {}).items()}
    by_judge: dict[str, dict] = {}
    collective_total = ZERO
    for judge in judges:
        given = marks.get(judge) or {}
        if any(item["key"] not in given for item in sheet):
            return Outcome(breakdown={"judges": by_judge, "waiting_for": judge})
        sections: dict[str, list[Decimal]] = {}
        total = ZERO
        maximum = ZERO
        for item in sheet:
            mark = dec(given[item["key"]], name=f"{judge}: {item['label']}")
            if mark < 0 or mark > max_mark:
                raise ResultDataError(f"{judge}: {item['label']} must be between 0 and {max_mark}.")
            if step and (mark / step) % 1 != 0:
                raise ResultDataError(f"{judge}: {item['label']} must be in steps of {step}.")
            coefficient = dec(item.get("coefficient", 1))
            total += mark * coefficient
            maximum += max_mark * coefficient
            if item.get("collective"):
                collective_total += mark * coefficient
            section = item.get("section", "")
            bucket = sections.setdefault(section, [ZERO, ZERO])
            bucket[0] += mark * coefficient
            bucket[1] += max_mark * coefficient
        if weights:
            percentage = sum(
                (
                    weights.get(name, ZERO) * (score / top * 100)
                    for name, (score, top) in sections.items()
                    if top
                ),
                ZERO,
            )
        else:
            percentage = (total - deductions) / maximum * 100
        by_judge[judge] = {
            "total": str(total - deductions),
            "percentage": str(_q(percentage, places)),
        }
    final = sum((Decimal(row["percentage"]) for row in by_judge.values()), ZERO) / len(by_judge)
    final = _q(final, places)
    collectives = collective_total / len(by_judge)
    return Outcome(
        primary=final,
        key=(-final, -collectives),
        breakdown={
            "percentage": str(final),
            "judges": by_judge,
            "deductions": str(deductions),
            "collectives": str(_q(collectives, 2)),
        },
    )


# --- timed_with_vet_gates --------------------------------------------------------


def timed_with_vet_gates(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    failed = config.get("failed_status", "FTQ")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    loops = config.get("loops") or []
    if not loops:
        raise ResultDataError("Set the loops (and their distances) for this ride.")
    max_rate = config.get("heart_rate_max")
    given = data.get("loops") or []
    ride = ZERO
    hold = ZERO
    distance = ZERO
    gates = []
    for index, loop in enumerate(loops):
        if index >= len(given) or not given[index]:
            return Outcome(breakdown={"gates": gates})
        row = given[index]
        reason = ""
        if str(row.get("result") or "").lower() == "ftq":
            reason = str(row.get("reason") or "Failed to qualify")
        elif row.get("presented_in_time") is False:
            reason = "Not presented in time"
        elif row.get("sound") is False:
            reason = "Lameness"
        elif max_rate is not None and row.get("heart_rate") not in (None, ""):
            if dec(row["heart_rate"], name="Heart rate") > dec(max_rate):
                reason = "Metabolic: heart rate above the limit"
        if row.get("ride_seconds") in (None, ""):
            if reason:
                return Outcome(
                    status=failed, status_reason=f"{loop.get('label', 'Gate')}: {reason}"
                )
            return Outcome(breakdown={"gates": gates})
        seconds = dec(row["ride_seconds"], name="Ride time")
        gates.append(
            {"loop": loop.get("label"), "ride_seconds": str(seconds), "passed": not reason}
        )
        if reason:
            return Outcome(
                status=failed,
                status_reason=f"{loop.get('label', 'Gate')}: {reason}",
                breakdown={"gates": gates},
            )
        ride += seconds
        hold += dec(row.get("hold_seconds") or 0)
        distance += dec(loop.get("distance_km") or 0)
    final = data.get("final_inspection") or {}
    if config.get("final_inspection", True):
        verdict = str(final.get("result") or "").lower()
        if not verdict:
            return Outcome(breakdown={"gates": gates})
        if verdict == "ftq":
            return Outcome(
                status=failed,
                status_reason=f"Final inspection: {final.get('reason') or 'Failed to qualify'}",
                breakdown={"gates": gates},
            )
    speed = _q(distance / (ride / 3600), 2) if ride else ZERO
    return Outcome(
        primary=ride,
        key=(ride,),
        breakdown={
            "ride_seconds": str(ride),
            "hold_seconds": str(hold),
            "distance_km": str(distance),
            "average_speed_kmh": str(speed),
            "gates": gates,
        },
    )


# --- points_per_run --------------------------------------------------------------


def _runs_total(runs: list, config: dict) -> tuple[Decimal, list]:
    points = {item["key"]: dec(item["points"]) for item in config.get("outcomes") or []}
    limit = config.get("time_limit_seconds")
    total = ZERO
    detail = []
    for run in runs or []:
        outcome = run.get("outcome")
        if outcome not in points:
            raise ResultDataError(f"'{outcome}' is not one of this event's run outcomes.")
        value = points[outcome]
        over = False
        if limit not in (None, "") and run.get("time") not in (None, ""):
            over = dec(run["time"], name="Run time") > dec(limit)
        if over:
            value = ZERO
        total += value
        detail.append({"outcome": outcome, "points": str(value), "over_time": over})
    return total, detail


def points_per_run(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    riders = data.get("riders")
    breakdown: dict = {}
    if riders:
        total = ZERO
        breakdown["riders"] = {}
        for name, runs in riders.items():
            rider_total, detail = _runs_total(runs, config)
            total += rider_total
            breakdown["riders"][name] = {"total": str(rider_total), "runs": detail}
    else:
        runs = data.get("runs") or []
        if not runs:
            return Outcome()
        total, detail = _runs_total(runs, config)
        breakdown["runs"] = detail
    run_off, run_off_detail = _runs_total(data.get("run_off") or [], config)
    if run_off_detail:
        breakdown["run_off"] = {"total": str(run_off), "runs": run_off_detail}
    breakdown["total"] = str(total)
    return Outcome(primary=total, key=(-total, -run_off), breakdown=breakdown)


# --- Registry and ranking ----------------------------------------------------------

CALCULATORS = {
    "finishing_order": finishing_order,
    "faults_then_time": faults_then_time,
    "penalty_total_lowest": penalty_total_lowest,
    "judged_percentage": judged_percentage,
    "timed_with_vet_gates": timed_with_vet_gates,
    "points_per_run": points_per_run,
}

CONTEXT = {"faults_then_time": faults_then_time_context}


def _serial(value):
    if isinstance(value, dict):
        return {key: _serial(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_serial(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def evaluate(result_type: str, entries: dict, config: dict, overrides: dict | None = None) -> dict:
    """Outcomes for every entrant, ranked.

    ``entries`` maps an id to its raw data; ``overrides`` maps an id to a status an
    official set, which always wins over a calculated one. Returns id -> (rank,
    order, Outcome). Rank is None for anyone with a status or no result yet.
    """

    calculator = CALCULATORS.get(result_type)
    if calculator is None:
        raise ResultDataError(f"Unknown result type '{result_type}'.")
    overrides = overrides or {}
    outcomes: dict = {}
    for entry_id, data in entries.items():
        forced = overrides.get(entry_id)
        if forced:
            outcomes[entry_id] = Outcome(status=forced[0], status_reason=forced[1])
            continue
        outcomes[entry_id] = calculator(data or {}, config)
    hook = CONTEXT.get(result_type)
    if hook:
        hook(outcomes, entries, config)
    return rank(outcomes, config)


def rank(outcomes: dict, config: dict) -> dict:
    order_of = {item["code"]: index for index, item in enumerate(statuses_for(config))}
    finishers = sorted(
        (entry_id for entry_id, outcome in outcomes.items() if outcome.finished),
        key=lambda entry_id: outcomes[entry_id].key,
    )
    result: dict = {}
    previous_key = None
    current_rank = 0
    for index, entry_id in enumerate(finishers):
        key = outcomes[entry_id].key
        if key != previous_key:
            current_rank = index + 1
            previous_key = key
        result[entry_id] = (current_rank, index, outcomes[entry_id])
    with_status = sorted(
        (entry_id for entry_id, outcome in outcomes.items() if outcome.status),
        key=lambda entry_id: order_of.get(outcomes[entry_id].status, len(order_of)),
    )
    position = len(finishers)
    for entry_id in with_status:
        result[entry_id] = (None, position, outcomes[entry_id])
        position += 1
    for entry_id, outcome in outcomes.items():
        if entry_id not in result:
            result[entry_id] = (None, position, outcome)
            position += 1
    return result
