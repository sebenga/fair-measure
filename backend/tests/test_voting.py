"""Custom points boards: members vote; private (secret) hides tallies until close."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.competitions.models import Competition, Membership, Participant, Vote
from apps.core.permissions import Role
from apps.fixtures.models import ScoreEvent

pytestmark = pytest.mark.django_db
User = get_user_model()


def _points_board(
    api,
    *,
    visibility="secret",
    votes_per_member=1,
    accumulate_as_vote_count=False,
    category_points=1,
):
    settings = {
        "points_by_voting": True,
        "voting_visibility": visibility,
        "score_all_on_criterion": False,
        "votes_per_member": votes_per_member,
        "accumulate_as_vote_count": accumulate_as_vote_count,
    }
    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Vote board",
            "preset": "custom",
            "format": "freeform",
            "scoring_basis": "criteria",
            "scoring_categories": [
                {
                    "name": "Popular pick",
                    "code": "pick",
                    "points": category_points,
                    "affects_score": True,
                }
            ],
            "settings_json": settings,
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    a = Participant.objects.create(competition=competition, name="Alpha", kind="individual")
    b = Participant.objects.create(competition=competition, name="Beta", kind="individual")
    category = competition.scoring_categories.get(code="pick")
    return competition, a, b, category


def test_member_vote_secret_hides_tallies_until_close(api, user):
    competition, alpha, beta, category = _points_board(api, visibility="secret")
    member = User.objects.create_user(email="voter@example.com", password="x")
    Membership.objects.create(competition=competition, user=member, role=Role.MEMBER)

    opened = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id), "title": "Week 1"},
        format="json",
    )
    assert opened.status_code == 201, opened.data
    round_id = opened.data["id"]
    assert opened.data["visibility"] == "secret"
    # Admins can always see running tallies while members cannot.
    assert opened.data["tallies_hidden"] is False

    api.force_authenticate(member)
    cast = api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {"participant": str(alpha.id)},
        format="json",
    )
    assert cast.status_code == 200, cast.data
    assert cast.data["vote"]["participant_id"] == str(alpha.id)
    assert cast.data["round"]["tallies_hidden"] is True
    assert cast.data["round"]["tallies"] is None
    assert cast.data["round"]["my_vote"]["participant_id"] == str(alpha.id)

    outsider = User.objects.create_user(email="outsider@example.com", password="x")
    api.force_authenticate(outsider)
    denied = api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {"participant": str(beta.id)},
        format="json",
    )
    assert denied.status_code == 403

    api.force_authenticate(user)
    closed = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/close",
        {},
        format="json",
    )
    assert closed.status_code == 200, closed.data
    assert closed.data["status"] == "closed"
    assert closed.data["tallies_hidden"] is False
    assert closed.data["tallies"][0]["participant_id"] == str(alpha.id)
    assert closed.data["tallies"][0]["votes"] == 1
    assert ScoreEvent.objects.filter(fixture__competition=competition).count() == 1
    event = ScoreEvent.objects.get(fixture__competition=competition)
    assert event.quantity == 1
    assert event.side.participant_id == alpha.id


def test_visible_voting_shows_live_tallies(api, user):
    competition, alpha, beta, category = _points_board(api, visibility="visible")
    member = User.objects.create_user(email="visible-voter@example.com", password="x")
    Membership.objects.create(competition=competition, user=member, role=Role.MEMBER)

    opened = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id)},
        format="json",
    )
    assert opened.status_code == 201, opened.data
    round_id = opened.data["id"]
    assert opened.data["visibility"] == "visible"
    assert opened.data["tallies_hidden"] is False

    api.force_authenticate(member)
    cast = api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {"participant": str(beta.id)},
        format="json",
    )
    assert cast.status_code == 200, cast.data
    assert cast.data["round"]["tallies"][0]["participant_id"] == str(beta.id)
    assert Vote.objects.filter(round_id=round_id).count() == 1


def test_open_round_can_override_competition_visibility(api, user):
    """Admin may open a public round even when the board default is private."""
    competition, alpha, beta, category = _points_board(api, visibility="secret")
    member = User.objects.create_user(email="override-voter@example.com", password="x")
    Membership.objects.create(competition=competition, user=member, role=Role.MEMBER)

    opened = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id), "visibility": "visible", "title": "Public this week"},
        format="json",
    )
    assert opened.status_code == 201, opened.data
    assert opened.data["visibility"] == "visible"
    round_id = opened.data["id"]

    api.force_authenticate(member)
    cast = api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {"participant": str(alpha.id)},
        format="json",
    )
    assert cast.status_code == 200, cast.data
    assert cast.data["round"]["tallies_hidden"] is False
    assert cast.data["round"]["tallies"][0]["participant_id"] == str(alpha.id)

    api.force_authenticate(user)
    private = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id), "visibility": "secret"},
        format="json",
    )
    assert private.status_code == 201, private.data
    assert private.data["visibility"] == "secret"

    bad = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id), "visibility": "public"},
        format="json",
    )
    assert bad.status_code == 400
    detail = bad.data.get("error", bad.data).get("detail", bad.data)
    assert "visibility" in detail


def test_split_vote_budget_awards_quantities_on_close(api, user):
    competition, alpha, beta, category = _points_board(api, visibility="visible", votes_per_member=5)
    member = User.objects.create_user(email="splitter@example.com", password="x")
    Membership.objects.create(competition=competition, user=member, role=Role.MEMBER)
    assert competition.settings_json["votes_per_member"] == 5

    opened = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id), "title": "Split week"},
        format="json",
    )
    assert opened.status_code == 201, opened.data
    round_id = opened.data["id"]
    assert opened.data["votes_per_member"] == 5
    assert opened.data["votes_remaining"] == 5

    api.force_authenticate(member)
    cast = api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {
            "allocations": [
                {"participant": str(alpha.id), "votes": 3},
                {"participant": str(beta.id), "votes": 2},
            ]
        },
        format="json",
    )
    assert cast.status_code == 200, cast.data
    assert cast.data["round"]["votes_used"] == 5
    assert cast.data["round"]["votes_remaining"] == 0
    assert cast.data["round"]["vote_count"] == 5
    by_id = {row["participant_id"]: row["votes"] for row in cast.data["round"]["tallies"]}
    assert by_id[str(alpha.id)] == 3
    assert by_id[str(beta.id)] == 2
    assert Vote.objects.filter(round_id=round_id, voter=member).count() == 2

    api.force_authenticate(user)
    closed = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/close",
        {},
        format="json",
    )
    assert closed.status_code == 200, closed.data
    events = {
        str(e.side.participant_id): e.quantity
        for e in ScoreEvent.objects.filter(fixture__competition=competition).select_related("side")
    }
    assert events[str(alpha.id)] == 3
    assert events[str(beta.id)] == 2


def test_over_budget_and_empty_allocations_rejected(api, user):
    competition, alpha, beta, category = _points_board(api, votes_per_member=3)
    member = User.objects.create_user(email="overbudget@example.com", password="x")
    Membership.objects.create(competition=competition, user=member, role=Role.MEMBER)

    opened = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id)},
        format="json",
    )
    assert opened.status_code == 201, opened.data
    round_id = opened.data["id"]

    api.force_authenticate(member)
    over = api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {
            "allocations": [
                {"participant": str(alpha.id), "votes": 2},
                {"participant": str(beta.id), "votes": 2},
            ]
        },
        format="json",
    )
    assert over.status_code == 400

    empty = api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {"allocations": []},
        format="json",
    )
    assert empty.status_code == 400


def test_legacy_single_participant_cast_with_budget_of_one(api, user):
    competition, alpha, beta, category = _points_board(api, votes_per_member=1)
    member = User.objects.create_user(email="legacy-voter@example.com", password="x")
    Membership.objects.create(competition=competition, user=member, role=Role.MEMBER)

    opened = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id)},
        format="json",
    )
    round_id = opened.data["id"]

    api.force_authenticate(member)
    cast = api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {"participant": str(alpha.id)},
        format="json",
    )
    assert cast.status_code == 200, cast.data
    assert cast.data["round"]["my_votes"] == [
        {"participant_id": str(alpha.id), "participant_name": "Alpha", "votes": 1}
    ]
    assert cast.data["round"]["votes_used"] == 1
    assert Vote.objects.get(round_id=round_id, voter=member).quantity == 1


def test_accumulate_as_vote_count_locks_category_points_to_one(api, user):
    competition, alpha, beta, category = _points_board(
        api,
        accumulate_as_vote_count=True,
        category_points=5,
        votes_per_member=3,
    )
    assert competition.settings_json["accumulate_as_vote_count"] is True
    category.refresh_from_db()
    assert float(category.points) == 1

    member = User.objects.create_user(email="vote-count@example.com", password="x")
    Membership.objects.create(competition=competition, user=member, role=Role.MEMBER)
    opened = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id)},
        format="json",
    )
    round_id = opened.data["id"]
    api.force_authenticate(member)
    cast = api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {
            "allocations": [
                {"participant": str(alpha.id), "votes": 2},
                {"participant": str(beta.id), "votes": 1},
            ]
        },
        format="json",
    )
    assert cast.status_code == 200, cast.data

    api.force_authenticate(user)
    closed = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/close",
        {},
        format="json",
    )
    assert closed.status_code == 200, closed.data
    events = {
        str(e.side.participant_id): e.quantity
        for e in ScoreEvent.objects.filter(fixture__competition=competition).select_related("side")
    }
    assert events[str(alpha.id)] == 2
    assert events[str(beta.id)] == 1


def test_weighted_criterion_points_still_multiply_when_vote_count_off(api, user):
    competition, alpha, beta, category = _points_board(
        api,
        accumulate_as_vote_count=False,
        category_points=2,
        votes_per_member=1,
    )
    assert competition.settings_json.get("accumulate_as_vote_count") is False
    category.refresh_from_db()
    assert float(category.points) == 2

    member = User.objects.create_user(email="weighted-voter@example.com", password="x")
    Membership.objects.create(competition=competition, user=member, role=Role.MEMBER)
    opened = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds",
        {"scoring_category": str(category.id)},
        format="json",
    )
    round_id = opened.data["id"]
    api.force_authenticate(member)
    api.put(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/vote",
        {"participant": str(alpha.id)},
        format="json",
    )
    api.force_authenticate(user)
    closed = api.post(
        f"/api/v1/competitions/{competition.id}/voting-rounds/{round_id}/close",
        {},
        format="json",
    )
    assert closed.status_code == 200, closed.data
    event = ScoreEvent.objects.select_related("scoring_category").get(
        fixture__competition=competition
    )
    assert event.quantity == 1
    assert float(event.points) == 2
