from __future__ import annotations

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.views import visible_competitions
from apps.core.permissions import Role, has_at_least
from apps.fixtures.models import Fixture

from .models import AiEventSuggestion, MatchRecording
from .services import accept_suggestion, ai_camera_enabled, process_recording


class RecordingCreateView(APIView):
    """Register a chunked recording metadata row (bytes live in object storage)."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, fixture_pk) -> Response:
        fixture = get_object_or_404(
            Fixture.objects.select_related("competition"),
            pk=fixture_pk,
            competition__in=visible_competitions(request.user),
        )
        if not has_at_least(fixture.competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only an admin or stats operator can start a recording.")
        if not ai_camera_enabled(fixture.competition):
            raise ValidationError({"ai_camera": "Enable AI camera on this competition first."})
        recording = MatchRecording.objects.create(
            fixture=fixture,
            uploaded_by=request.user,
            status=MatchRecording.Status.READY,
            storage_key=str(request.data.get("storage_key") or f"fixtures/{fixture.id}/sample.mp4")[:400],
            duration_seconds=request.data.get("duration_seconds"),
            consent_version=str(request.data.get("consent_version") or "")[:40],
        )
        return Response(
            {"id": str(recording.id), "status": recording.status, "storage_key": recording.storage_key},
            status=status.HTTP_201_CREATED,
        )


class SuggestionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, fixture_pk) -> Response:
        fixture = get_object_or_404(
            Fixture, pk=fixture_pk, competition__in=visible_competitions(request.user)
        )
        rows = AiEventSuggestion.objects.filter(fixture=fixture).order_by("timestamp_seconds")
        return Response(
            [
                {
                    "id": str(row.id),
                    "event_type": row.event_type,
                    "timestamp_seconds": str(row.timestamp_seconds),
                    "clip_url": row.clip_url,
                    "confidence": str(row.confidence),
                    "status": row.status,
                    "is_disciplinary": row.is_disciplinary,
                    "player_guess_id": str(row.player_guess_id) if row.player_guess_id else None,
                    "team_side_id": str(row.team_side_id) if row.team_side_id else None,
                }
                for row in rows
            ]
        )


class SuggestionAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["AI Camera"], summary="Accept an AI suggestion as a MatchEvent")
    def post(self, request: Request, suggestion_pk) -> Response:
        suggestion = get_object_or_404(
            AiEventSuggestion.objects.select_related("fixture", "fixture__competition"),
            pk=suggestion_pk,
            fixture__competition__in=visible_competitions(request.user),
        )
        category_id = request.data.get("scoring_category")
        side_id = request.data.get("side") or suggestion.team_side_id
        if not category_id or not side_id:
            raise ValidationError({"scoring_category": "Choose the category and side."})
        event = accept_suggestion(
            suggestion,
            user=request.user,
            category_id=category_id,
            side_id=side_id,
            player_id=request.data.get("player") or suggestion.player_guess_id,
            edit_type=request.data.get("event_type"),
        )
        return Response({"event_id": str(event.id), "suggestion_id": str(suggestion.id)})


class SuggestionRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, suggestion_pk) -> Response:
        suggestion = get_object_or_404(AiEventSuggestion, pk=suggestion_pk)
        suggestion.status = AiEventSuggestion.Status.REJECTED
        suggestion.reviewer = request.user
        suggestion.save(update_fields=["status", "reviewer", "updated_at"])
        return Response({"id": str(suggestion.id), "status": suggestion.status})


class ProcessRecordingView(APIView):
    """Enqueue/process a recording (worker calls the same service)."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, recording_pk) -> Response:
        recording = get_object_or_404(
            MatchRecording.objects.select_related("fixture", "fixture__competition"),
            pk=recording_pk,
        )
        if not has_at_least(recording.fixture.competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only an admin or stats operator can start processing.")
        if not ai_camera_enabled(recording.fixture.competition):
            raise ValidationError({"ai_camera": "Enable AI camera on this competition first."})
        rows = process_recording(recording)
        return Response(
            {"recording_id": str(recording.id), "suggestions": len(rows)},
            status=status.HTTP_202_ACCEPTED,
        )
