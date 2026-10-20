"""Locked polo presets: handicap start, chukkas, golden goal, penalties and awards."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.engine import settle_fixture
from apps.competitions.models import Competition, Membership, Participant, RosterMember
from apps.competitions.presets import PRESETS
from apps.core.permissions import Role
from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide, ScoreEvent
from apps.results.models import CompetitionOfficial
from apps.standings.services import compute_standings, refresh_standings

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _league(preset="polo_handicap", fmt="league", chukkas=None):
    owner = User.objects.create_user(email=f"{preset}.{fmt}.owner@polo.test", password="pw-123456789")
    umpire = User.objects.create_user(email=f"{preset}.{fmt}.umpire@polo.test", password="pw-123456789")
    body = {"name": "Polo Cup", "preset": preset, "format": fmt}
    if chukkas:
        body["unit_count"] = chukkas
    response = _client(owner).post("/api/v1/competitions", body, format="json")
    assert response.status_code == 201, response.data
    competition = Competition.objects.get(pk=response.data["id"])
    CompetitionOfficial.objects.create(
        competition=competition, user=umpire, title="umpire", appointed_by=owner
    )
    teams = {}
    for name, handicaps in (("La Dolfina", [4, 3, 2, 1]), ("Ellerston", [2, 2, 1, 0])):
        team = Participant.objects.create(competition=competition, name=name, kind="team")
        for number, handicap in enumerate(handicaps, start=1):
            RosterMember.objects.create(
                participant=team, name=f"{name} {number}", number=number, handicap=handicap
            )
        teams[name] = team
    return competition, owner, umpire, teams


def _match(competition, umpire, teams):
    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    sides = {}
    for position, (name, team) in enumerate(teams.items()):
        sides[name] = FixtureSide.objects.create(fixture=fixture, participant=team, position=position)
    FixtureReferee.objects.create(fixture=fixture, user=umpire)
    return fixture, sides


def _score(umpire, fixture, side, code, unit=0, player=True, **extra):
    category = fixture.competition.scoring_categories.get(code=code)
    body = {"side": str(side.id), "scoring_category": str(category.id), "unit_index": unit, **extra}
    if player:
        body["player"] = str(side.participant.roster.first().id)
    return _client(umpire).post(f"/api/v1/fixtures/{fixture.id}/events", body, format="json")


def test_both_polo_presets_are_locked_and_follow_the_fip():
    for key in ("polo_handicap", "polo_open"):
        preset = PRESETS[key]
        assert preset["locked"] is True
        assert preset["official_results"] is True
        assert preset["governing_body"] == "FIP"
        assert "HPA" in preset["rulebook"]
        assert "SAPA" in preset["local_body"]
        assert preset["league_points"] == {"win": 3, "draw": 1, "loss": 0}
        assert preset["unit_count_options"]["options"] == [4, 5, 6, 8]
        assert preset["roster_numbers"] == [1, 2, 3, 4]
        assert {award["key"] for award in preset["match_awards"]} == {"mvp", "best_playing_pony"}
    assert PRESETS["polo_handicap"]["head_start"]["max"] == 10
    assert "head_start" not in PRESETS["polo_open"]


def test_the_number_of_chukkas_is_chosen_at_creation_and_then_locked():
    competition, owner, _umpire, _teams = _league(chukkas=4)
    structure = competition.settings_json["match_structure"]
    assert structure[0] == {"unit": "chukka", "count": 4, "minutes": 7}
    assert competition.settings_json["time_limit_minutes"] == 28
    assert competition.settings_json["unit_count"] == 4

    bad = _client(owner).post(
        "/api/v1/competitions",
        {"name": "Odd", "preset": "polo_open", "unit_count": 7},
        format="json",
    )
    assert bad.status_code == 400
    elsewhere = _client(owner).post(
        "/api/v1/competitions",
        {"name": "Soccer", "preset": "soccer", "unit_count": 4},
        format="json",
    )
    assert elsewhere.status_code == 400

    changed = _client(owner).patch(
        f"/api/v1/competitions/{competition.id}",
        {
            "settings_json": {
                **competition.settings_json,
                "match_structure": [{"unit": "chukka", "count": 8, "minutes": 7}],
            }
        },
        format="json",
    )
    assert changed.status_code == 200
    competition.refresh_from_db()
    assert competition.settings_json["match_structure"][0]["count"] == 4


def test_the_lower_handicap_team_starts_with_the_difference():
    competition, _owner, umpire, teams = _league()
    fixture, sides = _match(competition, umpire, teams)
    detail = _client(umpire).get(f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}")
    starts = {side["participant"]["name"]: side["head_start"] for side in detail.data["sides"]}
    assert starts == {"La Dolfina": "0", "Ellerston": "5"}

    for _ in range(3):
        assert _score(umpire, fixture, sides["La Dolfina"], "goal").status_code == 201
    sides["La Dolfina"].refresh_from_db()
    sides["Ellerston"].refresh_from_db()
    assert sides["La Dolfina"].score == 3
    assert sides["Ellerston"].score == 5
    assert sides["Ellerston"].head_start == 5

    # Once scored, a later handicap change does not move this match.
    RosterMember.objects.filter(participant=teams["Ellerston"]).update(handicap=3)
    settle_fixture(fixture)
    sides["Ellerston"].refresh_from_db()
    assert sides["Ellerston"].score == 5

    done = _client(umpire).post(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/set-status",
        {"status": "completed"},
        format="json",
    )
    assert done.status_code == 200
    table = {row.name: row for row in compute_standings(competition)}
    assert table["Ellerston"].points == 3
    assert table["Ellerston"].score_difference == 2
    assert table["Ellerston"].net_score_difference == -3
    assert table["La Dolfina"].net_score_difference == 3
    saved = {row.participant.name: row for row in refresh_standings(competition)}
    assert saved["Ellerston"].detail["net_score_difference"] == "-3"
    assert saved["Ellerston"].detail["head_start_for"] == "5"


def test_a_shorter_match_scales_the_handicap_start_to_the_nearest_half_goal():
    competition, _owner, umpire, teams = _league(chukkas=4)
    fixture, sides = _match(competition, umpire, teams)
    settle_fixture(fixture)
    sides["Ellerston"].refresh_from_db()
    # 5 goals over 6 chukkas, scaled to 4: 3.33, which is 3.5 to the nearest half.
    assert sides["Ellerston"].head_start == Decimal("3.5")


def test_open_polo_starts_level():
    competition, _owner, umpire, teams = _league(preset="polo_open")
    fixture, sides = _match(competition, umpire, teams)
    settle_fixture(fixture)
    for side in sides.values():
        side.refresh_from_db()
        assert side.score == 0


def test_a_golden_goal_chukka_ends_on_the_first_goal():
    competition, _owner, umpire, teams = _league(preset="polo_open", fmt="knockout")
    fixture, sides = _match(competition, umpire, teams)
    for name in teams:
        for _ in range(2):
            assert _score(umpire, fixture, sides[name], "goal", unit=5).status_code == 201
    for side in sides.values():
        side.refresh_from_db()
        assert side.outcome == FixtureSide.Outcome.PENDING

    extra = 6  # the first extra chukka, after six chukkas
    assert _score(umpire, fixture, sides["Ellerston"], "goal", unit=extra).status_code == 201
    late = _score(umpire, fixture, sides["La Dolfina"], "goal", unit=extra)
    assert late.status_code == 400
    assert "golden goal" in str(late.data).lower()

    # Even a goal slipped in afterwards does not count.
    ScoreEvent.objects.create(
        fixture=fixture,
        side=sides["La Dolfina"],
        scoring_category=competition.scoring_categories.get(code="goal"),
        unit_index=extra + 1,
    )
    settle_fixture(fixture)
    for side in sides.values():
        side.refresh_from_db()
    assert sides["Ellerston"].outcome == FixtureSide.Outcome.WIN
    assert sides["Ellerston"].score == 3
    assert sides["La Dolfina"].score == 2


def test_a_penalty_one_adds_a_goal_without_a_shooter():
    competition, _owner, umpire, teams = _league(preset="polo_open")
    fixture, sides = _match(competition, umpire, teams)
    assert _score(umpire, fixture, sides["La Dolfina"], "penalty-1", player=False).status_code == 201
    assert _score(umpire, fixture, sides["La Dolfina"], "penalty-3", player=False).status_code == 201
    assert _score(umpire, fixture, sides["La Dolfina"], "goal", player=False).status_code == 400
    sides["La Dolfina"].refresh_from_db()
    assert sides["La Dolfina"].score == 1


def test_roster_numbers_and_handicaps_stay_in_range():
    competition, owner, _umpire, teams = _league()
    member = teams["La Dolfina"].roster.first()
    path = f"/api/v1/competitions/{competition.id}/participants/{teams['La Dolfina'].id}/roster/{member.id}"
    assert _client(owner).patch(path, {"handicap": "11"}, format="json").status_code == 400
    assert _client(owner).patch(path, {"handicap": "-3"}, format="json").status_code == 400
    assert _client(owner).patch(path, {"number": 5}, format="json").status_code == 400
    ok = _client(owner).patch(path, {"handicap": "7", "number": 1}, format="json")
    assert ok.status_code == 200, ok.data
    assert ok.data["handicap"] == "7.0"


def test_umpires_name_the_mvp_and_best_playing_pony_and_stats_follow():
    competition, owner, umpire, teams = _league(preset="polo_open")
    fixture, sides = _match(competition, umpire, teams)
    star = teams["La Dolfina"].roster.get(number=2)
    for code in ("goal", "goal", "penalty-goal"):
        category = competition.scoring_categories.get(code=code)
        _client(umpire).post(
            f"/api/v1/fixtures/{fixture.id}/events",
            {"side": str(sides["La Dolfina"].id), "scoring_category": str(category.id), "player": str(star.id)},
            format="json",
        )
    path = f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/awards"
    assert _client(owner).put(path, {"key": "mvp", "player": str(star.id)}, format="json").status_code == 403
    assert _client(umpire).put(path, {"key": "mvp"}, format="json").status_code == 200
    given = _client(umpire).put(path, {"key": "mvp", "player": str(star.id)}, format="json")
    assert given.status_code == 200
    pony = _client(umpire).put(
        path, {"key": "best_playing_pony", "name": "Cuartetera", "player": str(star.id)}, format="json"
    )
    assert pony.status_code == 200
    awards = {row["key"]: row["winner"] for row in pony.data["awards"]}
    assert awards["mvp"]["player_name"] == star.name
    assert awards["best_playing_pony"]["name"] == "Cuartetera"
    assert _client(umpire).put(path, {"key": "best_horse", "name": "X"}, format="json").status_code == 400

    _client(umpire).post(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/set-status",
        {"status": "completed"},
        format="json",
    )
    stats = _client(owner).get(f"/api/v1/competitions/{competition.id}/player-stats").data
    assert [column["key"] for column in stats["columns"]] == ["goals", "conversions", "mvp"]
    top = stats["rows"][0]
    assert top["name"] == star.name
    assert top["values"] == {"goals": "3", "conversions": "1", "mvp": "1"}


def test_membership_is_owner_role():
    competition, owner, _umpire, _teams = _league()
    assert Membership.objects.get(competition=competition, user=owner).role == Role.OWNER
