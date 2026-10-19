"""Scouting Phase 3: player stats from the engine, physical tests and percentiles."""

from __future__ import annotations

from datetime import date, timedelta
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.competitions.presets import apply_preset
from apps.fixtures.models import Fixture, FixtureSide, PlayerAppearance, ScoreEvent
from apps.scouting import stats
from apps.scouting.models import PhysicalTestResult, PlayerProfile, PlayerSport, PlayerStatLine

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _years_ago(years: int) -> date:
    today = date.today()
    return date(today.year - years, today.month, min(today.day, 28))


def _profile(email: str, *, position="striker", age=24, gender="men", visibility="scouts"):
    user = User.objects.create_user(
        email=email, password="pw-123456789", display_name=email.split("@")[0]
    )
    profile = PlayerProfile.objects.create(
        user=user,
        first_name=email.split("@")[0].title(),
        date_of_birth=_years_ago(age),
        gender_category=gender,
        visibility=visibility,
    )
    PlayerSport.objects.create(
        profile=profile, sport="soccer", primary_position=position, is_primary=True
    )
    return profile


@pytest.fixture
def league(db):
    owner = User.objects.create_user(email="owner@stats.test", password="pw-123456789")
    competition = Competition.objects.create(name="Stats league", owner=owner, sport="soccer")
    apply_preset(competition, "soccer")
    home = Participant.objects.create(competition=competition, name="Hawks", kind="team")
    away = Participant.objects.create(competition=competition, name="Owls", kind="team")
    profile = _profile("striker@stats.test")
    member = RosterMember.objects.create(
        participant=home, name="Striker", user=profile.user, position="striker"
    )
    RosterMember.objects.create(participant=away, name="Keeper", position="goalkeeper")
    return {
        "competition": competition,
        "home": home,
        "away": away,
        "profile": profile,
        "member": member,
        "owner": owner,
    }


def _match(league, events: dict, *, minutes=None, home_goals=None, days_ago=7):
    competition = league["competition"]
    fixture = Fixture.objects.create(
        competition=competition,
        status=Fixture.Status.LIVE,
        scheduled_at=timezone.now() - timedelta(days=days_ago),
    )
    side = FixtureSide.objects.create(
        fixture=fixture, participant=league["home"], position=0, is_home=True
    )
    FixtureSide.objects.create(fixture=fixture, participant=league["away"], position=1)
    for code, count in events.items():
        category = competition.scoring_categories.get(code=code)
        for _ in range(count):
            ScoreEvent.objects.create(
                fixture=fixture, side=side, scoring_category=category, player=league["member"]
            )
    if minutes is not None:
        PlayerAppearance.objects.create(fixture=fixture, player=league["member"], minutes=minutes)
    fixture.status = Fixture.Status.COMPLETED
    fixture.completed_at = timezone.now()
    fixture.save()
    fixture.recalculate_scores()
    return fixture


# --- Stats from the engine --------------------------------------------------------------------


def test_stats_per_90_and_rates_are_correct(league):
    _match(league, {"goal": 2, "shot": 3, "shot-on-target": 2, "assist": 1}, minutes=90)
    _match(league, {"shot": 1}, minutes=90)
    _match(league, {"goal": 1, "shot": 2, "shot-on-target": 1}, minutes=45)
    stats.recompute_user(league["profile"].user)
    season = timezone.localdate().year
    line = PlayerStatLine.objects.get(
        user=league["profile"].user, sport="soccer", season=season, competition=None
    )
    assert (line.matches, line.minutes) == (3, 225)
    values = line.values
    assert values["goals"] == {"value": 3.0, "per_match": 1.0}
    assert values["goals_per_90"]["value"] == 1.2  # 3 goals x 90 / 225 minutes
    assert values["assists_per_90"]["value"] == 0.4
    assert values["conversion_rate"]["value"] == 50.0  # 3 goals from 6 shots
    by_competition = PlayerStatLine.objects.get(
        user=league["profile"].user, competition=league["competition"], season=season
    )
    assert by_competition.values["goals"]["value"] == 3.0


def test_missing_minutes_count_as_the_full_match_and_benched_games_are_skipped(league):
    _match(league, {"goal": 1})  # tagged, no minutes: full 90
    benched = _match(league, {})  # the team played, the striker did not appear
    stats.recompute_user(league["profile"].user)
    line = PlayerStatLine.objects.get(user=league["profile"].user, competition=None)
    assert (line.matches, line.minutes) == (1, 90)
    assert line.values["goals_per_90"]["value"] == 1.0
    assert benched.status == Fixture.Status.COMPLETED


def test_seasons_are_kept_apart(league):
    _match(league, {"goal": 2}, minutes=90, days_ago=400)
    _match(league, {"goal": 1}, minutes=90)
    stats.recompute_user(league["profile"].user)
    seasons = {
        line.season: line.values["goals"]["value"]
        for line in PlayerStatLine.objects.filter(user=league["profile"].user, competition=None)
    }
    this_year = timezone.localdate().year
    assert seasons[this_year] == 1.0
    assert sum(seasons.values()) == 3.0 and len(seasons) in (1, 2)


def test_the_stats_job_runs_after_results_change(league, settings):
    with mock.patch("apps.core.bus.enqueue_job") as enqueue:
        from apps.core.signals import results_changed

        results_changed.send(sender=Competition, competition=league["competition"])
    enqueue.assert_called_once_with(
        "stats", "recompute", {"competition_id": str(league["competition"].id)}
    )

    _match(league, {"goal": 1}, minutes=90)
    settings.INTERNAL_API_TOKEN = "stats-token"
    response = APIClient().post(
        "/internal/scouting/stats",
        {"competition_id": str(league["competition"].id)},
        format="json",
        HTTP_AUTHORIZATION="Bearer stats-token",
    )
    assert response.status_code == 200 and response.json()["rows"] == 2
    assert PlayerStatLine.objects.filter(user=league["profile"].user).count() == 2


def test_tagging_is_optional_for_stats_and_minutes_ride_along(league):
    fixture = Fixture.objects.create(competition=league["competition"], status=Fixture.Status.LIVE)
    side = FixtureSide.objects.create(
        fixture=fixture, participant=league["home"], position=0, is_home=True
    )
    FixtureSide.objects.create(fixture=fixture, participant=league["away"], position=1)
    client = _client(league["owner"])
    category = league["competition"].scoring_categories
    untagged = client.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": str(category.get(code="assist").id),
            "quantity": "1",
        },
        format="json",
    )
    assert untagged.status_code == 201, untagged.data
    goal = client.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": str(category.get(code="goal").id),
            "quantity": "1",
        },
        format="json",
    )
    assert goal.status_code == 400, "a goal still names who scored"
    tagged = client.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": str(category.get(code="goal").id),
            "quantity": "1",
            "player": str(league["member"].id),
            "minutes": 70,
        },
        format="json",
    )
    assert tagged.status_code == 201, tagged.data
    assert PlayerAppearance.objects.get(fixture=fixture, player=league["member"]).minutes == 70


def test_the_stats_tab_api(league):
    _match(league, {"goal": 2, "shot": 4}, minutes=90)
    scout = User.objects.create_user(email="scout@stats.test", password="pw-123456789")
    from apps.scouting.services import grant_role

    grant_role(scout, "scout")
    response = _client(scout).get(f"/api/v1/scouting/profiles/{league['profile'].id}/stats")
    assert response.status_code == 200, response.data
    data = response.json()
    assert data["sport"] == "soccer" and data["season"] == timezone.localdate().year
    goals = next(row for row in data["stats"] if row["key"] == "goals")
    assert goals["value"] == 2.0 and goals["percentile"] is None  # only 1 player in the cohort
    assert data["history"][-1]["values"]["goals_per_90"] == 2.0
    assert data["competitions"] == [{"id": str(league["competition"].id), "name": "Stats league"}]
    stranger = User.objects.create_user(email="nobody@stats.test", password="pw-123456789")
    hidden = PlayerProfile.objects.filter(pk=league["profile"].pk)
    hidden.update(visibility="private")
    assert (
        _client(stranger).get(f"/api/v1/scouting/profiles/{league['profile'].id}/stats").status_code
        == 404
    )


# --- Percentiles ---------------------------------------------------------------------------------


def _peers(count: int, *, season: int, position="striker"):
    for index in range(count):
        peer = _profile(f"{position}{index}@stats.test", position=position)
        PlayerStatLine.objects.create(
            user=peer.user,
            sport="soccer",
            season=season,
            competition=None,
            matches=10,
            minutes=900,
            values={"goals": {"value": float(index), "per_match": index / 10}},
            computed_at=timezone.now(),
        )


def test_percentiles_are_hidden_below_the_sample_size(league):
    season = timezone.localdate().year
    me = PlayerStatLine.objects.create(
        user=league["profile"].user,
        sport="soccer",
        season=season,
        competition=None,
        matches=10,
        minutes=900,
        values={"goals": {"value": 15.0, "per_match": 1.5}},
        computed_at=timezone.now(),
    )
    _peers(18, season=season)
    _peers(5, season=season, position="goalkeeper")  # other position: not in the cohort
    hidden = stats.stat_percentiles(league["profile"], "soccer", season, me.values)
    assert hidden["goals"] == {"percentile": None, "sample": 19}

    extra = _profile("extra@stats.test")
    PlayerStatLine.objects.create(
        user=extra.user,
        sport="soccer",
        season=season,
        competition=None,
        values={"goals": {"value": 30.0}},
        computed_at=timezone.now(),
    )
    shown = stats.stat_percentiles(league["profile"], "soccer", season, me.values)
    # 20 in the cohort: 18 peers on 0-17, one on 30, and me on 15. I beat 15 of them and
    # tie two (the peer on 15 and myself): (15 + 0.5 x 2) / 20 = 80th percentile.
    assert shown["goals"] == {"percentile": 80.0, "sample": 20}


def test_private_profiles_never_feed_a_percentile(league):
    season = timezone.localdate().year
    _peers(19, season=season)
    PlayerProfile.objects.filter(first_name="Striker3").update(visibility="private")
    sample = stats.stat_percentiles(league["profile"], "soccer", season, {"goals": {"value": 5.0}})
    assert sample["goals"]["sample"] == 18


def test_lower_is_better_percentiles_flip():
    values = [float(index) for index in range(20)]
    assert stats.percentile(2.0, values, "lower") == 87.5
    assert stats.percentile(2.0, values, "higher") == 12.5
    assert stats.percentile(2.0, values[:19], "higher") is None
    assert stats.percentile(2.0, values, None) is None


# --- Physical tests ---------------------------------------------------------------------


def test_an_unverified_test_is_labelled_self_reported_and_a_coach_one_verified(league):
    player = _client(league["profile"].user)
    url = f"/api/v1/scouting/profiles/{league['profile'].id}/tests"
    mine = player.post(
        url,
        {"sport": "soccer", "test_key": "sprint_40m", "value": "5.42", "tested_on": "2026-02-01"},
        format="json",
    )
    assert mine.status_code == 201, mine.data
    assert (mine.json()["source"], mine.json()["verified"], mine.json()["label"]) == (
        "self",
        False,
        "Self-reported",
    )

    coach = User.objects.create_user(email="coach@stats.test", password="pw-123456789")
    from apps.scouting.services import grant_role

    grant_role(coach, "coach", team=league["home"])
    verified = _client(coach).post(
        url,
        {
            "sport": "soccer",
            "test_key": "sprint_40m",
            "value": "5.30",
            "tested_on": "2026-05-01",
            "venue": "Hawks field",
        },
        format="json",
    )
    assert verified.status_code == 201, verified.data
    assert (verified.json()["source"], verified.json()["label"]) == ("coach", "Verified")
    assert verified.json()["unit"] == "s"

    stranger = User.objects.create_user(email="random@stats.test", password="pw-123456789")
    assert (
        _client(stranger)
        .post(url, {"sport": "soccer", "test_key": "sprint_40m", "value": "4"}, format="json")
        .status_code
        == 403
    )
    assert (
        player.post(
            url, {"sport": "soccer", "test_key": "bench_press", "value": "4"}, format="json"
        ).status_code
        == 400
    )

    summary = stats.test_summary(league["profile"], "soccer")
    sprint = next(row for row in summary if row["key"] == "sprint_40m")
    assert sprint["personal_best"]["value"] == 5.3 and sprint["personal_best"]["verified"] is True
    assert sprint["latest"]["value"] == 5.3 and sprint["trend"] == "improving"
    assert [row["label"] for row in sprint["history"]] == ["Self-reported", "Verified"]
    assert sprint["percentile"] is None  # fewer than 20 players with this test


def test_officials_of_the_players_competition_record_verified_tests(league):
    from apps.results.models import CompetitionOfficial

    official = User.objects.create_user(email="official@stats.test", password="pw-123456789")
    CompetitionOfficial.objects.create(
        competition=league["competition"], user=official, title="judge"
    )
    response = _client(official).post(
        f"/api/v1/scouting/profiles/{league['profile'].id}/tests",
        {"sport": "soccer", "test_key": "yo_yo_ir1", "value": "1840"},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.json()["source"] == "official"
    players = _client(official).get("/api/v1/scouting/tests/players").json()["players"]
    assert [row["profile_id"] for row in players] == [str(league["profile"].id)]
    assert PhysicalTestResult.objects.get().verified_by == official


def test_the_stats_demo_seed_shows_percentiles(db):
    from django.core.management import call_command

    User.objects.create_user(email="owner@example.com", password="pw-123456789")
    User.objects.create_user(email="coach@example.com", password="pw-123456789")
    call_command("seed_scouting_stats", password="pw-123456789")
    striker = PlayerProfile.objects.get(user__email="striker01@example.com")
    scout = User.objects.create_user(email="seed-scout@stats.test", password="pw-123456789")
    from apps.scouting.services import grant_role

    grant_role(scout, "scout")
    data = _client(scout).get(f"/api/v1/scouting/profiles/{striker.id}/stats").json()
    assert data["cohort"] == 24 and data["line"]["matches"] == 3
    goals = next(row for row in data["stats"] if row["key"] == "goals")
    assert goals["percentile"] is not None and goals["sample"] == 24
    sprint = next(row for row in data["tests"] if row["key"] == "sprint_40m")
    assert sprint["percentile"] is not None and sprint["personal_best"]["label"] == "Verified"
    call_command("seed_scouting_stats", password="pw-123456789")  # re-running changes nothing
    assert PlayerProfile.objects.filter(user__email__startswith="striker").count() == 24
