"""A demo league whose season is over, so the next step is starting a new one."""

from __future__ import annotations

import pytest

from apps.competitions.models import Competition, Stage
from apps.fixtures.models import Fixture

pytestmark = pytest.mark.django_db


def _finished_demo(api, fmt: str = "league") -> Competition:
    created = api.post(
        "/api/v1/competitions",
        {"name": "Finished season", "format": fmt, "preset": "soccer"},
        format="json",
    )
    assert created.status_code == 201, created.data
    generated = api.post(
        f"/api/v1/competitions/{created.data['id']}/demo-league", {"season": "finished"}, format="json"
    )
    assert generated.status_code == 201, generated.data
    return Competition.objects.get(pk=created.data["id"])


@pytest.mark.parametrize("fmt", ["league", "league_knockout"])
def test_a_finished_season_demo_has_every_match_played(api, fmt):
    competition = _finished_demo(api, fmt)

    fixtures = Fixture.objects.filter(competition=competition)
    assert fixtures.count() == 16 * 15 // 2
    assert not fixtures.exclude(status=Fixture.Status.COMPLETED).exists()
    assert competition.status == Competition.Status.COMPLETED
    assert competition.settings_json["demo_league"]["season"] == "finished"
    assert competition.settings_json["demo_league"]["live_fixture"] is None

    detail = api.get(f"/api/v1/competitions/{competition.id}").data
    assert detail["season_finished"] is True
    table = api.get(f"/api/v1/competitions/{competition.id}/standings").data
    assert len(table["rows"]) == 16
    assert all(int(row["played"]) == 15 for row in table["rows"])


def test_the_owner_can_start_the_next_season(api):
    competition = _finished_demo(api)

    started = api.post(
        f"/api/v1/competitions/{competition.id}/next-season",
        {"kind": "season", "starts_on": "2026-12-05", "kickoff": "15:00"},
        format="json",
    )

    assert started.status_code == 201, started.data
    competition.refresh_from_db()
    assert competition.status == Competition.Status.ACTIVE
    season_two = Stage.objects.get(competition=competition, name="Season 2")
    assert Fixture.objects.filter(stage=season_two, status=Fixture.Status.SCHEDULED).count() == 120


def test_the_old_season_keeps_its_own_record(api):
    competition = _finished_demo(api)
    final_table = api.get(f"/api/v1/competitions/{competition.id}/standings").data["rows"]
    champion = final_table[0]["participant"]["name"]

    api.post(
        f"/api/v1/competitions/{competition.id}/next-season",
        {"kind": "season", "starts_on": "2026-12-05", "kickoff": "15:00"},
        format="json",
    )

    season_one = Stage.objects.get(competition=competition, name="Season 1")
    season_two = Stage.objects.get(competition=competition, name="Season 2")
    assert season_one.display_order < season_two.display_order
    assert Fixture.objects.filter(stage=season_one, status=Fixture.Status.COMPLETED).count() == 120
    assert not Fixture.objects.filter(competition=competition, stage__isnull=True).exists()
    assert season_one.ends_on is not None

    stages = {row["name"]: row for row in api.get(f"/api/v1/competitions/{competition.id}").data["stages"]}
    assert stages["Season 1"]["finished"] is True
    assert stages["Season 1"]["champion"] == champion
    assert stages["Season 2"]["finished"] is False
    assert stages["Season 2"]["champion"] is None

    old = api.get(f"/api/v1/competitions/{competition.id}/standings", {"stage": str(season_one.id)}).data
    assert old["rows"][0]["participant"]["name"] == champion
    assert all(int(row["played"]) == 15 for row in old["rows"])
    new = api.get(
        f"/api/v1/competitions/{competition.id}/standings", {"stage": str(season_two.id), "refresh": "true"}
    ).data
    assert len(new["rows"]) == 16
    assert all(int(row["played"]) == 0 for row in new["rows"])


def test_a_league_that_already_rolled_over_gets_its_first_season_named(api):
    """The data migration's job, run through the same helper on a hand-made rollover."""

    from apps.competitions.season import archive_first_season

    competition = _finished_demo(api)
    Stage.objects.create(competition=competition, name="Season 2", kind=Stage.Kind.LEAGUE, display_order=1)

    archived = archive_first_season(competition)

    assert archived is not None and archived.name == "Season 1"
    assert archived.participants.count() == 16
    assert archive_first_season(competition) is None
