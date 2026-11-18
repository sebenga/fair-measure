"""Accept AI suggestions into MatchEvent (ScoreEvent) with human review."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.fixtures.models import ScoreEvent
from apps.fixtures.officials import user_can_live_score, log_match_action
from apps.core.permissions import Role, has_at_least

from .models import AiEventSuggestion
from .providers import get_vision_provider


DISCIPLINARY_TYPES = {
    "yellow",
    "yellow-card",
    "second-yellow",
    "red",
    "red-card",
    "card",
    "goal",
    "try",
    "penalty-goal",
    "penalty-try",
    "conversion",
    "drop-goal",
}


def ai_camera_enabled(competition) -> bool:
    if not getattr(settings, "AI_CAMERA_ENABLED", False):
        return False
    flag = (competition.settings_json or {}).get("ai_camera_enabled")
    if flag is None:
        return False
    return bool(flag)


def process_recording(recording) -> list[AiEventSuggestion]:
    if not ai_camera_enabled(recording.fixture.competition):
        raise ValidationError({"recording": "AI camera is off for this competition."})
    provider = get_vision_provider()
    recording.status = recording.Status.PROCESSING
    recording.save(update_fields=["status", "updated_at"])
    kit = (recording.fixture.competition.settings_json or {}).get("kit_colours") or {}
    try:
        suggestions = provider.process_clip(
            storage_key=recording.storage_key,
            fixture_id=str(recording.fixture_id),
            kit_colours=kit if isinstance(kit, dict) else {},
        )
    except Exception as exc:  # noqa: BLE001 — surface provider failures on the recording
        recording.status = recording.Status.FAILED
        recording.error = str(exc)[:2000]
        recording.save(update_fields=["status", "error", "updated_at"])
        raise
    rows = []
    for item in suggestions:
        disciplinary = item.is_disciplinary or item.event_type.lower() in DISCIPLINARY_TYPES
        rows.append(
            AiEventSuggestion.objects.create(
                fixture=recording.fixture,
                recording=recording,
                event_type=item.event_type[:64],
                timestamp_seconds=item.timestamp_seconds,
                clip_url=item.clip_url[:200] if item.clip_url else "",
                team_side_id=item.team_side_id,
                player_guess_id=item.player_guess_id,
                confidence=item.confidence,
                is_disciplinary=disciplinary,
                provider=provider.name,
                raw=item.raw or {},
            )
        )
    recording.status = recording.Status.DONE
    recording.error = ""
    recording.save(update_fields=["status", "error", "updated_at"])
    return rows


@transaction.atomic
def accept_suggestion(
    suggestion: AiEventSuggestion,
    *,
    user,
    category_id,
    side_id,
    player_id=None,
    edit_type: str | None = None,
) -> ScoreEvent:
    fixture = suggestion.fixture
    if not (
        user_can_live_score(fixture, user)
        or has_at_least(fixture.competition, user, Role.ADMIN)
    ):
        raise PermissionDenied("Only the referee or an appointed stats operator can accept AI events.")
    if suggestion.status == AiEventSuggestion.Status.ACCEPTED and suggestion.match_event_id:
        return suggestion.match_event
    if suggestion.is_disciplinary and not (
        user_can_live_score(fixture, user)
        or has_at_least(fixture.competition, user, Role.ADMIN)
    ):
        raise PermissionDenied("Disciplinary events need the referee or an admin.")
    event = ScoreEvent.objects.create(
        fixture=fixture,
        side_id=side_id,
        scoring_category_id=category_id,
        quantity=1,
        player_id=player_id,
        note=f"AI suggestion {suggestion.id}"[:280],
        source=ScoreEvent.Source.AI_CAMERA,
        confidence=suggestion.confidence,
        recorded_by=user,
        minute=int(suggestion.timestamp_seconds // 60) if suggestion.timestamp_seconds is not None else None,
        second=int(suggestion.timestamp_seconds % 60) if suggestion.timestamp_seconds is not None else None,
    )
    suggestion.status = (
        AiEventSuggestion.Status.EDITED if edit_type else AiEventSuggestion.Status.ACCEPTED
    )
    suggestion.reviewer = user
    suggestion.match_event = event
    if edit_type:
        suggestion.event_type = edit_type[:64]
    suggestion.save()
    fixture.recalculate_scores()
    log_match_action(
        fixture=fixture,
        user=user,
        action="ai.suggestion_accepted",
        detail=suggestion.event_type,
        source="ai_camera",
        payload={"suggestion_id": str(suggestion.id), "event_id": str(event.id)},
    )
    return event
