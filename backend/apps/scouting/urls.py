from django.urls import path

from . import discovery_views, ratings_views, stats_views, views

urlpatterns = [
    path("scouting/catalog", views.CatalogView.as_view(), name="scouting-catalog"),
    path(
        "scouting/catalog/<slug:sport>",
        views.CatalogSportView.as_view(),
        name="scouting-catalog-sport",
    ),
    path("scouting/me", views.ScoutingMeView.as_view(), name="scouting-me"),
    path("scouting/me/teams", views.MyTeamsView.as_view(), name="scouting-my-teams"),
    path("scouting/teams", views.PlatformTeamsView.as_view(), name="scouting-teams"),
    path(
        "scouting/me/team-memberships",
        views.MyTeamMembershipsView.as_view(),
        name="scouting-my-team-memberships",
    ),
    path("scouting/roles/coach", views.CoachRoleView.as_view(), name="scouting-coach-role"),
    path("scouting/roles/<uuid:pk>", views.MyRoleDetailView.as_view(), name="scouting-role"),
    # My player profile
    path("scouting/profile", views.MyProfileView.as_view(), name="scouting-my-profile"),
    path("scouting/profile/sports", views.MySportsView.as_view()),
    path("scouting/profile/sports/<uuid:pk>", views.MySportDetailView.as_view()),
    path("scouting/profile/measurements", views.MyMeasurementsView.as_view()),
    path("scouting/profile/measurements/<uuid:pk>", views.MyMeasurementDetailView.as_view()),
    path("scouting/profile/injuries", views.MyInjuriesView.as_view()),
    path("scouting/profile/injuries/<uuid:pk>", views.MyInjuryDetailView.as_view()),
    path("scouting/profile/videos", views.MyVideosView.as_view()),
    path("scouting/profile/videos/<uuid:pk>", views.MyVideoDetailView.as_view()),
    path("scouting/profile/guardians", views.MyGuardiansView.as_view()),
    path("scouting/profile/guardians/<uuid:pk>", views.MyGuardianDetailView.as_view()),
    path("scouting/profile/consents", views.MyConsentsView.as_view()),
    # Guardians
    path(
        "scouting/guardian/links", views.GuardianLinksView.as_view(), name="scouting-guardian-links"
    ),
    path("scouting/guardian/links/<uuid:pk>/accept", views.GuardianAcceptView.as_view()),
    path("scouting/guardian/links/<uuid:pk>/decline", views.GuardianDeclineView.as_view()),
    path(
        "scouting/guardian/profiles/<uuid:profile_id>/consent", views.GuardianConsentView.as_view()
    ),
    path(
        "scouting/guardian/profiles/<uuid:profile_id>/consents",
        views.GuardianConsentHistoryView.as_view(),
    ),
    # Viewing
    path("scouting/profiles", views.ProfileListView.as_view(), name="scouting-profiles"),
    path("scouting/profiles/<uuid:pk>", views.ProfileDetailView.as_view(), name="scouting-profile"),
    path("scouting/profiles/<uuid:pk>/measurements", views.CoachMeasurementView.as_view()),
    path(
        "scouting/profiles/<uuid:pk>/stats",
        stats_views.ProfileStatsView.as_view(),
        name="scouting-profile-stats",
    ),
    path(
        "scouting/profiles/<uuid:pk>/tests",
        stats_views.ProfileTestsView.as_view(),
        name="scouting-profile-tests",
    ),
    path("scouting/tests/players", stats_views.RecordablePlayersView.as_view()),
    path("scouting/ratings", ratings_views.RatingCreateView.as_view(), name="scouting-ratings"),
    path(
        "scouting/ratings/sync",
        ratings_views.RatingSyncView.as_view(),
        name="scouting-ratings-sync",
    ),
    path("scouting/profiles/lookup", ratings_views.ProfileLookupView.as_view()),
    path("scouting/search", discovery_views.SearchView.as_view(), name="scouting-search"),
    path("scouting/saved-searches", discovery_views.SavedSearchListView.as_view()),
    path("scouting/saved-searches/<uuid:pk>", discovery_views.SavedSearchDetailView.as_view()),
    path("scouting/compare", discovery_views.CompareView.as_view(), name="scouting-compare"),
    path(
        "scouting/shortlists",
        discovery_views.ShortlistListView.as_view(),
        name="scouting-shortlists",
    ),
    path("scouting/shortlists/<uuid:pk>", discovery_views.ShortlistDetailView.as_view()),
    path("scouting/shortlists/<uuid:pk>/entries", discovery_views.ShortlistEntriesView.as_view()),
    path(
        "scouting/shortlists/<uuid:pk>/entries/<uuid:entry_id>",
        discovery_views.ShortlistEntryDetailView.as_view(),
    ),
    path(
        "scouting/shortlists/<uuid:pk>/entries/<uuid:entry_id>/comments",
        discovery_views.ShortlistCommentsView.as_view(),
    ),
    path("scouting/shortlists/<uuid:pk>/log", discovery_views.ShortlistLogView.as_view()),
    path("scouting/profiles/<uuid:pk>/contact", discovery_views.ContactRequestCreateView.as_view()),
    path("scouting/contact-requests", discovery_views.ContactRequestListView.as_view()),
    path(
        "scouting/contact-requests/<uuid:pk>/respond",
        discovery_views.ContactRequestRespondView.as_view(),
    ),
    path(
        "scouting/contact-requests/<uuid:pk>/withdraw",
        discovery_views.ContactRequestWithdrawView.as_view(),
    ),
    path(
        "scouting/profiles/<uuid:pk>/ratings",
        ratings_views.ProfileRatingsView.as_view(),
        name="scouting-profile-ratings",
    ),
    path("scouting/profiles/<uuid:pk>/rating-context", ratings_views.RatingContextView.as_view()),
    path("scouting/profiles/<uuid:pk>/qr", ratings_views.ProfileQrView.as_view()),
    path("scouting/tests/<uuid:pk>", stats_views.TestResultDetailView.as_view()),
    path(
        "scouting/profiles/<uuid:pk>/report",
        views.ProfileReportView.as_view(),
        name="scouting-profile-report",
    ),
    # Talent reports (screen) and their PDF exports
    path(
        "scouting/reports/<slug:kind>",
        views.TalentReportView.as_view(),
        name="scouting-talent-report",
    ),
    path(
        "scouting/reports/<slug:kind>/pdf",
        views.TalentReportView.as_view(),
        {"as_pdf": True},
        name="scouting-talent-report-pdf",
    ),
    # League squads ("team of the league", picked like a national squad)
    path("scouting/leagues", views.LeagueListView.as_view(), name="scouting-leagues"),
    path("scouting/leagues/<uuid:pk>/squad", views.LeagueSquadView.as_view()),
    path("scouting/leagues/<uuid:pk>/squad/generate", views.LeagueSquadGenerateView.as_view()),
    path("scouting/leagues/<uuid:pk>/squad/publish", views.LeagueSquadPublishView.as_view()),
    path("scouting/leagues/<uuid:pk>/squad/picks", views.LeagueSquadPicksView.as_view()),
    path(
        "scouting/leagues/<uuid:pk>/squad/picks/<uuid:pick_id>",
        views.LeagueSquadPickDetailView.as_view(),
    ),
    path(
        "scouting/leagues/<uuid:pk>/squad/excluded/<uuid:user_id>",
        views.LeagueSquadRestoreView.as_view(),
    ),
    path("scouting/leagues/<uuid:pk>/candidates", views.LeagueCandidatesView.as_view()),
    path("scouting/leagues/<uuid:pk>/scouts", views.LeagueScoutsView.as_view()),
    path(
        "scouting/leagues/<uuid:pk>/scouts/<uuid:scout_id>",
        views.LeagueScoutDetailView.as_view(),
    ),
    # Organisations
    path("scouting/organisations", views.OrganisationListView.as_view()),
    path("scouting/organisations/<uuid:pk>/members", views.OrganisationMembersView.as_view()),
    path(
        "scouting/organisations/<uuid:pk>/members/<uuid:role_id>",
        views.OrganisationMemberDetailView.as_view(),
    ),
]
