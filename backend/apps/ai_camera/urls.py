from django.urls import path

from . import views

urlpatterns = [
    path(
        "fixtures/<uuid:fixture_pk>/ai/recordings",
        views.RecordingCreateView.as_view(),
        name="ai-recording-create",
    ),
    path(
        "fixtures/<uuid:fixture_pk>/ai/suggestions",
        views.SuggestionListView.as_view(),
        name="ai-suggestions",
    ),
    path(
        "ai/suggestions/<uuid:suggestion_pk>/accept",
        views.SuggestionAcceptView.as_view(),
        name="ai-suggestion-accept",
    ),
    path(
        "ai/suggestions/<uuid:suggestion_pk>/reject",
        views.SuggestionRejectView.as_view(),
        name="ai-suggestion-reject",
    ),
    path(
        "ai/recordings/<uuid:recording_pk>/process",
        views.ProcessRecordingView.as_view(),
        name="ai-recording-process",
    ),
]
