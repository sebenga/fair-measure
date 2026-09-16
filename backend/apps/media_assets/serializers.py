from rest_framework import serializers

from .models import MediaAsset


class MediaAssetSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True)

    class Meta:
        model = MediaAsset
        fields = [
            "id",
            "kind",
            "status",
            "caption",
            "url",
            "playback_url",
            "thumbnail_url",
            "duration_seconds",
            "width",
            "height",
            "content_type",
            "size_bytes",
            "created_at",
            "ready_at",
        ]
        read_only_fields = [field for field in fields if field != "caption"]


class RequestUploadSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=MediaAsset.Kind.choices)
    filename = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    content_type = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default=""
    )
    size_bytes = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    competition_id = serializers.UUIDField(required=False, allow_null=True)
    caption = serializers.CharField(max_length=280, required=False, allow_blank=True, default="")
    max_duration_seconds = serializers.IntegerField(
        default=1800, min_value=1, max_value=21600, help_text="Videos only."
    )

    def validate(self, attrs: dict) -> dict:
        if attrs["kind"] == MediaAsset.Kind.IMAGE and not attrs.get("content_type"):
            raise serializers.ValidationError(
                {"content_type": "Required for image uploads."}
            )
        return attrs


class UploadTargetSerializer(serializers.Serializer):
    """What the client needs in order to upload without touching our servers."""

    media_asset = MediaAssetSerializer()
    upload_url = serializers.CharField()
    method = serializers.CharField()
    headers = serializers.DictField(child=serializers.CharField(), required=False)
    storage_key = serializers.CharField(required=False, allow_blank=True)
    expires_in = serializers.IntegerField(required=False)


class CompleteUploadSerializer(serializers.Serializer):
    width = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    height = serializers.IntegerField(required=False, allow_null=True, min_value=1)
