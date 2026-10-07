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


def knockout_pairs(participants: list[Participant]) -> list[tuple[Participant, Participant]]:
    """Seed a single-elimination first round, pairing strongest against weakest."""

    ordered = sorted(participants, key=lambda p: (p.seed is None, p.seed or 0, p.name))
    size = 2 ** math.ceil(math.log2(len(ordered))) if ordered else 0
    padded: list[Participant | None] = [*ordered, *([None] * (size - len(ordered)))]

    pairs = []
    for index in range(size // 2):
        home, away = padded[index], padded[size - 1 - index]
        if home is not None and away is not None:
            pairs.append((home, away))
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

    pairs = knockout_pairs(participants)
    slots = _slot_datetimes(options, max(len(pairs), 1))
    created: list[Fixture] = []

    for index, (home, away) in enumerate(pairs):
        kickoff = None
        if slots:
            kickoff = slots[0] + timedelta(minutes=options.minutes_between_fixtures * index)

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

    for side in winners:
        ScoreEvent.objects.create(
            fixture=fixture,
            side=side,
            scoring_category=category,
            quantity=1,
            note=note,
            recorded_by=user,
        )
    fixture.recalculate_scores()
    refresh_standings(competition)
    return fixture
