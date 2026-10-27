from pathlib import Path

import pytest
from django.test import override_settings

pytestmark = pytest.mark.django_db


@pytest.fixture
def spa_dir(tmp_path: Path, settings):
    (tmp_path / "index.html").write_text(
        "<html><script nonce=\"{{CSP_NONCE}}\">window.fm=1</script><body>app</body></html>",
        encoding="utf-8",
    )
    (tmp_path / "manifest.webmanifest").write_text("{}", encoding="utf-8")
    settings.SPA_DIR = tmp_path
    return tmp_path


def test_unknown_api_path_returns_json_not_html(anon_api, spa_dir):
    response = anon_api.get("/api/v1/this-route-does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
    assert "text/html" not in response["Content-Type"]


def test_unknown_socket_path_returns_json_not_html(anon_api, spa_dir):
    response = anon_api.get("/socket.io/missing")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_client_route_falls_back_to_the_spa(anon_api, spa_dir):
    response = anon_api.get("/tabs/competitions")
    assert response.status_code == 200
    assert "text/html" in response["Content-Type"]
    assert b"app" in response.content
    assert b"{{CSP_NONCE}}" not in response.content
    assert "Content-Security-Policy" in response


def test_missing_asset_is_not_the_spa(anon_api, spa_dir):
    response = anon_api.get("/ngsw.json")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_manifest_is_served_from_the_spa(anon_api, spa_dir):
    response = anon_api.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/manifest+json")
    assert b"".join(response.streaming_content) == b"{}"
