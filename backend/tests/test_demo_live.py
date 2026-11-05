"""Every demo is scheduled automatically and always has a match in play."""

from __future__ import annotations

import pytest

from apps.competitions.models import Competition
from apps.fixtures.models import Fixture

pytestmark = pytest.mark.django_db


def _demo(api, fmt: str) -> Competition:
    created = api.post(
        "/api/v1/competitions",
        {"name": f"Demo {fmt}", "format": fmt, "preset": "soccer"},
        format="json",
    )
    assert created.status_code == 201, created.data
    demo_url = f"/api/v1/competitions/{created.data['id']}/demo-league"
    generated = api.post(demo_url, {}, format="json")
    assert generated.status_code == 201, generated.data
    return Competition.objects.get(pk=created.data["id"])


@pytest.mark.parametrize("fmt", ["league", "league_knockout", "knockout", "freeform"])
def test_every_demo_has_a_schedule_and_a_live_match(api, fmt):
    competition = _demo(api, fmt)
    info = competition.settings_json["demo_league"]

    fixtures = Fixture.objects.filter(competition=competition)
    assert fixtures.filter(status=Fixture.Status.COMPLETED).exists()
    assert fixtures.filter(status=Fixture.Status.LIVE).exists()
    assert info["live_fixture"]
    live = fixtures.get(pk=info["live_fixture"])
    assert live.status == Fixture.Status.LIVE
    assert live.sides.filter(participant__isnull=False).count() == 2


def test_a_demo_cannot_be_scheduled_a_second_time(api):
    competition = _demo(api, "league")
    before = Fixture.objects.filter(competition=competition).count()

    again = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/generate",
        {"method": "round_robin", "starts_on": "2030-01-05", "kickoff": "15:00"},
        format="json",
    )

    assert again.status_code == 400
    assert "already has its whole schedule" in str(again.data)
    assert Fixture.objects.filter(competition=competition).count() == before
