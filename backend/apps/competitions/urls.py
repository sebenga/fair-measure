from django.urls import path
from rest_framework_nested import routers

from .views import (
    CompetitionViewSet,
    MembershipViewSet,
    MyPendingTeamPickListView,
    MyTeamPickListView,
    ParticipantViewSet,
    PlayerLeagueProfileView,
    PointsPolicyView,
    RosterMemberViewSet,
    RuleViewSet,
    ScoringCategoryViewSet,
    StageViewSet,
    TeamPickAcceptView,
    TeamPickDeclineView,
    TeamPickListCreateView,
    TeamDraftView,
)

# Trailing slashes are off everywhere so router-generated and hand-written
# routes share one convention and clients never hit a 301.
router = routers.SimpleRouter(trailing_slash=False)
router.register("competitions", CompetitionViewSet, basename="competition")

competition_router = routers.NestedSimpleRouter(
    router, "competitions", lookup="competition", trailing_slash=False
)
competition_router.register(
    "scoring-categories", ScoringCategoryViewSet, basename="scoring-category"
)
competition_router.register("rules", RuleViewSet, basename="rule")
competition_router.register("stages", StageViewSet, basename="stage")
competition_router.register("participants", ParticipantViewSet, basename="participant")
competition_router.register("members", MembershipViewSet, basename="membership")

participant_router = routers.NestedSimpleRouter(
    competition_router, "participants", lookup="participant", trailing_slash=False
)
participant_router.register("roster", RosterMemberViewSet, basename="roster-member")

urlpatterns = [
    path(
        "me/team-picks",
        MyPendingTeamPickListView.as_view(),
        name="my-pending-team-picks",
    ),
    path(
        "competitions/<uuid:competition_pk>/points-policy",
        PointsPolicyView.as_view(),
        name="points-policy",
    ),
    path(
        "competitions/<uuid:competition_pk>/players/<uuid:user_pk>",
        PlayerLeagueProfileView.as_view(),
        name="player-league-profile",
    ),
    path(
        "competitions/<uuid:competition_pk>/draft",
        TeamDraftView.as_view(),
        name="team-draft",
    ),
    path(
        "competitions/<uuid:competition_pk>/picks",
        MyTeamPickListView.as_view(),
        name="my-team-picks",
    ),
    path(
        "competitions/<uuid:competition_pk>/picks/<uuid:pick_pk>/accept",
        TeamPickAcceptView.as_view(),
        name="team-pick-accept",
    ),
    path(
        "competitions/<uuid:competition_pk>/picks/<uuid:pick_pk>/decline",
        TeamPickDeclineView.as_view(),
        name="team-pick-decline",
    ),
    path(
        "competitions/<uuid:competition_pk>/participants/<uuid:participant_pk>/picks",
        TeamPickListCreateView.as_view(),
        name="team-picks",
    ),
    *router.urls,
    *competition_router.urls,
    *participant_router.urls,
]
