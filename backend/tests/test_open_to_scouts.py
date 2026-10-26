"""The "Open to scouts" competition setting: exposure, league scouts and the league's squad."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Membership, Participant, RosterMember
from apps.core.permissions import Role
from apps.fixtures.models import Fixture, FixtureSide, PlayerMatchRating
from apps.scouting import catalog
from apps.scouting.models import LeagueScout, Organisation, PlayerProfile
from apps.scouting.services import grant_role

pytestmark = pytest.mark.django_db
User = get_user_model()

SPORT = next(iter(catalog.SQUADS))


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _user(email: str):
    return User.objects.create_user(email=email, password="pw-123456789")


def _scout(email: str):
    person = _user(email)
    grant_role(person, "scout", organisation=Organisation.objects.create(name=f"Org {email}"))
    return person


@pytest.fixture
def owner(db):
    return _user("owner@open.test")


def _league(owner, *, open_to_scouts=False, private=False, sport=SPORT) -> Competition:
    competition = Competition.objects.create(
        name=f"League {Competition.objects.count() + 1}",
        owner=owner,
        sport=sport,
        is_private=private,
        open_to_scouts=open_to_scouts,
    )
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    Participant.objects.create(competition=competition, name="Hawks", kind="team")
    return competition


def test_a_sport_competition_can_be_created_open_to_scouts(owner):
    response = _client(owner).post(
        "/api/v1/competitions",
        {"name": "Scouted league", "preset": "soccer", "open_to_scouts": True},
        format="json",
    )
    assert response.status_code == 201, response.data
    competition = Competition.objects.get(pk=response.data["id"])
    assert competition.open_to_scouts is True

    detail = _client(owner).get(f"/api/v1/competitions/{competition.id}").data
    assert detail["open_to_scouts"] is True
    assert detail["scouting_eligible"] is True


def test_non_sport_competitions_cannot_be_opened_to_scouts(owner):
    response = _client(owner).post(
        "/api/v1/competitions",
        {
            "name": "Office KPIs",
            "preset": "kpi",
            "open_to_scouts": True,
        },
        format="json",
    )
    assert response.status_code == 400
    assert "open_to_scouts" in response.data["error"]["detail"]

    chess = _league(owner, sport="chess")
    patched = _client(owner).patch(
        f"/api/v1/competitions/{chess.id}", {"open_to_scouts": True}, format="json"
    )
    assert patched.status_code == 400
    assert _client(owner).get(f"/api/v1/competitions/{chess.id}").data["scouting_eligible"] is False


def test_the_setting_is_off_by_default_and_can_be_turned_on_later(owner):
    competition = _league(owner)
    assert competition.open_to_scouts is False
    patched = _client(owner).patch(
        f"/api/v1/competitions/{competition.id}", {"open_to_scouts": True}, format="json"
    )
    assert patched.status_code == 200
    competition.refresh_from_db()
    assert competition.open_to_scouts is True


def test_closed_leagues_have_no_squad_and_are_hidden_from_scouts(owner):
    closed = _league(owner)
    scout = _scout("scout@open.test")

    generated = _client(owner).post(f"/api/v1/scouting/leagues/{closed.id}/squad/generate")
    assert generated.status_code == 200, generated.data
    blocked = _client(scout).post(f"/api/v1/scouting/leagues/{closed.id}/squad/generate")
    assert blocked.status_code == 403
    assert "not open to scouts" in str(blocked.data)
    assert _client(scout).get(f"/api/v1/scouting/leagues/{closed.id}/candidates").status_code == 403

    scout_rows = _client(scout).get("/api/v1/scouting/leagues").data
    assert all(row["id"] != str(closed.id) for row in scout_rows)

    # The owner still sees it listed, marked closed, so they know to turn it on.
    owner_rows = _client(owner).get("/api/v1/scouting/leagues").data
    row = next(item for item in owner_rows if item["id"] == str(closed.id))
    assert row["open_to_scouts"] is False
    assert row["can_select"] is False
    assert row["can_manage"] is True


def test_open_private_leagues_are_exposed_to_scouts_only(owner):
    league = _league(owner, open_to_scouts=True, private=True)
    scout = _scout("scout2@open.test")
    stranger = _user("stranger@open.test")

    assert any(
        row["id"] == str(league.id) for row in _client(scout).get("/api/v1/scouting/leagues").data
    )
    assert _client(scout).get(f"/api/v1/scouting/leagues/{league.id}/candidates").status_code == 200
    assert _client(stranger).get(f"/api/v1/scouting/leagues/{league.id}/squad").status_code == 404
    # Opening a league to scouts does not open its feed or table to them.
    assert _client(scout).get(f"/api/v1/competitions/{league.id}").status_code == 404


def test_admins_attach_scouts_who_then_help_pick_the_squad(owner):
    league = _league(owner, open_to_scouts=True)
    scout = _scout("league.scout@open.test")
    plain = _user("plain@open.test")
    owner_client = _client(owner)

    refused = owner_client.post(
        f"/api/v1/scouting/leagues/{league.id}/scouts", {"email": plain.email}, format="json"
    )
    assert refused.status_code == 400

    # A scout cannot attach themselves.
    self_added = _client(scout).post(
        f"/api/v1/scouting/leagues/{league.id}/scouts", {"email": scout.email}, format="json"
    )
    assert self_added.status_code == 403

    added = owner_client.post(
        f"/api/v1/scouting/leagues/{league.id}/scouts", {"email": scout.email}, format="json"
    )
    assert added.status_code == 201
    assert [row["user_id"] for row in added.data["scouts"]] == [str(scout.id)]
    assert LeagueScout.objects.get().organisation is not None

    generated = _client(scout).post(f"/api/v1/scouting/leagues/{league.id}/squad/generate")
    assert generated.status_code == 200
    assert generated.data["squad"]["can_edit"] is True

    other_scout = _scout("other.scout@open.test")
    assert (
        _client(other_scout)
        .post(f"/api/v1/scouting/leagues/{league.id}/squad/generate")
        .status_code
        == 403
    )

    row_id = added.data["scouts"][0]["id"]
    left = _client(scout).delete(f"/api/v1/scouting/leagues/{league.id}/scouts/{row_id}")
    assert left.status_code == 200
    assert left.data["scouts"] == []


def test_reports_only_use_leagues_open_to_scouts(owner):
    person = _user("player@open.test")
    profile = PlayerProfile.objects.create(
        user=person,
        first_name="Open",
        last_name="Player",
        date_of_birth=date(date.today().year - 22, 1, 1),
        visibility="scouts",
    )
    scout = _scout("reader@open.test")

    for opened in (True, False):
        league = _league(owner, open_to_scouts=opened)
        team = league.participants.get()
        member = RosterMember.objects.create(participant=team, name="Open Player", user=person)
        fixture = Fixture.objects.create(competition=league, status=Fixture.Status.COMPLETED)
        FixtureSide.objects.create(fixture=fixture, participant=team, position=0, outcome="win")
        PlayerMatchRating.objects.create(fixture=fixture, player=member, rating=Decimal("8"))

    report = _client(scout).get(f"/api/v1/scouting/profiles/{profile.id}/report").data
    assert [row["competition"] for row in report["leagues"]] == [
        Competition.objects.get(open_to_scouts=True, owner=owner).name
    ]
