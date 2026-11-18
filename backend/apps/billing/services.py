"""Paystack helpers and the effect of a paid visibility upgrade."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import urllib.error
import urllib.request
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.competitions.models import Competition

from .models import VisibilityPayment

logger = logging.getLogger(__name__)

PAYSTACK_INIT_URL = "https://api.paystack.co/transaction/initialize"
PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{reference}"


def payments_enabled() -> bool:
    return bool(getattr(settings, "PAYSTACK_SECRET_KEY", "").strip())


def amount_for(kind: str) -> int:
    if kind == VisibilityPayment.Kind.PRIVATE:
        return int(settings.BILLING_PRIVATE_CENTS)
    if kind == VisibilityPayment.Kind.LANDING:
        return int(settings.BILLING_LANDING_CENTS)
    raise ValueError(f"Unknown billing kind: {kind}")


def has_paid(competition: Competition, kind: str) -> bool:
    return VisibilityPayment.objects.filter(
        competition=competition,
        kind=kind,
        status=VisibilityPayment.Status.PAID,
    ).exists()


def new_reference(kind: str) -> str:
    return f"fm_{kind}_{secrets.token_hex(12)}"


def _paystack_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _http_json(method: str, url: str, body: dict | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers=_paystack_headers(),
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.warning("Paystack HTTP %s: %s", exc.code, detail[:500])
        raise RuntimeError(f"Paystack request failed ({exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Could not reach Paystack.") from exc
    if not payload.get("status"):
        message = payload.get("message") or "Paystack rejected the request."
        raise RuntimeError(str(message))
    return payload.get("data") or {}


def initialize_transaction(
    *,
    email: str,
    amount_cents: int,
    reference: str,
    callback_url: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return _http_json(
        "POST",
        PAYSTACK_INIT_URL,
        {
            "email": email,
            "amount": amount_cents,
            "currency": "ZAR",
            "reference": reference,
            "callback_url": callback_url,
            "metadata": metadata,
        },
    )


def verify_transaction(reference: str) -> dict[str, Any]:
    return _http_json("GET", PAYSTACK_VERIFY_URL.format(reference=reference))


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    secret = (
        getattr(settings, "PAYSTACK_WEBHOOK_SECRET", "").strip()
        or getattr(settings, "PAYSTACK_SECRET_KEY", "").strip()
    )
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature)


@transaction.atomic
def apply_paid_payment(payment: VisibilityPayment, payload: dict[str, Any] | None = None) -> VisibilityPayment:
    """Mark the row paid and apply the competition flag. Idempotent."""

    payment = VisibilityPayment.objects.select_for_update().select_related("competition").get(
        pk=payment.pk
    )
    if payment.status == VisibilityPayment.Status.PAID:
        return payment

    competition = payment.competition
    if payment.kind == VisibilityPayment.Kind.PRIVATE:
        competition.is_private = True
        competition.show_on_landing = False
        competition.save(update_fields=["is_private", "show_on_landing", "updated_at"])
    elif payment.kind == VisibilityPayment.Kind.LANDING:
        if competition.is_private:
            raise RuntimeError("A private competition cannot appear on the landing page.")
        competition.show_on_landing = True
        competition.save(update_fields=["show_on_landing", "updated_at"])

    payment.status = VisibilityPayment.Status.PAID
    payment.paid_at = timezone.now()
    if payload:
        payment.raw_payload = payload
        transaction_id = payload.get("id") or payload.get("transaction_id")
        if transaction_id is not None:
            payment.paystack_transaction_id = str(transaction_id)
    payment.save(
        update_fields=[
            "status",
            "paid_at",
            "raw_payload",
            "paystack_transaction_id",
            "updated_at",
        ]
    )
    return payment


def fulfill_reference(reference: str, payload: dict[str, Any] | None = None) -> VisibilityPayment:
    payment = VisibilityPayment.objects.select_related("competition").get(reference=reference)
    expected = payment.amount_cents
    if payload:
        amount = int(payload.get("amount") or 0)
        currency = str(payload.get("currency") or "ZAR").upper()
        status = str(payload.get("status") or "").lower()
        if status and status != "success":
            raise RuntimeError("Paystack transaction was not successful.")
        if amount and amount != expected:
            raise RuntimeError("Paid amount does not match the checkout.")
        if currency and currency != payment.currency.upper():
            raise RuntimeError("Paid currency does not match the checkout.")
    return apply_paid_payment(payment, payload)
