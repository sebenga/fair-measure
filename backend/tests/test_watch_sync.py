"""Watch pairing and offline event dedupe."""

from __future__ import annotations

import uuid

import pytest

from apps.competitions.models import Competition, Participant, RosterMember
from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide, ScoreEvent

pytestmark = pytest.mark.django_db


def test_watch_sync_dedupes_by_client_uuid(api, user):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Watch league", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    home = Participant.objects.create(competition=competition, name="Home", kind="team")
    away = Participant.objects.create(competition=competition, name="Away", kind="team")
    player = RosterMember.objects.create(participant=home, name="Nine", number=9)
    fixture = Fixture.objects.create(
        competition=competition, status=Fixture.Status.LIVE, duration_minutes=90
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0, is_home=True)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    FixtureReferee.objects.create(
        fixture=fixture,
        user=user,
        role=FixtureReferee.Role.REFEREE,
        status=FixtureReferee.Status.ACCEPTED,
    )
    codes = {
        item["code"]: item["id"]
        for item in api.get(f"/api/v1/competitions/{competition.id}").data["scoring_categories"]
    }

    paired = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/watch/pair",
        {},
        format="json",
    )
    assert paired.status_code == 201, paired.data
    token = paired.data["token"]
    client_uuid = str(uuid.uuid4())
    payload = {
        "events": [
            {
                "client_uuid": client_uuid,
                "side": str(home_side.id),
                "scoring_category": codes["goal"],
                "quantity": "1",
                "player": str(player.id),
                "minute": 12,
            }
        ]
    }
    first = api.post(
        f"/api/v1/fixtures/{fixture.id}/watch/sync",
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert first.status_code == 200, first.data
    assert len(first.data["created"]) == 1
    second = api.post(
        f"/api/v1/fixtures/{fixture.id}/watch/sync",
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert second.status_code == 200, second.data
    assert second.data["skipped"] == [client_uuid]
    assert ScoreEvent.objects.filter(fixture=fixture, client_uuid=client_uuid).count() == 1
    fixture.refresh_from_db()
    assert home_side.__class__.objects.get(pk=home_side.pk).score == 1
