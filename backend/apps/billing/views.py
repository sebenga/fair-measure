from __future__ import annotations

import json
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.models import Competition
from apps.competitions.views import visible_competitions
from apps.core.permissions import Role, has_at_least

from .models import VisibilityPayment
from .serializers import (
    BillingConfigSerializer,
    CheckoutCreateSerializer,
    CheckoutSerializer,
)
from .services import (
    amount_for,
    fulfill_reference,
    has_paid,
    initialize_transaction,
    new_reference,
    payments_enabled,
    verify_transaction,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)


class BillingConfigView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Billing"], responses={200: BillingConfigSerializer})
    def get(self, request: Request) -> Response:
        return Response(
            {
                "enabled": payments_enabled(),
                "public_key": settings.PAYSTACK_PUBLIC_KEY if payments_enabled() else "",
                "currency": "ZAR",
                "private_cents": settings.BILLING_PRIVATE_CENTS,
                "landing_cents": settings.BILLING_LANDING_CENTS,
                "gateway": "paystack",
            }
        )


class CheckoutCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Billing"],
        request=CheckoutCreateSerializer,
        responses={201: CheckoutSerializer},
    )
    def post(self, request: Request) -> Response:
        if not payments_enabled():
            raise ValidationError(
                {"detail": "Payments are not configured. Visibility changes stay free."}
            )

        serializer = CheckoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kind = serializer.validated_data["kind"]
        competition = get_object_or_404(
            visible_competitions(request.user),
            pk=serializer.validated_data["competition_id"],
        )
        if not has_at_least(competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only competition admins can pay for visibility upgrades.")

        if kind == VisibilityPayment.Kind.LANDING and competition.is_private:
            raise ValidationError(
                {
                    "kind": (
                        "Private competitions cannot appear on the landing page. "
                        "Make the competition public first."
                    )
                }
            )

        if has_paid(competition, kind):
            # Already unlocked: apply the flag again if somehow cleared, and return paid row.
            existing = (
                VisibilityPayment.objects.filter(
                    competition=competition,
                    kind=kind,
                    status=VisibilityPayment.Status.PAID,
                )
                .order_by("-paid_at")
                .first()
            )
            if existing:
                fulfill_reference(existing.reference)
                return Response(CheckoutSerializer(existing).data, status=status.HTTP_200_OK)

        amount_cents = amount_for(kind)
        reference = new_reference(kind)
        callback = (
            f"{settings.PUBLIC_APP_ORIGIN.rstrip('/')}/tabs/billing/return"
            f"?reference={reference}&competition={competition.id}"
        )
        email = (request.user.email or "").strip() or "organiser@fairmeasure.app"

        try:
            data = initialize_transaction(
                email=email,
                amount_cents=amount_cents,
                reference=reference,
                callback_url=callback,
                metadata={
                    "competition_id": str(competition.id),
                    "kind": kind,
                    "user_id": str(request.user.id),
                },
            )
        except RuntimeError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        payment = VisibilityPayment.objects.create(
            competition=competition,
            user=request.user,
            kind=kind,
            amount_cents=amount_cents,
            currency="ZAR",
            reference=reference,
            authorization_url=data.get("authorization_url") or "",
            paystack_access_code=data.get("access_code") or "",
            raw_payload={"initialize": data},
        )
        body = CheckoutSerializer(payment).data
        body["public_key"] = settings.PAYSTACK_PUBLIC_KEY
        body["email"] = email
        body["access_code"] = payment.paystack_access_code
        return Response(body, status=status.HTTP_201_CREATED)


class CheckoutDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Billing"], responses={200: CheckoutSerializer})
    def get(self, request: Request, reference: str) -> Response:
        payment = get_object_or_404(VisibilityPayment, reference=reference)
        if payment.user_id != request.user.id and not has_at_least(
            payment.competition, request.user, Role.ADMIN
        ):
            raise PermissionDenied("You cannot view this checkout.")

        # If the customer returned from Paystack before the webhook arrived, verify once.
        if payment.status == VisibilityPayment.Status.PENDING and payments_enabled():
            try:
                data = verify_transaction(reference)
                if str(data.get("status") or "").lower() == "success":
                    payment = fulfill_reference(reference, data)
            except Exception:
                logger.info("Paystack verify skipped or failed for %s", reference, exc_info=True)

        return Response(CheckoutSerializer(payment).data)


class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Billing"], request=None, responses={200: dict})
    def post(self, request: Request) -> Response:
        raw = request.body
        signature = request.headers.get("x-paystack-signature", "")
        if not verify_webhook_signature(raw, signature):
            return Response({"error": "invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            envelope = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return Response({"error": "invalid json"}, status=status.HTTP_400_BAD_REQUEST)

        event = envelope.get("event") or ""
        data = envelope.get("data") or {}
        if event != "charge.success":
            return Response({"received": True, "ignored": event})

        reference = data.get("reference") or ""
        if not reference:
            return Response({"error": "missing reference"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            fulfill_reference(reference, data)
        except VisibilityPayment.DoesNotExist:
            logger.warning("Paystack webhook for unknown reference %s", reference)
            return Response({"error": "unknown reference"}, status=status.HTTP_404_NOT_FOUND)
        except RuntimeError as exc:
            logger.warning("Paystack webhook rejected: %s", exc)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"received": True})
