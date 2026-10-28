from __future__ import annotations

import pytest

from apps.competitions.models import Competition, Membership
from apps.core.permissions import Role
from apps.marketing.models import Enquiry, Placement

pytestmark = pytest.mark.django_db


def test_anonymous_visitors_can_read_commercial_placements(anon_api):
    response = anon_api.get("/api/v1/marketing/placements")
    assert response.status_code == 200
    assert any(row["audience"] == "corporate" for row in response.data)
    assert any(row["audience"] == "government" for row in response.data)


def test_anonymous_visitors_can_send_a_partnership_enquiry(anon_api):
    response = anon_api.post(
        "/api/v1/marketing/enquiries",
        {
            "audience": "government",
            "organisation": "City of Harbour",
            "contact_name": "Ada Mayor",
            "email": "sport@harbour.gov",
            "phone": "+27 82 555 0100",
            "message": "We want a municipal schools cup on the public landing page.",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert Enquiry.objects.filter(organisation="City of Harbour").exists()


def test_guests_can_open_a_featured_competition(anon_api, user):
    competition = Competition.objects.create(
        name="Harbour Open",
        owner=user,
        show_on_landing=True,
        status=Competition.Status.ACTIVE,
    )
    Membership.objects.create(competition=competition, user=user, role=Role.OWNER)

    listed = anon_api.get("/api/v1/competitions", {"show_on_landing": True})
    assert listed.status_code == 200
    assert any(row["id"] == str(competition.id) for row in listed.data["results"])

    detail = anon_api.get(f"/api/v1/competitions/{competition.id}")
    assert detail.status_code == 200
    assert detail.data["name"] == "Harbour Open"

    table = anon_api.get(f"/api/v1/competitions/{competition.id}/standings")
    assert table.status_code == 200
    feed = anon_api.get(f"/api/v1/competitions/{competition.id}/posts")
    assert feed.status_code == 200


def test_inactive_placements_stay_off_the_landing_page(anon_api):
    hidden = Placement.objects.create(
        audience="corporate",
        slot="banner",
        name="Hidden brand",
        active=False,
    )
    listed = anon_api.get("/api/v1/marketing/placements")
    assert all(row["id"] != str(hidden.id) for row in listed.data)
