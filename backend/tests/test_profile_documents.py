"""Main profile: optional passport/ID uploads, and teams joined through invites."""

from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import IdentityDocument
from apps.competitions.models import Competition, Membership, Participant, TeamPick
from apps.core.permissions import Role
from apps.scouting.models import Organisation, PlayerProfile
from apps.scouting.services import grant_role

pytestmark = pytest.mark.django_db
User = get_user_model()

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def private_root(settings, tmp_path):
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "private"
    settings.MEDIA_ROOT = tmp_path / "public"
    return settings.PRIVATE_MEDIA_ROOT


def _client(email: str) -> tuple[APIClient, object]:
    person = User.objects.create_user(email=email, password="pw-123456789")
    client = APIClient()
    client.force_authenticate(person)
    return client, person


def _upload(client, kind: str, body: bytes, name: str = "scan.pdf", content_type="application/pdf"):
    return client.post(
        "/api/v1/auth/me/documents",
        {"kind": kind, "file": SimpleUploadedFile(name, body, content_type=content_type)},
        format="multipart",
    )


def test_documents_are_optional(private_root):
    client, _ = _client("nodocs@profile.test")
    assert client.get("/api/v1/auth/me/documents").data == []
    profile = client.post(
        "/api/v1/scouting/profile", {"first_name": "No", "last_name": "Docs"}, format="json"
    )
    assert profile.status_code == 201


def test_upload_download_and_replace_a_passport(private_root):
    client, person = _client("passport@profile.test")
    first = _upload(client, "passport", PDF)
    assert first.status_code == 201, first.data
    assert first.data["content_type"] == "application/pdf"
    assert "url" not in first.data and "file" not in first.data

    stored = IdentityDocument.objects.get(user=person)
    assert stored.file.path.startswith(str(private_root.resolve()))
    with pytest.raises(ValueError):
        stored.file.url  # noqa: B018 - there is deliberately no public URL

    downloaded = client.get(f"/api/v1/auth/me/documents/{first.data['id']}/file")
    assert downloaded.status_code == 200
    assert b"".join(downloaded.streaming_content) == PDF
    assert downloaded["Cache-Control"] == "private, no-store"

    old_path = stored.file.path
    second = _upload(client, "passport", PNG, name="passport.png", content_type="image/png")
    assert second.status_code == 201
    assert IdentityDocument.objects.filter(user=person).count() == 1
    assert IdentityDocument.objects.get(user=person).content_type == "image/png"
    import os

    assert not os.path.exists(old_path)


def test_a_disguised_file_is_refused(private_root):
    client, _ = _client("fake@profile.test")
    refused = _upload(client, "national_id", b"MZ\x90\x00 not really a pdf", name="id.pdf")
    assert refused.status_code == 400
    bad_kind = _upload(client, "drivers_licence", PDF)
    assert bad_kind.status_code == 400


def test_nobody_else_can_list_or_download_a_document(private_root):
    owner, _ = _client("owner.docs@profile.test")
    doc_id = _upload(owner, "national_id", PDF).data["id"]

    scout, scout_user = _client("scout.docs@profile.test")
    grant_role(scout_user, "scout_admin", organisation=Organisation.objects.create(name="Org"))
    assert scout.get("/api/v1/auth/me/documents").data == []
    assert scout.get(f"/api/v1/auth/me/documents/{doc_id}/file").status_code == 404
    assert scout.delete(f"/api/v1/auth/me/documents/{doc_id}").status_code == 404


def test_scouts_never_learn_a_document_exists(private_root):
    client, person = _client("hidden.docs@profile.test")
    profile = PlayerProfile.objects.create(
        user=person,
        first_name="Hidden",
        last_name="Docs",
        date_of_birth=date(date.today().year - 25, 1, 1),
        visibility="public",
    )
    _upload(client, "passport", PDF)

    scout, scout_user = _client("scout.view@profile.test")
    grant_role(scout_user, "scout", organisation=Organisation.objects.create(name="Org 2"))
    view = scout.get(f"/api/v1/scouting/profiles/{profile.id}")
    report = scout.get(f"/api/v1/scouting/profiles/{profile.id}/report")
    for response in (view, report):
        text = str(response.data).lower()
        assert "passport" not in text and "national_id" not in text and "identity" not in text


def test_deleting_a_document_or_account_removes_the_file(private_root):
    import os

    client, person = _client("cleanup@profile.test")
    first = _upload(client, "passport", PDF).data
    path = IdentityDocument.objects.get(pk=first["id"]).file.path
    assert client.delete(f"/api/v1/auth/me/documents/{first['id']}").status_code == 204
    assert not os.path.exists(path)

    _upload(client, "national_id", PDF)
    path = IdentityDocument.objects.get(user=person).file.path
    person.delete()
    assert not os.path.exists(path)


def test_accepted_team_invites_appear_on_my_profile():
    _, admin = _client("admin.teams@profile.test")
    competition = Competition.objects.create(name="Harbour League", owner=admin, sport="netball")
    Membership.objects.create(competition=competition, user=admin, role=Role.OWNER)
    team = Participant.objects.create(competition=competition, name="Harbour Hawks", kind="team")

    player, person = _client("invited@profile.test")
    PlayerProfile.objects.create(user=person, first_name="Invited", last_name="Player")
    pick = TeamPick.objects.create(participant=team, user=person, invited_by=admin)

    before = player.get("/api/v1/scouting/me/team-memberships").data
    assert before["teams"] == []
    assert before["pending_invites"] == 1
    assert before["invites"][0]["team_name"] == "Harbour Hawks"
    assert before["invites"][0]["competition_name"] == "Harbour League"

    inbox = player.get("/api/v1/me/team-picks")
    assert inbox.status_code == 200
    assert [row["team_name"] for row in inbox.data] == ["Harbour Hawks"]

    accepted = player.post(f"/api/v1/competitions/{competition.id}/picks/{pick.id}/accept")
    assert accepted.status_code in {200, 201}, accepted.data

    after = player.get("/api/v1/scouting/me/team-memberships").data
    assert [row["name"] for row in after["teams"]] == ["Harbour Hawks"]
    assert after["teams"][0]["sport_key"] == "netball"
    assert after["teams"][0]["sport_label"] == "Netball"
    assert after["pending_invites"] == 0

    talent = player.get("/api/v1/scouting/profile").data
    assert [row["name"] for row in talent["teams"]] == ["Harbour Hawks"]
    assert talent["school_or_club"] == "Harbour Hawks"
