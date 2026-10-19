"""Resolve a match and rank a table from preset data.

This module does not name a sport. Structure, score values, and tie-breakers
arrive as data on the competition.
"""

from __future__ import annotations

from decimal import Decimal

from apps.fixtures.models import FixtureSide

ZERO = Decimal("0")
WIN = FixtureSide.Outcome.WIN
LOSS = FixtureSide.Outcome.LOSS
DRAW = FixtureSide.Outcome.DRAW


def expand_units(structure: list[dict] | None) -> list[dict]:
    """Turn nested unit blocks into the slots a scorer fills in, in order.

    A block with ``repeat`` keeps the same rules for later slots, so an extra
    period can be played until the scores separate.
    """

    slots: list[dict] = []
    seen: dict[str, int] = {}
    for block in structure or []:
        count = int(block.get("count") or block.get("best_of") or 1)
        if block.get("repeat"):
            count = max(count, 3)
        for _offset in range(max(count, 1)):
            name = str(block.get("unit") or "unit")
            seen[name] = seen.get(name, 0) + 1
            slots.append(
                {
                    "index": len(slots),
                    "unit": name,
                    "label": f"{name.replace('_', ' ')} {seen[name]}",
                    "minutes": block.get("minutes"),
                    "affects_total": bool(block.get("affects_total", True)),
                    "resolves_draw": bool(block.get("resolves_draw", False)),
                    "first_to": block.get("first_to"),
                    "win_by": int(block.get("win_by") or 1),
                    "cap": block.get("cap"),
                    "tiebreak_at": block.get("tiebreak_at"),
                    "tiebreak_first_to": block.get("tiebreak_first_to"),
                    "tiebreak_win_by": int(block.get("tiebreak_win_by") or 2),
                    "start": block.get("start"),
                    "illegal_remaining": list(block.get("illegal_remaining") or []),
                    "finish": block.get("finish"),
                    "tied_winner": block.get("tied_winner"),
                    "target": block.get("target"),
                    "better": block.get("better") or "higher",
                }
            )
    return slots


def score_rules(settings: dict | None) -> dict[str, dict]:
    return {item["key"]: item for item in (settings or {}).get("score_types") or []}


def race_target(structure: list[dict] | None) -> int | None:
    """How many units a side must win. ``best_of: 5`` means first to 3."""

    target = None
    for block in structure or []:
        if block.get("race_to"):
            target = int(block["race_to"])
        elif block.get("best_of"):
            target = int(block["best_of"]) // 2 + 1
    return target


def match_target(structure: list[dict] | None, settings: dict | None) -> Decimal | None:
    if settings and settings.get("target") is not None:
        return Decimal(str(settings["target"]))
    for block in structure or []:
        if block.get("target") is not None:
            return Decimal(str(block["target"]))
    return None


def _event_amount(event) -> Decimal:
    category = event.scoring_category
    if category is None or not category.affects_score:
        return ZERO
    return Decimal(event.quantity) * Decimal(category.points)


def _quantity_allowed(rule: dict, quantity: Decimal) -> bool:
    if rule.get("minimum") is not None and quantity < Decimal(str(rule["minimum"])):
        return False
    if rule.get("maximum") is not None and quantity > Decimal(str(rule["maximum"])):
        return False
    return True


def _slot_for(index: int | None, slots: list[dict]) -> dict | None:
    if index is None:
        return None
    for slot in slots:
        if slot["index"] == index:
            return slot
    return None


def split_scores(sides, events, slots: list[dict], settings: dict | None = None) -> tuple[dict, dict, dict, dict]:
    """Match total, draw-decider totals by slot, per-slot totals, and tiebreak totals."""

    rules = score_rules(settings)
    side_ids = [side.id for side in sides]
    match = {side_id: ZERO for side_id in side_ids}
    per_unit = {side_id: [ZERO] * len(slots) for side_id in side_ids}
    tiebreak = {side_id: [ZERO] * len(slots) for side_id in side_ids}
    decider_by_slot: dict[int, dict] = {}
    ordered = list(events)
    countable = []
    for event in ordered:
        if event.scoring_category is None:
            continue
        rule = rules.get(event.scoring_category.code, {})
        if not _quantity_allowed(rule, Decimal(event.quantity)):
            continue
        # A fill ball can be the source of a bonus without joining the match total.
        if event.scoring_category.affects_score or rule.get("role") == "fill":
            countable.append(event)
    countable_ids = {id(event) for event in countable}
    bonus_extra: dict = {}
    for index, event in enumerate(countable):
        rule = rules.get(event.scoring_category.code, {})
        follow = int(rule.get("bonus_next") or 0)
        if follow:
            later = [other for other in countable[index + 1 :] if other.side_id == event.side_id]
            bonus_extra[id(event)] = sum(
                (_event_amount(other) for other in later[:follow]),
                ZERO,
            )

    unit_factor: dict[tuple, Decimal] = {}
    for event in ordered:
        if event.scoring_category is None or event.unit_index is None:
            continue
        rule = rules.get(event.scoring_category.code, {})
        if rule.get("multiplies_unit"):
            unit_factor[(event.side_id, event.unit_index)] = Decimal(str(rule["multiplies_unit"]))

    best_mode = any(rule.get("aggregate") == "best" for rule in rules.values())
    best_values: dict = {side_id: [] for side_id in side_ids}

    for event in ordered:
        if event.side_id not in match or event.scoring_category is None:
            continue
        if id(event) not in countable_ids:
            continue
        rule = rules.get(event.scoring_category.code, {})
        if rule.get("role") in {"no_result", "fill"}:
            continue
        amount = _event_amount(event) + bonus_extra.get(id(event), ZERO)
        slot = _slot_for(event.unit_index, slots)
        if slot is not None and slot.get("start") is not None and rule.get("role") not in {"tiebreak", "decider"}:
            current = per_unit[event.side_id][slot["index"]]
            remaining = Decimal(str(slot["start"])) - (current + amount)
            illegal = {Decimal(str(value)) for value in slot.get("illegal_remaining") or []}
            if remaining < 0 or remaining in illegal:
                continue
            if remaining == 0 and slot.get("finish") == "marked" and rule.get("role") != "checkout":
                continue
        if slot is not None:
            amount *= unit_factor.get((event.side_id, slot["index"]), Decimal("1"))
        recipients = [event.side_id]
        if rule.get("awards") == "opponent":
            recipients = [side_id for side_id in side_ids if side_id != event.side_id]
        role = rule.get("role")
        for side_id in recipients:
            if role in {"tiebreak", "decider"} and slot is not None:
                tiebreak[side_id][slot["index"]] += amount
                continue
            if best_mode and rule.get("aggregate") == "best":
                best_values[side_id].append((amount, rule.get("better") or "higher"))
                continue
            if slot is None:
                match[side_id] += amount
                continue
            per_unit[side_id][slot["index"]] += amount
            if slot["affects_total"]:
                match[side_id] += amount
            if slot["resolves_draw"]:
                bucket = decider_by_slot.setdefault(
                    slot["index"], {item: ZERO for item in side_ids}
                )
                bucket[side_id] += amount

    if best_mode:
        for side_id, values in best_values.items():
            if not values:
                continue
            lower = values[0][1] == "lower"
            ordered_values = sorted((item[0] for item in values), reverse=not lower)
            match[side_id] = ordered_values[0]
    return match, decider_by_slot, per_unit, tiebreak


def _best_ids(scores: dict, win_condition: str) -> list:
    if not scores:
        return []
    if win_condition in {"lowest_total", "count_down_to_zero"}:
        best = min(scores.values())
    else:
        best = max(scores.values())
    return [key for key, value in scores.items() if value == best]


def _label(side_ids, leaders: list) -> dict:
    if len(leaders) == 1:
        winner = leaders[0]
        return {side_id: WIN if side_id == winner else LOSS for side_id in side_ids}
    return {side_id: DRAW if side_id in leaders else LOSS for side_id in side_ids}


def _sequential_decider(
    leaders: list,
    decider_by_slot: dict,
    slots: list[dict] | None = None,
    home_of: dict | None = None,
) -> list:
    """Use each played decider slot in order. An unplayed slot is all zeroes.

    A slot can name ``tied_winner`` as ``home`` or ``away`` when a level
    decider still has to produce one winner.
    """

    slot_by_index = {slot["index"]: slot for slot in slots or []}
    for index in sorted(decider_by_slot):
        scores = {side_id: decider_by_slot[index].get(side_id, ZERO) for side_id in leaders}
        if not any(scores.values()):
            continue
        decided = _best_ids(scores, "highest_total")
        if len(decided) == 1:
            return decided
        preference = (slot_by_index.get(index) or {}).get("tied_winner")
        if preference in {"home", "away"} and home_of:
            wanted_home = preference == "home"
            chosen = [
                side_id
                for side_id in decided
                if bool(home_of.get(side_id)) is wanted_home
            ]
            if len(chosen) == 1:
                return chosen
    return leaders


def unit_winner(slot: dict, totals: dict, tiebreaks: dict | None = None) -> object | None:
    """The side that won one unit, or None when the unit was not decided."""

    if not totals or all(value == 0 for value in totals.values()):
        if not tiebreaks or all(value == 0 for value in tiebreaks.values()):
            return None
    start = slot.get("start")
    if start is not None:
        target = Decimal(str(start))
        finished = [side_id for side_id, total in totals.items() if total == target]
        return finished[0] if len(finished) == 1 else None

    first = slot.get("first_to")
    if first is not None:
        first = Decimal(str(first))
        win_by = Decimal(str(slot.get("win_by") or 1))
        cap = slot.get("cap")
        cap_value = Decimal(str(cap)) if cap is not None else None
        tie_at = slot.get("tiebreak_at")
        if tie_at is not None and tiebreaks is not None:
            mark = Decimal(str(tie_at))
            if all(total >= mark for total in totals.values()) and any(tiebreaks.values()):
                return _threshold_winner(
                    tiebreaks,
                    Decimal(str(slot.get("tiebreak_first_to") or 1)),
                    Decimal(str(slot.get("tiebreak_win_by") or 2)),
                    None,
                )
        return _threshold_winner(totals, first, win_by, cap_value)

    condition = "lowest_total" if slot.get("better") == "lower" else "highest_total"
    leaders = _best_ids(totals, condition)
    return leaders[0] if len(leaders) == 1 else None


def _threshold_winner(totals: dict, first: Decimal, win_by: Decimal, cap: Decimal | None):
    if not totals:
        return None
    ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    leader, best = ordered[0]
    second = ordered[1][1] if len(ordered) > 1 else ZERO
    if cap is not None and best >= cap and best > second:
        return leader
    if best >= first and best - second >= win_by:
        return leader
    return None


def unit_table(side_ids: list, slots: list[dict], per_unit: dict, tiebreak: dict) -> dict[int, object | None]:
    winners = {}
    for slot in slots:
        if slot.get("resolves_draw"):
            continue
        totals = {side_id: per_unit[side_id][slot["index"]] for side_id in side_ids}
        breaks = {side_id: tiebreak[side_id][slot["index"]] for side_id in side_ids}
        winners[slot["index"]] = unit_winner(slot, totals, breaks)
    return winners


def uses_unit_wins(settings: dict, slots: list[dict]) -> bool:
    condition = settings.get("win_condition")
    if condition == "most_units_won":
        return True
    if condition == "count_down_to_zero" and any(slot.get("start") is not None for slot in slots):
        return True
    return False


def decide_outcomes(
    side_ids: list,
    match: dict,
    decider_by_slot: dict,
    *,
    win_condition: str,
    draw_allowed: bool,
    target: Decimal | None = None,
    unit_wins: dict | None = None,
    race: int | None = None,
    slots: list[dict] | None = None,
    home_of: dict | None = None,
) -> dict:
    """Map each side id to win, loss, draw, or pending."""

    pending = FixtureSide.Outcome.PENDING
    if unit_wins is not None:
        counts = {side_id: 0 for side_id in side_ids}
        for winner in unit_wins.values():
            if winner in counts:
                counts[winner] += 1
        if race is not None:
            reached = [side_id for side_id, count in counts.items() if count >= race]
            if len(reached) == 1:
                return _label(side_ids, reached)
        leaders = _best_ids(counts, "highest_total")
        if len(leaders) == 1:
            return _label(side_ids, leaders)
        if draw_allowed:
            return _label(side_ids, leaders)
        return {side_id: pending for side_id in side_ids}

    if win_condition == "first_to_target" and target is not None:
        reached = [side_id for side_id in side_ids if match[side_id] >= target]
        if len(reached) == 1:
            return _label(side_ids, reached)
        if len(reached) > 1:
            return _label(side_ids, _best_ids({side_id: match[side_id] for side_id in reached}, "highest_total"))
        if draw_allowed:
            return {side_id: DRAW for side_id in side_ids}
        return {side_id: pending for side_id in side_ids}

    leaders = _best_ids({side_id: match[side_id] for side_id in side_ids}, win_condition)
    if len(leaders) <= 1 or draw_allowed:
        return _label(side_ids, leaders)

    decided = _sequential_decider(leaders, decider_by_slot, slots, home_of)
    if len(decided) == 1:
        return _label(side_ids, decided)
    return {side_id: pending for side_id in side_ids}


def draws_are_allowed(
    settings: dict,
    competition_format: str,
    *,
    allow_draws: bool | None = None,
) -> bool:
    """Whether a level score can stand.

    Knockouts always need a winner. A preset can forbid draws, and so can the
    competition's points policy (the checkbox on a custom competition).
    """

    if competition_format == "knockout":
        return False
    if not bool(settings.get("draw_allowed", True)):
        return False
    if allow_draws is False:
        return False
    return True


def _apply_bonuses(match: dict, sides, events, settings: dict) -> None:
    """Add a threshold award once the named categories reach it inside this contest."""

    bonuses = (settings or {}).get("bonuses") or []
    if not bonuses:
        return
    points: dict = {side.id: {} for side in sides}
    for event in events:
        if event.side_id not in points or event.scoring_category is None:
            continue
        if not event.scoring_category.affects_score:
            continue
        code = event.scoring_category.code
        points[event.side_id][code] = points[event.side_id].get(code, ZERO) + _event_amount(event)
    for bonus in bonuses:
        threshold = Decimal(str(bonus.get("when_at_least") or 0))
        award = Decimal(str(bonus.get("award") or 0))
        for side in sides:
            total = sum(
                (points[side.id].get(code, ZERO) for code in bonus.get("categories") or []),
                ZERO,
            )
            if total >= threshold:
                match[side.id] += award


def settle_fixture(fixture) -> None:
    """Write side totals and outcomes from the events and the preset structure."""

    settings = fixture.competition.settings_json or {}
    structure = settings.get("match_structure") or []
    if not structure and not settings.get("win_condition"):
        return

    sides = list(fixture.sides.all())
    events = list(fixture.events.select_related("scoring_category"))
    slots = expand_units(structure)
    match, decider, per_unit, tiebreak = split_scores(sides, events, slots, settings)
    win_condition = settings.get("win_condition") or "highest_total"
    rules = score_rules(settings)
    event_directions = {
        (rules.get(event.scoring_category.code, {}).get("better") or "higher")
        for event in events
        if event.scoring_category is not None
        and rules.get(event.scoring_category.code, {}).get("aggregate") == "best"
    }
    if event_directions == {"lower"}:
        win_condition = "lowest_total"
    elif event_directions == {"higher"}:
        win_condition = "highest_total"
    side_ids = [side.id for side in sides]
    unit_wins = unit_table(side_ids, slots, per_unit, tiebreak) if uses_unit_wins(settings, slots) else None
    if unit_wins is not None:
        for slot in slots:
            if slot.get("tiebreak_at") is None:
                continue
            winner = unit_wins.get(slot["index"])
            if winner is not None and any(tiebreak[side_id][slot["index"]] for side_id in side_ids):
                match[winner] += 1
    _apply_bonuses(match, sides, events, settings)
    from apps.competitions.models import PointsPolicy

    policy = (
        PointsPolicy.objects.filter(competition_id=fixture.competition_id)
        .only("allow_draws")
        .first()
    )
    outcomes = decide_outcomes(
        side_ids,
        match,
        decider,
        win_condition=win_condition,
        draw_allowed=draws_are_allowed(
            settings,
            fixture.competition.format,
            allow_draws=None if policy is None else policy.allow_draws,
        ),
        target=match_target(structure, settings),
        unit_wins=unit_wins,
        race=race_target(structure),
        slots=slots,
        home_of={side.id: side.is_home for side in sides},
    )
    for side in sides:
        side.score = match.get(side.id, ZERO)
        side.outcome = outcomes.get(side.id, DRAW)
        side.save(update_fields=["score", "outcome", "updated_at"])


def round_winners(fixtures) -> list | None:
    """Participant ids that advance, in fixture order. None if any match is unresolved."""

    winners = []
    for fixture in fixtures:
        advancing = [
            side.participant_id
            for side in fixture.sides.all()
            if side.outcome == WIN
        ]
        if len(advancing) != 1:
            return None
        winners.append(advancing[0])
    return winners


def pair_advancers(participant_ids: list) -> tuple[list[tuple], object | None]:
    """Pair a round's winners into the next round. A leftover id is a bye."""

    pairs = list(zip(participant_ids[0::2], participant_ids[1::2]))
    bye = participant_ids[-1] if len(participant_ids) % 2 else None
    return pairs, bye
