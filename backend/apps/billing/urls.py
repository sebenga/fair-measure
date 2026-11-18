from django.urls import path

from .views import (
    BillingConfigView,
    CheckoutCreateView,
    CheckoutDetailView,
    PaystackWebhookView,
)

urlpatterns = [
    path("billing/config", BillingConfigView.as_view(), name="billing-config"),
    path("billing/checkouts", CheckoutCreateView.as_view(), name="billing-checkout-create"),
    path(
        "billing/checkouts/<str:reference>",
        CheckoutDetailView.as_view(),
        name="billing-checkout-detail",
    ),
    path(
        "billing/paystack/webhook",
        PaystackWebhookView.as_view(),
        name="billing-paystack-webhook",
    ),
]
