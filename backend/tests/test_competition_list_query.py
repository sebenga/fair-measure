"""The competitions list must not multiply rows by members and teams."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.competitions.models import Competition, Membership, Participant
from apps.core.permissions import Role

pytestmark = pytest.mark.django_db
User = get_user_model()


def test_a_big_league_is_listed_once_with_its_team_count(api, user):
    league = Competition.objects.create(
        name="Big demo",
        owner=user,
        sport="soccer",
        settings_json={"demo_league": {"user_ids": [str(n) for n in range(300)]}},
    )
    Membership.objects.create(competition=league, user=user, role=Role.OWNER)
    for index in range(40):
        member = User.objects.create_user(email=f"m{index}@big.test", password="pw-123456789")
        Membership.objects.create(competition=league, user=member, role=Role.MEMBER)
    for index in range(16):
        Participant.objects.create(competition=league, name=f"Team {index}", kind="team")
    other = User.objects.create_user(email="owner@other.test", password="pw-123456789")
    Competition.objects.create(name="Someone else's", owner=other, sport="soccer")

    with CaptureQueriesContext(connection) as queries:
        mine = api.get("/api/v1/competitions", {"mine": "true", "page_size": 50})
    assert mine.status_code == 200
    rows = mine.data["results"]
    assert [row["name"] for row in rows] == ["Big demo"]
    assert rows[0]["participant_count"] == 16

    listing = next(
        q["sql"]
        for q in queries.captured_queries
        if '"competitions_competition"' in q["sql"] and "LIMIT" in q["sql"]
    )
    assert "DISTINCT" not in listing.upper()
    assert 'INNER JOIN "competitions_membership"' not in listing

    everything = api.get("/api/v1/competitions", {"page_size": 50})
    names = [row["name"] for row in everything.data["results"]]
    assert names.count("Big demo") == 1
    assert "Someone else's" in names
