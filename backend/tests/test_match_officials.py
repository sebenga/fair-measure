"""Appointed referee control: live scoring is referee-only."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Membership, Participant, RosterMember
from apps.core.permissions import Role
from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide, MatchAuditLog

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def live_match(api, user):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Ref control", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    home = Participant.objects.create(competition=competition, name="Home", kind="team")
    away = Participant.objects.create(competition=competition, name="Away", kind="team")
    player = RosterMember.objects.create(participant=home, name="Striker", number=9)
    fixture = Fixture.objects.create(
        competition=competition,
        label="R1",
        status=Fixture.Status.LIVE,
        duration_minutes=90,
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    return competition, fixture, home_side, player


def _goal(api, fixture, side, player, category):
    return api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": category,
            "quantity": "1",
            "player": str(player.id),
            "minute": 12,
        },
        format="json",
    )


def test_admin_cannot_record_live_events_without_appointment(api, live_match):
    competition, fixture, side, player = live_match
    codes = {
        item["code"]: item["id"]
        for item in api.get(f"/api/v1/competitions/{competition.id}").data["scoring_categories"]
    }
    # Owner is admin, but not an accepted referee.
    blocked = _goal(api, fixture, side, player, codes["goal"])
    assert blocked.status_code == 403


def test_accepted_referee_can_record_and_admin_cannot(api, live_match, user):
    competition, fixture, side, player = live_match
    referee = User.objects.create_user(
        email="ref@example.com", password="s3cret-password", display_name="Ref"
    )
    Membership.objects.create(competition=competition, user=referee, role=Role.MEMBER)
    FixtureReferee.objects.create(
        fixture=fixture,
        user=referee,
        role=FixtureReferee.Role.REFEREE,
        status=FixtureReferee.Status.ACCEPTED,
        appointed_by=user,
    )
    codes = {
        item["code"]: item["id"]
        for item in api.get(f"/api/v1/competitions/{competition.id}").data["scoring_categories"]
    }

    admin_blocked = _goal(api, fixture, side, player, codes["goal"])
    assert admin_blocked.status_code == 403

    ref_api = APIClient()
    ref_api.force_authenticate(user=referee)
    ok = _goal(ref_api, fixture, side, player, codes["goal"])
    assert ok.status_code == 201, ok.data
    assert MatchAuditLog.objects.filter(fixture=fixture, action="event.recorded").exists()


def test_appointment_invite_accept_and_dashboard(api, live_match, user):
    competition, fixture, side, player = live_match
    referee = User.objects.create_user(
        email="whistle@example.com", password="s3cret-password", display_name="Whistle"
    )
    Membership.objects.create(competition=competition, user=referee, role=Role.MEMBER)

    appointed = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/referees",
        {"user": str(referee.id), "role": "referee"},
        format="json",
    )
    assert appointed.status_code == 201, appointed.data
    row = FixtureReferee.objects.get(fixture=fixture, user=referee)
    assert row.status == FixtureReferee.Status.INVITED

    ref_api = APIClient()
    ref_api.force_authenticate(user=referee)
    dash = ref_api.get("/api/v1/referees/me")
    assert dash.status_code == 200
    assert any(item["appointment_id"] == str(row.id) for item in dash.data["pending"])

    accepted = ref_api.post(
        f"/api/v1/referees/appointments/{row.id}/respond",
        {"accept": True},
        format="json",
    )
    assert accepted.status_code == 200
    row.refresh_from_db()
    assert row.status == FixtureReferee.Status.ACCEPTED

    # Kickoff still needs a team sheet, but accepted referee clears the official gate.
    problems = api.get(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}"
    ).data["kickoff_problems"]
    assert "Pick the match officials before kickoff." not in problems
    assert "The appointed referee must accept before kickoff." not in problems


def test_confirm_match_card_moves_to_confirmed(api, live_match, user):
    competition, fixture, side, player = live_match
    FixtureReferee.objects.create(
        fixture=fixture,
        user=user,
        role=FixtureReferee.Role.REFEREE,
        status=FixtureReferee.Status.ACCEPTED,
    )
    fixture.status = Fixture.Status.COMPLETED
    fixture.save(update_fields=["status", "updated_at"])
    confirmed = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/confirm",
        {"notes": "All good"},
        format="json",
    )
    assert confirmed.status_code == 200, confirmed.data
    fixture.refresh_from_db()
    assert fixture.status == Fixture.Status.CONFIRMED
    assert fixture.confirmed_at is not None
