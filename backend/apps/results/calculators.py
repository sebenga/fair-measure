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
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation

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

    # A round marked qualify: "clear" is only ridden by those still clear after
    # the rounds before it (a two-phase class). The rest stop there.
    needed: list[dict] = []
    stopped = False
    for item in counted:
        if item.get("qualify") == "clear" and needed:
            if not all(prior["key"] in played for prior in needed):
                break
            before = [played[prior["key"]] for prior in needed]
            if any(row["eliminated"] for row in before) or sum(
                (row["faults"] for row in before), ZERO
            ):
                stopped = True
                break
        needed.append(item)
    staged = any(item.get("qualify") for item in counted)
    if not needed or not all(item["key"] in played for item in needed):
        return Outcome(breakdown={"rounds": _serial(played)})

    eliminated_in = next(
        (item for item in needed if played[item["key"]]["eliminated"]),
        None,
    )
    if eliminated_in is not None and not (staged and eliminated_in.get("qualify")):
        return Outcome(
            status=config.get("elimination_status", "EL"),
            status_reason=played[eliminated_in["key"]]["eliminated"],
            breakdown={"rounds": _serial(played)},
        )
    faults = sum((played[item["key"]]["faults"] for item in needed), ZERO)
    last = played[needed[-1]["key"]]
    time_value = (
        last["adjusted_time"] if config.get("ranking") == "time_plus_penalties" else last["time"]
    )
    time_value = time_value if time_value is not None else BIG
    breakdown = {"faults": str(faults), "time": str(time_value), "rounds": _serial(played)}
    if config.get("ranking") == "time_plus_penalties":
        key = (time_value,)
        primary = time_value
    elif staged:
        # Those who reached the later phase rank ahead of those who stopped.
        # Eliminated in the later phase: behind its finishers, ahead of those who stopped.
        out = eliminated_in is not None
        key = (1 if stopped else 0, 1 if out else 0, BIG if out else faults, BIG if out else time_value)
        primary = faults
        breakdown["reached"] = needed[-1]["key"]
        if out:
            breakdown["phase_out"] = (
                f"Eliminated in {eliminated_in.get('label', eliminated_in['key'])}: "
                f"{played[eliminated_in['key']]['eliminated']}"
            )
    else:
        key = (faults, time_value)
        primary = faults
    return Outcome(primary=primary, key=key, breakdown=breakdown)


def faults_then_time_context(outcomes: dict, entries: dict, config: dict) -> None:
    """A deciding round separates only those level on the first place."""

    deciders = [item for item in config.get("rounds") or [] if item.get("decides") == "first"]
    staged = any(item.get("qualify") for item in config.get("rounds") or [])
    if not deciders or staged or config.get("ranking") == "time_plus_penalties":
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
        codes = {item["code"]: item["label"] for item in config.get("ftq_codes") or []}
        presented = row.get("presentation_seconds")
        limit = config.get("presentation_limit_seconds")
        if row.get("ftq_code"):
            code = str(row["ftq_code"])
            reason = f"{code} · {codes.get(code, 'Failed to qualify')}"
        elif str(row.get("result") or "").lower() == "ftq":
            reason = str(row.get("reason") or "Failed to qualify")
        elif row.get("presented_in_time") is False:
            reason = "Not presented in time"
        elif limit is not None and presented not in (None, "") and dec(presented, name="Presentation time") > dec(limit):
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
    breakdown = {
        "ride_seconds": str(ride),
        "hold_seconds": str(hold),
        "distance_km": str(distance),
        "average_speed_kmh": str(speed),
        "gates": gates,
    }
    fastest = config.get("speed_max_kmh")
    slowest = config.get("speed_min_kmh")
    if fastest is not None and speed > dec(fastest):
        return Outcome(
            status=config.get("speed_status", "EL"),
            status_reason=f"Average speed {speed} km/h is above the {fastest} km/h limit",
            breakdown=breakdown,
        )
    if slowest is not None and speed < dec(slowest):
        return Outcome(
            status=config.get("speed_status", "EL"),
            status_reason=f"Average speed {speed} km/h is below the {slowest} km/h minimum",
            breakdown=breakdown,
        )
    return Outcome(primary=ride, key=(ride,), breakdown=breakdown)


def best_condition_context(outcomes: dict, entries: dict, config: dict) -> None:
    """A separate award among the leading finishers: the vets' marks plus time (and weight).

    Every number is preset data: the vet items and their weight, the time points and
    how fast they fall away behind the winner, and the optional rider weight points.
    """

    rule = config.get("best_condition")
    if not rule:
        return
    finishers = sorted(
        (entry_id for entry_id, outcome in outcomes.items() if outcome.finished),
        key=lambda entry_id: outcomes[entry_id].key,
    )
    if not finishers:
        return
    eligible = finishers[: int(rule.get("eligible") or len(finishers))]
    winner = outcomes[finishers[0]].primary
    items = rule.get("vet_items") or []
    weight_rule = rule.get("weight") or {}
    def sheet_of(entry_id) -> dict:
        return (entries[entry_id] or {}).get("best_condition") or {}

    weights = {
        entry_id: dec(sheet_of(entry_id)["weight_kg"], name="Rider weight")
        for entry_id in eligible
        if sheet_of(entry_id).get("weight_kg") not in (None, "")
    }
    heaviest = max(weights.values()) if weights else None
    scored = []
    for entry_id in eligible:
        marks = sheet_of(entry_id).get("marks") or {}
        if not items or any(item["key"] not in marks for item in items):
            continue
        vet = ZERO
        for item in items:
            mark = dec(marks[item["key"]], name=item["label"])
            top = dec(item.get("max", 10))
            if mark < 0 or mark > top:
                raise ResultDataError(f"{item['label']} must be between 0 and {top}.")
            vet += mark * dec(item.get("weight", 1))
        behind = (outcomes[entry_id].primary - winner) / 60
        time_points = max(ZERO, dec(rule.get("time_base", 0)) - behind * dec(rule.get("time_per_minute", 1)))
        weight_points = ZERO
        if weight_rule and heaviest is not None and entry_id in weights:
            weight_points = max(
                ZERO,
                dec(weight_rule.get("base", 0))
                - (heaviest - weights[entry_id]) * dec(weight_rule.get("per_kg", 1)),
            )
        total = _q(vet + time_points + weight_points, 2)
        scored.append((entry_id, total, vet, time_points, weight_points))
    scored.sort(key=lambda row: (-row[1], -row[2]))
    for position, (entry_id, total, vet, time_points, weight_points) in enumerate(scored, start=1):
        outcomes[entry_id].breakdown["best_condition"] = {
            "rank": position,
            "score": str(total),
            "vet": str(_q(vet, 2)),
            "time_points": str(_q(time_points, 2)),
            "weight_points": str(_q(weight_points, 2)),
        }


# --- points_per_run --------------------------------------------------------------


def _runs_total(runs: list, config: dict) -> tuple[Decimal, list]:
    points = {item["key"]: dec(item["points"]) for item in config.get("outcomes") or []}
    limit = config.get("time_limit_seconds")
    total = ZERO
    detail = []
    for run in runs or []:
        # A run not filled in yet (a gap left on the sheet) is not scored.
        if not run or not run.get("outcome"):
            continue
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


# --- timed_lowest -------------------------------------------------------------------


def _timing(value, config: dict, *, name: str = "Time") -> Decimal:
    taken = dec(value, name=name)
    if taken < 0:
        raise ResultDataError(f"{name} cannot be negative.")
    places = int(config.get("decimals", 2))
    rounding = ROUND_HALF_UP if config.get("rounding") == "half_up" else ROUND_CEILING
    # Hand-held and photo-finish times round up to the next unit by default.
    return taken.quantize(Decimal(1).scaleb(-places), rounding=rounding)


def timed_lowest(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    limit = config.get("reaction_limit")
    reaction = data.get("reaction_time")
    false_start = bool(data.get("false_start"))
    if not false_start and limit not in (None, "") and reaction not in (None, ""):
        false_start = dec(reaction, name="Reaction time") < dec(limit)
    if false_start:
        return Outcome(status=config.get("false_start_status", "DQ"), status_reason="False start")
    if data.get("time") in (None, ""):
        return Outcome()
    taken = _timing(data["time"], config)
    breakdown = {"time": str(taken)}
    # Seconds added per counted penalty, e.g. one minute per missed shooting target.
    added = ZERO
    for item in config.get("penalties") or []:
        count = _count(data.get(item["key"]) or 0, name=item.get("label", item["key"]))
        if count:
            added += dec(item.get("seconds") or 0) * count
            breakdown[item["key"]] = count
    if added:
        breakdown["course_time"] = str(taken)
        taken += added
        breakdown["penalty_seconds"] = str(added)
        breakdown["time"] = str(taken)
    for item in config.get("record_fields") or []:
        if data.get(item) not in (None, ""):
            breakdown[item] = data[item]
    if reaction not in (None, ""):
        breakdown["reaction_time"] = str(dec(reaction, name="Reaction time"))
    for flag in ("record", "wind"):
        if data.get(flag) not in (None, ""):
            breakdown[flag] = data[flag]
    return Outcome(primary=taken, key=(taken,), breakdown=breakdown)


# --- measured_highest -----------------------------------------------------------------


def _attempt_value(value):
    if value in (None, "", "-", "x", "X", "foul", "pass"):
        return None
    return dec(value, name="Attempt")


def measured_highest(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    no_mark = config.get("no_mark_status", "NM")
    if config.get("mode") == "total_of_best":
        # The best of each lift added together; level totals go to whoever made the
        # total first (the lower attempt sequence number).
        lifts = data.get("lifts") or {}
        if not lifts:
            return Outcome()
        bests = {}
        for lift in config.get("lifts") or []:
            marks = [
                value
                for value in map(_attempt_value, lifts.get(lift["key"]) or [])
                if value is not None
            ]
            if not marks:
                attempted = bool(lifts.get(lift["key"]))
                if attempted:
                    return Outcome(
                        status=no_mark, status_reason=f"No successful {lift['label'].lower()}"
                    )
                return Outcome(breakdown={"waiting_for": lift["label"]})
            bests[lift["key"]] = max(marks)
        total = sum(bests.values(), ZERO)
        reached = data.get("total_reached_at")
        order = dec(reached, name="Order") if reached not in (None, "") else BIG
        return Outcome(
            primary=total,
            key=(-total, order),
            breakdown={
                "total": str(total),
                "best": {key: str(value) for key, value in bests.items()},
            },
        )
    if config.get("mode") == "heights":
        heights = data.get("heights") or {}
        if not heights:
            return Outcome()
        best = None
        failures_at = {}
        total_failures = 0
        for height, sequence in sorted(
            heights.items(), key=lambda item: dec(item[0], name="Height")
        ):
            sequence = str(sequence).lower()
            if any(mark not in "ox-" for mark in sequence):
                raise ResultDataError("Record each height as o (clear), x (fail) or - (pass).")
            failures = sequence.count("x")
            if "o" in sequence:
                best = dec(height)
                failures_at[best] = failures
                total_failures += failures
                continue
            if failures >= int(config.get("failures_to_eliminate", 3)):
                break
            total_failures += failures
        if best is None:
            return Outcome(status=no_mark, status_reason="No height cleared")
        # Countback: fewest failures at the last height cleared, then fewest in total
        # up to and including it.
        return Outcome(
            primary=best,
            key=(-best, failures_at[best], total_failures),
            breakdown={
                "best": str(best),
                "failures_at_best": failures_at[best],
                "total_failures": total_failures,
            },
        )

    attempts = data.get("attempts") or []
    if not attempts:
        return Outcome()
    limit = int(config.get("max_attempts", 6))
    if len(attempts) > limit:
        raise ResultDataError(f"At most {limit} attempts.")
    marks = sorted(
        (value for value in map(_attempt_value, attempts) if value is not None), reverse=True
    )
    if not marks:
        return Outcome(status=no_mark, status_reason="No valid attempt")
    # Best mark first; a tie goes to the better next-best mark, and so on.
    key = tuple([-mark for mark in marks] + [ZERO] * (limit - len(marks)))
    return Outcome(
        primary=marks[0],
        key=key,
        breakdown={
            "best": str(marks[0]),
            "attempts": [
                str(value) if value is not None else "x" for value in map(_attempt_value, attempts)
            ],
        },
    )


# --- judged_score -----------------------------------------------------------------------


def _attempt_score(attempt: dict, config: dict, index: int) -> tuple[Decimal, dict]:
    scores = [dec(score, name="Judge's score") for score in attempt.get("scores") or []]
    judges = config.get("judges")
    if judges and len(scores) != int(judges):
        raise ResultDataError(f"Attempt {index + 1} needs {judges} judges' scores.")
    top = config.get("max_score")
    if top is not None and any(score < 0 or score > dec(top) for score in scores):
        raise ResultDataError(f"Judges score from 0 to {top}.")
    step = config.get("score_step")
    if step and any((score / dec(step)) % 1 != 0 for score in scores):
        raise ResultDataError(f"Judges score in steps of {step}.")
    ordered = sorted(scores)
    low = int(config.get("drop_low", 0))
    high = int(config.get("drop_high", 0))
    kept = ordered[low : len(ordered) - high if high else None]
    if scores and not kept:
        raise ResultDataError("Too few judges' scores after dropping the highest and lowest.")
    base = sum(kept, ZERO)
    if config.get("combine") == "average" and kept:
        base = base / len(kept)
    if config.get("multiply_by_difficulty"):
        base = base * dec(attempt.get("difficulty") or 0, name="Degree of difficulty")
    if attempt.get("d") not in (None, ""):
        base += dec(attempt["d"], name="Difficulty score")
    # Measured parts of a judged score, e.g. time of flight, added as they are.
    for name, value in (attempt.get("extras") or {}).items():
        base += dec(value, name=name)
    # A measured mark turned into points: base points at the target mark, plus or
    # minus a fixed value per unit beyond or short of it (e.g. distance points).
    mark = config.get("mark_points")
    if mark and attempt.get(mark["field"]) not in (None, ""):
        measured = dec(attempt[mark["field"]], name=mark.get("label", mark["field"]))
        base += dec(mark["base"]) + (measured - dec(mark["target"])) * dec(mark["per_unit"])
    base -= dec(attempt.get("penalty") or 0, name="Penalty")
    value = _q(base, int(config.get("decimals", 2)))
    return value, {"score": str(value), "kept": [str(score) for score in kept]}


def judged_score(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    attempts = data.get("attempts") or []
    if not attempts:
        return Outcome()
    needed = config.get("attempts")
    if needed and len(attempts) < int(needed) and not config.get("count_best"):
        return Outcome(breakdown={"waiting_for": f"{int(needed) - len(attempts)} more attempt(s)"})
    values, detail = [], []
    for index, attempt in enumerate(attempts):
        value, row = _attempt_score(attempt, config, index)
        values.append(value)
        detail.append(row)
    best_n = config.get("count_best")
    counted = sorted(values, reverse=True)[: int(best_n)] if best_n else values
    total = sum(counted, ZERO)
    return Outcome(
        primary=total,
        key=(-total, -max(values)),
        breakdown={
            "total": str(total),
            "attempts": detail,
            "counted": [str(value) for value in counted],
        },
    )


# --- points_highest / points_lowest ---------------------------------------------------------


def _points(data: dict, config: dict, lower: bool) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    rounds = [dec(value, name="Points") for value in data.get("rounds") or []]
    if not rounds:
        return Outcome()
    needed = config.get("rounds")
    if needed and len(rounds) < int(needed):
        return Outcome(breakdown={"waiting_for": f"{int(needed) - len(rounds)} more round(s)"})
    double_last = bool(config.get("double_last"))
    series = rounds[:-1] if double_last else list(rounds)
    discard = int(config.get("discard_worst", 0))
    worst_first = sorted(series, reverse=lower)
    discarded = worst_first[:discard] if discard and len(series) > discard else []
    kept = list(series)
    for value in discarded:
        kept.remove(value)
    total = sum(kept, ZERO) + (rounds[-1] * 2 if double_last else ZERO)
    sign = 1 if lower else -1
    key: list = [sign * total]
    rule = config.get("tie_break", "countback")
    if rule == "last_round":
        key.append(sign * rounds[-1])
    elif rule == "countback":
        key.extend(sign * value for value in sorted(kept, reverse=not lower))
    for value in data.get("tiebreak") or []:
        key.append(-dec(value, name="Tie-break count"))
    return Outcome(
        primary=total,
        key=tuple(key),
        breakdown={"total": str(total), "discarded": [str(value) for value in discarded]},
    )


def points_highest(data: dict, config: dict) -> Outcome:
    return _points(data, config, lower=False)


def points_lowest(data: dict, config: dict) -> Outcome:
    return _points(data, config, lower=True)


# --- combat_decision -----------------------------------------------------------------------


def combat_decision(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    methods = {item["code"]: item["label"] for item in config.get("methods") or []}
    method = data.get("method")
    if method and methods and method not in methods:
        raise ResultDataError(f"Use one of the result codes: {', '.join(methods)}.")
    breakdown = {"method": method, "method_label": methods.get(method, "")} if method else {}
    score = dec(data.get("score") or 0, name="Score")
    # The bout is decided across both sides by `combat_context`.
    return Outcome(primary=score, key=(1,), breakdown=breakdown)


def combat_context(outcomes: dict, entries: dict, config: dict) -> None:
    contenders = [entry_id for entry_id, outcome in outcomes.items() if not outcome.status]
    winners = [entry_id for entry_id in contenders if (entries[entry_id] or {}).get("winner")]
    if len(winners) > 1:
        raise ResultDataError("Only one side can win a bout.")
    if not winners and len(contenders) == 2:
        first, second = contenders
        cards_a = (entries[first] or {}).get("cards") or []
        cards_b = (entries[second] or {}).get("cards") or []
        if config.get("decide_by") == "cards" and cards_a and len(cards_a) == len(cards_b):
            a_votes = sum(1 for x, y in zip(cards_a, cards_b, strict=True) if dec(x) > dec(y))
            b_votes = sum(1 for x, y in zip(cards_a, cards_b, strict=True) if dec(y) > dec(x))
            if a_votes != b_votes:
                winners = [first if a_votes > b_votes else second]
                outcomes[winners[0]].breakdown["decision"] = (
                    f"Judges {max(a_votes, b_votes)}-{min(a_votes, b_votes)}"
                )
        elif config.get("decide_by") == "score":
            if outcomes[first].primary != outcomes[second].primary:
                winners = [first if outcomes[first].primary > outcomes[second].primary else second]
    if len(contenders) == 1 and not winners:
        winners = contenders
    for entry_id in contenders:
        if not winners:
            outcomes[entry_id].key = None  # still level: golden score or a decision to come
        else:
            outcomes[entry_id].key = (0,) if entry_id in winners else (1,)


# --- multi_run_aggregate ------------------------------------------------------------------------


def multi_run_aggregate(data: dict, config: dict) -> Outcome:
    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    runs = data.get("runs") or []
    needed = int(config.get("runs", 1))
    penalties = {item["key"]: dec(item["seconds"]) for item in config.get("penalties") or []}
    values = []
    for index, run in enumerate(runs):
        if isinstance(run, dict):
            if run.get("time") in (None, ""):
                continue
            value = _timing(run["time"], config, name=f"Run {index + 1}")
            for key, seconds in penalties.items():
                value += seconds * _count(run.get(key), name=key)
        else:
            if run in (None, ""):
                continue
            value = _timing(run, config, name=f"Run {index + 1}")
        values.append(value)
    if config.get("aggregate") == "best":
        if not values:
            return Outcome()
        total = min(values)
    else:
        if len(values) < needed:
            return Outcome(breakdown={"runs": [str(value) for value in values]})
        total = sum(values[:needed], ZERO)
    return Outcome(
        primary=total,
        key=(total,),
        breakdown={"total": str(total), "runs": [str(value) for value in values]},
    )


# --- combined_events ----------------------------------------------------------------


def _event_points(spec: dict, mark) -> int:
    if mark in (None, "", "DNF", "NM", "DQ", "DNS"):
        return 0
    value = float(dec(mark, name=spec["label"]))
    if spec.get("unit") == "cm":
        value *= 100
    a, b, c = float(spec["a"]), float(spec["b"]), float(spec["c"])
    base = (b - value) if spec["kind"] == "track" else (value - b)
    if base <= 0:
        return 0
    return math.floor(a * base**c)


def combined_events(data: dict, config: dict) -> Outcome:
    from .tables import COMBINED_EVENT_TABLES

    status = str(data.get("status") or "")
    if status:
        return Outcome(status=status, status_reason=str(data.get("status_reason") or ""))
    events = config.get("events") or COMBINED_EVENT_TABLES.get(config.get("table") or "", [])
    if not events:
        raise ResultDataError("This result type needs a points table in the preset.")
    marks = data.get("marks") or {}
    if not marks:
        return Outcome()
    points = {spec["key"]: _event_points(spec, marks.get(spec["key"])) for spec in events}
    done = sum(1 for spec in events if spec["key"] in marks)
    total = sum(points.values())
    breakdown = {"total": total, "points": points, "events_done": done, "events": len(events)}
    if done < len(events) and not config.get("rank_partial", True):
        return Outcome(breakdown=breakdown)
    return Outcome(primary=Decimal(total), key=(-total, -max(points.values())), breakdown=breakdown)


def combined_events_context(outcomes: dict, entries: dict, config: dict) -> None:
    """Level on points: more events with higher points wins, then the best single event."""

    groups: dict = {}
    for entry_id, outcome in outcomes.items():
        if outcome.finished:
            groups.setdefault(outcome.key[0], []).append(entry_id)
    for members in groups.values():
        if len(members) < 2:
            continue
        for entry_id in members:
            mine = outcomes[entry_id].breakdown["points"]
            beaten = sum(
                1
                for other in members
                if other != entry_id
                for key, value in mine.items()
                if value > outcomes[other].breakdown["points"].get(key, 0)
            )
            total, best = outcomes[entry_id].key
            outcomes[entry_id].key = (total, -beaten, best)


# --- Registry and ranking ----------------------------------------------------------

CALCULATORS = {
    "finishing_order": finishing_order,
    "faults_then_time": faults_then_time,
    "penalty_total_lowest": penalty_total_lowest,
    "judged_percentage": judged_percentage,
    "timed_with_vet_gates": timed_with_vet_gates,
    "points_per_run": points_per_run,
    "timed_lowest": timed_lowest,
    "measured_highest": measured_highest,
    "judged_score": judged_score,
    "points_highest": points_highest,
    "points_lowest": points_lowest,
    "combat_decision": combat_decision,
    "multi_run_aggregate": multi_run_aggregate,
    "combined_events": combined_events,
}

CONTEXT = {
    "faults_then_time": faults_then_time_context,
    "timed_with_vet_gates": best_condition_context,
    "combat_decision": combat_context,
    "combined_events": combined_events_context,
}


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
