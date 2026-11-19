"""Custom points boards: members vote; secret hides tallies until close."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.competitions.models import Competition, Membership, Participant, Vote
from apps.core.permissions import Role
from apps.fixtures.models import ScoreEvent

pytestmark = pytest.mark.django_db
User = get_user_model()


def _points_board(api, *, visibility="secret"):
    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Vote board",
            "preset": "custom",
            "format": "freeform",
            "scoring_basis": "criteria",
            "scoring_categories": [
                {"name": "Popular pick", "code": "pick", "points": 1, "affects_score": True}
            ],
            "settings_json": {
                "points_by_voting": True,
                "voting_visibility": visibility,
                "score_all_on_criterion": False,
            },
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
