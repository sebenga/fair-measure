from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _create(api, **dates):
    return api.post(
        "/api/v1/competitions",
        {"name": "Spring league", "timezone": "UTC", **{k: str(v) for k, v in dates.items()}},
        format="json",
    )


def _errors(response) -> dict:
    return response.data["error"]["detail"]


def _today():
    return timezone.now().date()


def test_a_competition_cannot_start_in_the_past(api):
    response = _create(api, starts_on=_today() - timedelta(days=1))
    assert response.status_code == 400
    assert "past" in str(_errors(response)["starts_on"])


def test_a_competition_starts_within_a_year(api):
    assert _create(api, starts_on=_today() + timedelta(days=365)).status_code == 201
    late = _create(api, starts_on=_today() + timedelta(days=366))
    assert late.status_code == 400
    assert "within a year" in str(_errors(late)["starts_on"])


def test_a_competition_runs_for_at_most_365_days(api):
    starts = _today() + timedelta(days=30)
    ok = _create(api, starts_on=starts, ends_on=starts + timedelta(days=365))
    assert ok.status_code == 201
    long = _create(api, starts_on=starts, ends_on=starts + timedelta(days=366))
    assert long.status_code == 400
    assert "at most a year" in str(_errors(long)["ends_on"])


def test_saved_past_dates_do_not_block_other_edits(api, competition):
    competition.starts_on = _today() - timedelta(days=40)
    competition.save()
    renamed = api.patch(
        f"/api/v1/competitions/{competition.id}",
        {"name": "Renamed", "starts_on": str(competition.starts_on)},
        format="json",
    )
    assert renamed.status_code == 200, renamed.data
    moved = api.patch(
        f"/api/v1/competitions/{competition.id}",
        {"starts_on": str(_today() - timedelta(days=2))},
        format="json",
    )
    assert moved.status_code == 400
