from __future__ import annotations

from decimal import Decimal

import pytest

from apps.competitions.models import Competition, RosterMember, ScoringCategory, Stage
from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def goal(competition) -> ScoringCategory:
    return ScoringCategory.objects.create(
        competition=competition, name="Goal", code="goal", points=Decimal("1")
    )


def _live_game(competition, participants, *, overtime=30, knockout=False) -> Fixture:
    stage = None
    if knockout:
        competition.format = Competition.Format.KNOCKOUT
        competition.save(update_fields=["format"])
    fixture = Fixture.objects.create(
        competition=competition,
        stage=stage,
        status=Fixture.Status.LIVE,
        phase="first_half",
        duration_minutes=90,
        overtime_minutes=overtime,
    )
    for index, participant in enumerate(participants[:2]):
        FixtureSide.objects.create(fixture=fixture, participant=participant, position=index)
        for number in range(1, 6):
            RosterMember.objects.create(
                participant=participant, name=f"{participant.name} {number}", number=number
            )
    return fixture


def _url(fixture, tail: str) -> str:
    return f"/api/v1/competitions/{fixture.competition_id}/fixtures/{fixture.id}/{tail}"


def _act(api, fixture, action: str):
    return api.post(_url(fixture, "phase"), {"action": action}, format="json")


def _detail(response) -> str:
    return str(response.data)


def _score(fixture, side_index: int, goal) -> None:
    side = fixture.sides.order_by("position")[side_index]
    ScoreEvent.objects.create(fixture=fixture, side=side, scoring_category=goal, quantity=1)
    fixture.recalculate_scores()


def test_halves_end_in_order_and_the_game_only_ends_in_the_second_half(
    api, competition, participants
):
    fixture = _live_game(competition, participants)
    assert api.get(_url(fixture, "")[:-1]).data["phase"] == "first_half"

    early = _act(api, fixture, "end_game")
    assert early.status_code == 400
    assert "first half" in _detail(early)
    blocked = api.post(_url(fixture, "set-status"), {"status": "completed"}, format="json")
    assert blocked.status_code == 400

    assert _act(api, fixture, "end_half").data["phase"] == "half_time"
    assert _act(api, fixture, "end_half").status_code == 400
    assert _act(api, fixture, "start_second_half").data["phase"] == "second_half"
    again = _act(api, fixture, "end_half")
    assert again.status_code == 400
    assert "End game" in _detail(again)

    ended = _act(api, fixture, "end_game")
    assert ended.status_code == 200, ended.data
    assert ended.data["status"] == "completed"
    assert ended.data["phase"] == "full_time"


def test_a_level_knockout_goes_to_extra_time_then_penalties(
    api, competition, participants, goal
):
    fixture = _live_game(competition, participants, knockout=True)
    _score(fixture, 0, goal)
    _score(fixture, 1, goal)
    _act(api, fixture, "end_half")
    _act(api, fixture, "start_second_half")

    full_time = _act(api, fixture, "end_game")
    assert full_time.data["status"] == "live"
    assert full_time.data["phase"] == "extra_time"
    assert _act(api, fixture, "start_extra_time").data["phase"] == "extra_first"
    assert _act(api, fixture, "end_game").status_code == 400
    _act(api, fixture, "end_half")
    assert _act(api, fixture, "start_second_half").data["phase"] == "extra_second"

    shootout = _act(api, fixture, "end_game")
    assert shootout.data["phase"] == "penalties"
    assert shootout.data["status"] == "live"
    state = shootout.data["shootout"]
    home = str(fixture.sides.order_by("position").first().id)
    assert state["next_side"] == home
    assert len(state["eligible"][home]) == 5
    closing = api.post(_url(fixture, "set-status"), {"status": "completed"}, format="json")
    assert closing.status_code == 400
    sneaky = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": home, "scoring_category": str(goal.id), "quantity": "1"},
        format="json",
    )
    assert sneaky.status_code == 400
    assert "shootout" in str(sneaky.data)


def test_the_shootout_uses_the_line_up_and_settles_the_winner(
    api, competition, participants
):
    fixture = _live_game(competition, participants, overtime=0, knockout=True)
    _act(api, fixture, "end_half")
    _act(api, fixture, "start_second_half")
    assert _act(api, fixture, "end_game").data["phase"] == "penalties"

    home_side, away_side = list(fixture.sides.order_by("position"))
    home_players = list(home_side.participant.roster.order_by("number"))
    away_players = list(away_side.participant.roster.order_by("number"))

    def kick(side, player, scored):
        return api.post(
            _url(fixture, "shootout"),
            {"side": str(side.id), "player": str(player.id), "scored": scored},
            format="json",
        )

    wrong_turn = kick(away_side, away_players[0], True)
    assert wrong_turn.status_code == 400
    outsider = kick(home_side, away_players[0], True)
    assert outsider.status_code == 400

    assert kick(home_side, home_players[0], True).status_code == 200
    assert kick(away_side, away_players[0], False).status_code == 200
    repeat = kick(home_side, home_players[0], True)
    assert repeat.status_code == 400
    assert "once" in _detail(repeat)

    # Undo the last kick, then replay it.
    assert api.delete(_url(fixture, "shootout")).data["shootout"]["taken"][str(away_side.id)] == 0
    kick(away_side, away_players[0], False)

    for round_index in range(1, 3):
        kick(home_side, home_players[round_index], True)
        last = kick(away_side, away_players[round_index], False)
    # 3-0 with two kicks each left: home cannot be caught.
    assert last.data["status"] == "completed"
    assert last.data["phase"] == "full_time"
    assert last.data["shootout"]["winner"] == str(home_side.id)
    outcomes = {side.id: side.outcome for side in fixture.sides.all()}
    assert outcomes[home_side.id] == FixtureSide.Outcome.WIN
    assert outcomes[away_side.id] == FixtureSide.Outcome.LOSS


def test_a_decided_knockout_ends_at_full_time(api, competition, participants, goal):
    fixture = _live_game(competition, participants, knockout=True)
    _score(fixture, 0, goal)
    _act(api, fixture, "end_half")
    _act(api, fixture, "start_second_half")
    ended = _act(api, fixture, "end_game")
    assert ended.data["status"] == "completed"


def test_a_cup_stage_counts_as_a_knockout(api, competition, participants, goal):
    competition.format = Competition.Format.LEAGUE_KNOCKOUT
    competition.save(update_fields=["format"])
    cup = Stage.objects.create(competition=competition, name="Cup", kind=Stage.Kind.KNOCKOUT)
    fixture = _live_game(competition, participants)
    fixture.stage = cup
    fixture.save(update_fields=["stage"])
    _act(api, fixture, "end_half")
    _act(api, fixture, "start_second_half")
    assert _act(api, fixture, "end_game").data["phase"] == "extra_time"
