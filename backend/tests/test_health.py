import pytest

pytestmark = pytest.mark.django_db


def test_healthz_is_public_and_does_not_name_dependencies(anon_api):
    response = anon_api.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded", "error"}
    assert "checks" not in body
    assert "debug" not in body


def test_healthz_details_need_the_shared_key(anon_api, settings):
    settings.HEALTH_KEY = "probe-secret"
    hidden = anon_api.get("/healthz")
    assert "checks" not in hidden.json()

    shown = anon_api.get("/healthz", HTTP_X_HEALTH_KEY="probe-secret")
    assert shown.status_code == 200
    assert "database" in shown.json()["checks"]


def test_version_is_public(anon_api):
    response = anon_api.get("/api/v1/version")
    assert response.status_code == 200
    assert "commit" in response.json()
    assert "built_at" in response.json()
