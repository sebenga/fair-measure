from django.urls import path

from . import views

urlpatterns = [
    path("competitions/<uuid:pk>/officials", views.OfficialsView.as_view(), name="officials"),
    path(
        "competitions/<uuid:pk>/officials/<uuid:official_id>",
        views.OfficialDetailView.as_view(),
        name="official-detail",
    ),
    path("competitions/<uuid:pk>/events", views.EventCreateView.as_view(), name="event-create"),
    path(
        "competitions/<uuid:pk>/combination-stats",
        views.CombinationStatsView.as_view(),
        name="combination-stats",
    ),
    path("fixtures/<uuid:pk>/results", views.ResultSheetView.as_view(), name="result-sheet"),
    path(
        "fixtures/<uuid:pk>/results/status", views.ResultStatusView.as_view(), name="result-status"
    ),
    path(
        "fixtures/<uuid:pk>/results/finalise",
        views.ResultFinaliseView.as_view(),
        name="result-finalise",
    ),
]
