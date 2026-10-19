"""The standings engine.

Given a competition's completed fixtures and its `PointsPolicy`, produce an
ordered league table. Everything the engine needs is data on the competition:
points, tie-breakers, and whether a lower total ranks first.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from apps.competitions.models import Competition, PointsPolicy, Stage
from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent

from apps.core.signals import results_changed

from .models import StandingRow

ZERO = Decimal("0")


@dataclass
class Row:
    participant_id: str
    name: str
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    score_for: Decimal = ZERO
    score_against: Decimal = ZERO
    points: Decimal = ZERO
    bonus_points: Decimal = ZERO
    form: list[str] = field(default_factory=list)
    beaten: set[str] = field(default_factory=set)
    units_difference: Decimal = ZERO
    units_for: Decimal = ZERO
    units_against: Decimal = ZERO
    rate: Decimal = ZERO
    sonneborn: Decimal = ZERO
    best_single: Decimal = ZERO
    next_attempt: Decimal = ZERO
    last_activity: Decimal = ZERO
    category_totals: dict = field(default_factory=dict)
    category_points: dict = field(default_factory=dict)
    drawn: set[str] = field(default_factory=set)
    countback: tuple = ()
    seconds: int = 0
    thirds: int = 0
    statuses: int = 0

    @property
    def score_difference(self) -> Decimal:
        return self.score_for - self.score_against


def _attempts(side, fixture, settings: dict) -> list[Decimal]:
    from apps.competitions.engine import score_rules

    rules = score_rules(settings)
    values = []
    for event in fixture.events.all():
        if event.side_id != side.id or event.scoring_category is None:
            continue
        rule = rules.get(event.scoring_category.code, {})
        if rule.get("aggregate") == "best" and event.scoring_category.affects_score:
            values.append(event.points)
    return values


def _attempt_sort(values: list[Decimal], lower: bool) -> tuple:
    ordered = sorted(values, reverse=not lower)
    best = ordered[0] if ordered else ZERO
    missing = Decimal("999999") if lower else ZERO
    second = ordered[1] if len(ordered) > 1 else missing
    if lower:
        return (best, second)
    return (-best, -second)


def _performance_is_lower(settings: dict, fixture) -> bool:
    """A fixture ranks low-to-high when every scored action on it says so."""

    better = settings.get("category_better") or {}
    directions = set()
    for event in fixture.events.all():
        if event.scoring_category is None:
            continue
        direction = better.get(event.scoring_category.code)
        if direction:
            directions.add(direction)
    if directions == {"lower"}:
        return True
    if directions == {"higher"}:
        return False
    return settings.get("performance") == "lower"


def _ratio(for_value: Decimal, against_value: Decimal) -> Decimal:
    if against_value == 0:
        return for_value
    return for_value / against_value


def _sort_key(row: Row, tiebreakers: list[str], settings: dict | None = None) -> tuple:
    """Build a sort key from the policy's ordered tiebreakers.

    Negation gives descending order for "more is better" metrics. Two are
    inverted deliberately: fewest goals conceded and fewest games played both
    rank ascending.
    """

    key: list = []
    for rule in tiebreakers:
        if rule == PointsPolicy.Tiebreaker.POINTS:
            key.append(-row.points)
        elif rule == PointsPolicy.Tiebreaker.SCORE_DIFFERENCE:
            key.append(-row.score_difference)
        elif rule == PointsPolicy.Tiebreaker.SCORE_FOR:
            if (settings or {}).get("performance") == "lower":
                key.append(row.score_for)
            else:
                key.append(-row.score_for)
        elif rule == PointsPolicy.Tiebreaker.SCORE_AGAINST:
            key.append(row.score_against)
        elif rule == PointsPolicy.Tiebreaker.WINS:
            key.append(-row.wins)
        elif rule == PointsPolicy.Tiebreaker.PLAYED:
            key.append(row.played)
        elif rule == PointsPolicy.Tiebreaker.UNITS_DIFFERENCE:
            key.append(-row.units_difference)
        elif rule == PointsPolicy.Tiebreaker.UNITS_FOR:
            key.append(-row.units_for)
        elif rule == PointsPolicy.Tiebreaker.UNITS_RATIO:
            key.append(-_ratio(row.units_for, row.units_against))
        elif rule == PointsPolicy.Tiebreaker.SCORE_RATIO:
            key.append(-_ratio(row.score_for, row.score_against))
        elif rule == PointsPolicy.Tiebreaker.RATE:
            key.append(-row.rate)
        elif rule == PointsPolicy.Tiebreaker.SONNEBORN_BERGER:
            key.append(-row.sonneborn)
        elif rule == PointsPolicy.Tiebreaker.BEST_SINGLE:
            key.append(-row.best_single)
        elif rule == PointsPolicy.Tiebreaker.NEXT_ATTEMPT:
            if (settings or {}).get("performance") == "lower":
                key.append(row.next_attempt or Decimal("999999"))
            else:
                key.append(-row.next_attempt)
        elif rule == PointsPolicy.Tiebreaker.RECENT:
            key.append(-row.last_activity)
        elif str(rule).startswith("category:"):
            code = str(rule).split(":", 1)[1]
            # "a+b" adds several categories, e.g. every 10 whether or not it was an X.
            total = sum((row.category_totals.get(part, ZERO) for part in code.split("+")), ZERO)
            better = ((settings or {}).get("category_better") or {}).get(code)
            key.append(total if better == "lower" else -total)
        elif rule == PointsPolicy.Tiebreaker.COUNTBACK:
            key.append(row.countback)
        elif rule == PointsPolicy.Tiebreaker.SECONDS:
            key.append(-row.seconds)
        elif rule == PointsPolicy.Tiebreaker.THIRDS:
            key.append(-row.thirds)
        elif rule == PointsPolicy.Tiebreaker.PLACINGS:
            key.extend([-row.wins, -row.seconds, -row.thirds])
        elif rule == PointsPolicy.Tiebreaker.NAME:
            key.append(row.name.lower())
        # HEAD_TO_HEAD needs the whole tied group, so it is applied afterwards.
    return tuple(key)


def _attach_unit_tiebreakers(rows: dict[str, Row], competition: Competition) -> None:
    """Fill unit records, countback, category totals and scoring rate from events."""

    from apps.competitions.engine import expand_units, split_scores, unit_table

    settings = competition.settings_json or {}
    lowest = settings.get("accumulation_ranking") == "lowest_first" or settings.get(
        "win_condition"
    ) in {"lowest_total", "count_down_to_zero"}
    events = list(
        ScoreEvent.objects.filter(
            fixture__competition=competition,
            fixture__status__in=[Fixture.Status.COMPLETED, Fixture.Status.FORFEIT],
        ).select_related("side", "scoring_category", "fixture")
    )
    by_fixture: dict[str, list] = defaultdict(list)
    for event in events:
        by_fixture[str(event.fixture_id)].append(event)
        if event.scoring_category is None:
            continue
        row = rows.get(str(event.side.participant_id))
        if row is None:
            continue
        code = event.scoring_category.code
        row.category_totals[code] = row.category_totals.get(code, ZERO) + Decimal(event.quantity)
        if event.scoring_category.affects_score:
            row.category_points[code] = row.category_points.get(code, ZERO) + event.points
        stamp = event.created_at.timestamp() if event.created_at else 0
        if stamp > row.last_activity:
            row.last_activity = Decimal(str(stamp))

    slots = expand_units(settings.get("match_structure") or [])
    combined: dict[str, dict[int, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    participant_of: dict[str, str] = {}
    for fixture_events in by_fixture.values():
        sides = list(fixture_events[0].fixture.sides.all())
        if len(sides) < 2 or not slots:
            for event in fixture_events:
                if event.unit_index is None or not event.scoring_category.affects_score:
                    continue
                combined[str(event.side.participant_id)][event.unit_index] += event.points
            continue
        _match, _decider, per_unit, tiebreak = split_scores(sides, fixture_events, slots, settings)
        side_ids = [side.id for side in sides]
        for side in sides:
            participant_of[side.id] = str(side.participant_id)
        winners = unit_table(side_ids, slots, per_unit, tiebreak)
        won_by: dict[str, int] = defaultdict(int)
        for winner in winners.values():
            if winner is not None:
                won_by[participant_of[winner]] += 1
        present = {participant_of[side.id] for side in sides}
        for participant_id in present:
            row = rows.get(participant_id)
            if row is None:
                continue
            row.units_for += won_by.get(participant_id, 0)
            row.units_against += sum(
                count for other, count in won_by.items() if other != participant_id
            )
        for side in sides:
            participant_id = participant_of[side.id]
            for slot in slots:
                combined[participant_id][slot["index"]] += per_unit[side.id][slot["index"]]

    for row in rows.values():
        row.units_difference = row.units_for - row.units_against

    windows = settings.get("countback_windows") or []
    for participant_id, slots_map in combined.items():
        row = rows.get(participant_id)
        if row is None or not slots_map:
            continue
        ordered = [slots_map[index] for index in sorted(slots_map)]
        if windows:
            sequence = []
            for size in windows:
                chunk = ordered[-int(size) :]
                total = sum(chunk, ZERO)
                sequence.append(total if lowest else -total)
            row.countback = tuple(sequence)
            continue
        sequence = list(reversed(ordered))
        if not lowest:
            sequence = [-value for value in sequence]
        row.countback = tuple(sequence)

    _attach_rate(rows, settings, by_fixture)


def _attach_rate(rows: dict[str, Row], settings: dict, by_fixture: dict[str, list]) -> None:
    basis = settings.get("rate_basis") or {}
    codes = set(basis.get("for") or [])
    balls_code = basis.get("balls")
    if not codes or not balls_code:
        return
    scale = Decimal(str(basis.get("scale") or 1))
    scored: dict[str, Decimal] = defaultdict(lambda: ZERO)
    faced: dict[str, Decimal] = defaultdict(lambda: ZERO)
    conceded: dict[str, Decimal] = defaultdict(lambda: ZERO)
    bowled: dict[str, Decimal] = defaultdict(lambda: ZERO)
    from apps.competitions.engine import expand_units

    decider_indexes = {
        slot["index"]
        for slot in expand_units(settings.get("match_structure") or [])
        if slot.get("resolves_draw")
    }
    for fixture_events in by_fixture.values():
        match_scored: dict[str, Decimal] = defaultdict(lambda: ZERO)
        match_faced: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for event in fixture_events:
            if event.scoring_category is None or event.unit_index in decider_indexes:
                continue
            participant_id = str(event.side.participant_id)
            code = event.scoring_category.code
            if code in codes and event.scoring_category.affects_score:
                match_scored[participant_id] += event.points
            if code == balls_code:
                match_faced[participant_id] += Decimal(event.quantity)
        players = set(match_scored) | set(match_faced)
        for participant_id in players:
            scored[participant_id] += match_scored[participant_id]
            faced[participant_id] += match_faced[participant_id]
            conceded[participant_id] += sum(
                (match_scored[other] for other in players if other != participant_id), ZERO
            )
            bowled[participant_id] += sum(
                (match_faced[other] for other in players if other != participant_id), ZERO
            )
    for participant_id, row in rows.items():
        overs = faced[participant_id] / scale if scale else ZERO
        overs_against = bowled[participant_id] / scale if scale else ZERO
        if overs <= 0 or overs_against <= 0:
            continue
        row.rate = scored[participant_id] / overs - conceded[participant_id] / overs_against


def _attach_sonneborn(rows: dict[str, Row]) -> None:
    for row in rows.values():
        total = ZERO
        for opponent_id in row.beaten:
            opponent = rows.get(opponent_id)
            if opponent is not None:
                total += opponent.score_for
        for opponent_id in row.drawn:
            opponent = rows.get(opponent_id)
            if opponent is not None:
                total += opponent.score_for / 2
        row.sonneborn = total


def _apply_head_to_head(
    rows: list[Row], tiebreakers: list[str], settings: dict | None = None
) -> list[Row]:
    """Reorder groups that are level on every earlier tiebreaker by head-to-head.

    Only pairs are resolved. Circular results among three or more participants
    have no unambiguous answer, so those are left in their existing order.
    """

    if PointsPolicy.Tiebreaker.HEAD_TO_HEAD not in tiebreakers:
        return rows

    cutoff = tiebreakers.index(PointsPolicy.Tiebreaker.HEAD_TO_HEAD)
    preceding = tiebreakers[:cutoff]

    result: list[Row] = []
    bucket: list[Row] = []
    bucket_key: tuple | None = None

    for row in [*rows, None]:
        key = _sort_key(row, preceding, settings) if row is not None else None
        if row is None or key != bucket_key:
            if len(bucket) == 2 and bucket[1].participant_id in bucket[0].beaten:
                pass  # already in the right order
            elif len(bucket) == 2 and bucket[0].participant_id in bucket[1].beaten:
                bucket.reverse()
            result.extend(bucket)
            bucket = []
            bucket_key = key
        if row is not None:
            bucket.append(row)

    return result


def _series_from_results(competition: Competition, rows: dict[str, Row], settings: dict) -> None:
    """A season across many events: placing points, and counts of 1st, 2nd and 3rd.

    Entrants with a status (eliminated, disqualified, withdrawn...) are counted as
    having started but never earn points.
    """

    from apps.results.services import counted_entries, placing_points_for

    for entry, tied in counted_entries(competition):
        row = rows.get(str(entry.side.participant_id))
        if row is None:
            continue
        row.played += 1
        if entry.rank is None:
            row.statuses += 1
            continue
        if entry.rank == 1:
            row.wins += 1
        elif entry.rank == 2:
            row.seconds += 1
        elif entry.rank == 3:
            row.thirds += 1
        else:
            row.losses += 1
        row.points += placing_points_for(settings, entry.rank, tied)
        if entry.primary is not None:
            row.score_for += entry.primary
            if row.best_single == 0 or entry.primary > row.best_single:
                row.best_single = entry.primary


def scoring_basis(competition: Competition) -> str:
    """results = win/draw/loss from fixtures; criteria = sum of scoring criteria."""

    settings = competition.settings_json or {}
    basis = settings.get("scoring_basis")
    if basis in {"results", "criteria"}:
        return basis
    if settings.get("table_mode") == "points":
        return "criteria"
    return "results"


def is_criteria_league(competition: Competition) -> bool:
    return scoring_basis(competition) == "criteria"


def criteria_breakdown(competition: Competition) -> dict[str, list[dict]]:
    """Per participant, the criteria that make up their accumulated points.

    Each criterion includes its description and the entries that explain how
    those points were logged.
    """

    events = (
        ScoreEvent.objects.filter(
            fixture__competition=competition,
            fixture__status__in=[Fixture.Status.COMPLETED, Fixture.Status.FORFEIT],
            scoring_category__affects_score=True,
        )
        .select_related("scoring_category", "side__participant")
        .order_by("created_at")
    )

    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    for event in events:
        participant_id = str(event.side.participant_id)
        category = event.scoring_category
        category_id = str(category.id)
        bucket = grouped[participant_id].get(category_id)
        if bucket is None:
            bucket = {
                "id": category_id,
                "name": category.name,
                "description": category.description,
                "points_each": str(category.points),
                "total": ZERO,
                "entries": [],
            }
            grouped[participant_id][category_id] = bucket
        awarded = event.points
        bucket["total"] += awarded
        bucket["entries"].append(
            {
                "quantity": str(event.quantity),
                "awarded": str(awarded),
                "note": event.note,
                "created_at": event.created_at.isoformat(),
            }
        )

    return {
        participant_id: [
            {**bucket, "total": str(bucket["total"])} for bucket in categories.values()
        ]
        for participant_id, categories in grouped.items()
    }


def _decided_after_regulation(fixtures, settings: dict) -> set:
    """Fixtures level at the end of regulation and won in extra blocks (overtime,
    shoot-out), when the preset scores those results differently."""

    league_points = settings.get("league_points") or {}
    if "extra_time_win" not in league_points or not fixtures:
        return set()
    from apps.competitions.engine import expand_units

    slots = expand_units(settings.get("match_structure") or [])
    regulation = {slot["index"] for slot in slots if not slot["extra"]}
    fixtures = list(fixtures)
    totals: dict = defaultdict(lambda: ZERO)
    for event in ScoreEvent.objects.filter(
        fixture__in=fixtures, scoring_category__affects_score=True
    ):
        if event.unit_index is None or event.unit_index in regulation:
            totals[(event.fixture_id, event.side_id)] += event.points
    decided = set()
    for fixture in fixtures:
        sides = list(fixture.sides.all())
        if len(sides) != 2 or not any(side.outcome == FixtureSide.Outcome.WIN for side in sides):
            continue
        if totals[(fixture.id, sides[0].id)] == totals[(fixture.id, sides[1].id)]:
            decided.add(fixture.id)
    return decided


def compute_standings(competition: Competition, stage: Stage | None = None) -> list[Row]:
    """Aggregate every counted fixture into an ordered table."""

    policy, _ = PointsPolicy.objects.get_or_create(competition=competition)
    criteria_league = is_criteria_league(competition)
    settings = competition.settings_json or {}

    rows: dict[str, Row] = {}
    participants = competition.participants.all()
    if stage is not None:
        participants = participants.filter(stages=stage)
    for participant in participants:
        rows[str(participant.id)] = Row(participant_id=str(participant.id), name=participant.name)

    fixtures = (
        Fixture.objects.filter(
            competition=competition,
            status__in=[Fixture.Status.COMPLETED, Fixture.Status.FORFEIT],
        )
        .prefetch_related("sides__participant")
        .order_by("scheduled_at", "created_at")
    )
    if stage is not None:
        fixtures = fixtures.filter(stage=stage)

    form_by_participant: dict[str, list[str]] = defaultdict(list)

    placing = [Decimal(str(value)) for value in (settings.get("placing_points") or [])]
    no_result_codes = {
        item["key"]
        for item in (settings.get("score_types") or [])
        if item.get("role") == "no_result"
    }
    no_result_fixtures = set()
    if no_result_codes:
        no_result_fixtures = set(
            ScoreEvent.objects.filter(
                fixture__competition=competition,
                scoring_category__code__in=no_result_codes,
            ).values_list("fixture_id", flat=True)
        )
    no_result_points = Decimal(str((settings.get("league_points") or {}).get("no_result", 1)))

    if settings.get("result_type"):
        _series_from_results(competition, rows, settings)
        fixtures = []

    league_points = settings.get("league_points") or {}
    after_regulation = _decided_after_regulation(fixtures, settings)

    for fixture in fixtures:
        sides = list(fixture.sides.all())
        if not sides:
            continue
        if fixture.id in no_result_fixtures:
            for side in sides:
                row = rows.get(str(side.participant_id))
                if row is None:
                    continue
                row.played += 1
                row.draws += 1
                row.points += no_result_points
            continue
        # A one-entrant fixture is an awarded criterion; it has no opponent to beat.
        if len(sides) > 1 and any(side.outcome == FixtureSide.Outcome.PENDING for side in sides):
            continue
        if placing and len(sides) >= 2:
            lower = _performance_is_lower(settings, fixture)
            attempts = {side.id: _attempts(side, fixture, settings) for side in sides}
            ordered_sides = sorted(sides, key=lambda side: _attempt_sort(attempts[side.id], lower))
            for index, side in enumerate(ordered_sides):
                row = rows.get(str(side.participant_id))
                if row is None:
                    continue
                row.played += 1
                best = side.score
                row.score_for += best
                if best > row.best_single:
                    row.best_single = best
                ordered_attempts = sorted(attempts[side.id], reverse=not lower)
                second = ordered_attempts[1] if len(ordered_attempts) > 1 else ZERO
                if row.next_attempt == 0:
                    row.next_attempt = second
                if index < len(placing):
                    row.points += placing[index]
            continue

        # Criteria leagues add each side's score. A one-person entry is how
        # an awarded criterion is stored, so its score always reaches the table.
        if criteria_league or len(sides) == 1:
            for side in sides:
                participant_id = str(side.participant_id)
                row = rows.get(participant_id)
                if row is None:
                    continue
                row.played += 1
                row.score_for += side.score
                row.points += side.score
                if side.score > row.best_single:
                    row.best_single = side.score
            continue

        if len(sides) < 2:
            continue

        total_score = sum((side.score for side in sides), ZERO)

        for side in sides:
            participant_id = str(side.participant_id)
            row = rows.get(participant_id)
            if row is None:
                continue

            row.played += 1
            row.score_for += side.score
            # In a multi-way fixture, "against" is everything the others scored.
            row.score_against += total_score - side.score

            if side.forfeited:
                row.losses += 1
                row.points += policy.forfeit_points
                form_by_participant[participant_id].append("L")
                continue

            if side.outcome == FixtureSide.Outcome.WIN:
                row.wins += 1
                row.points += (
                    Decimal(str(league_points["extra_time_win"]))
                    if fixture.id in after_regulation
                    else policy.win_points
                )
                form_by_participant[participant_id].append("W")
                for other in sides:
                    if other.id != side.id:
                        row.beaten.add(str(other.participant_id))
            elif side.outcome == FixtureSide.Outcome.DRAW:
                row.draws += 1
                row.points += policy.draw_points
                form_by_participant[participant_id].append("D")
                for other in sides:
                    if other.id != side.id:
                        row.drawn.add(str(other.participant_id))
            else:
                row.losses += 1
                row.points += (
                    Decimal(str(league_points["extra_time_loss"]))
                    if fixture.id in after_regulation
                    else policy.loss_points
                )
                form_by_participant[participant_id].append("L")

            # Optional margin bonus. Margin is measured against the best
            # of the other sides, which also works for multi-way fixtures.
            best_other = max((other.score for other in sides if other.id != side.id), default=ZERO)
            margin = side.score - best_other

            if (
                policy.bonus_win_margin is not None
                and side.outcome == FixtureSide.Outcome.WIN
                and margin >= policy.bonus_win_margin
            ):
                row.bonus_points += policy.bonus_win_points
                row.points += policy.bonus_win_points

            if (
                policy.bonus_loss_margin is not None
                and side.outcome == FixtureSide.Outcome.LOSS
                and -margin <= policy.bonus_loss_margin
            ):
                row.bonus_points += policy.bonus_loss_points
                row.points += policy.bonus_loss_points

    for participant_id, results in form_by_participant.items():
        if participant_id in rows:
            rows[participant_id].form = list(reversed(results[-5:]))

    if settings.get("handicap"):
        for participant in participants:
            adjustment = Decimal(str((participant.metadata or {}).get("handicap") or 0))
            row = rows.get(str(participant.id))
            if row is not None and adjustment:
                row.points += adjustment
                row.score_for += adjustment

    if not settings.get("result_type"):
        _attach_unit_tiebreakers(rows, competition)
        _attach_sonneborn(rows)
    tiebreakers = policy.effective_tiebreakers
    if settings.get("result_type"):
        ordered = sorted(rows.values(), key=lambda row: _sort_key(row, tiebreakers, settings))
    elif settings.get("placing_points"):
        ordered = sorted(rows.values(), key=lambda row: _sort_key(row, tiebreakers, settings))
    elif settings.get("contest_type") == "accumulation":
        lowest = settings.get("accumulation_ranking") == "lowest_first"

        def accumulation_key(row: Row) -> tuple:
            if lowest:
                # Lowest total wins, but only among entrants who have played the
                # most rounds: an empty card (0) must never beat a finished one,
                # and a shorter card is not "better" for being shorter.
                return (
                    row.played == 0,
                    -row.played,
                    row.score_for,
                    _sort_key(row, tiebreakers, settings),
                )
            return (-row.score_for, _sort_key(row, tiebreakers, settings))

        ordered = sorted(rows.values(), key=accumulation_key)
    else:
        ordered = sorted(rows.values(), key=lambda row: _sort_key(row, tiebreakers, settings))
    return _apply_head_to_head(ordered, tiebreakers, settings)


@transaction.atomic
def refresh_standings(competition: Competition, stage: Stage | None = None) -> list[StandingRow]:
    """Recompute and persist the cached table."""

    computed = compute_standings(competition, stage)

    StandingRow.objects.filter(competition=competition, stage=stage).delete()
    results_changed.send(sender=Competition, competition=competition)
    saved = StandingRow.objects.bulk_create(
        [
            StandingRow(
                competition=competition,
                stage=stage,
                participant_id=row.participant_id,
                position=index + 1,
                played=row.played,
                wins=row.wins,
                draws=row.draws,
                losses=row.losses,
                score_for=row.score_for,
                score_against=row.score_against,
                score_difference=row.score_difference,
                points=row.points,
                bonus_points=row.bonus_points,
                form=row.form,
                detail=(
                    {"seconds": row.seconds, "thirds": row.thirds, "statuses": row.statuses}
                    if (competition.settings_json or {}).get("result_type")
                    else {}
                ),
            )
            for index, row in enumerate(computed)
        ]
    )
    return saved
