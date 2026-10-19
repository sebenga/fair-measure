"""The table, the bracket, and a stroke-play ranking, driven only by preset data."""

from decimal import Decimal

import pytest

from apps.competitions.models import Participant
from apps.competitions.presets import apply_preset
from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent
from apps.standings.services import compute_standings, refresh_standings

pytestmark = pytest.mark.django_db


def _sides(competition, home, away, *, round_number=1, status=Fixture.Status.COMPLETED):
    fixture = Fixture.objects.create(
        competition=competition,
        round_number=round_number,
        status=status,
    )
    home_side = FixtureSide.objects.create(
        fixture=fixture, participant=home, position=0, is_home=True
    )
    away_side = FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    return fixture, home_side, away_side


def _goals(fixture, side, quantity, unit_index=0):
    category = fixture.competition.scoring_categories.get(code="goal")
    ScoreEvent.objects.create(
        fixture=fixture,
        side=side,
        scoring_category=category,
        quantity=Decimal(quantity),
        unit_index=unit_index,
    )


def _finish(fixture):
    fixture.recalculate_scores()
    fixture.save()


def test_head_to_head_league_uses_three_one_zero(api):
    created = api.post("/api/v1/competitions", {"name": "Sunday league", "preset": "soccer"}, format="json")
    assert created.status_code == 201
    competition_id = created.data["id"]
    from apps.competitions.models import Competition

    competition = Competition.objects.get(pk=competition_id)
    alpha = Participant.objects.create(competition=competition, name="Alpha", kind="team")
    beta = Participant.objects.create(competition=competition, name="Beta", kind="team")

    won, home, away = _sides(competition, alpha, beta)
    _goals(won, home, 2)
    _goals(won, away, 1)
    _finish(won)

    level, home, away = _sides(competition, alpha, beta)
    _goals(level, home, 1, unit_index=0)
    _goals(level, away, 1, unit_index=1)
    _finish(level)

    rows = {row.name: row for row in compute_standings(competition)}
    assert rows["Alpha"].points == Decimal("4")
    assert rows["Alpha"].wins == 1
    assert rows["Alpha"].draws == 1
    assert rows["Beta"].points == Decimal("1")
    assert rows["Beta"].losses == 1


def test_tiebreakers_apply_in_order(api):
    created = api.post("/api/v1/competitions", {"name": "Order", "preset": "soccer"}, format="json")
    competition_id = created.data["id"]
    from apps.competitions.models import Competition

    competition = Competition.objects.get(pk=competition_id)
    alpha = Participant.objects.create(competition=competition, name="Alpha", kind="team")
    beta = Participant.objects.create(competition=competition, name="Beta", kind="team")
    gamma = Participant.objects.create(competition=competition, name="Gamma", kind="team")
    delta = Participant.objects.create(competition=competition, name="Delta", kind="team")

    # Same points (3). Alpha's goal difference is larger.
    first, home, away = _sides(competition, alpha, gamma)
    _goals(first, home, 3)
    _finish(first)
    second, home, away = _sides(competition, beta, delta)
    _goals(second, home, 1)
    _finish(second)

    rows = compute_standings(competition)
    assert [row.name for row in rows[:2]] == ["Alpha", "Beta"]
    assert rows[0].points == rows[1].points


def test_goals_for_splits_equal_difference(api):
    created = api.post("/api/v1/competitions", {"name": "Goals for", "preset": "soccer"}, format="json")
    from apps.competitions.models import Competition

    competition = Competition.objects.get(pk=created.data["id"])
    alpha = Participant.objects.create(competition=competition, name="Alpha", kind="team")
    beta = Participant.objects.create(competition=competition, name="Beta", kind="team")
    gamma = Participant.objects.create(competition=competition, name="Gamma", kind="team")
    delta = Participant.objects.create(competition=competition, name="Delta", kind="team")

    narrow, home, away = _sides(competition, alpha, gamma)
    _goals(narrow, home, 1)
    _finish(narrow)
    open_game, home, away = _sides(competition, beta, delta)
    _goals(open_game, home, 2)
    _goals(open_game, away, 1)
    _finish(open_game)

    rows = {row.name: row for row in compute_standings(competition)}
    assert rows["Alpha"].points == rows["Beta"].points == Decimal("3")
    assert rows["Alpha"].score_difference == rows["Beta"].score_difference
    assert rows["Beta"].score_for > rows["Alpha"].score_for
    ordered = [row.name for row in compute_standings(competition) if row.points == Decimal("3")]
    assert ordered == ["Beta", "Alpha"]


def test_head_to_head_splits_a_level_pair(api):
    created = api.post("/api/v1/competitions", {"name": "Split", "preset": "soccer"}, format="json")
    from apps.competitions.models import Competition

    competition = Competition.objects.get(pk=created.data["id"])
    policy = competition.points_policy
    policy.tiebreakers = ["points", "head_to_head", "score_difference", "score_for"]
    policy.save()

    alpha = Participant.objects.create(competition=competition, name="Alpha", kind="team")
    beta = Participant.objects.create(competition=competition, name="Beta", kind="team")
    gamma = Participant.objects.create(competition=competition, name="Gamma", kind="team")
    delta = Participant.objects.create(competition=competition, name="Delta", kind="team")

    # Beta beat Alpha. Each then wins once more, so the points are level and
    # only the meeting separates them.
    meeting, home, away = _sides(competition, beta, alpha)
    _goals(meeting, home, 1)
    _finish(meeting)
    extra_a, home, away = _sides(competition, alpha, gamma)
    _goals(extra_a, home, 1)
    _finish(extra_a)
    extra_a2, home, away = _sides(competition, alpha, delta)
    _goals(extra_a2, home, 1)
    _finish(extra_a2)
    extra_b, home, away = _sides(competition, beta, gamma)
    _goals(extra_b, home, 1)
    _finish(extra_b)

    rows = {row.name: row for row in compute_standings(competition)}
    assert rows["Alpha"].points == rows["Beta"].points
    ordered = [row.name for row in compute_standings(competition) if row.name in {"Alpha", "Beta"}]
    assert ordered[0] == "Beta"


def test_knockout_penalties_advance_the_winner(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Cup", "preset": "soccer", "format": "knockout"},
        format="json",
    )
    assert created.status_code == 201
    competition_id = created.data["id"]
    from apps.competitions.models import Competition

    competition = Competition.objects.get(pk=competition_id)
    assert competition.format == "knockout"
    teams = [
        Participant.objects.create(competition=competition, name=name, kind="team")
        for name in ("Alpha", "Beta", "Gamma", "Delta")
    ]
    level, home, away = _sides(competition, teams[0], teams[1])
    _goals(level, home, 1, unit_index=0)
    _goals(level, away, 1, unit_index=1)
    _goals(level, home, 5, unit_index=4)
    _goals(level, away, 4, unit_index=4)
    _finish(level)
    home.refresh_from_db()
    away.refresh_from_db()
    assert home.outcome == "win"
    assert home.score == Decimal("1")

    decided, home, away = _sides(competition, teams[2], teams[3])
    _goals(decided, home, 2, unit_index=0)
    _finish(decided)

    advanced = api.post(f"/api/v1/competitions/{competition_id}/advance", {}, format="json")
    assert advanced.status_code == 201
    assert advanced.data["advanced"] is True
    final = Fixture.objects.get(competition=competition, round_number=2)
    names = set(final.sides.values_list("participant__name", flat=True))
    assert names == {"Alpha", "Gamma"}


def test_golf_ranks_lowest_total_then_countback(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Monthly medal", "preset": "golf_stroke"},
        format="json",
    )
    assert created.status_code == 201
    from apps.competitions.models import Competition

    competition = Competition.objects.get(pk=created.data["id"])
    ada = Participant.objects.create(competition=competition, name="Ada", kind="individual")
    bo = Participant.objects.create(competition=competition, name="Bo", kind="individual")
    cy = Participant.objects.create(competition=competition, name="Cy", kind="individual")
    Participant.objects.create(competition=competition, name="Dee", kind="individual")
    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.COMPLETED, label="Round 1")
    sides = {
        player.name: FixtureSide.objects.create(fixture=fixture, participant=player, position=index)
        for index, player in enumerate((ada, bo, cy))
    }
    stroke = competition.scoring_categories.get(code="stroke")

    def hole(player, unit_index, strokes):
        ScoreEvent.objects.create(
            fixture=fixture,
            side=sides[player],
            scoring_category=stroke,
            quantity=Decimal(strokes),
            unit_index=unit_index,
        )

    for unit in range(16):
        hole("Ada", unit, 4)
        hole("Bo", unit, 4)
        hole("Cy", unit, 5)
    hole("Ada", 16, 4)
    hole("Bo", 16, 5)
    hole("Ada", 17, 4)
    hole("Bo", 17, 3)
    hole("Cy", 16, 5)
    hole("Cy", 17, 5)
    fixture.recalculate_scores()

    fay = Participant.objects.create(competition=competition, name="Fay", kind="individual")
    short = Fixture.objects.create(competition=competition, status=Fixture.Status.COMPLETED, label="Nine holes")
    fay_side = FixtureSide.objects.create(fixture=short, participant=fay, position=0)
    for unit in range(9):
        ScoreEvent.objects.create(
            fixture=short,
            side=fay_side,
            scoring_category=stroke,
            quantity=Decimal(3),
            unit_index=unit,
        )
    short.recalculate_scores()

    names = [row.name for row in compute_standings(competition)]
    assert names == ["Bo", "Ada", "Cy", "Fay", "Dee"]
    rows = {row.name: row for row in compute_standings(competition)}
    assert rows["Ada"].score_for == rows["Bo"].score_for == Decimal("72")
    assert rows["Cy"].score_for == Decimal("90")


def test_locked_preset_refuses_structure_edits(api):
    created = api.post("/api/v1/competitions", {"name": "Locked", "preset": "soccer"}, format="json")
    competition_id = created.data["id"]
    edited = api.patch(
        f"/api/v1/competitions/{competition_id}/points-policy",
        {"win_points": "10", "tiebreakers": ["name"]},
        format="json",
    )
    assert edited.status_code == 403
