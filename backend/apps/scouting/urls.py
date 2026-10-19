from django.urls import path

from . import views

urlpatterns = [
    path("scouting/catalog", views.CatalogView.as_view(), name="scouting-catalog"),
    path("scouting/me", views.ScoutingMeView.as_view(), name="scouting-me"),
    path("scouting/me/teams", views.MyTeamsView.as_view(), name="scouting-my-teams"),
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
    # Organisations
    path("scouting/organisations", views.OrganisationListView.as_view()),
    path("scouting/organisations/<uuid:pk>/members", views.OrganisationMembersView.as_view()),
    path(
        "scouting/organisations/<uuid:pk>/members/<uuid:role_id>",
        views.OrganisationMemberDetailView.as_view(),
    ),
]
