"""Serializers for the singleton CompanyLegalDetails record."""

from __future__ import annotations

import re
from datetime import date

from rest_framework import serializers

from .models import CompanyLegalDetails

SA_PROVINCES = frozenset(
    {
        "Eastern Cape",
        "Free State",
        "Gauteng",
        "KwaZulu-Natal",
        "Limpopo",
        "Mpumalanga",
        "North West",
        "Northern Cape",
        "Western Cape",
    }
)

CIPC_RE = re.compile(r"^\d{4}/\d{6}/\d{2}$")
VAT_RE = re.compile(r"^4\d{9}$")
PHONE_RE = re.compile(r"^\+27\d{9}$")


class AddressSerializer(serializers.Serializer):
    street = serializers.CharField(max_length=255, allow_blank=True, required=False, default="")
    suburb = serializers.CharField(max_length=120, allow_blank=True, required=False, default="")
    city = serializers.CharField(max_length=120, allow_blank=True, required=False, default="")
    province = serializers.CharField(max_length=64, allow_blank=True, required=False, default="")
    postal_code = serializers.CharField(max_length=12, allow_blank=True, required=False, default="")

    def validate_province(self, value: str) -> str:
        if value and value not in SA_PROVINCES:
            raise serializers.ValidationError(
                "Choose a South African province."
            )
        return value


class TrademarkSerializer(serializers.Serializer):
    mark = serializers.CharField(max_length=120)
    status = serializers.ChoiceField(choices=["registered", "pending"])


class CompanyLegalDetailsSerializer(serializers.ModelSerializer):
    physical_address = AddressSerializer(required=False)
    postal_address = AddressSerializer(required=False)
    directors = serializers.ListField(
        child=serializers.CharField(max_length=120),
        allow_empty=False,
        required=False,
    )
    trademarks = TrademarkSerializer(many=True, required=False)
    copyright_year_range = serializers.SerializerMethodField()
    formatted_physical_address = serializers.SerializerMethodField()
    formatted_postal_address = serializers.SerializerMethodField()
    trademark_labels = serializers.SerializerMethodField()

    class Meta:
        model = CompanyLegalDetails
        fields = [
            "id",
            "product",
            "legal_name",
            "trading_name",
            "registration_number",
            "vat_number",
            "directors",
            "physical_address",
            "postal_address",
            "postal_same_as_physical",
            "email",
            "phone",
            "website",
            "information_officer_name",
            "information_officer_email",
            "privacy_policy_effective_date",
            "copyright_holder",
            "copyright_start_year",
            "copyright_year_range",
            "trademarks",
            "trademark_labels",
            "terms_effective_date",
            "governing_law",
            "formatted_physical_address",
            "formatted_postal_address",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def get_copyright_year_range(self, obj: CompanyLegalDetails) -> str:
        start = int(obj.copyright_start_year or date.today().year)
        current = date.today().year
        if start >= current:
            return str(current)
        return f"{start}–{current}"

    def _format_address(self, raw: dict | None) -> str:
        if not isinstance(raw, dict):
            return ""
        parts = [
            str(raw.get("street") or "").strip(),
            str(raw.get("suburb") or "").strip(),
            str(raw.get("city") or "").strip(),
            str(raw.get("province") or "").strip(),
            str(raw.get("postal_code") or "").strip(),
        ]
        return ", ".join(part for part in parts if part)

    def get_formatted_physical_address(self, obj: CompanyLegalDetails) -> str:
        return self._format_address(obj.physical_address)

    def get_formatted_postal_address(self, obj: CompanyLegalDetails) -> str:
        if obj.postal_same_as_physical:
            return self._format_address(obj.physical_address)
        return self._format_address(obj.postal_address)

    def get_trademark_labels(self, obj: CompanyLegalDetails) -> list[str]:
        labels = []
        for row in obj.trademarks or []:
            if not isinstance(row, dict):
                continue
            mark = str(row.get("mark") or "").strip()
            if not mark:
                continue
            status = row.get("status")
            suffix = "®" if status == "registered" else "™"
            labels.append(f"{mark}{suffix}")
        return labels

    def validate_registration_number(self, value: str) -> str:
        value = (value or "").strip()
        if value and not CIPC_RE.match(value):
            raise serializers.ValidationError(
                "Use CIPC format YYYY/NNNNNN/NN."
            )
        return value

    def validate_vat_number(self, value: str) -> str:
        value = (value or "").strip()
        if value and not VAT_RE.match(value):
            raise serializers.ValidationError(
                "VAT numbers are 10 digits starting with 4."
            )
        return value

    def validate_phone(self, value: str) -> str:
        value = (value or "").strip().replace(" ", "")
        if value and not PHONE_RE.match(value):
            raise serializers.ValidationError(
                "Use South African format +27 followed by 9 digits."
            )
        return value

    def validate_directors(self, value: list) -> list:
        cleaned = [str(name).strip() for name in value if str(name).strip()]
        if not cleaned:
            raise serializers.ValidationError("Add at least one director.")
        return cleaned

    def validate(self, attrs: dict) -> dict:
        # On update, require a complete disclosure once the admin starts saving.
        instance = getattr(self, "instance", None)
        merged = {
            "legal_name": attrs.get(
                "legal_name", getattr(instance, "legal_name", "") if instance else ""
            ),
            "registration_number": attrs.get(
                "registration_number",
                getattr(instance, "registration_number", "") if instance else "",
            ),
            "directors": attrs.get(
                "directors", getattr(instance, "directors", None) if instance else None
            ),
            "email": attrs.get("email", getattr(instance, "email", "") if instance else ""),
            "phone": attrs.get("phone", getattr(instance, "phone", "") if instance else ""),
            "website": attrs.get(
                "website", getattr(instance, "website", "") if instance else ""
            ),
            "information_officer_name": attrs.get(
                "information_officer_name",
                getattr(instance, "information_officer_name", "") if instance else "",
            ),
            "information_officer_email": attrs.get(
                "information_officer_email",
                getattr(instance, "information_officer_email", "") if instance else "",
            ),
            "privacy_policy_effective_date": attrs.get(
                "privacy_policy_effective_date",
                getattr(instance, "privacy_policy_effective_date", None) if instance else None,
            ),
            "copyright_holder": attrs.get(
                "copyright_holder",
                getattr(instance, "copyright_holder", "") if instance else "",
            ),
            "copyright_start_year": attrs.get(
                "copyright_start_year",
                getattr(instance, "copyright_start_year", None) if instance else None,
            ),
            "terms_effective_date": attrs.get(
                "terms_effective_date",
                getattr(instance, "terms_effective_date", None) if instance else None,
            ),
            "governing_law": attrs.get(
                "governing_law",
                getattr(instance, "governing_law", "") if instance else "",
            ),
            "physical_address": attrs.get(
                "physical_address",
                getattr(instance, "physical_address", {}) if instance else {},
            ),
            "postal_same_as_physical": attrs.get(
                "postal_same_as_physical",
                getattr(instance, "postal_same_as_physical", True) if instance else True,
            ),
            "postal_address": attrs.get(
                "postal_address",
                getattr(instance, "postal_address", {}) if instance else {},
            ),
        }

        required = [
            "legal_name",
            "registration_number",
            "email",
            "phone",
            "website",
            "information_officer_name",
            "information_officer_email",
            "privacy_policy_effective_date",
            "copyright_holder",
            "copyright_start_year",
            "terms_effective_date",
            "governing_law",
        ]
        errors: dict[str, str] = {}
        for key in required:
            if not merged.get(key):
                errors[key] = "This field is required."

        directors = merged.get("directors")
        if not directors or not any(str(name).strip() for name in directors):
            errors["directors"] = "Add at least one director."

        address = merged.get("physical_address") or {}
        for key in ("street", "suburb", "city", "province", "postal_code"):
            if not str(address.get(key) or "").strip():
                errors["physical_address"] = "Complete the physical address."
                break
        if address.get("province") and address["province"] not in SA_PROVINCES:
            errors["physical_address"] = "Choose a South African province."

        if not merged.get("postal_same_as_physical"):
            postal = merged.get("postal_address") or {}
            for key in ("street", "suburb", "city", "province", "postal_code"):
                if not str(postal.get(key) or "").strip():
                    errors["postal_address"] = "Complete the postal address, or mark it the same as physical."
                    break

        if errors:
            raise serializers.ValidationError(errors)

        if not attrs.get("copyright_holder") and merged.get("legal_name"):
            attrs.setdefault("copyright_holder", merged["legal_name"])
        return attrs

    def update(self, instance: CompanyLegalDetails, validated_data: dict) -> CompanyLegalDetails:
        physical = validated_data.pop("physical_address", None)
        postal = validated_data.pop("postal_address", None)
        trademarks = validated_data.pop("trademarks", None)
        directors = validated_data.pop("directors", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if physical is not None:
            instance.physical_address = physical
        if postal is not None:
            instance.postal_address = postal
        if trademarks is not None:
            instance.trademarks = trademarks
        if directors is not None:
            instance.directors = directors
        if instance.postal_same_as_physical:
            instance.postal_address = dict(instance.physical_address or {})
        if not instance.copyright_holder:
            instance.copyright_holder = instance.legal_name
        instance.save()
        return instance
