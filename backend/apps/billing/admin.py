from django.contrib import admin

from .models import VisibilityPayment


@admin.register(VisibilityPayment)
class VisibilityPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "kind",
        "status",
        "amount_cents",
        "currency",
        "competition",
        "user",
        "paid_at",
        "created_at",
    )
    list_filter = ("kind", "status", "currency")
    search_fields = ("reference", "competition__name", "user__email")
    readonly_fields = ("id", "created_at", "updated_at", "raw_payload")
