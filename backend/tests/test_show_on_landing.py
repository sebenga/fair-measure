"""Opt-in for featuring a public competition on the marketing landing page."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Membership
from apps.core.permissions import Role

pytestmark = pytest.mark.django_db


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_a_competition_can_be_created_for_the_landing_page(api, user):
    response = api.post(
        "/api/v1/competitions",
        {"name": "Harbour Cup", "show_on_landing": True},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["is_private"] is False
    assert response.data["show_on_landing"] is True

    listed = api.get("/api/v1/competitions", {"show_on_landing": True})
    assert listed.status_code == 200
    assert any(row["id"] == response.data["id"] for row in listed.data["results"])


def test_new_competitions_stay_off_the_landing_page_until_chosen(api):
    response = api.post("/api/v1/competitions", {"name": "Office ladder"}, format="json")
    assert response.status_code == 201, response.data
    assert response.data["show_on_landing"] is False

    listed = api.get("/api/v1/competitions", {"show_on_landing": True})
    assert all(row["id"] != response.data["id"] for row in listed.data["results"])


def test_private_competitions_cannot_appear_on_the_landing_page(api):
    response = api.post(
        "/api/v1/competitions",
        {"name": "Invite only", "is_private": True, "show_on_landing": True},
        format="json",
    )
    assert response.status_code == 400
    assert "show_on_landing" in response.data["error"]["detail"]


def test_making_a_featured_competition_private_takes_it_off_the_landing_page(api, user):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Open league", "show_on_landing": True},
        format="json",
    )
    assert created.status_code == 201, created.data

    updated = api.patch(
        f"/api/v1/competitions/{created.data['id']}",
        {"is_private": True},
        format="json",
    )
    assert updated.status_code == 200, updated.data
    assert updated.data["is_private"] is True
    assert updated.data["show_on_landing"] is False

    listed = api.get("/api/v1/competitions", {"show_on_landing": True})
    assert all(row["id"] != created.data["id"] for row in listed.data["results"])


def test_anonymous_visitors_can_list_landing_page_competitions(anon_api, user):
    featured = Competition.objects.create(
        name="City Open",
        owner=user,
        show_on_landing=True,
    )
    Membership.objects.create(competition=featured, user=user, role=Role.OWNER)
    hidden = Competition.objects.create(name="Club nights", owner=user)
    Membership.objects.create(competition=hidden, user=user, role=Role.OWNER)

    response = anon_api.get("/api/v1/competitions", {"show_on_landing": True})
    assert response.status_code == 200
    ids = {row["id"] for row in response.data["results"]}
    assert str(featured.id) in ids
    assert str(hidden.id) not in ids
