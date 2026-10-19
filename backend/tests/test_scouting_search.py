"""Scouting Phase 5: talent search, saved searches, compare, shortlists and contact."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.notifications.models import Notification
from apps.scouting.discovery_views import run_saved_search_alerts
from apps.scouting.models import (
    ConsentRecord,
    GuardianLink,
    HighlightVideo,
    Organisation,
    PhysicalTestResult,
    PlayerProfile,
    PlayerSport,
    PlayerStatLine,
    ScoutRating,
    ShortlistLog,
)
from apps.scouting.services import grant_role

pytestmark = pytest.mark.django_db
User = get_user_model()
SEASON = timezone.localdate().year


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _years_ago(years: int) -> date:
    today = date.today()
    return date(today.year - years, 3, 1)


def _player(
    name, *, position="striker", age=22, gender="men", region="gauteng", visibility="scouts"
):
    user = User.objects.create_user(
        email=f"{name.lower()}@search.test", password="pw-123456789", display_name=name
    )
    profile = PlayerProfile.objects.create(
        user=user,
        first_name=name,
        last_name="Test",
        date_of_birth=_years_ago(age),
        gender_category=gender,
        region=region,
        visibility=visibility,
    )
    PlayerSport.objects.create(
        profile=profile, sport="soccer", primary_position=position, is_primary=True
    )
    return profile


def _line(profile, **values):
    PlayerStatLine.objects.create(
        user=profile.user,
        sport="soccer",
        season=SEASON,
        competition=None,
        matches=10,
        minutes=900,
        values={key: {"value": value} for key, value in values.items()},
        computed_at=timezone.now(),
    )


def _sprint(profile, value):
    PhysicalTestResult.objects.create(
        profile=profile,
        sport="soccer",
        test_key="sprint_40m",
        value=value,
        unit="s",
        tested_on=date.today(),
    )


@pytest.fixture
def world(db):
    lions = Organisation.objects.create(name="Lions", kind="academy")
    rivals = Organisation.objects.create(name="Rivals", kind="club")
    scout = User.objects.create_user(
        email="scout@search.test", password="pw-123456789", display_name="Scout One"
    )
    mate = User.objects.create_user(
        email="mate@search.test", password="pw-123456789", display_name="Scout Two"
    )
    rival = User.objects.create_user(
        email="rival@search.test", password="pw-123456789", display_name="Rival"
    )
    grant_role(scout, "scout", organisation=lions)
    grant_role(mate, "scout", organisation=lions)
    grant_role(rival, "scout", organisation=rivals)

    fast = _player("Fast", region="western-cape")
    keeper = _player("Keeper", position="goalkeeper", gender="women")
    young = _player("Young", age=16)  # under 18, no consent: never visible
    veteran = _player("Veteran", age=38)
    _sprint(fast, "4.95")
    _sprint(veteran, "5.60")
    _line(fast, goals=12, goals_per_90=1.2)
    _line(veteran, goals=3, goals_per_90=0.3)
    HighlightVideo.objects.create(
        profile=fast, title="Goals reel", url="https://video.example/fast"
    )
    owner = User.objects.create_user(email="owner@search.test", password="pw-123456789")
    national = Competition.objects.create(
        name="National league", owner=owner, sport="soccer", settings_json={"level": "national"}
    )
    team = Participant.objects.create(competition=national, name="Stars", kind="team")
    RosterMember.objects.create(participant=team, name="Fast", user=fast.user)
    school = Competition.objects.create(
        name="Schools cup", owner=owner, sport="soccer", settings_json={"level": "school"}
    )
    other = Participant.objects.create(competition=school, name="Juniors", kind="team")
    RosterMember.objects.create(participant=other, name="Veteran", user=veteran.user)
    for profile, physical, potential, rec in ((fast, 8, 9, "sign"), (veteran, 5, 4, "monitor")):
        ScoutRating.objects.create(
            client_id=uuid.uuid4(),
            profile=profile,
            scout=scout,
            organisation=lions,
            sport="soccer",
            confidence="high",
            area_scores={"physical": physical},
            potential=potential,
            recommendation=rec,
            observed_at=timezone.now(),
        )
    return {
        "lions": lions,
        "rivals": rivals,
        "scout": scout,
        "mate": mate,
        "rival": rival,
        "fast": fast,
        "keeper": keeper,
        "young": young,
        "veteran": veteran,
    }


def _search(user, **filters) -> list[str]:
    response = _client(user).post("/api/v1/scouting/search", {"filters": filters}, format="json")
    assert response.status_code == 200, response.data
    return sorted(row["name"].split()[0] for row in response.json()["results"])


@pytest.mark.parametrize(
    "filters, expected",
    [
        ({}, ["Fast", "Keeper", "Veteran"]),
        ({"q": "fas"}, ["Fast"]),
        ({"sport": "soccer", "position": "goalkeeper"}, ["Keeper"]),
        ({"age_group": "masters"}, ["Veteran"]),
        ({"gender": "women"}, ["Keeper"]),
        ({"region": "western-cape"}, ["Fast"]),
        ({"level": "club"}, ["Fast"]),  # national is above club; school is below it
        ({"level": "school"}, ["Fast", "Veteran"]),
        ({"has_video": True}, ["Fast"]),
        ({"sport": "soccer", "tests": [{"key": "sprint_40m", "op": "lt", "value": 5.2}]}, ["Fast"]),
        (
            {"sport": "soccer", "stats": [{"key": "goals_per_90", "op": "gte", "value": 1}]},
            ["Fast"],
        ),
        ({"sport": "soccer", "areas": [{"key": "physical", "min": 7}]}, ["Fast"]),
        ({"sport": "soccer", "potential_min": 5}, ["Fast"]),
        ({"sport": "soccer", "recommendation": "monitor"}, ["Veteran"]),
    ],
    ids=[
        "everyone visible",
        "name",
        "position",
        "age group",
        "gender",
        "region",
        "competition level",
        "level at or above",
        "has video",
        "test value",
        "match stat",
        "area score",
        "potential",
        "recommendation",
    ],
)
def test_each_filter_type_works(world, filters, expected):
    assert _search(world["scout"], **filters) == expected


def test_percentile_filter_needs_a_big_enough_cohort(world):
    for index in range(20):
        peer = _player(f"Peer{index}")
        _line(peer, goals=index)
    # 21 senior male strikers: 20 peers on 0-19 goals and Fast on 12. Fast beats 12 and ties
    # two (Peer12 and himself): (12 + 1) / 21 = 61.9th percentile.
    top = _search(world["scout"], sport="soccer", percentiles=[{"key": "goals", "min": 90}])
    assert top == ["Peer18", "Peer19"]
    assert "Fast" in _search(
        world["scout"], sport="soccer", percentiles=[{"key": "goals", "min": 60}]
    )
    # Only Fast has a sprint time: too few for a percentile, so nobody matches.
    assert (
        _search(world["scout"], sport="soccer", percentiles=[{"key": "sprint_40m", "min": 1}]) == []
    )


def test_ratings_filters_use_only_my_organisation(world):
    assert _search(world["rival"], sport="soccer", potential_min=1) == []
    assert _search(world["mate"], sport="soccer", potential_min=1) == ["Fast", "Veteran"]


def test_bad_filters_are_rejected(world):
    client = _client(world["scout"])
    for filters in (
        {"nonsense": 1},
        {"tests": [{"key": "sprint_40m", "op": "lt", "value": 5}]},  # no sport
        {"sport": "soccer", "tests": [{"key": "bench_press", "op": "lt", "value": 5}]},
        {"sport": "soccer", "stats": [{"key": "goals", "op": "about", "value": 5}]},
        {"position": "striker"},
    ):
        assert (
            client.post("/api/v1/scouting/search", {"filters": filters}, format="json").status_code
            == 400
        )
    player = world["fast"].user
    assert (
        _client(player).post("/api/v1/scouting/search", {"filters": {}}, format="json").status_code
        == 403
    )


def test_an_under_18_without_consent_never_appears(world):
    young = world["young"]
    young.visibility = "public"
    young.save()
    assert "Young" not in _search(world["scout"])
    assert "Young" not in _search(
        world["scout"], sport="soccer", position="striker", age_group="u17"
    )
    guardian = User.objects.create_user(email="parent@search.test", password="pw-123456789")
    GuardianLink.objects.create(
        profile=young, guardian=guardian, invited_email=guardian.email, status="active"
    )
    ConsentRecord.objects.create(
        profile=young,
        given_by=guardian,
        given_as="guardian",
        action="granted",
        visibility="scouts",
        sections=["identity", "sports"],
    )
    assert "Young" in _search(world["scout"])


# --- Saved searches --------------------------------------------------------------------


def test_saved_search_alerts_name_only_new_matches(world, settings):
    client = _client(world["scout"])
    saved = client.post(
        "/api/v1/scouting/saved-searches",
        {
            "name": "Fast strikers",
            "filters": {
                "sport": "soccer",
                "tests": [{"key": "sprint_40m", "op": "lt", "value": 5.2}],
            },
        },
        format="json",
    )
    assert saved.status_code == 201, saved.data
    assert saved.json()["matches"] == 1
    assert run_saved_search_alerts() == 0, "players who already matched are not news"
    _sprint(world["veteran"], "5.10")  # the veteran now runs fast enough
    settings.INTERNAL_API_TOKEN = "alerts-token"
    response = APIClient().post(
        "/internal/scouting/saved-searches",
        {},
        format="json",
        HTTP_AUTHORIZATION="Bearer alerts-token",
    )
    assert response.status_code == 200 and response.json()["alerts"] == 1
    alert = Notification.objects.get(user=world["scout"], kind="scouting.search_match")
    assert alert.title == 'New match for "Fast strikers"' and "Veteran" in alert.body
    assert run_saved_search_alerts() == 0
    off = client.patch(
        f"/api/v1/scouting/saved-searches/{saved.json()['id']}", {"alerts": False}, format="json"
    )
    assert off.json()["alerts"] is False


# --- Compare --------------------------------------------------------------------


def test_compare_two_to_four_players(world):
    client = _client(world["scout"])
    ids = f"{world['fast'].id},{world['veteran'].id}"
    data = client.get("/api/v1/scouting/compare", {"profiles": ids, "sport": "soccer"}).json()
    assert [area["key"] for area in data["areas"]] == [
        "physical",
        "technical",
        "tactical",
        "mental",
        "context",
    ]
    fast = next(row for row in data["players"] if row["id"] == str(world["fast"].id))
    assert fast["areas"]["physical"] == 8.0 and fast["potential"] == 9.0
    assert fast["stats"]["goals"]["value"] == 12 and fast["tests"]["sprint_40m"]["best"] == 4.95
    assert (
        client.get("/api/v1/scouting/compare", {"profiles": str(world["fast"].id)}).status_code
        == 400
    )
    hidden = f"{world['fast'].id},{world['young'].id}"
    assert client.get("/api/v1/scouting/compare", {"profiles": hidden}).status_code == 404


# --- Shortlists --------------------------------------------------------------------


def test_the_shortlist_audit_log_is_written(world):
    client = _client(world["scout"])
    shortlist = client.post(
        "/api/v1/scouting/shortlists", {"name": "U23 strikers"}, format="json"
    ).json()
    base = f"/api/v1/scouting/shortlists/{shortlist['id']}"
    entry = client.post(f"{base}/entries", {"profile": str(world["fast"].id)}, format="json").json()
    assert (
        client.post(
            f"{base}/entries", {"profile": str(world["fast"].id)}, format="json"
        ).status_code
        == 400
    )
    client.patch(f"{base}/entries/{entry['id']}", {"status": "trial_booked"}, format="json")
    assigned = client.patch(
        f"{base}/entries/{entry['id']}", {"assigned_to": str(world["mate"].id)}, format="json"
    )
    assert assigned.json()["assigned_to"]["name"] == "Scout Two"
    assert (
        client.patch(
            f"{base}/entries/{entry['id']}", {"assigned_to": str(world["rival"].id)}, format="json"
        ).status_code
        == 400
    )
    client.post(
        f"{base}/entries/{entry['id']}/comments",
        {"body": "Book him for the March trial."},
        format="json",
    )
    assert client.delete(f"{base}/entries/{entry['id']}").status_code == 204
    log = client.get(f"{base}/log").json()
    assert [row["action"] for row in reversed(log)] == [
        "added",
        "status",
        "assigned",
        "commented",
        "removed",
    ]
    assert log[-2]["before"] == {"status": "watching"} and log[-2]["after"] == {
        "status": "trial_booked"
    }
    row = ShortlistLog.objects.first()
    row.action = "added"
    with pytest.raises(ValueError):
        row.save()
    assert _client(world["rival"]).get(base).status_code == 404
    assert _client(world["mate"]).get(base).status_code == 200


# --- Contact requests --------------------------------------------------------------------


def test_contact_requests_reach_the_guardian_for_minors(world):
    young = world["young"]
    guardian = User.objects.create_user(email="mum@search.test", password="pw-123456789")
    GuardianLink.objects.create(
        profile=young, guardian=guardian, invited_email=guardian.email, status="active"
    )
    ConsentRecord.objects.create(
        profile=young,
        given_by=guardian,
        given_as="guardian",
        action="granted",
        visibility="scouts",
        sections=["identity", "sports"],
    )
    client = _client(world["scout"])
    shortlist = client.post(
        "/api/v1/scouting/shortlists", {"name": "Juniors"}, format="json"
    ).json()
    client.post(
        f"/api/v1/scouting/shortlists/{shortlist['id']}/entries",
        {"profile": str(young.id)},
        format="json",
    )
    sent = client.post(
        f"/api/v1/scouting/profiles/{young.id}/contact",
        {"message": "Lions Academy would like to invite Young to a trial."},
        format="json",
    )
    assert sent.status_code == 201, sent.data
    assert sent.json()["to_guardian"] is True
    assert Notification.objects.filter(user=guardian, kind="scouting.contact_request").count() == 1
    assert not Notification.objects.filter(
        user=young.user, kind="scouting.contact_request"
    ).exists()
    request_id = sent.json()["id"]
    assert (
        _client(young.user)
        .post(
            f"/api/v1/scouting/contact-requests/{request_id}/respond",
            {"accept": True},
            format="json",
        )
        .status_code
        == 403
    )
    inbox = _client(guardian).get("/api/v1/scouting/contact-requests").json()
    assert inbox[0]["can_respond"] is True and inbox[0]["player"]["name"] == "Young Test"
    answer = _client(guardian).post(
        f"/api/v1/scouting/contact-requests/{request_id}/respond",
        {"accept": True, "message": "Happy to talk through the app."},
        format="json",
    )
    assert answer.json()["status"] == "accepted"
    assert (
        Notification.objects.filter(user=world["scout"], kind="scouting.contact_answer").count()
        == 1
    )
    detail = client.get(f"/api/v1/scouting/shortlists/{shortlist['id']}").json()
    assert detail["entries"][0]["status"] == "contacted"
    assert young.user.email not in str(detail) and guardian.email not in str(sent.json())


def test_an_adult_answers_their_own_contact_request(world):
    client = _client(world["scout"])
    sent = client.post(
        f"/api/v1/scouting/profiles/{world['fast'].id}/contact",
        {"message": "We would like to see you at a Lions trial."},
        format="json",
    ).json()
    assert sent["to_guardian"] is False
    assert (
        Notification.objects.filter(
            user=world["fast"].user, kind="scouting.contact_request"
        ).count()
        == 1
    )
    again = client.post(
        f"/api/v1/scouting/profiles/{world['fast'].id}/contact",
        {"message": "Second request please."},
        format="json",
    )
    assert again.status_code == 400, "one waiting request per organisation"
    declined = _client(world["fast"].user).post(
        f"/api/v1/scouting/contact-requests/{sent['id']}/respond", {"accept": False}, format="json"
    )
    assert declined.json()["status"] == "declined"
    assert world["fast"].user.email not in str(declined.json())
