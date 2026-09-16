from rest_framework.routers import SimpleRouter

from .views import DeviceTokenViewSet, NotificationPreferenceViewSet, NotificationViewSet

router = SimpleRouter(trailing_slash=False)
router.register("devices", DeviceTokenViewSet, basename="device-token")
router.register("notifications", NotificationViewSet, basename="notification")
router.register(
    "notification-preferences",
    NotificationPreferenceViewSet,
    basename="notification-preference",
)

urlpatterns = router.urls
