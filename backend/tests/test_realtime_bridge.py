"""The contract between Django and the Node realtime/worker service."""

from __future__ import annotations

import json

import pytest
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Membership
from apps.core import bus
from apps.core.permissions import Role
from apps.fixtures.models import Fixture

pytestmark = pytest.mark.django_db

TOKEN = "the-shared-secret"


@pytest.fixture
def internal_api(settings) -> APIClient:
    settings.INTERNAL_API_TOKEN = TOKEN
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    return client


def test_public_competition_rooms_are_open_to_any_signed_in_user(
    internal_api, competition, other_user
):
    response = internal_api.post(
        "/internal/rooms/authorize",
        {"user_id": str(other_user.id), "rooms": [f"competition:{competition.id}"]},
        format="json",
    )
    assert response.data["allowed"] == [f"competition:{competition.id}"]


def test_private_competition_rooms_require_membership(internal_api, user, other_user):
    private = Competition.objects.create(name="Invite Only", owner=user, is_private=True)
    Membership.objects.create(competition=private, user=user, role=Role.OWNER)
    room = f"competition:{private.id}"

    denied = internal_api.post(
        "/internal/rooms/authorize",
        {"user_id": str(other_user.id), "rooms": [room]},
        format="json",
    )
    assert denied.data["allowed"] == []

    granted = internal_api.post(
        "/internal/rooms/authorize",
        {"user_id": str(user.id), "rooms": [room]},
        format="json",
    )
    assert granted.data["allowed"] == [room]


def test_fixture_rooms_inherit_the_competitions_privacy(internal_api, user, other_user):
    private = Competition.objects.create(name="Invite Only", owner=user, is_private=True)
    Membership.objects.create(competition=private, user=user, role=Role.OWNER)
    fixture = Fixture.objects.create(competition=private)
    room = f"fixture:{fixture.id}"

    denied = internal_api.post(
        "/internal/rooms/authorize",
        {"user_id": str(other_user.id), "rooms": [room]},
        format="json",
    )
    assert denied.data["allowed"] == []

    granted = internal_api.post(
        "/internal/rooms/authorize",
        {"user_id": str(user.id), "rooms": [room]},
        format="json",
    )
    assert granted.data["allowed"] == [room]


def test_a_user_room_only_belongs_to_that_user(internal_api, user, other_user):
    response = internal_api.post(
        "/internal/rooms/authorize",
        {
            "user_id": str(user.id),
            "rooms": [f"user:{user.id}", f"user:{other_user.id}"],
        },
        format="json",
    )
    assert response.data["allowed"] == [f"user:{user.id}"]


def test_unknown_and_malformed_rooms_are_ignored(internal_api, user):
    response = internal_api.post(
        "/internal/rooms/authorize",
        {"user_id": str(user.id), "rooms": ["nonsense", "team:123", 42, None]},
        format="json",
    )
    assert response.data["allowed"] == []


def test_published_events_match_the_shape_the_gateway_expects(bus_redis, competition):
    """The envelope is parsed by realtime/src/types.ts; keep the keys in step."""

    bus.publish_event(
        "score.recorded",
        {"fixture_id": "abc"},
        [bus.competition_room(competition.id)],
        immediate=True,
    )

    channel, raw = bus_redis.published[0]
    envelope = json.loads(raw)

    assert channel == "fm:events"
    assert set(envelope) == {"id", "event", "rooms", "payload", "ts"}
    assert envelope["event"] == "score.recorded"
    assert envelope["rooms"] == [f"competition:{competition.id}"]


def test_enqueued_jobs_match_the_shape_the_bridge_expects(bus_redis):
    """The envelope is parsed by realtime/src/bridge.ts; keep the keys in step."""

    bus.enqueue_job(
        bus.Queues.STANDINGS,
        "recompute",
        {"competition_id": "abc"},
        delay_ms=500,
        immediate=True,
    )

    key, raw = bus_redis.pushed[0]
    envelope = json.loads(raw)

    assert key == "fm:jobs:inbox"
    assert set(envelope) == {"id", "queue", "name", "data", "opts"}
    assert envelope["queue"] == "standings"
    assert envelope["opts"] == {"attempts": 3, "delay": 500}


def test_queue_names_match_the_node_service():
    """Mirrors QUEUE_NAMES in realtime/src/queues.ts."""

    assert {
        bus.Queues.MEDIA,
        bus.Queues.NOTIFICATIONS,
        bus.Queues.STANDINGS,
        bus.Queues.SEARCH,
    } == {"media", "notifications", "standings", "search"}
