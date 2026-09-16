from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import DeviceToken, Notification, NotificationPreference
from .serializers import (
    DeviceTokenSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=["Notifications"], summary="List your registered devices"),
    create=extend_schema(
        tags=["Notifications"],
        summary="Register an FCM device token",
        description="Re-registering an existing token moves it to the current user.",
    ),
    destroy=extend_schema(tags=["Notifications"], summary="Unregister a device"),
)
class DeviceTokenViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DeviceToken.objects.none()
    serializer_class = DeviceTokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DeviceToken.objects.filter(user=self.request.user)

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # A device that changes hands must stop receiving the old user's pushes.
        token, _ = DeviceToken.objects.update_or_create(
            token=serializer.validated_data["token"],
            defaults={
                "user": request.user,
                "platform": serializer.validated_data["platform"],
                "device_name": serializer.validated_data.get("device_name", ""),
                "is_active": True,
            },
        )
        return Response(
            DeviceTokenSerializer(token).data, status=status.HTTP_201_CREATED
        )


@extend_schema_view(
    list=extend_schema(tags=["Notifications"], summary="List your notifications"),
    retrieve=extend_schema(tags=["Notifications"], summary="Get a notification"),
)
class NotificationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["competition", "kind"]

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user)
        if self.request.query_params.get("unread") in {"1", "true", "yes"}:
            queryset = queryset.filter(read_at__isnull=True)
        return queryset

    @extend_schema(
        tags=["Notifications"],
        summary="Mark notifications as read",
        description="Marks every unread notification as read and returns the count.",
        request=None,
        responses={200: dict},
    )
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request: Request) -> Response:
        updated = Notification.objects.filter(
            user=request.user, read_at__isnull=True
        ).update(read_at=timezone.now())
        return Response({"marked_read": updated})

    @extend_schema(tags=["Notifications"], summary="Mark one notification as read", request=None)
    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request: Request, pk: str | None = None) -> Response:
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)


@extend_schema_view(
    list=extend_schema(tags=["Notifications"], summary="List your notification preferences"),
    create=extend_schema(tags=["Notifications"], summary="Set preferences for a competition"),
    partial_update=extend_schema(tags=["Notifications"], summary="Update preferences"),
)
class NotificationPreferenceViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = NotificationPreference.objects.none()
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preference, created = NotificationPreference.objects.update_or_create(
            user=request.user,
            competition=serializer.validated_data.get("competition"),
            defaults={
                key: value
                for key, value in serializer.validated_data.items()
                if key != "competition"
            },
        )
        return Response(
            NotificationPreferenceSerializer(preference).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
