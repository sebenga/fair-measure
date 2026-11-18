"""AI camera stub pipeline: process → suggestions → accept creates MatchEvent."""

from __future__ import annotations

import pytest
from django.test import override_settings

from apps.ai_camera.models import AiEventSuggestion, MatchRecording
from apps.competitions.models import Competition, Participant
from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide, ScoreEvent

pytestmark = pytest.mark.django_db


@override_settings(AI_CAMERA_ENABLED=True, AI_VISION_PROVIDER="stub")
def test_ai_pipeline_accept_creates_event_cards_not_auto(api, user):
    created = api.post(
        "/api/v1/competitions",
        {"name": "AI league", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    competition.settings_json = {**(competition.settings_json or {}), "ai_camera_enabled": True}
    competition.save(update_fields=["settings_json", "updated_at"])
    home = Participant.objects.create(competition=competition, name="Home", kind="team")
    away = Participant.objects.create(competition=competition, name="Away", kind="team")
    fixture = Fixture.objects.create(
        competition=competition, status=Fixture.Status.LIVE, duration_minutes=90
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0, is_home=True)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    FixtureReferee.objects.create(
        fixture=fixture,
        user=user,
        role=FixtureReferee.Role.REFEREE,
        status=FixtureReferee.Status.ACCEPTED,
    )
    cats = {
        item["code"]: item["id"]
        for item in api.get(f"/api/v1/competitions/{competition.id}").data["scoring_categories"]
    }

    recording = MatchRecording.objects.create(
        fixture=fixture,
        uploaded_by=user,
        status=MatchRecording.Status.READY,
        storage_key=f"fixtures/{fixture.id}/sample.mp4",
    )
    process = api.post(f"/api/v1/ai/recordings/{recording.id}/process", {}, format="json")
    assert process.status_code == 202, process.data
    assert process.data["suggestions"] == 2

    suggestions = list(AiEventSuggestion.objects.filter(fixture=fixture).order_by("timestamp_seconds"))
    assert len(suggestions) == 2
    tackle = next(s for s in suggestions if s.event_type == "tackle")
    yellow = next(s for s in suggestions if s.event_type == "yellow")
    assert yellow.is_disciplinary is True
    assert AiEventSuggestion.objects.filter(status=AiEventSuggestion.Status.ACCEPTED).count() == 0

    # Cards must not become ScoreEvents until accepted.
    assert ScoreEvent.objects.filter(fixture=fixture).count() == 0

    accept = api.post(
        f"/api/v1/ai/suggestions/{tackle.id}/accept",
        {"scoring_category": cats.get("tackle") or cats["goal"], "side": str(home_side.id)},
        format="json",
    )
    assert accept.status_code == 200, accept.data
    tackle.refresh_from_db()
    assert tackle.status == AiEventSuggestion.Status.ACCEPTED
    assert tackle.match_event_id is not None
    event = ScoreEvent.objects.get(pk=tackle.match_event_id)
    assert event.source == ScoreEvent.Source.AI_CAMERA

    # Yellow remains pending — never auto-applied.
    yellow.refresh_from_db()
    assert yellow.status == AiEventSuggestion.Status.PENDING
