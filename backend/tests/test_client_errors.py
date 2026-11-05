"""Browser and phone errors land in the server log."""

from __future__ import annotations

import logging

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

URL = "/api/v1/client-errors"


def test_a_report_is_logged_with_its_details(caplog, api, user):
    caplog.set_level(logging.WARNING, logger="fm.client")
    sent = api.post(
        URL,
        {
            "kind": "request",
            "message": "HTTP 400",
            "method": "POST",
            "endpoint": "/api/v1/competitions",
            "status": 400,
            "detail": "The start date cannot be in the past.",
            "page": "/tabs/competitions/new",
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) CriOS/126.0",
            "stack": "x" * 5000,
        },
        format="json",
    )
    assert sent.status_code == 204
    record = next(row for row in caplog.records if row.name == "fm.client")
    assert record.client["endpoint"] == "/api/v1/competitions"
    assert record.client["detail"] == "The start date cannot be in the past."
    assert "iPhone" in record.client["user_agent"]
    assert record.client["user"] == str(user.pk)
    assert len(record.client["stack"]) == 2000


def test_anyone_can_report_and_rubbish_is_tolerated(caplog):
    caplog.set_level(logging.WARNING, logger="fm.client")
    client = APIClient()
    assert client.post(URL, {"kind": "crash", "message": "boom"}, format="json").status_code == 204
    assert client.post(URL, ["not", "a", "dict"], format="json").status_code == 204
    assert sum(1 for row in caplog.records if row.name == "fm.client") == 2
