from django.urls import path

from .internal import (
    authorize_rooms,
    dispatch_notification,
    finalize_media,
    index_search_document,
    recompute_standings,
)

app_name = "internal"

urlpatterns = [
    path("rooms/authorize", authorize_rooms, name="authorize-rooms"),
    path("standings/recompute", recompute_standings, name="recompute-standings"),
    path("notifications/dispatch", dispatch_notification, name="dispatch-notification"),
    path("search/index", index_search_document, name="index-search-document"),
    path("media/finalize", finalize_media, name="finalize-media"),
]
