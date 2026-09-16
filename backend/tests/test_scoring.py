"""Scoring is derived from events, never entered directly."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent

pytestmark = pytest.mark.django_db


def make_fixture(competition, home, away, status=Fixture.Status.COMPLETED) -> Fixture:
    fixture = Fixture.objects.create(competition=competition, status=status)
    FixtureSide.objects.create(fixture=fixture, participant=home, position=0, is_home=True)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    return fixture


def record(fixture, participant, category, quantity=1):
    side = fixture.sides.get(participant=participant)
    return ScoreEvent.objects.create(
        fixture=fixture, side=side, scoring_category=category, quantity=quantity
    )


def test_score_is_the_sum_of_event_points(competition, rugby_scoring, participants):
    home, away = participants[0], participants[1]
    fixture = make_fixture(competition, home, away)

    # Two converted tries and a penalty: (5+2) * 2 + 3 = 17.
    record(fixture, home, rugby_scoring["try"], 2)
    record(fixture, home, rugby_scoring["conversion"], 2)
    record(fixture, home, rugby_scoring["penalty"], 1)
    record(fixture, away, rugby_scoring["try"], 1)

    fixture.recalculate_scores()

    assert fixture.sides.get(participant=home).score == Decimal("17.00")
    assert fixture.sides.get(participant=away).score == Decimal("5.00")


def test_non_scoring_events_do_not_move_the_score(competition, rugby_scoring, participants):
    home, away = participants[0], participants[1]
    fixture = make_fixture(competition, home, away)

    record(fixture, home, rugby_scoring["try"], 1)
    record(fixture, home, rugby_scoring["yellow"], 3)
    fixture.recalculate_scores()

    assert fixture.sides.get(participant=home).score == Decimal("5.00")
    # The card is still on the timeline even though it scores nothing.
    assert fixture.events.count() == 2


def test_outcomes_are_resolved_from_the_scores(competition, rugby_scoring, participants):
    home, away = participants[0], participants[1]
    fixture = make_fixture(competition, home, away)

    record(fixture, home, rugby_scoring["try"], 2)
    record(fixture, away, rugby_scoring["penalty"], 1)
    fixture.recalculate_scores()

    assert fixture.sides.get(participant=home).outcome == FixtureSide.Outcome.WIN
    assert fixture.sides.get(participant=away).outcome == FixtureSide.Outcome.LOSS


def test_equal_scores_produce_a_draw(competition, rugby_scoring, participants):
    home, away = participants[0], participants[1]
    fixture = make_fixture(competition, home, away)

    record(fixture, home, rugby_scoring["penalty"], 1)
    record(fixture, away, rugby_scoring["penalty"], 1)
    fixture.recalculate_scores()

    assert {side.outcome for side in fixture.sides.all()} == {FixtureSide.Outcome.DRAW}


def test_deleting_an_event_corrects_the_score(competition, rugby_scoring, participants):
    home, away = participants[0], participants[1]
    fixture = make_fixture(competition, home, away)

    record(fixture, home, rugby_scoring["try"], 1)
    mistake = record(fixture, home, rugby_scoring["try"], 1)
    fixture.recalculate_scores()
    assert fixture.sides.get(participant=home).score == Decimal("10.00")

    mistake.delete()
    fixture.recalculate_scores()
    assert fixture.sides.get(participant=home).score == Decimal("5.00")


def test_a_forfeit_overrides_the_scoreboard(competition, rugby_scoring, participants):
    home, away = participants[0], participants[1]
    fixture = make_fixture(competition, home, away, status=Fixture.Status.FORFEIT)

    # The home side was ahead but forfeited, so they lose regardless.
    record(fixture, home, rugby_scoring["try"], 4)
    home_side = fixture.sides.get(participant=home)
    home_side.forfeited = True
    home_side.save(update_fields=["forfeited"])

    fixture.recalculate_scores()

    assert fixture.sides.get(participant=home).outcome == FixtureSide.Outcome.LOSS
    assert fixture.sides.get(participant=away).outcome == FixtureSide.Outcome.WIN


def test_negative_points_support_lower_is_better_sports(competition, participants):
    """Golf: each stroke is worth -1, so the fewest strokes wins."""

    from apps.competitions.models import ScoringCategory

    stroke = ScoringCategory.objects.create(
        competition=competition, name="Stroke", code="stroke", points=Decimal("-1")
    )
    home, away = participants[0], participants[1]
    fixture = make_fixture(competition, home, away)

    record(fixture, home, stroke, 72)
    record(fixture, away, stroke, 79)
    fixture.recalculate_scores()

    assert fixture.sides.get(participant=home).score == Decimal("-72.00")
    assert fixture.sides.get(participant=home).outcome == FixtureSide.Outcome.WIN
