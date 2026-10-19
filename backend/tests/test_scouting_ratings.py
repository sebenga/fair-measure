"""Scouting Phase 4: the scout rating tool."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.fixtures.models import Fixture, FixtureSide
from apps.scouting.models import Organisation, PlayerProfile, PlayerSport, ScoutRating
from apps.scouting.services import grant_role

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _scout(email: str, organisation: Organisation):
    user = User.objects.create_user(
        email=email, password="pw-123456789", display_name=email.split("@")[0]
    )
    grant_role(user, "scout", organisation=organisation)
    return user


@pytest.fixture
def world(db):
    lions = Organisation.objects.create(name="Lions Academy", kind="academy")
    rivals = Organisation.objects.create(name="Rival FC", kind="club")
    player = User.objects.create_user(email="player@ratings.test", password="pw-123456789")
    today = date.today()
    profile = PlayerProfile.objects.create(
        user=player,
        first_name="Thabo",
        last_name="Nkosi",
        date_of_birth=date(today.year - 22, 3, 1),
        gender_category="men",
        visibility="scouts",
    )
    PlayerSport.objects.create(
        profile=profile, sport="soccer", primary_position="striker", is_primary=True
    )
    return {
        "lions": lions,
        "rivals": rivals,
        "profile": profile,
        "player": player,
        "a1": _scout("a1@lions.test", lions),
        "a2": _scout("a2@lions.test", lions),
        "b1": _scout("b1@rivals.test", rivals),
    }


def _rating(world, **fields) -> dict:
    return {
        "client_id": str(uuid.uuid4()),
        "profile": str(world["profile"].id),
        "sport": "soccer",
        "mode": "quick",
        "confidence": "medium",
        "watched": "live",
        "area_scores": {"physical": 6, "technical": 7, "tactical": 5, "mental": 8, "context": 4},
        "current_ability": 6,
        "potential": 8,
        "recommendation": "trial",
        "notes": "Sharp in the box, drifts out of games.",
        **fields,
    }


def test_an_offline_rating_syncs_once(world):
    client = _client(world["a1"])
    rating = _rating(world, observed_at=(timezone.now() - timedelta(hours=3)).isoformat())
    first = client.post(
        "/api/v1/scouting/ratings/sync", {"ratings": [rating, rating]}, format="json"
    )
    assert first.status_code == 200, first.data
    assert [row["status"] for row in first.json()["results"]] == ["created", "duplicate"]
    again = client.post("/api/v1/scouting/ratings/sync", {"ratings": [rating]}, format="json")
    assert again.json()["results"][0]["status"] == "duplicate"
    single = client.post("/api/v1/scouting/ratings", rating, format="json")
    assert single.status_code == 200  # already stored
    assert ScoutRating.objects.count() == 1
    stored = ScoutRating.objects.get()
    assert stored.observed_at < timezone.now() - timedelta(hours=2), "keeps when it was rated"


def test_a_bad_rating_in_a_batch_does_not_stop_the_rest(world):
    client = _client(world["a1"])
    good = _rating(world)
    bad = _rating(world, area_scores={"physical": 11})
    response = client.post("/api/v1/scouting/ratings/sync", {"ratings": [bad, good]}, format="json")
    results = response.json()["results"]
    assert results[0]["status"] == "rejected" and "1 to 10" in results[0]["error"]
    assert results[1]["status"] == "created"


def test_ratings_are_visible_only_to_the_same_organisation(world):
    _client(world["a1"]).post("/api/v1/scouting/ratings", _rating(world), format="json")
    url = f"/api/v1/scouting/profiles/{world['profile'].id}/ratings"
    same = _client(world["a2"]).get(url).json()
    assert len(same["ratings"]) == 1 and same["ratings"][0]["notes"].startswith("Sharp")
    other = _client(world["b1"]).get(url).json()
    assert other["ratings"] == [] and other["summary"]["scouts"] == 0
    assert _client(world["player"]).get(url).status_code == 403
    profile_page = _client(world["player"]).get("/api/v1/scouting/profile")
    assert "Sharp in the box" not in profile_page.content.decode()
    scout_view = _client(world["b1"]).get(f"/api/v1/scouting/profiles/{world['profile'].id}")
    assert "Sharp in the box" not in scout_view.content.decode()


def test_weighted_averages_use_each_scouts_latest_rating(world):
    a1, a2 = _client(world["a1"]), _client(world["a2"])
    earlier = (timezone.now() - timedelta(days=30)).isoformat()
    a1.post(
        "/api/v1/scouting/ratings",
        _rating(world, observed_at=earlier, area_scores={"physical": 2}),
        format="json",
    )
    a1.post(
        "/api/v1/scouting/ratings",
        _rating(
            world, confidence="high", area_scores={"physical": 8}, current_ability=7, potential=9
        ),
        format="json",
    )
    a2.post(
        "/api/v1/scouting/ratings",
        _rating(
            world, confidence="low", area_scores={"physical": 4}, current_ability=3, potential=5
        ),
        format="json",
    )
    summary = a2.get(f"/api/v1/scouting/profiles/{world['profile'].id}/ratings").json()["summary"]
    physical = next(row for row in summary["areas"] if row["key"] == "physical")
    assert physical == {
        "key": "physical",
        "label": "Physical",
        "average": 7.0,
        "scouts": 2,
    }  # (8x3 + 4x1) / 4
    assert summary["current_ability"] == 6.0  # (7x3 + 3x1) / 4
    assert summary["potential"] == 8.0  # (9x3 + 5x1) / 4
    assert summary["scouts"] == 2 and summary["ratings"] == 3
    assert [row["count"] for row in summary["recommendations"] if row["key"] == "trial"] == [2]
    assert len(summary["progress"]) == 3, "every dated rating stays for the progress chart"


def test_skipping_attributes_is_allowed_in_full_mode(world):
    client = _client(world["a1"])
    full = _rating(
        world,
        mode="full",
        area_scores={},
        attribute_scores={
            "finishing": 9,
            "first_touch": 7,
            "heading": None,
            "speed": 6,
            "dribbling": "",
        },
        current_ability=None,
        recommendation="",
    )
    response = client.post("/api/v1/scouting/ratings", full, format="json")
    assert response.status_code == 201, response.data
    data = response.json()
    assert data["attribute_scores"] == {"finishing": 9, "first_touch": 7, "speed": 6}
    assert data["areas"] == {"technical": 8.0, "physical": 6.0}

    keeper_only = _rating(world, mode="full", area_scores={}, attribute_scores={"gk_handling": 6})
    assert client.post("/api/v1/scouting/ratings", keeper_only, format="json").status_code == 400
    quick_with_attributes = _rating(world, attribute_scores={"finishing": 9})
    assert (
        client.post("/api/v1/scouting/ratings", quick_with_attributes, format="json").status_code
        == 400
    )
    empty = _rating(world, area_scores={}, current_ability=None, potential=None, recommendation="")
    assert client.post("/api/v1/scouting/ratings", empty, format="json").status_code == 400


def test_only_scouts_rate_and_records_are_never_changed(world):
    stranger = User.objects.create_user(email="fan@ratings.test", password="pw-123456789")
    assert (
        _client(stranger)
        .post("/api/v1/scouting/ratings", _rating(world), format="json")
        .status_code
        == 403
    )
    response = _client(world["a1"]).post("/api/v1/scouting/ratings", _rating(world), format="json")
    rating = ScoutRating.objects.get(pk=response.json()["id"])
    rating.notes = "edited"
    with pytest.raises(ValueError):
        rating.save()
    hidden = PlayerProfile.objects.filter(pk=world["profile"].pk)
    hidden.update(visibility="private")
    assert (
        _client(world["a1"])
        .post("/api/v1/scouting/ratings", _rating(world), format="json")
        .status_code
        == 400
    )


def test_fixture_context_clips_and_the_rate_screen_context(world):
    owner = User.objects.create_user(email="owner@ratings.test", password="pw-123456789")
    competition = Competition.objects.create(name="Ratings league", owner=owner, sport="soccer")
    team = Participant.objects.create(competition=competition, name="Hawks", kind="team")
    other = Participant.objects.create(competition=competition, name="Owls", kind="team")
    RosterMember.objects.create(participant=team, name="Thabo", user=world["player"])
    played = Fixture.objects.create(
        competition=competition, label="Week 1", scheduled_at=timezone.now()
    )
    FixtureSide.objects.create(fixture=played, participant=team, position=0)
    FixtureSide.objects.create(fixture=played, participant=other, position=1)
    elsewhere = Fixture.objects.create(competition=competition, label="Week 2")
    FixtureSide.objects.create(fixture=elsewhere, participant=other, position=0)

    client = _client(world["a1"])
    context = client.get(f"/api/v1/scouting/profiles/{world['profile'].id}/rating-context").json()
    assert [row["id"] for row in context["fixtures"]] == [str(played.id)]
    assert context["sports"][0] == {"key": "soccer", "label": "Soccer", "position": "striker"}
    assert len(context["profile"]["code"]) == 8

    with_fixture = _rating(
        world,
        fixture=str(played.id),
        clips=[
            {"url": "https://video.example/match", "at_seconds": 754, "note": "Near-post finish"}
        ],
    )
    response = client.post("/api/v1/scouting/ratings", with_fixture, format="json")
    assert response.status_code == 201, response.data
    assert response.json()["fixture"]["label"] == "Week 1"
    assert response.json()["clips"][0]["at_seconds"] == 754
    wrong = _rating(world, fixture=str(elsewhere.id))
    assert client.post("/api/v1/scouting/ratings", wrong, format="json").status_code == 400
    bad_clip = _rating(world, clips=[{"url": "not a link", "at_seconds": 3}])
    assert client.post("/api/v1/scouting/ratings", bad_clip, format="json").status_code == 400


def test_qr_code_and_short_code_lookup(world):
    qr = APIClient().get(f"/api/v1/scouting/profiles/{world['profile'].id}/qr")
    assert qr.status_code == 200 and qr["Content-Type"] == "image/svg+xml"
    assert qr.content.startswith(b"<?xml") and b"<svg" in qr.content
    code = qr["X-Profile-Code"]
    found = _client(world["a1"]).get("/api/v1/scouting/profiles/lookup", {"code": code.lower()})
    assert found.status_code == 200 and found.json()["id"] == str(world["profile"].id)
    assert (
        _client(world["player"]).get("/api/v1/scouting/profiles/lookup", {"code": code}).status_code
        == 403
    )
    assert (
        _client(world["a1"]).get("/api/v1/scouting/profiles/lookup", {"code": "ABC"}).status_code
        == 400
    )
