from rest_framework import serializers

from .models import Enquiry, Placement


class PlacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Placement
        fields = [
            "id",
            "audience",
            "slot",
            "name",
            "tagline",
            "body",
            "cta_label",
            "cta_url",
            "logo_url",
            "display_order",
        ]


class EnquiryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enquiry
        fields = ["audience", "organisation", "contact_name", "email", "phone", "message"]

    def validate_phone(self, value: str) -> str:
        text = value.strip()
        if len(text) < 7:
            raise serializers.ValidationError("Enter a cellphone number.")
        return text

    def validate_message(self, value: str) -> str:
        text = value.strip()
        if len(text) < 12:
            raise serializers.ValidationError("Tell us a little more about the partnership.")
        return text
