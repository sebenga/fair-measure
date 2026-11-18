from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.fixtures.models import (
    Fixture,
    FixtureLineup,
    FixtureRater,
    FixtureReferee,
    FixtureSide,
    LineupEntry,
    ScoreEvent,
)

User = get_user_model()


@pytest.fixture
def match(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Caution league", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    home = Participant.objects.create(competition=competition, name="Home", kind="team")
    away = Participant.objects.create(competition=competition, name="Away", kind="team")
    player = RosterMember.objects.create(participant=home, name="Booked", number=4)
    fixture = Fixture.objects.create(
        competition=competition, label="Round 1", status=Fixture.Status.LIVE, duration_minutes=90
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    from apps.fixtures.models import FixtureReferee

    FixtureReferee.objects.create(
        fixture=fixture,
        user=competition.owner,
        role=FixtureReferee.Role.REFEREE,
        status=FixtureReferee.Status.ACCEPTED,
    )
    return competition, fixture, home_side, player


def _codes(api, competition):
    detail = api.get(f"/api/v1/competitions/{competition.id}").data
    return {item["code"]: item["id"] for item in detail["scoring_categories"]}


def _card(api, fixture, side, player, category, minute):
    return api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": category,
            "quantity": "1",
            "player": str(player.id),
            "minute": minute,
        },
        format="json",
    )


def test_two_yellow_cards_become_a_red(api, match):
    competition, fixture, side, player = match
    codes = _codes(api, competition)

    first = _card(api, fixture, side, player, codes["yellow-card"], 18)
    assert first.status_code == 201, first.data
    reds = ScoreEvent.objects.filter(fixture=fixture, scoring_category__code="red-card")
    assert reds.count() == 0

    second = _card(api, fixture, side, player, codes["yellow-card"], 40)
    assert second.status_code == 201, second.data
    red = ScoreEvent.objects.get(fixture=fixture, scoring_category__code="red-card")
    assert red.player_id == player.id
    assert red.minute == 40
    assert red.note == "Second yellow"

    third = _card(api, fixture, side, player, codes["yellow-card"], 70)
    assert third.status_code == 400


def test_team_sheet_marks_each_players_cards(api, match):
    competition, fixture, side, player = match
    codes = _codes(api, competition)
    clean = RosterMember.objects.create(participant=side.participant, name="Clean", number=7)
    lineup = FixtureLineup.objects.create(fixture=fixture, side=side)
    for order, member in enumerate((player, clean)):
        LineupEntry.objects.create(
            lineup=lineup, player=member, role=LineupEntry.Role.STARTER, slot=order, position="MF", order=order
        )
    url = f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/team-sheets"

    def cards():
        sheet = api.get(url).data
        starters = next(item for item in sheet["sides"] if item["side_id"] == str(side.id))["lineup"]["starters"]
        return {row["name"]: row["cards"] for row in starters}

    assert cards() == {
        "Booked": {"yellow": 0, "upgraded_yellow": 0, "red": 0},
        "Clean": {"yellow": 0, "upgraded_yellow": 0, "red": 0},
    }

    _card(api, fixture, side, player, codes["yellow-card"], 18)
    assert cards()["Booked"] == {"yellow": 1, "upgraded_yellow": 0, "red": 0}

    _card(api, fixture, side, player, codes["yellow-card"], 40)
    assert cards() == {
        "Booked": {"yellow": 2, "upgraded_yellow": 0, "red": 1},
        "Clean": {"yellow": 0, "upgraded_yellow": 0, "red": 0},
    }


def test_a_red_card_stops_the_players_rating(api, match):
    competition, fixture, side, player = match
    codes = _codes(api, competition)
    first = User.objects.create_user(email="r1@cards.test", password="pw-123456")
    second = User.objects.create_user(email="r2@cards.test", password="pw-123456")
    FixtureRater.objects.create(fixture=fixture, user=first)
    FixtureRater.objects.create(fixture=fixture, user=second)

    _card(api, fixture, side, player, codes["yellow-card"], 12)
    _card(api, fixture, side, player, codes["yellow-card"], 33)

    rater = APIClient()
    rater.force_authenticate(user=first)
    url = f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/raters"
    sheet = rater.get(url).data
    row = next(item for item in sheet["teams"][0]["players"] if item["player_id"] == str(player.id))
    assert row["sent_off"] is True
    assert row["rating_locked"] is True

    blocked = rater.put(
        f"{url}/ratings",
        {"ratings": [{"player": str(player.id), "rating": "6"}]},
        format="json",
    )
    assert blocked.status_code == 400
    assert "sent off" in str(blocked.data).lower()

    stats = rater.post(f"{url}/stats", {"player": str(player.id), "code": "assist"}, format="json")
    assert stats.status_code == 400


@pytest.fixture
def rugby_match(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Rugby cards", "preset": "rugby_union", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    home = Participant.objects.create(competition=competition, name="Home", kind="team")
    away = Participant.objects.create(competition=competition, name="Away", kind="team")
    player = RosterMember.objects.create(participant=home, name="Flanker", number=7)
    fixture = Fixture.objects.create(
        competition=competition, label="Round 1", status=Fixture.Status.LIVE, duration_minutes=80
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    lineup = FixtureLineup.objects.create(fixture=fixture, side=home_side)
    LineupEntry.objects.create(
        lineup=lineup, player=player, role=LineupEntry.Role.STARTER, slot=0, position="FL", order=0
    )
    FixtureReferee.objects.create(
        fixture=fixture,
        user=competition.owner,
        role=FixtureReferee.Role.REFEREE,
        status=FixtureReferee.Status.ACCEPTED,
    )
    return competition, fixture, home_side, player


def test_rugby_yellow_is_a_ten_minute_sin_bin(api, rugby_match):
    competition, fixture, side, player = rugby_match
    codes = _codes(api, competition)
    assert "upgraded-yellow-card" in codes
    sheet = competition.settings_json["team_sheet"]
    assert sheet["min_squad"] == 17
    assert sheet["max_substitutions"] == 8
    assert sheet["number_layout"] == "rugby_15"
    assert sheet["starter_numbers"] == list(range(1, 16))
    assert sheet["bench_numbers"] == list(range(16, 24))
    assert sheet.get("formations") in ([], None)

    booked = _card(api, fixture, side, player, codes["yellow-card"], 12)
    assert booked.status_code == 201, booked.data

    sheet = api.get(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/team-sheets",
        {"minute": 15},
    ).data
    assert sheet["discipline_style"] == "rugby"
    starter = sheet["sides"][0]["lineup"]["starters"][0]
    assert starter["sin_binned"] is True
    assert starter["sin_bin"]["until_minute"] == 22
    assert starter["on_field"] is False

    back = api.get(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/team-sheets",
        {"minute": 22},
    ).data
    returned = back["sides"][0]["lineup"]["starters"][0]
    assert returned["sin_binned"] is False
    assert returned["on_field"] is True


def test_rugby_upgraded_yellow_is_twenty_minutes_and_two_yellows_send_off(api, rugby_match):
    competition, fixture, side, player = rugby_match
    codes = _codes(api, competition)

    upgraded = _card(api, fixture, side, player, codes["upgraded-yellow-card"], 8)
    assert upgraded.status_code == 201, upgraded.data
    mid = api.get(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/team-sheets",
        {"minute": 20},
    ).data["sides"][0]["lineup"]["starters"][0]
    assert mid["sin_binned"] is True
    assert mid["sin_bin"]["until_minute"] == 28

    other = RosterMember.objects.create(participant=side.participant, name="Lock", number=4)
    LineupEntry.objects.create(
        lineup=FixtureLineup.objects.get(side=side),
        player=other,
        role=LineupEntry.Role.STARTER,
        slot=1,
        position="LK",
        order=1,
    )
    first = _card(api, fixture, side, other, codes["yellow-card"], 30)
    second = _card(api, fixture, side, other, codes["yellow-card"], 41)
    assert first.status_code == 201, first.data
    assert second.status_code == 201, second.data
    assert ScoreEvent.objects.filter(
        fixture=fixture, player=other, scoring_category__code="red-card", note="Second yellow"
    ).exists()
    sheet = api.get(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/team-sheets",
        {"minute": 50},
    ).data
    lock = next(row for row in sheet["sides"][0]["lineup"]["starters"] if row["name"] == "Lock")
    assert lock["sent_off"] is True
    assert lock["on_field"] is False
