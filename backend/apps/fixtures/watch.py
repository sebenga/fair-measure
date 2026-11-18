"""Watch PWA pairing and offline event sync."""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.views import visible_competitions
from apps.core.permissions import Role, has_at_least

from .models import Fixture, FixtureReferee, ScoreEvent, WatchDeviceToken
from .officials import assert_can_live_score, log_match_action, user_can_live_score


def _active_token(raw: str | None) -> WatchDeviceToken:
    token = (raw or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        raise PermissionDenied("Pair this watch with a match code first.")
    row = (
        WatchDeviceToken.objects.select_related("fixture", "official", "official__user")
        .filter(token=token)
        .first()
    )
    if row is None or not row.is_active:
        raise PermissionDenied("That watch link has expired. Pair again from the phone.")
    return row


class WatchPairView(APIView):
    """Phone: issue a 6-digit / QR code for the watch."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Watch"], summary="Create a short-lived watch pairing code")
    def post(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = get_object_or_404(
            Fixture.objects.select_related("competition"),
            pk=fixture_pk,
            competition_id=competition_pk,
            competition__in=visible_competitions(request.user),
        )
        if not user_can_live_score(fixture, request.user) and not has_at_least(
            fixture.competition, request.user, Role.ADMIN
        ):
            raise PermissionDenied("Only the match referee can pair a watch.")
        official = fixture.referees.filter(
            user=request.user, status=FixtureReferee.Status.ACCEPTED
        ).first()
        # Tokens die at the later of +6h or scheduled end; always revocable.
        expires = timezone.now() + timedelta(hours=6)
        if fixture.scheduled_at:
            expires = max(expires, fixture.scheduled_at + timedelta(hours=4))
        code = f"{secrets.randbelow(1_000_000):06d}"
        token = secrets.token_urlsafe(32)
        row = WatchDeviceToken.objects.create(
            fixture=fixture,
            official=official,
            code=code,
            token=token,
            created_by=request.user,
            expires_at=expires,
            device_label=str(request.data.get("device_label") or "watch")[:80],
        )
        log_match_action(
            fixture=fixture,
            user=request.user,
            action="watch.paired",
            detail=code,
            source="watch",
            payload={"token_id": str(row.id)},
        )
        return Response(
            {
                "code": code,
                "token": token,
                "expires_at": row.expires_at,
                "fixture_id": str(fixture.id),
                "competition_id": str(fixture.competition_id),
                "watch_path": f"/ref/watch/{fixture.id}?code={code}",
            },
            status=status.HTTP_201_CREATED,
        )


class WatchClaimView(APIView):
    """Watch: exchange the 6-digit code for a device token."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["Watch"], summary="Claim a watch token with the 6-digit code")
    def post(self, request: Request, fixture_pk) -> Response:
        code = str(request.data.get("code") or "").strip()
        if len(code) != 6 or not code.isdigit():
            raise ValidationError({"code": "Enter the 6-digit code from the phone."})
        row = (
            WatchDeviceToken.objects.select_related("fixture")
            .filter(fixture_id=fixture_pk, code=code)
            .order_by("-created_at")
            .first()
        )
        if row is None or not row.is_active:
            raise ValidationError({"code": "That code is wrong or has expired."})
        row.last_seen_at = timezone.now()
        row.save(update_fields=["last_seen_at", "updated_at"])
        return Response(
            {
                "token": row.token,
                "fixture_id": str(row.fixture_id),
                "expires_at": row.expires_at,
            }
        )


class WatchSyncView(APIView):
    """Watch: push queued offline events (deduped by client_uuid)."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["Watch"], summary="Sync offline watch events")
    def post(self, request: Request, fixture_pk) -> Response:
        row = _active_token(request.headers.get("Authorization") or request.data.get("token"))
        if str(row.fixture_id) != str(fixture_pk):
            raise PermissionDenied("This watch is paired to a different match.")
        fixture = row.fixture
        if fixture.status not in {
            Fixture.Status.LIVE,
            Fixture.Status.SCHEDULED,
            Fixture.Status.POSTPONED,
        }:
            raise ValidationError({"status": "This match is no longer live."})
        actor = row.official.user if row.official_id else row.created_by
        if actor is None:
            raise PermissionDenied("This watch pairing has no referee.")
        # Treat the paired official as the live scorer.
        if row.official_id:
            assert_can_live_score(fixture, actor)
        events = request.data.get("events") or []
        if not isinstance(events, list):
            raise ValidationError({"events": "Send a list of events."})
        created = []
        skipped = []
        for raw in events[:200]:
            client_uuid = raw.get("client_uuid") or raw.get("id")
            try:
                client_uuid = uuid.UUID(str(client_uuid))
            except (TypeError, ValueError):
                raise ValidationError({"events": "Each event needs a client_uuid."}) from None
            if ScoreEvent.objects.filter(client_uuid=client_uuid).exists():
                skipped.append(str(client_uuid))
                continue
            side_id = raw.get("side")
            category_id = raw.get("scoring_category")
            if not side_id or not category_id:
                raise ValidationError({"events": "Each event needs side and scoring_category."})
            event = ScoreEvent.objects.create(
                fixture=fixture,
                side_id=side_id,
                scoring_category_id=category_id,
                quantity=raw.get("quantity") or 1,
                minute=raw.get("minute"),
                second=raw.get("second"),
                period=str(raw.get("period") or "")[:40],
                player_id=raw.get("player") or None,
                note=str(raw.get("note") or "")[:280],
                source=ScoreEvent.Source.WATCH,
                client_uuid=client_uuid,
                recorded_by=actor,
            )
            created.append(str(event.id))
        if created:
            fixture.recalculate_scores()
            log_match_action(
                fixture=fixture,
                user=actor,
                action="watch.sync",
                detail=f"{len(created)} events",
                source="watch",
                device=row.device_label,
            )
        row.last_seen_at = timezone.now()
        row.save(update_fields=["last_seen_at", "updated_at"])
        return Response({"created": created, "skipped": skipped, "score_synced": bool(created)})


class WatchStateView(APIView):
    """Minimal match payload for the watch UI."""

    permission_classes = [AllowAny]

    def get(self, request: Request, fixture_pk) -> Response:
        row = _active_token(request.headers.get("Authorization") or request.query_params.get("token"))
        if str(row.fixture_id) != str(fixture_pk):
            raise PermissionDenied("This watch is paired to a different match.")
        fixture = (
            Fixture.objects.select_related("competition")
            .prefetch_related("sides__participant", "competition__scoring_categories")
            .get(pk=fixture_pk)
        )
        categories = [
            {
                "id": str(cat.id),
                "code": cat.code,
                "name": cat.name,
                "affects_score": cat.affects_score,
                "points": str(cat.points),
            }
            for cat in fixture.competition.scoring_categories.all().order_by("display_order", "name")
        ]
        sides = [
            {
                "id": str(side.id),
                "name": side.participant.name,
                "score": str(side.score),
                "is_home": side.is_home,
            }
            for side in fixture.sides.all()
        ]
        return Response(
            {
                "fixture_id": str(fixture.id),
                "competition_id": str(fixture.competition_id),
                "status": fixture.status,
                "phase": fixture.phase,
                "sides": sides,
                "categories": categories,
                "sport": fixture.competition.sport,
            }
        )
