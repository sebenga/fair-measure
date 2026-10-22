from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.fixtures.models import Fixture, FixtureRater, FixtureSide, ScoreEvent

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
