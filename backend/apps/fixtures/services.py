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
    cup_every_league_rounds: int = 0


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


def _bracket_order(size: int) -> list[int]:
    """Standard seed positions: 1 v size, with seeds 1 and 2 only meeting in the final."""

    order = [1]
    while len(order) < size:
        total = len(order) * 2 + 1
        order = [value for seed in order for value in (seed, total - seed)]
    return order


def knockout_slots(
    participants: list[Participant],
) -> list[tuple[Participant, Participant | None]]:
    """Seed a single-elimination first round in bracket order.

    The top seeds get a bye (the second slot is `None`) when the field is not a
    power of two, so every entrant stays in the bracket.
    """

    ordered = sorted(participants, key=lambda p: (p.seed is None, p.seed or 0, p.name))
    size = 2 ** math.ceil(math.log2(len(ordered))) if len(ordered) > 1 else 0
    order = _bracket_order(size) if size else []
    seeded: list[Participant | None] = [
        ordered[seed - 1] if seed <= len(ordered) else None for seed in order
    ]
    slots: list[tuple[Participant, Participant | None]] = []
    for index in range(0, len(seeded), 2):
        home, away = seeded[index], seeded[index + 1]
        if home is None:
            home, away = away, home
        if home is not None:
            slots.append((home, away))
    return slots


def knockout_pairs(participants: list[Participant]) -> list[tuple[Participant, Participant]]:
    """The first-round matches that are actually played (byes excluded)."""

    return [(home, away) for home, away in knockout_slots(participants) if away is not None]


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


def knockout_round_count(team_count: int) -> int:
    """How many knockout rounds a field of this size needs, including byes."""

    if team_count < 2:
        return 0
    size = 1
    while size < team_count:
        size *= 2
    return int(math.log2(size))


def interleave_match_days(league_rounds: int, cup_rounds: int, every: int) -> list[str]:
    """League match days, with a cup day after every `every` league days."""

    every = max(1, every)
    sequence: list[str] = []
    league_left = league_rounds
    cup_left = cup_rounds
    since_cup = 0
    while league_left or cup_left:
        if league_left and (since_cup < every or not cup_left):
            sequence.append("league")
            league_left -= 1
            since_cup += 1
        elif cup_left:
            sequence.append("cup")
            cup_left -= 1
            since_cup = 0
        else:
            break
    return sequence


def league_and_cup_stages(competition: Competition) -> tuple[Stage, Stage]:
    from apps.competitions.cups import ensure_league_and_cup_stages

    league, cups = ensure_league_and_cup_stages(competition)
    return league, cups[0]


def _write_pair_round(
    *,
    competition: Competition,
    stage: Stage | None,
    pairs: list[tuple[Participant, Participant | None]],
    round_number: int,
    label: str,
    kickoff: datetime | None,
    options: ScheduleOptions,
) -> list[Fixture]:
    created: list[Fixture] = []
    played = 0
    for index, (home, away) in enumerate(pairs):
        if away is None:
            bye = Fixture.objects.create(
                competition=competition,
                stage=stage,
                round_number=round_number,
                label=f"{label} — match {index + 1} (bye)",
                status=Fixture.Status.COMPLETED,
                completed_at=timezone.now(),
            )
            side = FixtureSide.objects.create(
                fixture=bye, participant=home, position=0, is_home=True
            )
            side.outcome = FixtureSide.Outcome.WIN
            side.save(update_fields=["outcome", "updated_at"])
            created.append(bye)
            continue
        when = None
        if kickoff is not None:
            when = kickoff + timedelta(minutes=options.minutes_between_fixtures * played)
        played += 1
        fixture = Fixture.objects.create(
            competition=competition,
            stage=stage,
            round_number=round_number,
            label=f"{label} — match {index + 1}",
            scheduled_at=when,
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
def generate_league_and_knockout(
    competition: Competition, participants: list[Participant], options: ScheduleOptions
) -> list[Fixture]:
    """League rounds with a cup match day after every N league match days."""

    from apps.competitions.serializers import cup_every_league_rounds

    league_rounds = round_robin_rounds(participants)
    if options.double_round:
        league_rounds += [[(away, home) for home, away in pairs] for pairs in league_rounds]
    if not league_rounds:
        return []

    every = options.cup_every_league_rounds or cup_every_league_rounds(competition)
    cup_rounds = knockout_round_count(len(participants))
    sequence = interleave_match_days(len(league_rounds), cup_rounds, every)
    slots = _slot_datetimes(options, len(sequence))
    league_stage, cup_stage = league_and_cup_stages(competition)

    created: list[Fixture] = []
    league_index = 0
    cup_index = 0
    reserved_cup: list[str] = []
    first_cup_pairs = knockout_slots(participants)
    cup_label = f"{cup_stage.name} round 1"

    for step, kind in enumerate(sequence):
        kickoff = slots[step] if step < len(slots) else None
        if kind == "league":
            pairs = [(home, away) for home, away in league_rounds[league_index]]
            created.extend(
                _write_pair_round(
                    competition=competition,
                    stage=league_stage,
                    pairs=[(home, away) for home, away in pairs],
                    round_number=league_index + 1,
                    label=f"League round {league_index + 1}",
                    kickoff=kickoff,
                    options=options,
                )
            )
            league_index += 1
            continue
        if cup_index == 0:
            created.extend(
                _write_pair_round(
                    competition=competition,
                    stage=cup_stage,
                    pairs=first_cup_pairs,
                    round_number=1,
                    label=cup_label,
                    kickoff=kickoff,
                    options=options,
                )
            )
        elif kickoff is not None:
            reserved_cup.append(kickoff.isoformat())
        cup_index += 1

    settings = dict(competition.settings_json or {})
    settings["cup_every_league_rounds"] = every
    settings["cup_slot_datetimes"] = reserved_cup
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])
    return created


@transaction.atomic
def generate_knockout(
    competition: Competition, participants: list[Participant], options: ScheduleOptions
) -> list[Fixture]:
    """Create the first round of a single-elimination bracket."""

    pairs = knockout_slots(participants)
    slots = _slot_datetimes(options, max(len(pairs), 1))
    created: list[Fixture] = []
    played = 0

    for index, (home, away) in enumerate(pairs):
        if away is None:
            # A bye: the top seed goes straight through, recorded so the bracket
            # keeps its position and "advance" carries them into round 2.
            bye = Fixture.objects.create(
                competition=competition,
                stage=options.stage,
                round_number=1,
                label=f"Round 1 — match {index + 1} (bye)",
                status=Fixture.Status.COMPLETED,
                completed_at=timezone.now(),
            )
            side = FixtureSide.objects.create(
                fixture=bye, participant=home, position=0, is_home=True
            )
            side.outcome = FixtureSide.Outcome.WIN
            side.save(update_fields=["outcome", "updated_at"])
            created.append(bye)
            continue

        kickoff = None
        if slots:
            kickoff = slots[0] + timedelta(minutes=options.minutes_between_fixtures * played)
        played += 1

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


@transaction.atomic
def start_named_cup(competition: Competition, stage: Stage, participants: list[Participant]) -> list[Fixture]:
    """Open the next cup after the current one has finished."""

    from apps.competitions.cups import assert_cups_are_sequential, cup_is_complete

    if stage.kind != Stage.Kind.KNOCKOUT or stage.competition_id != competition.id:
        raise ValueError("Choose a cup in this competition.")
    if stage.fixtures.exists():
        raise ValueError("This cup already has fixtures.")
    if len(participants) < 2:
        raise ValueError("Add at least two sides before starting a cup.")
    assert_cups_are_sequential(competition, starting=stage)
    priors = list(
        competition.stages.filter(kind=Stage.Kind.KNOCKOUT, display_order__lt=stage.display_order).order_by(
            "display_order"
        )
    )
    for prior in priors:
        if not prior.fixtures.exists():
            raise ValueError(f"Start {prior.name} first.")
        if not cup_is_complete(prior):
            raise ValueError(f"{prior.name} is still running. Only one cup can run at a time.")

    reserved = list((competition.settings_json or {}).get("cup_slot_datetimes") or [])
    kickoff = None
    if reserved:
        from django.utils.dateparse import parse_datetime

        kickoff = parse_datetime(reserved.pop(0))
    if kickoff is None:
        last = (
            competition.fixtures.exclude(scheduled_at=None)
            .order_by("-scheduled_at")
            .values_list("scheduled_at", flat=True)
            .first()
        )
        start_day = (last.date() + timedelta(days=1)) if last else timezone.now().date()
        weekdays = competition.match_weekdays or list(range(7))
        options = ScheduleOptions(starts_on=start_day, weekdays=weekdays, kickoff=time(15, 0))
        slots = _slot_datetimes(options, 1)
        kickoff = slots[0] if slots else None
        extra_needed = max(knockout_round_count(len(participants)) - 1, 0)
        if extra_needed and kickoff is not None:
            extra_start = kickoff.date() + timedelta(days=1)
            extra = _slot_datetimes(
                ScheduleOptions(starts_on=extra_start, weekdays=weekdays, kickoff=time(15, 0)),
                extra_needed,
            )
            reserved.extend(slot.isoformat() for slot in extra)

    options = ScheduleOptions(
        starts_on=kickoff.date() if kickoff else timezone.now().date(),
        weekdays=competition.match_weekdays or [],
        kickoff=kickoff.time() if kickoff else time(15, 0),
    )
    created = _write_pair_round(
        competition=competition,
        stage=stage,
        pairs=knockout_slots(participants),
        round_number=1,
        label=f"{stage.name} round 1",
        kickoff=kickoff,
        options=options,
    )
    settings = dict(competition.settings_json or {})
    settings["cup_slot_datetimes"] = reserved
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])
    return created
