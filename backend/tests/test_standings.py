"""The standings engine turns fixtures plus a points policy into a table."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.competitions.models import PointsPolicy
from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent
from apps.standings.services import compute_standings, refresh_standings

pytestmark = pytest.mark.django_db


def play(competition, home, away, home_points, away_points, category):
    """Record a completed fixture with the given scores, in units of `category`."""

    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.COMPLETED)
    home_side = FixtureSide.objects.create(
        fixture=fixture, participant=home, position=0, is_home=True
    )
    away_side = FixtureSide.objects.create(fixture=fixture, participant=away, position=1)

    if home_points:
        ScoreEvent.objects.create(
            fixture=fixture,
            side=home_side,
            scoring_category=category,
            quantity=Decimal(home_points) / category.points,
        )
    if away_points:
        ScoreEvent.objects.create(
            fixture=fixture,
            side=away_side,
            scoring_category=category,
            quantity=Decimal(away_points) / category.points,
        )

    fixture.recalculate_scores()
    return fixture


def test_win_draw_loss_points_follow_the_policy(
    competition, rugby_scoring, points_policy, participants
):
    a, b, c, _ = participants
    penalty = rugby_scoring["penalty"]  # worth 3

    play(competition, a, b, 30, 3, penalty)  # a wins by 27
    play(competition, b, c, 9, 9, penalty)  # draw
    play(competition, a, c, 6, 12, penalty)  # a loses by 6

    rows = {row.name: row for row in compute_standings(competition)}

    # a: 4 for the win, 0 for the loss, plus 1 losing bonus for being within 7.
    assert rows["Tank United"].wins == 1
    assert rows["Tank United"].losses == 1
    assert rows["Tank United"].bonus_points == Decimal("1")
    assert rows["Tank United"].points == Decimal("5")

    # b: a 27-point loss is outside the bonus margin, so only the draw scores.
    assert rows["Real United"].draws == 1
    assert rows["Real United"].bonus_points == Decimal("0")
    assert rows["Real United"].points == Decimal("2")


def test_losing_bonus_point_is_awarded_within_the_margin(
    competition, rugby_scoring, points_policy, participants
):
    a, b = participants[0], participants[1]
    penalty = rugby_scoring["penalty"]

    # b loses by 6, inside the 7-point bonus margin.
    play(competition, a, b, 18, 12, penalty)

    rows = {row.name: row for row in compute_standings(competition)}

    assert rows["Real United"].bonus_points == Decimal("1")
    assert rows["Real United"].points == Decimal("1")  # 0 for the loss + 1 bonus
    assert rows["Tank United"].points == Decimal("4")


def test_score_difference_breaks_a_tie_on_points(
    competition, rugby_scoring, points_policy, participants
):
    a, b, c, d = participants
    penalty = rugby_scoring["penalty"]

    # a and b both win once, but a's margin is larger.
    play(competition, a, c, 30, 3, penalty)
    play(competition, b, d, 12, 9, penalty)

    ordered = compute_standings(competition)
    assert [row.name for row in ordered[:2]] == ["Tank United", "Real United"]
    assert ordered[0].score_difference == Decimal("27")
    assert ordered[1].score_difference == Decimal("3")


def test_tiebreaker_order_is_configurable(
    competition, rugby_scoring, points_policy, participants
):
    """Reordering the policy's tiebreakers reorders the table."""

    a, b, c, d = participants
    penalty = rugby_scoring["penalty"]

    play(competition, a, c, 30, 3, penalty)  # a: +27
    play(competition, b, d, 12, 0, penalty)  # b: +12, and concedes nothing

    by_difference = [row.name for row in compute_standings(competition)[:2]]
    assert by_difference == ["Tank United", "Real United"]

    # Rank by fewest points conceded instead; b conceded 0, a conceded 3.
    points_policy.tiebreakers = ["points", "score_against", "name"]
    points_policy.save()

    by_defence = [row.name for row in compute_standings(competition)[:2]]
    assert by_defence == ["Real United", "Tank United"]


def test_head_to_head_separates_two_level_participants(
    competition, rugby_scoring, participants
):
    policy, _ = PointsPolicy.objects.get_or_create(competition=competition)
    policy.win_points = Decimal("3")
    policy.draw_points = Decimal("1")
    policy.loss_points = Decimal("0")
    policy.tiebreakers = ["points", "head_to_head", "name"]
    policy.save()

    a, b, c, d = participants
    penalty = rugby_scoring["penalty"]

    # a and b each beat c and d by the same margin, so only head-to-head separates them.
    play(competition, a, c, 9, 3, penalty)
    play(competition, b, d, 9, 3, penalty)
    # b beat a head-to-head, but that game also gives b more points, so level them
    # by giving a an extra win too.
    play(competition, b, a, 6, 3, penalty)
    play(competition, a, d, 6, 3, penalty)

    rows = {row.name: row for row in compute_standings(competition)}
    assert rows["Real United"].points == rows["Tank United"].points

    ordered = [row.name for row in compute_standings(competition)]
    # Real United (b) beat Tank United (a), so it ranks higher.
    assert ordered.index("Real United") < ordered.index("Tank United")


def test_only_completed_fixtures_count(competition, rugby_scoring, points_policy, participants):
    a, b = participants[0], participants[1]
    penalty = rugby_scoring["penalty"]

    fixture = play(competition, a, b, 30, 3, penalty)
    fixture.status = Fixture.Status.SCHEDULED
    fixture.save(update_fields=["status"])

    rows = {row.name: row for row in compute_standings(competition)}
    assert rows["Tank United"].played == 0
    assert rows["Tank United"].points == Decimal("0")


def test_refresh_persists_positions(competition, rugby_scoring, points_policy, participants):
    a, b, c, d = participants
    penalty = rugby_scoring["penalty"]

    play(competition, a, b, 30, 3, penalty)
    play(competition, c, d, 12, 9, penalty)

    saved = refresh_standings(competition)

    assert [row.position for row in saved] == [1, 2, 3, 4]
    assert saved[0].participant.name == "Tank United"
    # Recomputing replaces rather than duplicates.
    assert len(refresh_standings(competition)) == 4


def test_form_lists_the_most_recent_results_first(
    competition, rugby_scoring, points_policy, participants
):
    a, b, c, d = participants
    penalty = rugby_scoring["penalty"]

    play(competition, a, b, 30, 3, penalty)  # a wins
    play(competition, a, c, 3, 30, penalty)  # a loses
    play(competition, a, d, 9, 9, penalty)  # a draws

    rows = {row.name: row for row in compute_standings(competition)}
    assert rows["Tank United"].form == ["D", "L", "W"]
