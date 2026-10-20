"""Scouting Phase 6: the six talent reports and their PDF exports.

A report only shows what its viewer may see, the PDF generates, every export is
logged, and the numbers match the stats API.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.scouting.models import (
    Organisation,
    PhysicalTestResult,
    PlayerProfile,
    PlayerSport,
    PlayerStatLine,
    ReportExport,
    ScoutRating,
    Shortlist,
    ShortlistEntry,
)
from apps.scouting.services import grant_role

pytestmark = pytest.mark.django_db
User = get_user_model()
SEASON = timezone.localdate().year
SECRET = "Left foot needs work - do not share"


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _player(name, *, position="striker", age=22, region="gauteng", visibility="scouts"):
    today = date.today()
    user = User.objects.create_user(email=f"{name.lower()}@reports.test", password="pw-123456789", display_name=name)
    profile = PlayerProfile.objects.create(
        user=user,
        first_name=name,
        last_name="Test",
        date_of_birth=date(today.year - age, 3, 1),
        gender_category="men",
        region=region,
        visibility=visibility,
    )
    PlayerSport.objects.create(profile=profile, sport="soccer", primary_position=position, is_primary=True)
    return profile


def _line(profile, season, competition=None, matches=10, **values):
    return PlayerStatLine.objects.create(
        user=profile.user,
        sport="soccer",
        season=season,
        competition=competition,
        matches=matches,
        minutes=matches * 90,
        values={key: {"value": value * matches, "per_match": value} for key, value in values.items()},
        computed_at=timezone.now(),
    )


def _test(profile, value, days_ago, verified_by=None):
    return PhysicalTestResult.objects.create(
        profile=profile,
        sport="soccer",
        test_key="sprint_40m",
        value=value,
        unit="s",
        tested_on=date.today() - timedelta(days=days_ago),
        source="coach" if verified_by else "self",
        verified_by=verified_by,
    )


def _rate(profile, scout, organisation, average, days_ago, notes="", clips=None):
    return ScoutRating.objects.create(
        client_id=uuid.uuid4(),
        profile=profile,
        scout=scout,
        organisation=organisation,
        sport="soccer",
        confidence="high",
        area_scores={area: average for area in ("physical", "technical", "tactical", "mental", "context")},
        current_ability=average,
        potential=average + 1,
        recommendation="trial",
        notes=notes,
        clips=clips or [],
        observed_at=timezone.now() - timedelta(days=days_ago),
    )


@pytest.fixture
def world(db):
    lions = Organisation.objects.create(name="Lions", kind="academy", region="gauteng")
    rivals = Organisation.objects.create(name="Rivals", kind="club")
    scout = User.objects.create_user(email="scout@reports.test", password="pw-123456789", display_name="Scout One")
    admin = User.objects.create_user(email="admin@reports.test", password="pw-123456789", display_name="Scout Admin")
    rival = User.objects.create_user(email="rival@reports.test", password="pw-123456789", display_name="Rival")
    coach = User.objects.create_user(email="coach@reports.test", password="pw-123456789", display_name="Coach")
    grant_role(scout, "scout", organisation=lions)
    grant_role(admin, "scout_admin", organisation=lions)
    grant_role(rival, "scout", organisation=rivals)

    fast = _player("Fast", region="western-cape")
    steady = _player("Steady", position="central-midfield")
    young = _player("Young", age=16)  # under 18 without consent: hidden from scouts
    hidden = _player("Hidden", visibility="private")

    _test(fast, "5.30", 200)
    _test(fast, "4.95", 20, verified_by=coach)
    _test(steady, "5.40", 30, verified_by=coach)
    _line(fast, SEASON - 1, goals=0.4, assists=0.1)
    _line(fast, SEASON, goals=0.9, assists=0.3)
    _line(steady, SEASON, goals=0.2, assists=0.5)

    _rate(fast, scout, lions, 6, 120, notes="Quick but raw")
    _rate(fast, scout, lions, 8, 10, notes=SECRET, clips=[{"url": "https://video.example/clip-1"}])
    _rate(fast, admin, lions, 7, 5)
    _rate(steady, scout, lions, 6, 15)
    _rate(young, scout, lions, 9, 5)

    owner = User.objects.create_user(email="owner@reports.test", password="pw-123456789")
    league = Competition.objects.create(name="Provincial league", owner=owner, sport="soccer", open_to_scouts=True)
    closed = Competition.objects.create(name="Closed league", owner=owner, sport="soccer")
    team = Participant.objects.create(competition=league, name="Stars", kind="team")
    for profile in (fast, steady, young, hidden):
        RosterMember.objects.create(participant=team, name=profile.first_name, user=profile.user)
        _line(profile, SEASON, competition=league, matches=6, goals=0.5 if profile is fast else 0.2, assists=0.1)

    shortlist = Shortlist.objects.create(organisation=lions, name="Strikers", created_by=scout)
    ShortlistEntry.objects.create(shortlist=shortlist, profile=fast, added_by=scout, assigned_to=scout)
    ShortlistEntry.objects.create(shortlist=shortlist, profile=steady, added_by=scout, status="contacted")
    return {
        "lions": lions,
        "scout": scout,
        "admin": admin,
        "rival": rival,
        "fast": fast,
        "steady": steady,
        "young": young,
        "hidden": hidden,
        "league": league,
        "closed": closed,
        "shortlist": shortlist,
    }


def _report(user, kind, **params):
    return _client(user).get(f"/api/v1/scouting/reports/{kind}", params)


def _sections(data) -> dict:
    return {section["heading"]: section for section in data["sections"]}


def test_the_player_report_has_every_part_for_a_scout(world):
    response = _report(world["scout"], "player", profile=str(world["fast"].id))
    assert response.status_code == 200, response.data
    data = response.data
    assert data["organisation"]["name"] == "Lions"
    kinds = {section["type"] for section in data["sections"]}
    assert {"facts", "table", "radar", "line", "notes", "links"} <= kinds
    sections = _sections(data)
    tests = sections["Physical tests vs percentiles"]
    assert tests["columns"][2:4] == ["Date", "Verified"]
    assert tests["rows"][0][1] == "4.95 s" and tests["rows"][0][3] == "Verified"
    notes = next(section for section in data["sections"] if section["type"] == "notes")
    assert {item["text"] for item in notes["items"]} == {SECRET, "Quick but raw"}
    links = next(section for section in data["sections"] if section["type"] == "links")
    assert any(item["url"] == "https://video.example/clip-1" for item in links["items"])
    history = next(section for section in data["sections"] if section["type"] == "line")
    assert [point["value"] for point in history["points"]] == [6.0, 8.0, 7.0]
    ability = sections["Ability and recommendation"]
    assert ability["rows"][2]["value"].startswith("Trial")
    profile = sections["Profile"]
    assert all("@" not in row["value"] for row in profile["rows"])


def test_report_numbers_match_the_stats_api(world):
    fast = world["fast"]
    stats = _client(world["scout"]).get(f"/api/v1/scouting/profiles/{fast.id}/stats", {"sport": "soccer"}).data
    report = _sections(_report(world["scout"], "player", profile=str(fast.id)).data)
    best = next(row for row in stats["tests"] if row["key"] == "sprint_40m")["personal_best"]
    row = next(row for row in report["Physical tests vs percentiles"]["rows"] if row[0] == "40 m sprint")
    assert row[1] == f"{best['value']:g} s"
    assert row[2] == best["tested_on"].isoformat()
    season = report[f"Season {SEASON} stats (10 matches)"]
    goals = next(item for item in stats["stats"] if item["key"] == "goals")
    assert next(row for row in season["rows"] if row[0] == "Goals")[1] == f"{goals['value']:g}"


def test_scout_notes_and_ratings_stay_inside_the_organisation(world):
    fast = world["fast"]
    rival = _report(world["rival"], "player", profile=str(fast.id)).data
    assert SECRET not in json.dumps(rival, default=str)
    assert rival["organisation"]["name"] == "Rivals"
    assert not any(section["type"] in {"radar", "notes"} for section in rival["sections"])

    own = _report(fast.user, "player", profile=str(fast.id)).data
    assert own["access"] == "owner"
    assert own["organisation"] is None
    assert SECRET not in json.dumps(own, default=str)
    assert not any(section["type"] in {"radar", "notes", "line"} for section in own["sections"])
    assert "clip-1" not in json.dumps(own, default=str)


def test_hidden_players_have_no_report(world):
    for name in ("young", "hidden"):
        for kind in ("player", "progress"):
            response = _report(world["scout"], kind, profile=str(world[name].id))
            assert response.status_code == 404, (name, kind)
    assert _client(world["scout"]).get(
        "/api/v1/scouting/reports/compare", {"profiles": f"{world['fast'].id},{world['young'].id}"}
    ).status_code == 404


def test_the_progress_report_highlights_the_biggest_improvements(world):
    data = _report(world["scout"], "progress", profile=str(world["fast"].id)).data
    highlights = next(section for section in data["sections"] if section["type"] == "highlights")
    # The largest relative gains lead: assists 0.1 → 0.3, goals 0.4 → 0.9, rating 6 → 7.
    assert [item.split(":")[0] for item in highlights["items"]] == [
        "Assists per match",
        "Goals per match",
        "Average scout rating",
    ]
    tests = _sections(data)["Physical tests over time"]
    assert tests["rows"][0][0] == "40 m sprint"
    assert tests["rows"][0][-1] == "better" and tests["highlight"] == [0]
    assert "Self-reported" in tests["rows"][0][1] and "Verified" in tests["rows"][0][2]
    windowed = _report(
        world["scout"], "progress", profile=str(world["fast"].id), **{"from": (date.today() - timedelta(days=60)).isoformat()}
    ).data
    assert "Physical tests over time" not in _sections(windowed)


def test_compare_and_shortlist_reports(world):
    ids = f"{world['fast'].id},{world['steady'].id}"
    compare = _report(world["scout"], "compare", profiles=ids).data
    radar = next(section for section in compare["sections"] if section["type"] == "radar")
    assert [series["name"] for series in radar["series"]] == ["Fast Test", "Steady Test"]

    shortlist = _report(world["scout"], "shortlist", shortlist=str(world["shortlist"].id)).data
    players = _sections(shortlist)["Players"]
    assert [row[0] for row in players["rows"]] == ["Fast Test", "Steady Test"]
    assert players["rows"][0][1] == "Watching" and players["rows"][1][1] == "Contacted"
    assert _report(world["rival"], "shortlist", shortlist=str(world["shortlist"].id)).status_code == 404


def test_the_competition_report_lists_visible_standouts_by_position(world):
    data = _report(world["scout"], "competition", competition=str(world["league"].id)).data
    sections = _sections(data)
    strikers = sections["Striker"]
    assert [row[0] for row in strikers["rows"]] == ["Fast Test"]
    names = json.dumps(data, default=str)
    assert "Young" not in names and "Hidden" not in names
    assert [row[0] for row in sections["Central midfielder"]["rows"]] == ["Steady Test"]
    assert _report(world["scout"], "competition", competition=str(world["closed"].id)).status_code == 404


def test_scout_activity_is_for_scout_admins(world):
    assert _report(world["scout"], "activity").status_code == 403
    data = _report(world["admin"], "activity").data
    sections = _sections(data)
    # The last 90 days: Scout One's rating from 120 days ago is outside the window.
    per_scout = {row[0]: row for row in sections["Ratings per scout"]["rows"]}
    assert per_scout["Scout One"][1] == "3"
    assert per_scout["Scout Admin"][1] == "1"
    longer = _report(world["admin"], "activity", **{"from": (date.today() - timedelta(days=200)).isoformat()}).data
    assert {row[0]: row[1] for row in _sections(longer)["Ratings per scout"]["rows"]}["Scout One"] == "4"
    summary = {row["label"]: row["value"] for row in sections["Summary"]["rows"]}
    assert summary["Players watched"] == "3"
    regions = dict(sections["Coverage by region"]["rows"])
    assert regions == {"gauteng": "2", "western-cape": "1"}


@pytest.mark.parametrize(
    "kind,params",
    [
        ("player", lambda w: {"profile": str(w["fast"].id)}),
        ("progress", lambda w: {"profile": str(w["fast"].id)}),
        ("compare", lambda w: {"profiles": f"{w['fast'].id},{w['steady'].id}"}),
        ("shortlist", lambda w: {"shortlist": str(w["shortlist"].id)}),
        ("competition", lambda w: {"competition": str(w["league"].id)}),
        ("activity", lambda w: {}),
    ],
)
def test_every_report_exports_a_logged_pdf(world, kind, params):
    viewer = world["admin"] if kind == "activity" else world["scout"]
    before = ReportExport.objects.count()
    response = _client(viewer).get(f"/api/v1/scouting/reports/{kind}/pdf", params(world))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert f"{kind}-report" in response["Content-Disposition"]
    log = ReportExport.objects.order_by("-created_at").first()
    assert ReportExport.objects.count() == before + 1
    assert (log.kind, log.file_format, log.viewer_id) == (f"{kind}_report", "pdf", viewer.id)
    # Viewing on screen is not an export.
    _client(viewer).get(f"/api/v1/scouting/reports/{kind}", params(world))
    assert ReportExport.objects.count() == before + 1


def test_unknown_reports_and_strangers_are_refused(world):
    assert _report(world["scout"], "everything").status_code == 404
    stranger = User.objects.create_user(email="stranger@reports.test", password="pw-123456789")
    assert _report(stranger, "compare", profiles=f"{world['fast'].id},{world['steady'].id}").status_code == 403
    assert APIClient().get("/api/v1/scouting/reports/player", {"profile": str(world["fast"].id)}).status_code == 401
