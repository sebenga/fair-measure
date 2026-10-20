"""Final scouting regression: the whole journey through the API, then the privacy rules.

player creates a profile → guardian consents → coach records tests → matches are
scored with player tags → a scout rates offline and syncs → search finds the
player → compare with two others → add to a shortlist → player report PDF.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.competitions.presets import apply_preset
from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide
from apps.scouting import catalog
from apps.scouting.models import (
    Organisation,
    PlayerProfile,
    PlayerSport,
    PlayerStatLine,
    ReportExport,
    ScoutRating,
    ShortlistLog,
)
from apps.scouting.services import grant_role

pytestmark = pytest.mark.django_db
User = get_user_model()
NOTE = "Private to Lions: hesitant on his weaker foot"


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _person(email, name):
    return User.objects.create_user(email=email, password="pw-123456789", display_name=name)


def _adult(name, sprint):
    from apps.scouting.models import PhysicalTestResult

    user = _person(f"{name.lower()}@journey.test", name)
    profile = PlayerProfile.objects.create(
        user=user,
        first_name=name,
        last_name="Adult",
        date_of_birth=date(date.today().year - 23, 2, 1),
        gender_category="men",
        region="gauteng",
        visibility="scouts",
    )
    PlayerSport.objects.create(profile=profile, sport="soccer", primary_position="striker", is_primary=True)
    PhysicalTestResult.objects.create(
        profile=profile, sport="soccer", test_key="sprint_40m", value=sprint, unit="s", tested_on=date.today()
    )
    return profile


def _contains_contact(payload, *emails) -> bool:
    text = json.dumps(payload, default=str).lower()
    return any(email.lower() in text for email in emails)


def test_the_whole_scouting_journey_and_its_privacy(settings):
    # --- People -----------------------------------------------------------------------
    player_user = _person("teen.striker@journey.test", "Teen Striker")
    guardian_user = _person("mum@journey.test", "Mum")
    coach_user = _person("coach@journey.test", "Coach")
    scout_user = _person("scout@journey.test", "Lions Scout")
    rival_user = _person("rival@journey.test", "Rival Scout")
    owner = _person("owner@journey.test", "League Owner")
    lions = Organisation.objects.create(name="Lions", kind="academy")
    rivals = Organisation.objects.create(name="Rivals", kind="club")
    grant_role(scout_user, "scout", organisation=lions)
    grant_role(rival_user, "scout", organisation=rivals)
    player, guardian, coach, scout, rival = (
        _client(player_user),
        _client(guardian_user),
        _client(coach_user),
        _client(scout_user),
        _client(rival_user),
    )

    # --- 1. The player creates a profile (16, so a minor) -----------------------------------
    born = date(date.today().year - 16, 3, 1).isoformat()
    created = player.post(
        "/api/v1/scouting/profile",
        {
            "first_name": "Sizwe",
            "last_name": "Dube",
            "date_of_birth": born,
            "gender_category": "men",
            "region": "gauteng",
            "visibility": "scouts",
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    profile_id = created.data["id"]
    assert created.data["is_minor"] is True and created.data["effective_visibility"] == "private"
    sport = player.post(
        "/api/v1/scouting/profile/sports",
        {"sport": "soccer", "primary_position": "striker", "is_primary": True},
        format="json",
    )
    assert sport.status_code == 201, sport.data
    # Hidden from scouts until a guardian consents.
    assert scout.get(f"/api/v1/scouting/profiles/{profile_id}").status_code == 404
    hidden_search = scout.post("/api/v1/scouting/search", {"filters": {}}, format="json").json()["results"]
    assert profile_id not in {row["id"] for row in hidden_search}

    # --- 2. The guardian consents ------------------------------------------------------------
    assert player.post("/api/v1/scouting/profile/guardians", {"email": "mum@journey.test", "relationship": "Mother"}, format="json").status_code == 201
    link = guardian.get("/api/v1/scouting/guardian/links").data[0]["id"]
    assert guardian.post(f"/api/v1/scouting/guardian/links/{link}/accept").status_code == 200
    consent = guardian.post(
        f"/api/v1/scouting/guardian/profiles/{profile_id}/consent",
        {"visibility": "scouts", "sections": ["physical", "videos"], "note": "Happy for scouts to see"},
        format="json",
    )
    assert consent.status_code == 201, consent.data
    seen = scout.get(f"/api/v1/scouting/profiles/{profile_id}")
    assert seen.status_code == 200 and seen.data["access"] == "scout"

    # --- 3. The team and its coach; the coach records verified tests ---------------------------
    league = Competition.objects.create(name="Provincial U17", owner=owner, sport="soccer", open_to_scouts=True)
    apply_preset(league, "soccer")
    hawks = Participant.objects.create(competition=league, name="Hawks", kind="team")
    owls = Participant.objects.create(competition=league, name="Owls", kind="team")
    member = RosterMember.objects.create(participant=hawks, name="Sizwe Dube", user=player_user, position="striker")
    keeper = RosterMember.objects.create(participant=owls, name="Owls keeper", position="goalkeeper")
    grant_role(coach_user, "coach", team=hawks)
    for days, value in ((60, "5.20"), (5, "4.88")):
        recorded = coach.post(
            f"/api/v1/scouting/profiles/{profile_id}/tests",
            {"sport": "soccer", "test_key": "sprint_40m", "value": value, "tested_on": (date.today() - timedelta(days=days)).isoformat()},
            format="json",
        )
        assert recorded.status_code == 201, recorded.data
        assert recorded.json()["label"] == "Verified"

    # --- 4. Matches are scored with player tags -------------------------------------------
    referee = _person("ref@journey.test", "Referee")
    goal = league.scoring_categories.get(code="goal")
    for days in (14, 7):
        fixture = Fixture.objects.create(
            competition=league, status=Fixture.Status.LIVE, scheduled_at=timezone.now() - timedelta(days=days)
        )
        home = FixtureSide.objects.create(fixture=fixture, participant=hawks, position=0, is_home=True)
        FixtureSide.objects.create(fixture=fixture, participant=owls, position=1)
        FixtureReferee.objects.create(fixture=fixture, user=referee)
        tagged = _client(referee).post(
            f"/api/v1/fixtures/{fixture.id}/events",
            {"side": str(home.id), "scoring_category": str(goal.id), "quantity": "1", "player": str(member.id), "minutes": 90},
            format="json",
        )
        assert tagged.status_code == 201, tagged.data
        done = _client(owner).post(
            f"/api/v1/competitions/{league.id}/fixtures/{fixture.id}/set-status", {"status": "completed"}, format="json"
        )
        assert done.status_code == 200, done.data
    # The stats job (the worker calls this endpoint after results change).
    settings.INTERNAL_API_TOKEN = "journey-token"
    job = APIClient().post(
        "/internal/scouting/stats",
        {"competition_id": str(league.id)},
        format="json",
        HTTP_AUTHORIZATION="Bearer journey-token",
    )
    assert job.status_code == 200, job.data
    line = PlayerStatLine.objects.get(user=player_user, competition=None, sport="soccer")
    assert line.values["goals"]["value"] == 2.0 and line.matches == 2
    assert keeper.user_id is None

    # --- 5. A scout rates pitch-side offline, then syncs (twice: the retry is a duplicate) ---------
    queued = {
        "client_id": str(uuid.uuid4()),
        "profile": profile_id,
        "sport": "soccer",
        "mode": "quick",
        "confidence": "high",
        "watched": "live",
        "area_scores": {"physical": 8, "technical": 7, "tactical": 6, "mental": 8, "context": 6},
        "current_ability": 7,
        "potential": 9,
        "recommendation": "trial",
        "notes": NOTE,
        "observed_at": (timezone.now() - timedelta(hours=5)).isoformat(),
    }
    first = scout.post("/api/v1/scouting/ratings/sync", {"ratings": [queued]}, format="json")
    retry = scout.post("/api/v1/scouting/ratings/sync", {"ratings": [queued]}, format="json")
    assert first.json()["results"][0]["status"] == "created"
    assert retry.json()["results"][0]["status"] == "duplicate"
    assert ScoutRating.objects.filter(profile_id=profile_id).count() == 1

    # --- 6. Search finds the player ----------------------------------------------------------
    others = [_adult("Ayo", "5.05"), _adult("Bongani", "5.30")]
    found = scout.post(
        "/api/v1/scouting/search",
        {"filters": {"sport": "soccer", "position": "striker", "tests": [{"key": "sprint_40m", "op": "lt", "value": 5}]}},
        format="json",
    )
    assert found.status_code == 200, found.data
    assert [row["id"] for row in found.json()["results"]] == [profile_id]

    # --- 7. Compare with two others ------------------------------------------------------------
    ids = ",".join([profile_id, *[str(other.id) for other in others]])
    compared = scout.get("/api/v1/scouting/compare", {"profiles": ids, "sport": "soccer"})
    assert compared.status_code == 200, compared.data
    assert [row["id"] for row in compared.data["players"]][0] == profile_id
    assert compared.data["players"][0]["tests"]["sprint_40m"]["best"] == 4.88

    # --- 8. Add to a shortlist ---------------------------------------------------------------
    shortlist = scout.post("/api/v1/scouting/shortlists", {"name": "U17 strikers"}, format="json")
    assert shortlist.status_code == 201, shortlist.data
    entry = scout.post(f"/api/v1/scouting/shortlists/{shortlist.data['id']}/entries", {"profile": profile_id}, format="json")
    assert entry.status_code == 201, entry.data
    assert ShortlistLog.objects.filter(shortlist_id=shortlist.data["id"], profile_id=profile_id).exists()

    # --- 9. Generate the player report PDF -----------------------------------------------------
    report = scout.get("/api/v1/scouting/reports/player", {"profile": profile_id})
    assert report.status_code == 200
    pdf = scout.get("/api/v1/scouting/reports/player/pdf", {"profile": profile_id})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert ReportExport.objects.filter(viewer=scout_user, kind="player_report", file_format="pdf", profile_id=profile_id).exists()

    # --- Privacy: contact details are never exposed to scouts ------------------------------
    for payload in (
        seen.data,
        found.json(),
        compared.data,
        report.data,
        scout.get(f"/api/v1/scouting/shortlists/{shortlist.data['id']}").data,
        scout.get(f"/api/v1/scouting/profiles/{profile_id}/stats").data,
    ):
        assert not _contains_contact(payload, player_user.email, guardian_user.email), payload

    # --- Privacy: scout notes never reach the player, the guardian or another organisation ---
    assert NOTE in json.dumps(report.data, default=str)
    for viewer in (player, guardian, rival):
        own = viewer.get("/api/v1/scouting/reports/player", {"profile": profile_id})
        assert own.status_code == 200
        assert NOTE not in json.dumps(own.data, default=str)
        ratings = viewer.get(f"/api/v1/scouting/profiles/{profile_id}/ratings")
        assert ratings.status_code in {200, 403, 404}
        assert NOTE not in json.dumps(getattr(ratings, "data", {}), default=str)

    # --- Privacy: a minor is hidden again the moment consent is withdrawn --------------------
    assert guardian.delete(f"/api/v1/scouting/guardian/profiles/{profile_id}/consent").status_code == 200
    assert scout.get(f"/api/v1/scouting/profiles/{profile_id}").status_code == 404
    assert scout.get("/api/v1/scouting/reports/player", {"profile": profile_id}).status_code == 404
    after = scout.post("/api/v1/scouting/search", {"filters": {}}, format="json").json()["results"]
    assert profile_id not in {row["id"] for row in after}
    competition = scout.get("/api/v1/scouting/reports/competition", {"competition": str(league.id)}).data
    assert "Sizwe" not in json.dumps(competition, default=str)


SCOUTING_CODE = [
    "apps/scouting/search.py",
    "apps/scouting/stats.py",
    "apps/scouting/ratings.py",
    "apps/scouting/services.py",
    "apps/scouting/selection.py",
    "apps/scouting/reports.py",
    "apps/scouting/talent_reports.py",
    "apps/scouting/report_pdf.py",
    "apps/scouting/discovery_views.py",
    "apps/scouting/stats_views.py",
    "apps/scouting/ratings_views.py",
    "apps/scouting/views.py",
    "apps/scouting/serializers.py",
]


def test_no_scouting_code_branches_on_a_sport_name():
    names = set()
    for key, entry in catalog.SPORTS.items():
        names |= {key, key.replace("_", " "), str(entry["label"]).lower()}
    pattern = re.compile(r"""(==|!=|\bin\b|\bis\b)\s*\(?\s*['"]([a-z _-]+)['"]""")
    for module in SCOUTING_CODE:
        text = Path(module).read_text().lower()
        for match in pattern.finditer(text):
            assert match.group(2).strip() not in names, f"{module} compares against {match.group(2)!r}"
        for name in names:
            assert f'"{name}"' not in text and f"'{name}'" not in text, f"{module} names {name}"
