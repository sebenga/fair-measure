from __future__ import annotations

import json
import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.competitions.views import visible_competitions
from apps.core.bus import Queues, enqueue_job, publish_event, user_room

from .models import MediaAsset
from .serializers import (
    CompleteUploadSerializer,
    MediaAssetSerializer,
    RequestUploadSerializer,
    UploadTargetSerializer,
)
from .storage import build_key, create_presigned_upload, head_object, validate_upload
from .video import get_video_provider

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(tags=["Media"], summary="List your media assets"),
    retrieve=extend_schema(tags=["Media"], summary="Get a media asset"),
    destroy=extend_schema(tags=["Media"], summary="Delete a media asset"),
)
class MediaAssetViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = MediaAsset.objects.none()
    serializer_class = MediaAssetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["kind", "status", "competition"]

    def get_queryset(self):
        return MediaAsset.objects.filter(owner=self.request.user)

    @extend_schema(
        tags=["Media"],
        summary="Request an upload target",
        description=(
            "Returns a signed URL the client uploads to directly. Images go to "
            "object storage (R2 or S3); videos go to the configured video provider "
            "(Cloudflare Stream or Mux). Bytes never pass through this API."
        ),
        request=RequestUploadSerializer,
        responses={201: UploadTargetSerializer},
    )
    @action(detail=False, methods=["post"], url_path="request-upload")
    def request_upload(self, request: Request) -> Response:
        serializer = RequestUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        competition = None
        if data.get("competition_id"):
            competition = get_object_or_404(
                visible_competitions(request.user), pk=data["competition_id"]
            )

        asset = MediaAsset.objects.create(
            owner=request.user,
            competition=competition,
            kind=data["kind"],
            caption=data.get("caption", ""),
            status=MediaAsset.Status.PENDING,
        )

        if data["kind"] == MediaAsset.Kind.IMAGE:
            content_type = validate_upload(
                "image", data.get("content_type", ""), data.get("size_bytes")
            )
            key = build_key(f"images/{request.user.id}", data.get("filename", ""))
            signed = create_presigned_upload(key, content_type)

            asset.storage_provider = request.headers.get("X-Storage-Provider") or ""
            asset.storage_key = key
            asset.content_type = content_type
            asset.size_bytes = data.get("size_bytes")
            asset.save(
                update_fields=[
                    "storage_provider",
                    "storage_key",
                    "content_type",
                    "size_bytes",
                ]
            )

            payload = {
                "media_asset": MediaAssetSerializer(asset).data,
                "upload_url": signed.upload_url,
                "method": signed.method,
                "headers": signed.headers,
                "storage_key": signed.key,
                "expires_in": signed.expires_in,
            }
        else:
            provider = get_video_provider()
            direct = provider.create_direct_upload(
                max_duration_seconds=data["max_duration_seconds"],
                metadata={
                    "media_asset_id": str(asset.id),
                    "user_id": str(request.user.id),
                },
            )

            asset.video_provider = direct.provider
            asset.provider_asset_id = direct.provider_asset_id
            asset.status = MediaAsset.Status.PROCESSING
            asset.save(
                update_fields=["video_provider", "provider_asset_id", "status"]
            )

            payload = {
                "media_asset": MediaAssetSerializer(asset).data,
                "upload_url": direct.upload_url,
                "method": "POST",
                "headers": {},
            }

        return Response(payload, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Media"],
        summary="Confirm an image upload finished",
        description=(
            "Call this after a successful PUT to object storage. The object is "
            "verified server-side, so a client cannot mark a missing file as ready."
        ),
        request=CompleteUploadSerializer,
        responses={200: MediaAssetSerializer},
    )
    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request: Request, pk: str | None = None) -> Response:
        asset = self.get_object()

        if asset.kind != MediaAsset.Kind.IMAGE:
            raise ValidationError(
                "Videos become ready through the provider webhook, not this endpoint."
            )

        serializer = CompleteUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stored = head_object(asset.storage_key)
        if stored is None:
            raise ValidationError("No uploaded file was found for this asset.")

        asset.size_bytes = stored["size_bytes"]
        asset.content_type = stored["content_type"] or asset.content_type
        asset.width = serializer.validated_data.get("width")
        asset.height = serializer.validated_data.get("height")
        asset.status = MediaAsset.Status.READY
        asset.ready_at = timezone.now()
        asset.save()

        enqueue_job(Queues.MEDIA, "generate-thumbnail", {"media_asset_id": str(asset.id)})
        return Response(MediaAssetSerializer(asset).data)

    def perform_destroy(self, instance: MediaAsset) -> None:
        if instance.owner_id != self.request.user.id:
            raise PermissionDenied("You can only delete your own media.")
        enqueue_job(
            Queues.MEDIA,
            "delete-remote-asset",
            {
                "storage_key": instance.storage_key,
                "video_provider": instance.video_provider,
                "provider_asset_id": instance.provider_asset_id,
            },
        )
        instance.delete()


@extend_schema(
    tags=["Media"],
    summary="Video provider webhook",
    description=(
        "Receives encoding status from Cloudflare Stream or Mux. The signature is "
        "verified against the provider's shared secret before anything is trusted."
    ),
    request=None,
    responses={200: dict},
    auth=[],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def video_webhook(request: Request, provider: str) -> Response:
    handler = get_video_provider(provider)

    if not handler.verify_webhook(request.body, request.headers):
        logger.warning("Rejected %s webhook: bad signature", provider)
        return Response({"detail": "Invalid signature."}, status=status.HTTP_403_FORBIDDEN)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({"detail": "Malformed payload."}, status=status.HTTP_400_BAD_REQUEST)

    parsed = handler.parse_webhook(payload)
    if parsed is None:
        return Response({"detail": "Ignored."})

    provider_asset_id, video_status = parsed
    asset = MediaAsset.objects.filter(provider_asset_id=provider_asset_id).first()
    if asset is None:
        logger.info("No media asset for %s id %s", provider, provider_asset_id)
        return Response({"detail": "Unknown asset."})

    if video_status.playback_id and not video_status.ready and not video_status.failed:
        # Mux upload -> asset handoff: remember the real asset id for later events.
        asset.provider_asset_id = video_status.playback_id
        asset.save(update_fields=["provider_asset_id"])
        return Response({"detail": "Linked."})

    if video_status.failed:
        asset.status = MediaAsset.Status.FAILED
        asset.error_message = video_status.error_message[:400]
    elif video_status.ready:
        asset.status = MediaAsset.Status.READY
        asset.playback_id = video_status.playback_id
        asset.playback_url = video_status.playback_url
        asset.thumbnail_url = video_status.thumbnail_url
        asset.duration_seconds = video_status.duration_seconds
        asset.ready_at = timezone.now()

    asset.save()

    publish_event(
        "media.updated",
        {"media_asset_id": str(asset.id), "status": asset.status},
        [user_room(asset.owner_id)],
        immediate=True,
    )
    return Response({"detail": "Applied."})
