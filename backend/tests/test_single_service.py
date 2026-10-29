"""The single-service deployment: no Node worker or Socket.io gateway.

Jobs run inside Django and the app polls for live events instead.
"""

from __future__ import annotations

import time

import pytest
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Membership
from apps.core import bus
from apps.core.permissions import Role
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def single_service(settings):
    settings.JOBS_INLINE = True
    settings.JOBS_INLINE_SYNC = True
    settings.REALTIME_POLLING = True
    return settings


def test_inline_jobs_run_instead_of_waiting_for_a_worker(
    single_service, bus_redis, competition, other_user
):
    Membership.objects.get_or_create(
        competition=competition, user=other_user, defaults={"role": Role.MEMBER}
    )

    bus.enqueue_job(
        bus.Queues.NOTIFICATIONS,
        "fixtures-published",
        {"competition_id": str(competition.id), "count": 3},
        immediate=True,
    )

    assert not [key for key, _ in bus_redis.pushed if key == "fm:jobs:inbox"]
    assert Notification.objects.filter(user=other_user, kind="fixtures-published").exists()


def test_a_failing_inline_job_never_breaks_the_request(single_service):
    bus.enqueue_job(bus.Queues.STANDINGS, "recompute", {"competition_id": "nope"}, immediate=True)


def test_polling_returns_new_events_for_rooms_the_viewer_may_follow(
    single_service, competition, user
):
    private = Competition.objects.create(name="Invite Only", owner=user, is_private=True)
    open_room = bus.competition_room(competition.id)
    closed_room = bus.competition_room(private.id)
    guest = APIClient()

    start = guest.get("/api/v1/realtime/events").data["now"]
    bus.publish_event("fixture.updated", {"n": 1}, [open_room], immediate=True)
    bus.publish_event("fixture.updated", {"n": 2}, [closed_room], immediate=True)
    time.sleep(0.002)

    seen = guest.get(
        "/api/v1/realtime/events", {"rooms": f"{open_room},{closed_room}", "since": start - 1}
    ).data
    assert [row["payload"] for row in seen["events"]] == [{"n": 1}]

    later = guest.get("/api/v1/realtime/events", {"rooms": open_room, "since": seen["now"]}).data
    assert later["events"] == []


def test_polling_is_off_when_a_socket_gateway_exists(settings, competition):
    settings.REALTIME_POLLING = False
    response = APIClient().get(
        "/api/v1/realtime/events",
        {"rooms": bus.competition_room(competition.id), "since": 1},
    )
    assert response.data["enabled"] is False


def test_malformed_room_ids_are_ignored_on_postgres(single_service):
    response = APIClient().get(
        "/api/v1/realtime/events", {"rooms": "competition:abc,fixture:1,games:x", "since": 1}
    )
    assert response.status_code == 200
    assert response.data["events"] == []
