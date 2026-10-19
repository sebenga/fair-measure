from django.urls import path

from . import views

urlpatterns = [
    path("games", views.GamesListView.as_view(), name="games-list"),
    path("games/catalog", views.CatalogView.as_view(), name="games-catalog"),
    path("games/<uuid:pk>", views.GamesDetailView.as_view(), name="games-detail"),
    path("games/<uuid:pk>/sports", views.GamesSportsView.as_view(), name="games-sports"),
    path("games/<uuid:pk>/events", views.GamesEventsView.as_view(), name="games-events"),
    path(
        "games/<uuid:pk>/events/<uuid:event_id>",
        views.GamesEventDetailView.as_view(),
        name="games-event",
    ),
    path(
        "games/<uuid:pk>/events/<uuid:event_id>/entries",
        views.EventEntriesView.as_view(),
        name="games-event-entries",
    ),
    path(
        "games/<uuid:pk>/events/<uuid:event_id>/bronze-match",
        views.BronzeMatchView.as_view(),
        name="games-bronze-match",
    ),
    path("games/<uuid:pk>/nocs", views.NOCListView.as_view(), name="games-nocs"),
    path("games/<uuid:pk>/nocs/<uuid:noc_id>", views.NOCDetailView.as_view(), name="games-noc"),
    path("games/<uuid:pk>/athletes", views.AthleteListView.as_view(), name="games-athletes"),
    path("games/<uuid:pk>/medals", views.MedalsView.as_view(), name="games-medals"),
    path("games/<uuid:pk>/schedule", views.ScheduleView.as_view(), name="games-schedule"),
    path("games/<uuid:pk>/officials", views.GamesOfficialsView.as_view(), name="games-officials"),
    path("games/<uuid:pk>/overview", views.OverviewView.as_view(), name="games-overview"),
    path(
        "games/<uuid:pk>/athletes/<uuid:athlete_id>",
        views.AthleteDetailView.as_view(),
        name="games-athlete",
    ),
    path("games/<uuid:pk>/records", views.RecordsView.as_view(), name="games-records"),
    path(
        "games/<uuid:pk>/records/<uuid:record_id>",
        views.RecordDetailView.as_view(),
        name="games-record",
    ),
    path(
        "games/<uuid:pk>/events/<uuid:event_id>/records",
        views.EventRecordsView.as_view(),
        name="games-event-records",
    ),
    path("games/<uuid:pk>/follows", views.FollowsView.as_view(), name="games-follows"),
    path(
        "games/<uuid:pk>/follows/<uuid:follow_id>",
        views.FollowDetailView.as_view(),
        name="games-follow",
    ),
    path("games/<uuid:pk>/reports/<slug:kind>", views.ReportView.as_view(), name="games-report"),
]
