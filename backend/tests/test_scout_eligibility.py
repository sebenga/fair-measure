"""Scouts only see profiles with every field filled in, and the profile says so."""

from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.scouting.models import PlayerProfile, PlayerSport
from apps.scouting.sample import fill_sample_profile
from apps.scouting.services import ACCOUNT_FIELDS, SCOUTING_FIELDS, grant_role

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def player():
    user = User.objects.create_user(email="lerato@eligible.test", password="pw-123456789")
    profile = PlayerProfile.objects.create(
        user=user,
        first_name="Lerato",
        last_name="Mokoena",
        date_of_birth=date(date.today().year - 21, 5, 1),
        visibility=PlayerProfile.Visibility.SCOUTS,
    )
    return user, profile


@pytest.fixture
def scout():
    user = User.objects.create_user(email="scout@eligible.test", password="pw-123456789")
    grant_role(user, "scout")
    return _client(user)


def test_an_incomplete_profile_is_hidden_from_scouts_and_lists_what_is_missing(player, scout):
    user, profile = player
    mine = _client(user).get("/api/v1/scouting/profile").data
    readiness = mine["scout_readiness"]
    assert readiness["eligible"] is False
    assert readiness["total"] == len(ACCOUNT_FIELDS) + len(SCOUTING_FIELDS)
    missing = {row["key"] for row in readiness["missing"]}
    assert {"id_number", "phone", "region", "school_or_club", "sport"} <= missing
    assert "website" not in missing
    assert "date_of_birth" not in missing
    assert mine["effective_visibility"] == "private"

    assert scout.get(f"/api/v1/scouting/profiles/{profile.id}").status_code == 404
    search = scout.post("/api/v1/scouting/search", {"filters": {}}, format="json")
    results = search.json()["results"]
    assert str(profile.id) not in {row["id"] for row in results}


def test_a_complete_profile_becomes_eligible_and_visible(player, scout):
    user, profile = player
    fill_sample_profile(profile)
    mine = _client(user).get("/api/v1/scouting/profile").data
    assert mine["scout_readiness"]["eligible"] is True
    assert mine["scout_readiness"]["missing"] == []
    assert mine["effective_visibility"] == "scouts"
    assert scout.get(f"/api/v1/scouting/profiles/{profile.id}").status_code == 200


def test_clearing_one_field_hides_the_profile_again(player, scout):
    user, profile = player
    fill_sample_profile(profile)
    user.refresh_from_db()
    user.city = ""
    user.save(update_fields=["city"])
    readiness = _client(user).get("/api/v1/scouting/profile").data["scout_readiness"]
    assert [row["key"] for row in readiness["missing"]] == ["city"]
    assert scout.get(f"/api/v1/scouting/profiles/{profile.id}").status_code == 404


def test_a_sport_needs_a_main_position(player):
    user, profile = player
    fill_sample_profile(profile)
    profile.sports.all().delete()
    PlayerSport.objects.create(
        profile=profile, sport="soccer", primary_position="", is_primary=True
    )
    readiness = _client(user).get("/api/v1/scouting/profile").data["scout_readiness"]
    assert [row["key"] for row in readiness["missing"]] == ["sport"]


def test_the_id_number_is_compulsory_on_the_profile(player):
    user, _profile = player
    client = _client(user)
    blank = client.patch("/api/v1/auth/me", {"id_number": "  "}, format="json")
    assert blank.status_code == 400
    saved = client.patch("/api/v1/auth/me", {"id_number": "0101015800085"}, format="json")
    assert saved.status_code == 200, saved.data
    assert saved.data["id_number"] == "0101015800085"
    # Other changes still save without resending it.
    assert client.patch("/api/v1/auth/me", {"city": "Durban"}, format="json").status_code == 200
