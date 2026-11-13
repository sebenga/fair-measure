from django.urls import path

from . import views

urlpatterns = [
    path("platform/releases", views.ReleaseStateView.as_view(), name="platform-releases"),
    path(
        "platform/admin/releases",
        views.ReleaseAdminView.as_view(),
        name="platform-admin-releases",
    ),
    path(
        "platform/admin/competitions",
        views.CompetitionAdminListView.as_view(),
        name="platform-admin-competitions",
    ),
    path(
        "platform/admin/competitions/clear",
        views.ClearCompetitionsView.as_view(),
        name="platform-admin-competitions-clear",
    ),
    path(
        "platform/admin/competitions/<uuid:pk>",
        views.CompetitionAdminDetailView.as_view(),
        name="platform-admin-competition",
    ),
]
