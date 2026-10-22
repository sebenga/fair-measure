from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Membership, Participant, RosterMember
from apps.core.permissions import Role
from apps.fixtures.models import (
    Fixture,
    FixtureLineup,
    FixtureReferee,
    FixtureSide,
    LineupEntry,
    PlayerAppearance,
)

User = get_user_model()


@pytest.fixture
def league(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Match day league", "preset": "soccer", "format": "league"},
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    teams = []
    for name in ("Home XI", "Away XI"):
        team = Participant.objects.create(competition=competition, name=name, kind="team")
        for index in range(14):
            RosterMember.objects.create(participant=team, name=f"{name} {index + 1}", number=index + 1)
        teams.append(team)
    fixture = Fixture.objects.create(competition=competition, label="Round 1", duration_minutes=90)
    sides = [
        FixtureSide.objects.create(fixture=fixture, participant=team, position=index)
        for index, team in enumerate(teams)
    ]
    return competition, fixture, sides


def _url(fixture, tail=""):
    return f"/api/v1/competitions/{fixture.competition_id}/fixtures/{fixture.id}/{tail}"


def _squad(side):
    return list(RosterMember.objects.filter(participant=side.participant).order_by("number"))


def _sheet(side, formation="4-4-2"):
    squad = _squad(side)
    return {
        "formation": formation,
        "captain": str(squad[0].id),
        "starters": [{"player": str(member.id), "slot": index} for index, member in enumerate(squad[:11])],
        "bench": [{"player": str(member.id)} for member in squad[11:]],
    }


def test_team_sheet_uses_the_preset_formations_and_limits(api, league):
    _, fixture, sides = league
    day = api.get(_url(fixture, "team-sheets")).data
    assert day["enabled"] is True
    assert day["config"]["starters"] == 11
    assert day["config"]["min_personnel"] == 11
    assert day["config"]["max_substitutions"] == 5
    four_four_two = next(item for item in day["formations"] if item["key"] == "4-4-2")
    assert [slot["label"] for slot in four_four_two["slots"]] == ["GK"] + ["DEF"] * 4 + ["MID"] * 4 + ["FWD"] * 2

    saved = api.put(_url(fixture, f"team-sheets/{sides[0].id}"), _sheet(sides[0]), format="json")
    assert saved.status_code == 200, saved.data
    home = saved.data["sides"][0]
    assert home["lineup"]["formation"] == "4-4-2"
    assert len(home["lineup"]["starters"]) == 11
    assert len(home["lineup"]["bench"]) == 3
    assert home["lineup"]["starters"][0]["position"] == "GK"
    assert home["lineup"]["captain_id"] == str(_squad(sides[0])[0].id)

    bad = _sheet(sides[0], formation="4-4-3")
    assert api.put(_url(fixture, f"team-sheets/{sides[0].id}"), bad, format="json").status_code == 400

    too_many = _sheet(sides[0])
    too_many["starters"].append({"player": too_many["bench"].pop()["player"]})
    assert api.put(_url(fixture, f"team-sheets/{sides[0].id}"), too_many, format="json").status_code == 400

    too_few = _sheet(sides[0])
    too_few["starters"] = too_few["starters"][:10]
    short = api.put(_url(fixture, f"team-sheets/{sides[0].id}"), too_few, format="json")
    assert short.status_code == 400
    assert "at least 11" in str(short.data)

    stranger = _sheet(sides[0])
    stranger["bench"].append({"player": str(_squad(sides[1])[0].id)})
    assert api.put(_url(fixture, f"team-sheets/{sides[0].id}"), stranger, format="json").status_code == 400


def test_team_manager_picks_before_kickoff_and_sheet_locks_after(api, league, other_user):
    competition, fixture, sides = league
    Membership.objects.create(competition=competition, user=other_user, role=Role.MEMBER)
    manager = APIClient()
    manager.force_authenticate(other_user)

    assert manager.put(_url(fixture, f"team-sheets/{sides[0].id}"), _sheet(sides[0]), format="json").status_code == 403
    sides[0].participant.managed_by = other_user
    sides[0].participant.save()
    assert manager.put(_url(fixture, f"team-sheets/{sides[0].id}"), _sheet(sides[0]), format="json").status_code == 200
    assert manager.put(_url(fixture, f"team-sheets/{sides[1].id}"), _sheet(sides[1]), format="json").status_code == 403

    fixture.status = Fixture.Status.LIVE
    fixture.save()
    locked = manager.put(_url(fixture, f"team-sheets/{sides[0].id}"), _sheet(sides[0]), format="json")
    assert locked.status_code == 403
    assert "locked" in str(locked.data)
    assert api.put(_url(fixture, f"team-sheets/{sides[0].id}"), _sheet(sides[0]), format="json").status_code == 200


def test_substitutions_follow_the_bench_and_the_limit(api, league):
    _, fixture, sides = league
    api.put(_url(fixture, f"team-sheets/{sides[0].id}"), _sheet(sides[0]), format="json")
    squad = _squad(sides[0])

    def sub(off, on, minute=60):
        return api.post(
            _url(fixture, "substitutions"),
            {"side": str(sides[0].id), "player_off": str(off.id), "player_on": str(on.id), "minute": minute},
            format="json",
        )

    assert sub(squad[1], squad[11]).status_code == 400  # not kicked off yet
    fixture.status = Fixture.Status.LIVE
    fixture.save()

    first = sub(squad[1], squad[11], minute=55)
    assert first.status_code == 201, first.data
    home = first.data["sides"][0]
    assert str(squad[11].id) in home["on_field"]
    assert str(squad[1].id) not in home["on_field"]
    assert home["substitutions_left"] == 4

    assert sub(squad[1], squad[12]).status_code == 400  # already off
    assert sub(squad[2], squad[1]).status_code == 400  # cannot come back on
    assert sub(squad[2], squad[11]).status_code == 400  # already on
    assert sub(squad[2], _squad(sides[1])[12]).status_code == 400  # other team

    assert sub(squad[2], squad[12], minute=70).status_code == 201
    assert sub(squad[3], squad[13], minute=80).status_code == 201
    assert sub(squad[4], squad[1]).status_code == 400  # bench is empty

    minutes = dict(PlayerAppearance.objects.filter(fixture=fixture).values_list("player_id", "minutes"))
    assert minutes[squad[0].id] == 90
    assert minutes[squad[1].id] == 55
    assert minutes[squad[11].id] == 35
    assert minutes[squad[13].id] == 10


def test_substitution_limit_and_delete_order(api, league):
    _, fixture, sides = league
    sheet = _sheet(sides[0])
    squad = _squad(sides[0])
    extra = [RosterMember.objects.create(participant=sides[0].participant, name=f"Extra {i}") for i in range(4)]
    sheet["bench"] += [{"player": str(member.id)} for member in extra]
    assert api.put(_url(fixture, f"team-sheets/{sides[0].id}"), sheet, format="json").status_code == 200
    fixture.status = Fixture.Status.LIVE
    fixture.save()

    bench = squad[11:] + extra
    ids = []
    for index in range(5):
        made = api.post(
            _url(fixture, "substitutions"),
            {"side": str(sides[0].id), "player_off": str(squad[index + 1].id), "player_on": str(bench[index].id)},
            format="json",
        )
        assert made.status_code == 201, made.data
        ids.append(made.data["substitutions"][-1]["id"])
    sixth = api.post(
        _url(fixture, "substitutions"),
        {"side": str(sides[0].id), "player_off": str(squad[7].id), "player_on": str(bench[5].id)},
        format="json",
    )
    assert sixth.status_code == 400
    assert "all 5" in str(sixth.data)

    removed = api.delete(_url(fixture, f"substitutions/{ids[0]}"))
    assert removed.status_code == 200
    assert removed.data["sides"][0]["substitutions_left"] == 1


def test_cannot_delete_a_substitution_a_later_one_depends_on(api, league):
    _, fixture, sides = league
    api.put(_url(fixture, f"team-sheets/{sides[0].id}"), _sheet(sides[0]), format="json")
    squad = _squad(sides[0])
    fixture.status = Fixture.Status.LIVE
    fixture.save()
    first = api.post(
        _url(fixture, "substitutions"),
        {"side": str(sides[0].id), "player_off": str(squad[1].id), "player_on": str(squad[11].id)},
        format="json",
    ).data["substitutions"][-1]["id"]
    api.post(
        _url(fixture, "substitutions"),
        {"side": str(sides[0].id), "player_off": str(squad[11].id), "player_on": str(squad[12].id)},
        format="json",
    )
    assert api.delete(_url(fixture, f"substitutions/{first}")).status_code == 400


def test_post_match_report_is_written_by_officials_after_the_result(api, league, other_user):
    competition, fixture, sides = league
    for side in sides:
        api.put(_url(fixture, f"team-sheets/{side.id}"), _sheet(side), format="json")
    report = {"summary": "A tight game settled late.", "attendance": 420, "conditions": "Dry, firm pitch"}
    assert api.put(_url(fixture, "report"), report, format="json").status_code == 400

    Membership.objects.create(competition=competition, user=other_user, role=Role.MEMBER)
    FixtureReferee.objects.create(fixture=fixture, user=other_user)
    started = api.post(_url(fixture, "set-status"), {"status": "live"}, format="json")
    assert started.status_code == 200, started.data
    squad = _squad(sides[0])
    api.post(
        _url(fixture, "substitutions"),
        {"side": str(sides[0].id), "player_off": str(squad[9].id), "player_on": str(squad[12].id), "minute": 75},
        format="json",
    )
    goal = competition.scoring_categories.get(code="goal")
    api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(sides[0].id), "scoring_category": str(goal.id), "minute": 88, "player": str(squad[12].id)},
        format="json",
    )
    finished = api.post(_url(fixture, "set-status"), {"status": "completed"}, format="json")
    assert finished.status_code == 200, finished.data

    member = APIClient()
    member.force_authenticate(User.objects.create_user(email="fan@example.com", password="x-password-1"))
    assert member.put(_url(fixture, "report"), report, format="json").status_code == 403
    assert api.put(_url(fixture, "report"), {"summary": ""}, format="json").status_code == 400

    referee = APIClient()
    referee.force_authenticate(other_user)
    written = referee.put(_url(fixture, "report"), report, format="json")
    assert written.status_code == 200, written.data
    data = written.data
    assert data["report"]["attendance"] == 420
    assert data["sides"][0]["score"] == "1"
    assert data["goals"][0]["player"] == squad[12].name
    assert data["substitutions"][0]["minute"] == 75
    assert len(data["sides"][1]["lineup"]["starters"]) == 11
    assert data["can_edit"] is True

    minutes = dict(PlayerAppearance.objects.filter(fixture=fixture).values_list("player_id", "minutes"))
    assert minutes[squad[9].id] == 75
    assert minutes[squad[12].id] == 15
    assert squad[13].id not in minutes


def test_lineup_includes_minutes_and_updated_ratings(api, league):
    from decimal import Decimal

    from apps.fixtures.models import PlayerMatchRating

    _, fixture, sides = league
    saved = api.put(_url(fixture, f"team-sheets/{sides[0].id}"), _sheet(sides[0]), format="json")
    assert saved.status_code == 200, saved.data
    player = _squad(sides[0])[0]
    blank = next(row for row in saved.data["sides"][0]["lineup"]["starters"] if row["player_id"] == str(player.id))
    assert blank["minutes"] is None
    assert blank["rating"] is None

    PlayerAppearance.objects.create(fixture=fixture, player=player, minutes=67)
    PlayerMatchRating.objects.create(fixture=fixture, player=player, rating=Decimal("7.2"))
    day = api.get(_url(fixture, "team-sheets")).data
    starter = next(row for row in day["sides"][0]["lineup"]["starters"] if row["player_id"] == str(player.id))
    assert starter["minutes"] == 67
    assert starter["rating"] == "7.2"


def test_kickoff_needs_both_team_sheets_of_eleven_and_officials(api, league, other_user):
    competition, fixture, sides = league
    detail = f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}"
    problems = api.get(detail).data["kickoff_problems"]
    assert "Pick the match officials before kickoff." in problems
    assert "Submit Home XI's team sheet before kickoff." in problems
    assert "Submit Away XI's team sheet before kickoff." in problems
    assert api.post(_url(fixture, "set-status"), {"status": "live"}, format="json").status_code == 400

    Membership.objects.create(competition=competition, user=other_user, role=Role.MEMBER)
    FixtureReferee.objects.create(fixture=fixture, user=other_user)
    officials_only = api.get(detail).data["kickoff_problems"]
    assert "Pick the match officials before kickoff." not in officials_only
    assert api.post(_url(fixture, "set-status"), {"status": "live"}, format="json").status_code == 400

    api.put(_url(fixture, f"team-sheets/{sides[0].id}"), _sheet(sides[0]), format="json")
    assert api.get(detail).data["kickoff_problems"] == [
        "Submit Away XI's team sheet before kickoff."
    ]

    lineup = FixtureLineup.objects.create(fixture=fixture, side=sides[1])
    for index, member in enumerate(_squad(sides[1])[:10]):
        LineupEntry.objects.create(
            lineup=lineup, player=member, role=LineupEntry.Role.STARTER, order=index
        )
    short = fixture.kickoff_problems()
    assert "Away XI's team sheet needs at least 11 named players." in short
    lineup.delete()

    api.put(_url(fixture, f"team-sheets/{sides[1].id}"), _sheet(sides[1]), format="json")
    started = api.post(_url(fixture, "set-status"), {"status": "live"}, format="json")
    assert started.status_code == 200, started.data
    assert started.data["status"] == "live"
