"""Locked horseball and tent pegging presets."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.engine import settle_fixture
from apps.competitions.models import Competition, Membership, Participant, RosterMember
from apps.competitions.presets import PRESETS, apply_preset
from apps.core.permissions import Role
from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide
from apps.results import services
from apps.results.calculators import evaluate
from apps.results.models import CompetitionOfficial
from apps.standings.services import compute_standings

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --- Horseball ----------------------------------------------------------------------


def test_horseball_is_locked_under_the_fihb():
    preset = PRESETS["horseball"]
    assert preset["locked"] is True
    assert preset["official_results"] is True
    assert preset["governing_body"] == "FIHB"
    assert preset["league_points"] == {"win": 3, "draw": 1, "loss": 0}
    assert preset["tiebreakers"] == ["points", "score_difference", "score_for", "head_to_head"]
    assert preset["match_structure"][0] == {"unit": "half", "count": 2, "minutes": 10}
    assert any(rule["name"] == "Passing rule" for rule in preset["rules"])


def _horseball(fmt: str):
    owner = User.objects.create_user(email=f"hb.{fmt}@test", password="pw-123456789")
    referee = User.objects.create_user(email=f"hb.ref.{fmt}@test", password="pw-123456789")
    response = _client(owner).post(
        "/api/v1/competitions", {"name": "Horseball", "preset": "horseball", "format": fmt}, format="json"
    )
    assert response.status_code == 201, response.data
    competition = Competition.objects.get(pk=response.data["id"])
    assert competition.settings_json["time_limit_minutes"] == 20
    CompetitionOfficial.objects.create(competition=competition, user=referee, title="umpire", appointed_by=owner)
    teams = []
    for name in ("Chevaliers", "Cavaliers"):
        team = Participant.objects.create(competition=competition, name=name, kind="team")
        for number in range(1, 5):
            RosterMember.objects.create(participant=team, name=f"{name} {number}", number=number)
        teams.append(team)
    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    sides = [FixtureSide.objects.create(fixture=fixture, participant=team, position=index) for index, team in enumerate(teams)]
    FixtureReferee.objects.create(fixture=fixture, user=referee)
    return competition, referee, fixture, sides


def _goal(referee, fixture, side, unit, code="goal"):
    category = fixture.competition.scoring_categories.get(code=code)
    return _client(referee).post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": str(category.id),
            "unit_index": unit,
            "player": str(side.participant.roster.first().id),
        },
        format="json",
    )


def test_a_horseball_league_draw_shares_the_points():
    competition, referee, fixture, sides = _horseball("league")
    assert _goal(referee, fixture, sides[0], 0).status_code == 201
    assert _goal(referee, fixture, sides[1], 1, code="penalty-goal").status_code == 201
    _client(referee).post(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/set-status",
        {"status": "completed"},
        format="json",
    )
    table = {row.name: row.points for row in compute_standings(competition)}
    assert table == {"Chevaliers": 1, "Cavaliers": 1}


def test_a_level_horseball_knockout_goes_to_extra_time_then_the_next_goal():
    competition, referee, fixture, sides = _horseball("knockout")
    _goal(referee, fixture, sides[0], 0)
    _goal(referee, fixture, sides[1], 1)
    _goal(referee, fixture, sides[0], 2)  # extra time, first period
    _goal(referee, fixture, sides[1], 3)  # extra time, second period
    for side in sides:
        side.refresh_from_db()
        assert side.outcome == FixtureSide.Outcome.PENDING
    assert _goal(referee, fixture, sides[1], 4).status_code == 201  # sudden death
    assert _goal(referee, fixture, sides[0], 4).status_code == 400
    settle_fixture(fixture)
    for side in sides:
        side.refresh_from_db()
    assert sides[1].outcome == FixtureSide.Outcome.WIN
    assert (sides[0].score, sides[1].score) == (2, 3)


# --- Tent pegging -------------------------------------------------------------------


def _pegging_config(key: str, test: str = "lance") -> dict:
    preset = PRESETS[key]
    config = {**preset["result_config"], "statuses": preset["statuses"]}
    return {**config, **config["tests"][test]}


def test_tent_pegging_presets_are_locked_under_the_itpf():
    for key in ("tent_pegging", "tent_pegging_team"):
        preset = PRESETS[key]
        assert preset["locked"] is True
        assert preset["result_type"] == "points_per_run"
        assert preset["governing_body"] == "ITPF"
        points = {item["key"]: item["points"] for item in preset["result_config"]["outcomes"]}
        assert points == {"carried": 6, "drawn": 4, "strike": 2, "miss": 0}
    assert PRESETS["tent_pegging_team"]["result_config"]["team_size"] == 4
    assert PRESETS["tent_pegging"]["participant_type"] == "combination"


def test_the_points_table_and_over_time_runs_score_nothing():
    config = _pegging_config("tent_pegging")
    result = evaluate(
        "points_per_run",
        {
            "a": {"runs": [{"outcome": "carried", "time": "6.3"}, {"outcome": "drawn", "time": "6.0"}, {"outcome": "strike", "time": "6.4"}]},
            "slow": {"runs": [{"outcome": "carried", "time": "6.5"}, {"outcome": "carried", "time": "6.2"}, {"outcome": "miss", "time": "6.0"}]},
        },
        config,
    )
    assert result["a"][2].primary == Decimal("12")
    assert result["slow"][2].primary == Decimal("6")
    sword = evaluate(
        "points_per_run", {"a": {"runs": [{"outcome": "carried", "time": "6.8"}]}}, _pegging_config("tent_pegging", "sword")
    )
    assert sword["a"][2].primary == Decimal("6")


def test_a_team_total_is_the_sum_of_its_riders_and_a_run_off_breaks_a_tie():
    config = _pegging_config("tent_pegging_team")
    four = {
        f"Rider {index}": [{"outcome": "carried", "time": "6.0"}, {"outcome": "strike", "time": "6.1"}]
        for index in range(1, 5)
    }
    result = evaluate(
        "points_per_run",
        {
            "team": {"riders": four},
            "level": {"riders": four, "run_off": [{"outcome": "drawn", "time": "6.0"}]},
        },
        config,
    )
    assert result["team"][2].primary == Decimal("32")
    assert result["level"][2].primary == Decimal("32")
    assert result["level"][0] == 1 and result["team"][0] == 2


def test_a_team_event_lists_its_riders_on_the_sheet():
    owner = User.objects.create_user(email="tp.owner@test", password="pw-123456789")
    judge = User.objects.create_user(email="tp.judge@test", password="pw-123456789")
    competition = Competition.objects.create(name="Pegging", owner=owner, sport="tent pegging", status="active")
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    apply_preset(competition, "tent_pegging_team")
    CompetitionOfficial.objects.create(competition=competition, user=judge, title="judge", appointed_by=owner)
    team = Participant.objects.create(competition=competition, name="Lancers", kind="team")
    RosterMember.objects.create(participant=team, name="Ayesha", number=1)
    RosterMember.objects.create(participant=team, name="Bilal", number=2)
    fixture = services.create_event(competition, label="Team lance", actor=judge)
    sheet = _client(judge).get(f"/api/v1/fixtures/{fixture.id}/results")
    assert sheet.status_code == 200, sheet.data
    assert sheet.data["entries"][0]["riders"] == ["Ayesha", "Bilal", "Rider 3", "Rider 4"]
