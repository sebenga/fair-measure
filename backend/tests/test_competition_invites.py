"""Invites to a competition: the person is told, and joins only if they accept."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.competitions.models import CompetitionInvite, Membership
from apps.notifications.models import Notification, NotificationPreference

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def jobs_run_inline(settings, monkeypatch):
    settings.JOBS_INLINE = True
    settings.JOBS_INLINE_SYNC = True
    # Jobs wait for the commit, which a test transaction never reaches.
    monkeypatch.setattr("apps.core.bus.transaction.on_commit", lambda job, using=None: job())


@pytest.fixture
def invitee(other_user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


def _invite(api, competition, other_user, role="member"):
    response = api.post(
        f"/api/v1/competitions/{competition.id}/members",
        {"user_id": str(other_user.id), "role": role},
        format="json",
    )
    assert response.status_code == 201, response.data
    return response.data


def test_a_private_invite_notifies_and_only_accepting_joins(
    api, invitee, competition, user, other_user
):
    competition.is_private = True
    competition.save(update_fields=["is_private"])

    invite = _invite(api, competition, other_user, role="admin")

    assert invite["status"] == "pending"
    assert not Membership.objects.filter(competition=competition, user=other_user).exists()
    note = Notification.objects.get(user=other_user, kind="competition-invite")
    assert note.data["invite_id"] == invite["id"]
    assert "invited you to Fourways Winter League" in note.title
    assert "Accept or decline" in note.body
    assert invitee.get(f"/api/v1/competitions/{competition.id}").status_code == 404

    waiting = invitee.get("/api/v1/me/invites").data
    assert [row["id"] for row in waiting] == [invite["id"]]
    assert waiting[0]["competition_name"] == "Fourways Winter League"
    assert waiting[0]["competition_is_private"] is True

    accepted = invitee.post(f"/api/v1/invites/{invite['id']}/accept")
    assert accepted.status_code == 200
    assert accepted.data["status"] == "accepted"
    assert Membership.objects.get(competition=competition, user=other_user).role == "admin"
    assert invitee.get(f"/api/v1/competitions/{competition.id}").status_code == 200
    assert invitee.get("/api/v1/me/invites").data == []
    told = Notification.objects.get(user=user, kind="competition-invite-answered")
    assert told.title == "Member joined Fourways Winter League"


def test_declining_a_public_invite_leaves_no_membership(
    api, invitee, competition, user, other_user
):
    invite = _invite(api, competition, other_user)

    declined = invitee.post(f"/api/v1/invites/{invite['id']}/decline")

    assert declined.status_code == 200
    assert declined.data["status"] == "declined"
    assert not Membership.objects.filter(competition=competition, user=other_user).exists()
    told = Notification.objects.get(user=user, kind="competition-invite-answered")
    assert "declined" in told.title
    assert invitee.post(f"/api/v1/invites/{invite['id']}/accept").status_code == 400


def test_only_the_invited_person_can_answer(api, competition, other_user):
    invite = _invite(api, competition, other_user)

    assert api.post(f"/api/v1/invites/{invite['id']}/accept").status_code == 403
    assert CompetitionInvite.objects.get(pk=invite["id"]).status == "pending"


def test_invites_are_not_sent_twice_or_to_members(api, invitee, competition, other_user, user):
    invite = _invite(api, competition, other_user)
    again = api.post(
        f"/api/v1/competitions/{competition.id}/members",
        {"user_id": str(other_user.id)},
        format="json",
    )
    assert again.status_code == 400
    assert "waiting for their answer" in str(again.data)

    invitee.post(f"/api/v1/invites/{invite['id']}/accept")
    member = api.post(
        f"/api/v1/competitions/{competition.id}/members",
        {"email": other_user.email},
        format="json",
    )
    assert member.status_code == 400
    assert "already a member" in str(member.data)


def test_admins_see_and_withdraw_waiting_invites(api, invitee, competition, other_user):
    invite = _invite(api, competition, other_user)

    listed = api.get(f"/api/v1/competitions/{competition.id}/invites")
    assert [row["id"] for row in listed.data] == [invite["id"]]
    assert invitee.get(f"/api/v1/competitions/{competition.id}/invites").status_code == 403

    withdrawn = api.delete(f"/api/v1/competitions/{competition.id}/invites/{invite['id']}")
    assert withdrawn.status_code == 204
    assert invitee.get("/api/v1/me/invites").data == []
    assert invitee.post(f"/api/v1/invites/{invite['id']}/accept").status_code == 400


def test_muting_a_competition_never_hides_an_invite(api, competition, other_user):
    NotificationPreference.objects.create(
        user=other_user, competition=competition, announcements=False, feed_activity=False
    )

    _invite(api, competition, other_user)

    assert Notification.objects.filter(user=other_user, kind="competition-invite").exists()


def test_a_team_pick_joins_the_competition_only_when_accepted(api, invitee, other_user):
    created = api.post(
        "/api/v1/competitions", {"name": "Private Sunday league", "is_private": True}, format="json"
    )
    competition_id = created.data["id"]
    team = api.post(
        f"/api/v1/competitions/{competition_id}/participants",
        {"name": "Northside", "kind": "team"},
        format="json",
    )
    picks_url = f"/api/v1/competitions/{competition_id}/participants/{team.data['id']}/picks"

    offered = api.post(picks_url, {"email": other_user.email.upper()}, format="json")

    assert offered.status_code == 201, offered.data
    assert not Membership.objects.filter(competition_id=competition_id, user=other_user).exists()
    assert Notification.objects.filter(user=other_user, kind="team-invite").exists()
    assert invitee.get(f"/api/v1/competitions/{competition_id}").status_code == 404

    accepted = invitee.post(
        f"/api/v1/competitions/{competition_id}/picks/{offered.data['id']}/accept"
    )
    assert accepted.status_code == 200
    assert Membership.objects.filter(competition_id=competition_id, user=other_user).exists()
    assert invitee.get(f"/api/v1/competitions/{competition_id}").status_code == 200

    unknown = api.post(picks_url, {"email": "nobody@example.com"}, format="json")
    assert unknown.status_code == 400
