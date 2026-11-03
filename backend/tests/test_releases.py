from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.competitions.models import Competition, Membership
from apps.core.permissions import Role
from apps.releases.models import Release

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture(autouse=True)
def gradual_release(settings):
    settings.RELEASES_SPORTS_LIVE_BY_DEFAULT = False


@pytest.fixture
def admin_api(db) -> APIClient:
    admin = User.objects.create_user(
        email="platform@example.com", password="s3cret-password", display_name="Platform"
    )
    admin.is_staff = True
    admin.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(admin)}")
    return client


def _names(response) -> set[str]:
    rows = response.data["results"] if isinstance(response.data, dict) else response.data
    return {row["name"] for row in rows}


def _league(owner, name: str, preset: str, **extra) -> Competition:
    competition = Competition.objects.create(
        name=name,
        owner=owner,
        sport=preset,
        status=Competition.Status.ACTIVE,
        settings_json={"preset": preset},
        **extra,
    )
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    return competition


def test_unreleased_sports_are_left_out_of_the_sport_picker(api, admin_api):
    keys = {row["key"] for row in api.get("/api/v1/competitions/presets").data}
    assert "soccer" in keys
    assert {"kpi", "cleaning", "custom"} <= keys
    assert "tennis" not in keys

    # The admin sees the same picker as everyone else.
    admin_keys = {row["key"] for row in admin_api.get("/api/v1/competitions/presets").data}
    assert admin_keys == keys


def test_nobody_can_start_an_unreleased_sport(api, admin_api):
    blocked = api.post(
        "/api/v1/competitions", {"name": "Tennis club", "preset": "tennis"}, format="json"
    )
    assert blocked.status_code == 400
    assert "not open yet" in str(blocked.data)

    also_blocked = admin_api.post(
        "/api/v1/competitions", {"name": "Tennis trial", "preset": "tennis"}, format="json"
    )
    assert also_blocked.status_code == 400

    opened = admin_api.post(
        "/api/v1/platform/admin/releases",
        {"kind": "sport", "keys": ["tennis"], "live": True},
        format="json",
    )
    assert opened.status_code == 200
    assert next(row for row in opened.data["sports"] if row["key"] == "tennis")["live"] is True
    created = api.post(
        "/api/v1/competitions", {"name": "Tennis club", "preset": "tennis"}, format="json"
    )
    assert created.status_code == 201


def test_hidden_sport_and_hidden_competition_leave_public_lists(
    user, other_user, anon_api, admin_api
):
    no_preset = Competition.objects.create(name="Office KPIs", owner=user, settings_json={})
    _league(user, "Sunday football", "soccer")
    _league(user, "Padel ladder", "padel")
    held = _league(user, "Quiet league", "soccer")
    held.platform_hidden = True
    held.save()

    assert _names(anon_api.get("/api/v1/competitions")) == {"Sunday football", no_preset.name}

    stranger = APIClient()
    stranger.force_authenticate(user=other_user)
    assert _names(stranger.get("/api/v1/competitions")) == {"Sunday football", no_preset.name}
    assert stranger.get(f"/api/v1/competitions/{held.id}").status_code == 404

    owner = APIClient()
    owner.force_authenticate(user=user)
    assert _names(owner.get("/api/v1/competitions?mine=1")) >= {
        "Sunday football",
        "Padel ladder",
        "Quiet league",
    }

    assert _names(admin_api.get("/api/v1/competitions")) == {"Sunday football", no_preset.name}

    search = anon_api.get("/api/v1/search?q=league&type=competitions")
    assert search.data["results"]["competitions"] == []


def test_admin_shows_a_hidden_competition_again(user, anon_api, admin_api):
    held = _league(user, "Quiet league", "soccer", platform_hidden=True)
    listed = admin_api.get("/api/v1/platform/admin/competitions?hidden=1").data
    assert [row["name"] for row in listed["results"]] == ["Quiet league"]

    shown = admin_api.patch(
        f"/api/v1/platform/admin/competitions/{held.id}",
        {"platform_hidden": False},
        format="json",
    )
    assert shown.status_code == 200
    assert shown.data["platform_hidden"] is False
    assert _names(anon_api.get("/api/v1/competitions")) == {"Quiet league"}


def test_only_the_platform_admin_reaches_the_admin_api(api, anon_api, settings, user):
    assert api.get("/api/v1/platform/admin/releases").status_code == 403
    assert anon_api.get("/api/v1/platform/admin/competitions").status_code in (401, 403)
    assert anon_api.get("/api/v1/platform/releases").data["platform_admin"] is False

    settings.PLATFORM_ADMIN_EMAILS = [user.email.upper()]
    assert api.get("/api/v1/platform/admin/releases").status_code == 200
    assert api.get("/api/v1/platform/releases").data["platform_admin"] is True


def test_closed_feature_answers_not_found_for_everyone(api, admin_api):
    assert api.get("/api/v1/games").status_code == 200

    admin_api.post(
        "/api/v1/platform/admin/releases",
        {"kind": "feature", "keys": ["games", "scouting"], "live": False},
        format="json",
    )
    assert Release.objects.filter(kind="feature", live=False).count() == 2
    assert api.get("/api/v1/platform/releases").data["features"]["games"] is False

    closed = api.get("/api/v1/games")
    assert closed.status_code == 404
    assert closed.json()["error"] == "not_released"
    assert admin_api.get("/api/v1/games").status_code == 404

    assert api.get("/api/v1/scouting/search").status_code == 404
    # A player's own profile and team invites stay open.
    assert api.get("/api/v1/scouting/me/teams").status_code == 200


def test_unknown_keys_are_rejected(admin_api):
    response = admin_api.post(
        "/api/v1/platform/admin/releases",
        {"kind": "sport", "keys": ["quidditch"], "live": True},
        format="json",
    )
    assert response.status_code == 400
