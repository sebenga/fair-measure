"""Only the named owner account can delete every competition on the platform."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from apps.competitions.models import Competition
from apps.fixtures.models import Fixture, ScoreEvent
from apps.games.models import Games, GamesEvent

User = get_user_model()
pytestmark = pytest.mark.django_db

URL = "/api/v1/platform/admin/competitions/clear"
OWNER = "sebengamt@gmail.com"


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def platform_owner():
    return User.objects.create_user(email="Sebengamt@Gmail.com", password="pw-123456")


@pytest.fixture
def full_platform(api, user):
    """A demo league with recorded scores, a plain league and a Games event."""

    created = api.post(
        "/api/v1/competitions", {"name": "Demo", "preset": "soccer", "format": "league"}, format="json"
    )
    assert api.post(f"/api/v1/competitions/{created.data['id']}/demo-league", {}, format="json").status_code == 201
    api.post("/api/v1/competitions", {"name": "Office cup", "preset": "kpi"}, format="json")
    games = Games.objects.create(name="Schools Games", owner=user)
    event_competition = Competition.objects.create(name="100 m", owner=user)
    GamesEvent.objects.create(
        games=games, sport_key="athletics", sport_label="Athletics", name="100 m", competition=event_competition
    )
    assert ScoreEvent.objects.exists()
    return games


@override_settings(LEAGUE_RESET_EMAILS=[OWNER], PLATFORM_ADMIN_EMAILS=[])
def test_only_the_named_owner_may_clear(api, user, platform_owner):
    staff = User.objects.create_user(email="staff@example.com", password="pw-123456", is_staff=True)
    api.post("/api/v1/competitions", {"name": "Keep me", "preset": "kpi"}, format="json")

    assert _client(staff).post(URL, {"confirm": "CLEAR ALL LEAGUES"}, format="json").status_code == 403
    assert api.post(URL, {"confirm": "CLEAR ALL LEAGUES"}, format="json").status_code == 403
    assert APIClient().post(URL, {"confirm": "CLEAR ALL LEAGUES"}, format="json").status_code in (401, 403)
    assert Competition.objects.filter(name="Keep me").exists()

    state = lambda client: client.get("/api/v1/platform/releases").data["clear_leagues"]  # noqa: E731
    assert state(_client(platform_owner)) is True
    assert state(_client(staff)) is False
    assert state(api) is False


@override_settings(LEAGUE_RESET_EMAILS=[OWNER])
def test_the_confirmation_phrase_is_required(api, platform_owner):
    api.post("/api/v1/competitions", {"name": "Keep me", "preset": "kpi"}, format="json")

    refused = _client(platform_owner).post(URL, {"confirm": "yes"}, format="json")

    assert refused.status_code == 400
    assert "CLEAR ALL LEAGUES" in str(refused.data)
    assert Competition.objects.filter(name="Keep me").exists()


@override_settings(LEAGUE_RESET_EMAILS=[OWNER])
def test_clearing_removes_every_competition_and_demo_account(user, platform_owner, full_platform):
    demo = Competition.objects.get(name="Demo")
    demo_users = demo.settings_json["demo_league"]["user_ids"]
    assert User.objects.filter(id__in=demo_users).exists()

    cleared = _client(platform_owner).post(URL, {"confirm": " CLEAR ALL LEAGUES "}, format="json")

    assert cleared.status_code == 200, cleared.data
    assert cleared.data["cleared"]["competitions"] == 3
    assert cleared.data["cleared"]["games_events"] == 1
    assert not Competition.objects.exists()
    assert not Fixture.objects.exists()
    assert not ScoreEvent.objects.exists()
    assert not GamesEvent.objects.exists()
    assert Games.objects.filter(pk=full_platform.pk).exists()
    assert not User.objects.filter(id__in=demo_users).exists()
    assert User.objects.filter(pk__in=[user.pk, platform_owner.pk]).count() == 2
