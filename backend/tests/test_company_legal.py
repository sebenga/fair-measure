from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.models import CompanyLegalDetails

pytestmark = pytest.mark.django_db

User = get_user_model()

PUBLIC = "/api/v1/legal/company"
ADMIN = "/api/v1/platform/admin/legal"


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


def _valid_payload(**overrides) -> dict:
    body = {
        "product": "Fair Measure",
        "legal_name": "Example (Pty) Ltd",
        "trading_name": "Fair Measure",
        "registration_number": "2020/123456/07",
        "vat_number": "4123456789",
        "directors": ["Ada Example", "Bob Example"],
        "physical_address": {
            "street": "1 Main Road",
            "suburb": "Gardens",
            "city": "Cape Town",
            "province": "Western Cape",
            "postal_code": "8001",
        },
        "postal_same_as_physical": True,
        "postal_address": {},
        "email": "legal@example.com",
        "phone": "+27821234567",
        "website": "https://fairmeasure-v2.onrender.com",
        "information_officer_name": "Ada Example",
        "information_officer_email": "privacy@example.com",
        "privacy_policy_effective_date": "2026-01-01",
        "copyright_holder": "Example (Pty) Ltd",
        "copyright_start_year": 2024,
        "trademarks": [{"mark": "Fair Measure", "status": "registered"}],
        "terms_effective_date": "2026-01-01",
        "governing_law": "Republic of South Africa",
    }
    body.update(overrides)
    return body


def test_anonymous_get_succeeds(anon_api):
    response = anon_api.get(PUBLIC)
    assert response.status_code == 200
    assert response.data["product"] == "Fair Measure"
    assert response.data["website"] == "https://fairmeasure-v2.onrender.com"
    assert "copyright_year_range" in response.data
    assert "formatted_physical_address" in response.data


def test_unauthenticated_patch_is_401(anon_api):
    response = anon_api.patch(ADMIN, _valid_payload(), format="json")
    assert response.status_code in (401, 403)


def test_non_admin_patch_is_403(api):
    response = api.patch(ADMIN, _valid_payload(), format="json")
    assert response.status_code == 403


def test_platform_admin_can_update(admin_api, anon_api):
    response = admin_api.patch(ADMIN, _valid_payload(), format="json")
    assert response.status_code == 200
    assert response.data["legal_name"] == "Example (Pty) Ltd"
    assert response.data["registration_number"] == "2020/123456/07"
    assert response.data["directors"] == ["Ada Example", "Bob Example"]
    assert response.data["copyright_year_range"].startswith("2024")
    assert "Fair Measure®" in response.data["trademark_labels"]

    public = anon_api.get(PUBLIC)
    assert public.status_code == 200
    assert public.data["legal_name"] == "Example (Pty) Ltd"
    assert public.data["vat_number"] == "4123456789"
    assert "Cape Town" in public.data["formatted_physical_address"]
    assert public.data["information_officer_email"] == "privacy@example.com"


def _detail(response) -> dict:
    return response.data.get("error", response.data).get("detail", response.data)


def test_serializer_rejects_invalid_cipc(admin_api):
    response = admin_api.patch(
        ADMIN, _valid_payload(registration_number="bad"), format="json"
    )
    assert response.status_code == 400
    assert "registration_number" in _detail(response)


def test_serializer_rejects_invalid_vat(admin_api):
    response = admin_api.patch(ADMIN, _valid_payload(vat_number="123"), format="json")
    assert response.status_code == 400
    assert "vat_number" in _detail(response)


def test_serializer_rejects_invalid_phone(admin_api):
    response = admin_api.patch(ADMIN, _valid_payload(phone="0821234567"), format="json")
    assert response.status_code == 400
    assert "phone" in _detail(response)


def test_serializer_rejects_missing_directors(admin_api):
    response = admin_api.patch(ADMIN, _valid_payload(directors=[]), format="json")
    assert response.status_code == 400
    assert "directors" in _detail(response)


def test_get_solo_does_not_create_a_second_row(anon_api):
    first = CompanyLegalDetails.get_solo()
    second = CompanyLegalDetails.get_solo()
    assert first.pk == second.pk
    assert CompanyLegalDetails.objects.count() == 1
    anon_api.get(PUBLIC)
    assert CompanyLegalDetails.objects.count() == 1


def test_public_payload_drives_footer_and_legal_fields(admin_api, anon_api):
    admin_api.put(ADMIN, _valid_payload(copyright_start_year=2025), format="json")
    data = anon_api.get(PUBLIC).data
    assert data["legal_name"]
    assert data["registration_number"]
    assert data["copyright_holder"]
    assert data["copyright_year_range"]
    assert data["email"]
    assert data["phone"]
    assert data["directors"]
    assert data["formatted_physical_address"]
