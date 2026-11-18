"""Paystack visibility unlocks for private competitions and landing placement."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.test import override_settings

from apps.billing.models import VisibilityPayment
from apps.billing.services import apply_paid_payment
from apps.competitions.models import Competition

pytestmark = pytest.mark.django_db

PAYSTACK = {
    "PAYSTACK_SECRET_KEY": "sk_test_dummy",
    "PAYSTACK_PUBLIC_KEY": "pk_test_dummy",
    "PAYSTACK_WEBHOOK_SECRET": "sk_test_dummy",
    "BILLING_PRIVATE_CENTS": 9900,
    "BILLING_LANDING_CENTS": 14900,
}


def _sign(body: bytes, secret: str = "sk_test_dummy") -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()


@override_settings(**PAYSTACK)
def test_billing_config_reports_enabled(api):
    response = api.get("/api/v1/billing/config")
    assert response.status_code == 200
    assert response.data["enabled"] is True
    assert response.data["public_key"] == "pk_test_dummy"
    assert response.data["private_cents"] == 9900
    assert response.data["landing_cents"] == 14900


def test_billing_config_disabled_without_keys(api):
    response = api.get("/api/v1/billing/config")
    assert response.status_code == 200
    assert response.data["enabled"] is False


@override_settings(**PAYSTACK)
def test_unpaid_private_toggle_rejected(api, competition):
    response = api.patch(
        f"/api/v1/competitions/{competition.id}",
        {"is_private": True},
        format="json",
    )
    assert response.status_code == 400
    competition.refresh_from_db()
    assert competition.is_private is False


@override_settings(**PAYSTACK)
def test_unpaid_landing_toggle_rejected(api, competition):
    response = api.patch(
        f"/api/v1/competitions/{competition.id}",
        {"show_on_landing": True},
        format="json",
    )
    assert response.status_code == 400
    competition.refresh_from_db()
    assert competition.show_on_landing is False


@override_settings(**PAYSTACK)
def test_create_strips_paid_visibility_flags(api, user):
    response = api.post(
        "/api/v1/competitions",
        {
            "name": "Paid Visibility Intent",
            "is_private": True,
            "show_on_landing": True,
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    competition = Competition.objects.get(pk=response.data["id"])
    assert competition.is_private is False
    assert competition.show_on_landing is False


@override_settings(**PAYSTACK)
def test_checkout_initialize_and_webhook_makes_private(api, competition):
    with patch(
        "apps.billing.views.initialize_transaction",
        return_value={
            "authorization_url": "https://checkout.paystack.com/test",
            "access_code": "access_test",
            "reference": "ignored",
        },
    ):
        created = api.post(
            "/api/v1/billing/checkouts",
            {"competition_id": str(competition.id), "kind": "private"},
            format="json",
        )
    assert created.status_code == 201, created.data
    reference = created.data["reference"]
    assert created.data["amount_cents"] == 9900
    assert created.data["authorization_url"]
    payment = VisibilityPayment.objects.get(reference=reference)
    assert payment.status == VisibilityPayment.Status.PENDING

    body = json.dumps(
        {
            "event": "charge.success",
            "data": {
                "reference": reference,
                "amount": 9900,
                "currency": "ZAR",
                "status": "success",
                "id": 12345,
            },
        }
    ).encode("utf-8")
    webhook = api.post(
        "/api/v1/billing/paystack/webhook",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=_sign(body),
    )
    assert webhook.status_code == 200, webhook.data
    payment.refresh_from_db()
    competition.refresh_from_db()
    assert payment.status == VisibilityPayment.Status.PAID
    assert competition.is_private is True
    assert competition.show_on_landing is False


@override_settings(**PAYSTACK)
def test_webhook_landing_requires_public_competition(api, competition):
    payment = VisibilityPayment.objects.create(
        competition=competition,
        user=competition.owner,
        kind=VisibilityPayment.Kind.LANDING,
        amount_cents=14900,
        reference="fm_landing_testref",
        status=VisibilityPayment.Status.PENDING,
    )
    body = json.dumps(
        {
            "event": "charge.success",
            "data": {
                "reference": payment.reference,
                "amount": 14900,
                "currency": "ZAR",
                "status": "success",
                "id": 99,
            },
        }
    ).encode("utf-8")
    webhook = api.post(
        "/api/v1/billing/paystack/webhook",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE=_sign(body),
    )
    assert webhook.status_code == 200
    competition.refresh_from_db()
    assert competition.show_on_landing is True


@override_settings(**PAYSTACK)
def test_paid_row_allows_patch_private(api, competition):
    payment = VisibilityPayment.objects.create(
        competition=competition,
        user=competition.owner,
        kind=VisibilityPayment.Kind.PRIVATE,
        amount_cents=9900,
        reference="fm_private_already",
        status=VisibilityPayment.Status.PAID,
    )
    apply_paid_payment(payment)
    competition.refresh_from_db()
    competition.is_private = False
    competition.save(update_fields=["is_private"])

    response = api.patch(
        f"/api/v1/competitions/{competition.id}",
        {"is_private": True},
        format="json",
    )
    assert response.status_code == 200, response.data
    competition.refresh_from_db()
    assert competition.is_private is True


@override_settings(**PAYSTACK)
def test_turning_off_visibility_stays_free(api, competition):
    competition.is_private = True
    competition.show_on_landing = False
    competition.save(update_fields=["is_private", "show_on_landing"])
    response = api.patch(
        f"/api/v1/competitions/{competition.id}",
        {"is_private": False},
        format="json",
    )
    assert response.status_code == 200, response.data
    competition.refresh_from_db()
    assert competition.is_private is False


@override_settings(**PAYSTACK)
def test_webhook_rejects_bad_signature(api, competition):
    payment = VisibilityPayment.objects.create(
        competition=competition,
        user=competition.owner,
        kind=VisibilityPayment.Kind.PRIVATE,
        amount_cents=9900,
        reference="fm_private_bad_sig",
        status=VisibilityPayment.Status.PENDING,
    )
    body = json.dumps(
        {
            "event": "charge.success",
            "data": {
                "reference": payment.reference,
                "amount": 9900,
                "currency": "ZAR",
                "status": "success",
            },
        }
    ).encode("utf-8")
    webhook = api.post(
        "/api/v1/billing/paystack/webhook",
        data=body,
        content_type="application/json",
        HTTP_X_PAYSTACK_SIGNATURE="not-valid",
    )
    assert webhook.status_code == 400
    payment.refresh_from_db()
    assert payment.status == VisibilityPayment.Status.PENDING


def test_free_path_without_paystack_keys(api, competition):
    response = api.patch(
        f"/api/v1/competitions/{competition.id}",
        {"is_private": True, "show_on_landing": False},
        format="json",
    )
    assert response.status_code == 200, response.data
    competition.refresh_from_db()
    assert competition.is_private is True
