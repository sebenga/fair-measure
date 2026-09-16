from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import MediaAssetViewSet, video_webhook

router = SimpleRouter(trailing_slash=False)
router.register("media", MediaAssetViewSet, basename="media-asset")

urlpatterns = [
    path("webhooks/video/<str:provider>", video_webhook, name="video-webhook"),
    *router.urls,
]
