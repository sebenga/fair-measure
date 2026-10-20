from django.urls import path

from .awards import FixtureAwardsView, PlayerStatsView
from .matchday import (
    MatchReportView,
    SubstitutionsView,
    SubstitutionView,
    TeamSheetsView,
    TeamSheetView,
)
from .views import FixtureRefereeView, FixtureViewSet, ScoreAssistView, ScoreEventViewSet

fixture_list = FixtureViewSet.as_view({"get": "list", "post": "create"})
fixture_detail = FixtureViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)
fixture_generate = FixtureViewSet.as_view({"post": "generate"})
fixture_set_status = FixtureViewSet.as_view({"post": "set_status"})

event_list = ScoreEventViewSet.as_view({"get": "list", "post": "create"})
event_detail = ScoreEventViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
)
event_bulk = ScoreEventViewSet.as_view({"post": "bulk"})

urlpatterns = [
    path(
        "competitions/<uuid:competition_pk>/fixtures",
        fixture_list,
        name="fixture-list",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/generate",
        fixture_generate,
        name="fixture-generate",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/<uuid:pk>",
        fixture_detail,
        name="fixture-detail",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/<uuid:pk>/set-status",
        fixture_set_status,
        name="fixture-set-status",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/<uuid:fixture_pk>/referees",
        FixtureRefereeView.as_view(),
        name="fixture-referees",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/<uuid:fixture_pk>/awards",
        FixtureAwardsView.as_view(),
        name="fixture-awards",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/<uuid:fixture_pk>/team-sheets",
        TeamSheetsView.as_view(),
        name="fixture-team-sheets",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/<uuid:fixture_pk>/team-sheets/<uuid:side_pk>",
        TeamSheetView.as_view(),
        name="fixture-team-sheet",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/<uuid:fixture_pk>/substitutions",
        SubstitutionsView.as_view(),
        name="fixture-substitutions",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/<uuid:fixture_pk>/substitutions/<uuid:sub_pk>",
        SubstitutionView.as_view(),
        name="fixture-substitution",
    ),
    path(
        "competitions/<uuid:competition_pk>/fixtures/<uuid:fixture_pk>/report",
        MatchReportView.as_view(),
        name="fixture-report",
    ),
    path(
        "competitions/<uuid:competition_pk>/player-stats",
        PlayerStatsView.as_view(),
        name="competition-player-stats",
    ),
    path(
        "competitions/<uuid:competition_pk>/score-assist",
        ScoreAssistView.as_view(),
        name="score-assist",
    ),
    path("fixtures/<uuid:fixture_pk>/events", event_list, name="score-event-list"),
    path("fixtures/<uuid:fixture_pk>/events/bulk", event_bulk, name="score-event-bulk"),
    path(
        "fixtures/<uuid:fixture_pk>/events/<uuid:pk>",
        event_detail,
        name="score-event-detail",
    ),
]
