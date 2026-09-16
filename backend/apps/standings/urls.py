from django.urls import path

from .views import StandingsView

urlpatterns = [
    path(
        "competitions/<uuid:competition_pk>/standings",
        StandingsView.as_view(),
        name="standings",
    ),
]
