"""Landing-page one-hour soccer and custom demos."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.competitions.models import Competition
from apps.fixtures.models import Fixture

pytestmark = pytest.mark.django_db


def test_try_soccer_demo_builds_a_live_one_hour_league(api):
    started = api.post("/api/v1/demos/try", {"kind": "soccer"}, format="json")
    assert started.status_code == 201, started.data
    assert started.data["kind"] == "soccer"
    assert started.data["active"] is True
    assert started.data["fixtures"] > 0
    assert started.data["competition_id"]

    competition = Competition.objects.get(pk=started.data["competition_id"])
    info = competition.settings_json["demo_league"]
    assert info["active"] is True
    expires = parse_datetime(info["expires_at"])
    assert expires is not None
    assert expires > timezone.now() + timedelta(minutes=50)
    assert expires <= timezone.now() + timedelta(hours=1, minutes=5)
    assert Fixture.objects.filter(competition=competition, status=Fixture.Status.LIVE).exists()


def test_try_custom_demo_builds_a_versus_league(api):
    started = api.post("/api/v1/demos/try", {"kind": "custom"}, format="json")
    assert started.status_code == 201, started.data
    assert started.data["kind"] == "custom"

    competition = Competition.objects.get(pk=started.data["competition_id"])
    settings = competition.settings_json
    assert settings["scoring_basis"] == "results"
    assert settings["participant_type"] == "team"
    assert competition.format in {
        Competition.Format.LEAGUE,
        Competition.Format.LEAGUE_KNOCKOUT,
    }
    assert competition.scoring_categories.filter(code="goal").exists()
    assert Fixture.objects.filter(competition=competition, status=Fixture.Status.LIVE).exists()
    expires = parse_datetime(settings["demo_league"]["expires_at"])
    assert expires is not None
    assert expires > timezone.now() + timedelta(minutes=50)


def test_try_demo_rejects_unknown_kinds(api):
    bad = api.post("/api/v1/demos/try", {"kind": "tennis"}, format="json")
    assert bad.status_code == 400


def test_try_custom_points_demo_scores_everyone_on_one_board(api):
    started = api.post("/api/v1/demos/try", {"kind": "custom_points"}, format="json")
    assert started.status_code == 201, started.data
    assert started.data["kind"] == "custom_points"

    competition = Competition.objects.get(pk=started.data["competition_id"])
    settings = competition.settings_json
    assert settings["score_all_on_criterion"] is True
    assert settings["scoring_basis"] == "criteria"
    assert settings["participant_type"] == "individual"
    assert competition.participants.filter(kind="individual").count() == 16
    assert competition.scoring_categories.filter(code="sales").exists()
    table = api.get(f"/api/v1/competitions/{competition.id}/standings")
    assert table.status_code == 200
    assert len(table.data["rows"]) == 16


def test_try_demos_appear_on_my_leagues_list(api):
    for kind in ("soccer", "custom", "custom_points"):
        started = api.post("/api/v1/demos/try", {"kind": kind}, format="json")
        assert started.status_code == 201, started.data

    mine = api.get("/api/v1/competitions", {"mine": "true", "page_size": 50})
    assert mine.status_code == 200
    demos = [row for row in mine.data["results"] if row.get("is_demo")]
    assert len(demos) == 3
    assert all(row.get("demo_expires_at") for row in demos)
    names = {row["name"] for row in demos}
    assert names == {"Soccer demo", "Custom VS demo", "Custom points demo"}


def test_try_demo_works_while_logged_out(api):
    api.force_authenticate(user=None)
    started = api.post("/api/v1/demos/try", {"kind": "soccer"}, format="json")
    assert started.status_code == 201, started.data
    assert started.data["guest"] is True
    assert started.data["access"]
    assert started.data["refresh"]
    assert started.data["user"]["email"].endswith("@fairmeasure.demo")
    assert Competition.objects.filter(pk=started.data["competition_id"]).exists()
    assert Fixture.objects.filter(
        competition_id=started.data["competition_id"], status=Fixture.Status.LIVE
    ).exists()
