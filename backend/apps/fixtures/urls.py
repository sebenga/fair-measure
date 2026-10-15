from django.urls import path

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
