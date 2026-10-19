from django.urls import path

from . import views

urlpatterns = [
    path("horses", views.HorseListView.as_view(), name="horse-list"),
    path("horses/<uuid:pk>", views.HorseDetailView.as_view(), name="horse-detail"),
    path(
        "competitions/<uuid:pk>/combinations",
        views.CombinationCreateView.as_view(),
        name="competition-combinations",
    ),
]
