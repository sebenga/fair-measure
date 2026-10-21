from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.fixtures.models import Fixture, FixtureSide, PlayerMatchRating

User = get_user_model()


@pytest.fixture
def match(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Rated league", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    sides = []
    fixture = Fixture.objects.create(competition=competition, label="Round 1", duration_minutes=90)
    for index, name in enumerate(("Home", "Away")):
        team = Participant.objects.create(competition=competition, name=name, kind="team")
        for number in range(1, 4):
            player = User.objects.create_user(email=f"{name.lower()}{number}@example.com", password="pw-123456")
            RosterMember.objects.create(participant=team, name=f"{name} {number}", number=number, user=player)
        sides.append(FixtureSide.objects.create(fixture=fixture, participant=team, position=index))
    return competition, fixture, sides


def _url(fixture, tail=""):
    return f"/api/v1/competitions/{fixture.competition_id}/fixtures/{fixture.id}/raters{tail}"


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_raters_come_from_profiles_who_are_not_playing(api, match):
    _, fixture, _ = match
    player = User.objects.get(email="home1@example.com")
    blocked = api.post(_url(fixture), {"user": str(player.id)}, format="json")
    assert blocked.status_code == 400
    assert "Active players" in str(blocked.data)

    judge = User.objects.create_user(email="judge@example.com", password="pw-123456", display_name="Judge Dee")
    search = api.get(_url(fixture), {"q": "example.com"}).data["candidates"]
    emails = {row["email"] for row in search}
    assert "judge@example.com" in emails
    assert "home1@example.com" not in emails

    added = api.post(_url(fixture), {"user": str(judge.id)}, format="json")
    assert added.status_code == 201
    assert added.data["raters"][0]["name"] == "Judge Dee"
    assert added.data["enough"] is False
    assert api.post(_url(fixture), {"user": str(judge.id)}, format="json").status_code == 400

    outsider = _client(User.objects.create_user(email="fan@example.com", password="pw-123456"))
    assert outsider.post(_url(fixture), {"user": str(judge.id)}, format="json").status_code == 403


def test_ratings_need_two_raters_and_publish_the_average(api, match):
    _, fixture, sides = match
    first = User.objects.create_user(email="r1@example.com", password="pw-123456")
    second = User.objects.create_user(email="r2@example.com", password="pw-123456")
    api.post(_url(fixture), {"user": str(first.id)}, format="json")
    fixture.status = Fixture.Status.LIVE
    fixture.save()
    player = RosterMember.objects.get(name="Home 1")
    body = {"ratings": [{"player": str(player.id), "rating": "7"}]}

    one = _client(first)
    assert one.put(_url(fixture, "/ratings"), body, format="json").status_code == 400  # only one rater

    api.post(_url(fixture), {"user": str(second.id)}, format="json")
    assert one.put(_url(fixture, "/ratings"), body, format="json").status_code == 200
    assert not PlayerMatchRating.objects.filter(fixture=fixture, player=player).exists()

    two = _client(second)
    saved = two.put(_url(fixture, "/ratings"), {"ratings": [{"player": str(player.id), "rating": "8"}]}, format="json")
    assert saved.status_code == 200
    home = saved.data["teams"][0]["players"]
    row = next(item for item in home if item["player_id"] == str(player.id))
    assert row["average"] == "7.5"
    assert row["count"] == 2
    assert row["mine"] == "8.0"
    assert PlayerMatchRating.objects.get(fixture=fixture, player=player).rating == 7.5

    assert two.put(_url(fixture, "/ratings"), {"ratings": [{"player": str(player.id), "rating": "11"}]}, format="json").status_code == 400
    assert api.put(_url(fixture, "/ratings"), body, format="json").status_code == 403  # admin is not a rater

    api.delete(_url(fixture) + f"?user={second.id}")
    assert not PlayerMatchRating.objects.filter(fixture=fixture, player=player).exists()


def test_ratings_are_judged_from_the_player_stats_on_the_raters_tab(api, match):
    competition, fixture, sides = match
    fixture.status = Fixture.Status.LIVE
    fixture.save()
    goal = competition.scoring_categories.get(code="goal")
    assist = competition.scoring_categories.get(code="assist")
    player = RosterMember.objects.get(name="Home 1")
    api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(sides[0].id), "scoring_category": str(goal.id), "player": str(player.id)},
        format="json",
    )
    blocked_stat = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(sides[0].id), "scoring_category": str(assist.id), "player": str(player.id)},
        format="json",
    )
    assert blocked_stat.status_code == 400
    assert "Raters tab" in str(blocked_stat.data)
    recorded = api.post(_url(fixture, "/stats"), {"player": str(player.id), "code": "assist"}, format="json")
    assert recorded.status_code == 200, recorded.data
    blocked = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(sides[0].id), "scoring_category": str(goal.id), "player": str(player.id), "rating": "9"},
        format="json",
    )
    assert blocked.status_code == 400
    assert "Raters tab" in str(blocked.data)

    first = User.objects.create_user(email="r1@example.com", password="pw-123456")
    second = User.objects.create_user(email="r2@example.com", password="pw-123456")
    api.post(_url(fixture), {"user": str(first.id)}, format="json")
    api.post(_url(fixture), {"user": str(second.id)}, format="json")
    sheet = api.get(_url(fixture)).data
    row = next(item for item in sheet["teams"][0]["players"] if item["player_id"] == str(player.id))
    counts = {item["label"]: item["count"] for item in row["stats"]}
    assert counts["Assist"] == "1"
    assert counts["Goal"] == "1"
    assert counts["Tackle won"] == "0"
    assert any(item["recorded"] for item in row["stats"] if item["label"] == "Goal")
    saved = _client(first).put(
        _url(fixture, "/ratings"),
        {"ratings": [{"player": str(player.id), "rating": "8"}]},
        format="json",
    )
    assert saved.status_code == 200
    labels = {item["label"] for item in saved.data["teams"][0]["players"][0]["stats"]}
    assert {"Minutes", "Assist", "Goal"} <= labels
