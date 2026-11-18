from rest_framework import serializers

from .models import VisibilityPayment


class CheckoutCreateSerializer(serializers.Serializer):
    competition_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=VisibilityPayment.Kind.values)


class CheckoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisibilityPayment
        fields = [
            "id",
            "competition",
            "kind",
            "amount_cents",
            "currency",
            "reference",
            "status",
            "authorization_url",
            "paid_at",
            "created_at",
        ]
        read_only_fields = fields


class BillingConfigSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    public_key = serializers.CharField(allow_blank=True)
    currency = serializers.CharField()
    private_cents = serializers.IntegerField()
    landing_cents = serializers.IntegerField()
    gateway = serializers.CharField()
