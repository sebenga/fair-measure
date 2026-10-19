"""Fixture generation: turn a list of participants into a playable schedule."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from apps.competitions.models import Competition, Participant, Stage

from .models import Fixture, FixtureSide


@dataclass(slots=True)
class ScheduleOptions:
    starts_on: date
    weekdays: list[int]  # 0 = Monday
    kickoff: time
    minutes_between_fixtures: int = 0
    double_round: bool = False  # home and away
    location: str = ""
    stage: Stage | None = None


Pairing = tuple[Participant, Participant]


def round_robin_rounds(participants: list[Participant]) -> list[list[Pairing]]:
    """Pair every participant with every other exactly once (the circle method).

    An odd number of entrants gets a `None` bye slot, which is dropped from the
    output so nobody is scheduled against nothing.
    """

    entrants: list[Participant | None] = list(participants)
    if len(entrants) < 2:
        return []
    if len(entrants) % 2:
        entrants.append(None)

    count = len(entrants)
    rounds: list[list[tuple[Participant, Participant]]] = []

    for round_index in range(count - 1):
        pairs: list[tuple[Participant, Participant]] = []
        for slot in range(count // 2):
            home = entrants[slot]
            away = entrants[count - 1 - slot]
            if home is None or away is None:
                continue
            # Alternate who is nominally at home so the fixture list stays balanced.
            pairs.append((home, away) if round_index % 2 == 0 else (away, home))
        rounds.append(pairs)
        # Rotate everything except the first entrant.
        entrants = [entrants[0], entrants[-1], *entrants[1:-1]]

    return rounds


BRACKET_BYE_NOTE = "bracket-bye"


def _bracket_seed_order(size: int) -> list[int]:
    """1-based seed numbers in first-round order, so byes sit next to their half."""

    order = [1]
    while len(order) < size:
        limit = len(order) * 2 + 1
        order = [seed for place in order for seed in (place, limit - place)]
    return order


def knockout_bracket(
    participants: list[Participant],
) -> list[tuple[Participant | None, Participant | None]]:
    """First-round slots in bracket order. A missing side is a bye."""

    ordered = sorted(participants, key=lambda p: (p.seed is None, p.seed or 0, p.name))
    if len(ordered) < 2:
        return []
    size = 2 ** math.ceil(math.log2(len(ordered)))
    placed = {number: person for number, person in enumerate(ordered, start=1)}
    seats = [placed.get(number) for number in _bracket_seed_order(size)]
    return [(seats[index], seats[index + 1]) for index in range(0, size, 2)]


def knockout_slots(
    participants: list[Participant],
) -> tuple[list[tuple[Participant, Participant]], list[Participant]]:
    """Seed a first round. A spare entrant receives a bye instead of disappearing."""

    pairs: list[tuple[Participant, Participant]] = []
    byes: list[Participant] = []
    for home, away in knockout_bracket(participants):
        if home is not None and away is not None:
            pairs.append((home, away))
        elif home is not None:
            byes.append(home)
        elif away is not None:
            byes.append(away)
    return pairs, byes


def knockout_pairs(participants: list[Participant]) -> list[tuple[Participant, Participant]]:
    """The played ties in a seeded first round. Byes are returned by knockout_slots."""

    pairs, _byes = knockout_slots(participants)
    return pairs


def _slot_datetimes(options: ScheduleOptions, count: int) -> list[datetime]:
    """Produce `count` kickoff datetimes on the competition's allowed weekdays."""

    weekdays = sorted(set(options.weekdays)) or list(range(7))
    tz = timezone.get_current_timezone()
    slots: list[datetime] = []

    cursor = options.starts_on
    guard = 0
    while len(slots) < count and guard < 4000:
        guard += 1
        if cursor.weekday() in weekdays:
            naive = datetime.combine(cursor, options.kickoff)
            slots.append(timezone.make_aware(naive, tz))
        cursor += timedelta(days=1)

    return slots


@transaction.atomic
def generate_round_robin(
    competition: Competition, participants: list[Participant], options: ScheduleOptions
) -> list[Fixture]:
    """Create a full round-robin schedule, one round per available date slot."""

    rounds = round_robin_rounds(participants)
    if options.double_round:
        # The reverse leg swaps home and away.
        rounds += [[(away, home) for home, away in pairs] for pairs in rounds]

    slots = _slot_datetimes(options, len(rounds))
    created: list[Fixture] = []

    for round_index, pairs in enumerate(rounds):
        round_start = slots[round_index] if round_index < len(slots) else None
        for pair_index, (home, away) in enumerate(pairs):
            kickoff = None
            if round_start is not None:
                kickoff = round_start + timedelta(
                    minutes=options.minutes_between_fixtures * pair_index
                )

            fixture = Fixture.objects.create(
                competition=competition,
                stage=options.stage,
                round_number=round_index + 1,
                label=f"Round {round_index + 1}",
                scheduled_at=kickoff,
                location=options.location,
            )
            FixtureSide.objects.bulk_create(
                [
                    FixtureSide(fixture=fixture, participant=home, position=0, is_home=True),
                    FixtureSide(fixture=fixture, participant=away, position=1, is_home=False),
                ]
            )
            created.append(fixture)

    return created


@transaction.atomic
def generate_knockout(
    competition: Competition, participants: list[Participant], options: ScheduleOptions
) -> list[Fixture]:
    """Create the first round of a single-elimination bracket."""

    bracket = knockout_bracket(participants)
    slots = _slot_datetimes(options, 1)
    created: list[Fixture] = []
    base = slots[0] if slots else None

    for index, (home, away) in enumerate(bracket):
        kickoff = None
        if base is not None:
            kickoff = base + timedelta(minutes=options.minutes_between_fixtures * index)
        if home is not None and away is not None:
            fixture = Fixture.objects.create(
                competition=competition,
                stage=options.stage,
                round_number=1,
                label=f"Round 1 — match {index + 1}",
                scheduled_at=kickoff,
                location=options.location,
            )
            FixtureSide.objects.bulk_create(
                [
                    FixtureSide(fixture=fixture, participant=home, position=0, is_home=True),
                    FixtureSide(fixture=fixture, participant=away, position=1, is_home=False),
                ]
            )
            created.append(fixture)
            continue
        participant = home or away
        if participant is None:
            continue
        fixture = Fixture.objects.create(
            competition=competition,
            stage=options.stage,
            round_number=1,
            label="Bye",
            notes=BRACKET_BYE_NOTE,
            status=Fixture.Status.COMPLETED,
            completed_at=timezone.now(),
            scheduled_at=kickoff,
            location=options.location,
        )
        FixtureSide.objects.create(
            fixture=fixture,
            participant=participant,
            position=0,
            is_home=True,
            outcome=FixtureSide.Outcome.WIN,
        )
        created.append(fixture)

    return created


def award_criterion(*, competition, participant, category, quantity, note, user):
    """Log one scoring criterion against one participant and refresh the table."""

    from django.utils import timezone

    from apps.standings.services import refresh_standings

    from .models import FixtureSide, ScoreEvent

    fixture = Fixture.objects.create(
        competition=competition,
        status=Fixture.Status.COMPLETED,
        label=category.name,
        completed_at=timezone.now(),
        created_by=user,
        notes=note,
    )
    side = FixtureSide.objects.create(
        fixture=fixture, participant=participant, position=0, is_home=True
    )
    event = ScoreEvent.objects.create(
        fixture=fixture,
        side=side,
        scoring_category=category,
        quantity=quantity,
        note=note,
        recorded_by=user,
    )
    fixture.recalculate_scores()
    refresh_standings(competition)
    return event


def _result_events(competition, winners, category, outcome):
    """Events that make a quick result satisfy the competition's win condition."""

    from decimal import Decimal

    from apps.competitions.engine import expand_units, match_target, race_target

    if outcome == "draw" or len(winners) != 1:
        return [(side, category, Decimal(1), None) for side in winners]

    settings = competition.settings_json or {}
    structure = settings.get("match_structure") or []
    condition = settings.get("win_condition") or "highest_total"
    slots = [slot for slot in expand_units(structure) if not slot.get("resolves_draw")]
    by_code = {item.code: item for item in competition.scoring_categories.all()}

    def with_role(role: str):
        for item in settings.get("score_types") or []:
            if item.get("role") == role and item.get("key") in by_code:
                return by_code[item["key"]]
        return None

    winner = winners[0]
    if condition == "most_units_won":
        race = race_target(structure) or 1
        playable = slots or [{"index": None, "first_to": 1}]
        rows = []
        for index in range(race):
            slot = playable[min(index, len(playable) - 1)]
            rows.append(
                (winner, category, Decimal(str(slot.get("first_to") or 1)), slot.get("index"))
            )
        return rows
    if condition == "count_down_to_zero":
        checkout = with_role("checkout") or category
        race = race_target(structure) or 1
        playable = [slot for slot in slots if slot.get("start") is not None] or slots or [
            {"index": None, "start": 1}
        ]
        rows = []
        for index in range(race):
            slot = playable[min(index, len(playable) - 1)]
            rows.append(
                (winner, checkout, Decimal(str(slot.get("start") or 1)), slot.get("index"))
            )
        return rows
    if condition == "first_to_target":
        target = match_target(structure, settings) or Decimal(1)
        unit_index = slots[0]["index"] if slots else None
        return [(winner, category, target, unit_index)]
    return [(winner, category, Decimal(1), None)]


def record_result(*, competition, home, away, outcome, note, user):
    """Record a completed fixture decided by win, draw, or loss."""

    from django.utils import timezone

    from apps.standings.services import refresh_standings

    from .models import FixtureSide, ScoreEvent

    category = (
        competition.scoring_categories.filter(affects_score=True)
        .order_by("display_order", "name")
        .first()
    )
    if category is None:
        raise ValueError("Define a scoring criterion that counts toward the score first.")

    if outcome == "draw":
        from apps.competitions.engine import draws_are_allowed
        from apps.competitions.models import PointsPolicy

        policy = PointsPolicy.objects.filter(competition=competition).only("allow_draws").first()
        if not draws_are_allowed(
            competition.settings_json or {},
            competition.format,
            allow_draws=None if policy is None else policy.allow_draws,
        ):
            raise ValueError("This competition does not allow draws.")

    fixture = Fixture.objects.create(
        competition=competition,
        status=Fixture.Status.COMPLETED,
        label=f"{home.name} v {away.name}",
        completed_at=timezone.now(),
        created_by=user,
        notes=note,
    )
    home_side = FixtureSide.objects.create(
        fixture=fixture, participant=home, position=0, is_home=True
    )
    away_side = FixtureSide.objects.create(
        fixture=fixture, participant=away, position=1, is_home=False
    )

    if outcome == "draw":
        winners = [home_side, away_side]
    elif outcome == "home":
        winners = [home_side]
    elif outcome == "away":
        winners = [away_side]
    else:
        raise ValueError("Outcome must be home, away, or draw.")

    for side, scored_as, quantity, unit_index in _result_events(
        competition, winners, category, outcome
    ):
        ScoreEvent.objects.create(
            fixture=fixture,
            side=side,
            scoring_category=scored_as,
            quantity=quantity,
            unit_index=unit_index,
            note=note,
            recorded_by=user,
        )
    fixture.recalculate_scores()
    refresh_standings(competition)
    return fixture
