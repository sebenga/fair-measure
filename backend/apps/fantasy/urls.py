from django.urls import path

from .views import (
    FantasyAutoPickView,
    FantasyPlayersView,
    FantasyStandingsView,
    FantasyTeamView,
    PlayerPerformanceView,
)

urlpatterns = [
    path(
        "competitions/<uuid:competition_pk>/fantasy/players/<uuid:player_pk>/performance",
        PlayerPerformanceView.as_view(),
        name="fantasy-player-performance",
    ),
    path(
        "competitions/<uuid:competition_pk>/fantasy",
        FantasyTeamView.as_view(),
        name="fantasy-team",
    ),
    path(
        "competitions/<uuid:competition_pk>/fantasy/players",
        FantasyPlayersView.as_view(),
        name="fantasy-players",
    ),
    path(
        "competitions/<uuid:competition_pk>/fantasy/standings",
        FantasyStandingsView.as_view(),
        name="fantasy-standings",
    ),
    path(
        "competitions/<uuid:competition_pk>/fantasy/auto-pick",
        FantasyAutoPickView.as_view(),
        name="fantasy-auto-pick",
    ),
]
