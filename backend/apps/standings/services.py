"""The standings engine.

Given a competition's completed fixtures and its `PointsPolicy`, produce an
ordered league table. Everything the engine needs is data, so the same code
ranks a soccer league, a rugby league with bonus points and a golf order of
merit where lower scores are better.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from apps.competitions.models import Competition, PointsPolicy, Stage
from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent

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

    @property
    def score_difference(self) -> Decimal:
        return self.score_for - self.score_against


def _sort_key(row: Row, tiebreakers: list[str]) -> tuple:
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
            key.append(-row.score_for)
        elif rule == PointsPolicy.Tiebreaker.SCORE_AGAINST:
            key.append(row.score_against)
        elif rule == PointsPolicy.Tiebreaker.WINS:
            key.append(-row.wins)
        elif rule == PointsPolicy.Tiebreaker.PLAYED:
            key.append(row.played)
        elif rule == PointsPolicy.Tiebreaker.NAME:
            key.append(row.name.lower())
        # HEAD_TO_HEAD needs the whole tied group, so it is applied afterwards.
    return tuple(key)


def _apply_head_to_head(rows: list[Row], tiebreakers: list[str]) -> list[Row]:
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
        key = _sort_key(row, preceding) if row is not None else None
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
            {**bucket, "total": str(bucket["total"])}
            for bucket in categories.values()
        ]
        for participant_id, categories in grouped.items()
    }


def compute_standings(competition: Competition, stage: Stage | None = None) -> list[Row]:
    """Aggregate every counted fixture into an ordered table."""

    policy, _ = PointsPolicy.objects.get_or_create(competition=competition)
    criteria_league = is_criteria_league(competition)

    rows: dict[str, Row] = {}
    participants = competition.participants.all()
    if stage is not None:
        participants = participants.filter(stages=stage)
    for participant in participants:
        rows[str(participant.id)] = Row(
            participant_id=str(participant.id), name=participant.name
        )

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

    for fixture in fixtures:
        sides = list(fixture.sides.all())
        if not sides:
            continue

        # Criteria leagues add each side's score, including a one-person entry.
        if criteria_league:
            for side in sides:
                participant_id = str(side.participant_id)
                row = rows.get(participant_id)
                if row is None:
                    continue
                row.played += 1
                row.score_for += side.score
                row.points += side.score
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
                row.points += policy.win_points
                form_by_participant[participant_id].append("W")
                for other in sides:
                    if other.id != side.id:
                        row.beaten.add(str(other.participant_id))
            elif side.outcome == FixtureSide.Outcome.DRAW:
                row.draws += 1
                row.points += policy.draw_points
                form_by_participant[participant_id].append("D")
            else:
                row.losses += 1
                row.points += policy.loss_points
                form_by_participant[participant_id].append("L")

            # Bonus points (rugby style). Margin is measured against the best
            # of the other sides, which also works for multi-way fixtures.
            best_other = max(
                (other.score for other in sides if other.id != side.id), default=ZERO
            )
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

    tiebreakers = policy.effective_tiebreakers
    ordered = sorted(rows.values(), key=lambda row: _sort_key(row, tiebreakers))
    return _apply_head_to_head(ordered, tiebreakers)


@transaction.atomic
def refresh_standings(competition: Competition, stage: Stage | None = None) -> list[StandingRow]:
    """Recompute and persist the cached table."""

    computed = compute_standings(competition, stage)

    StandingRow.objects.filter(competition=competition, stage=stage).delete()
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
            )
            for index, row in enumerate(computed)
        ]
    )
    return saved
