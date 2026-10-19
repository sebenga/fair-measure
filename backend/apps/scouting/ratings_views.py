"""Scouting Phase 4 API: scout ratings, offline sync, organisation summaries and QR."""

from __future__ import annotations

import io

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import attributes, catalog, ratings
from .models import HighlightVideo, PlayerProfile, PlayerSport, ScoutRating
from .services import access_level, is_scout, scout_organisations, visible_profiles

TAG = ["Scouting"]
SHORT_CODE_LENGTH = 8


def short_code(profile: PlayerProfile) -> str:
    return str(profile.id).replace("-", "")[:SHORT_CODE_LENGTH].upper()


def _error_text(error) -> str:
    detail = getattr(error, "detail", error)
    if isinstance(detail, dict):
        return "; ".join(f"{key}: {_error_text(value)}" for key, value in detail.items())
    if isinstance(detail, list):
        return " ".join(_error_text(value) for value in detail)
    return str(detail)


class RatingCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Save one scout rating (repeats of the same client_id are stored once)",
        request=dict,
        responses={201: dict, 200: dict},
    )
    def post(self, request: Request) -> Response:
        rating, created = ratings.submit(request.user, request.data)
        return Response(
            ratings.rating_row(rating),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RatingSyncView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Sync ratings saved offline",
        description=(
            "Body: {ratings: [...]}. Each rating carries the client_id the app made when it "
            "was saved, so a rating sent twice is stored once. Each item reports created, "
            "duplicate or rejected (with the reason); one bad rating does not stop the rest."
        ),
        request=dict,
        responses=dict,
    )
    def post(self, request: Request) -> Response:
        items = request.data.get("ratings")
        if not isinstance(items, list) or len(items) > 100:
            raise ValidationError({"ratings": "Send a list of up to 100 ratings."})
        results = []
        for item in items:
            client_id = str((item or {}).get("client_id") or "")
            try:
                rating, created = ratings.submit(request.user, item or {})
            except (ValidationError, PermissionDenied) as error:
                results.append(
                    {"client_id": client_id, "status": "rejected", "error": _error_text(error)}
                )
                continue
            results.append(
                {
                    "client_id": client_id,
                    "status": "created" if created else "duplicate",
                    "id": str(rating.id),
                }
            )
        return Response({"results": results})


def _scout_profile(request: Request, pk) -> PlayerProfile:
    profile = get_object_or_404(PlayerProfile, pk=pk)
    if profile.user_id == request.user.id:
        raise PermissionDenied("Scout ratings and notes are private to the scouting organisation.")
    if not is_scout(request.user):
        raise PermissionDenied("Only scouts see ratings.")
    if access_level(profile, request.user) != "scout":
        raise NotFound("No profile found.")
    return profile


class ProfileRatingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="My organisation's ratings of a player, and the confidence-weighted summary",
        parameters=[
            OpenApiParameter("organisation", str, description="Which of my organisations"),
            OpenApiParameter("sport", str, description="Only ratings in this sport"),
        ],
        responses=dict,
    )
    def get(self, request: Request, pk) -> Response:
        profile = _scout_profile(request, pk)
        mine = scout_organisations(request.user)
        if not mine:
            raise PermissionDenied("Join a scouting organisation to see ratings.")
        wanted = request.query_params.get("organisation")
        organisation = next((row for row in mine if str(row.id) == wanted), mine[0])
        sport = request.query_params.get("sport") or None
        rows = ScoutRating.objects.filter(
            profile=profile, organisation=organisation
        ).select_related("scout", "fixture__competition")
        if sport:
            rows = rows.filter(sport=sport)
        return Response(
            {
                "summary": ratings.summary(profile, organisation, sport),
                "ratings": [ratings.rating_row(row) for row in rows],
                "organisations": [{"id": str(row.id), "name": row.name} for row in mine],
            }
        )


class RatingContextView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="What the rate screen needs: the player's sports, positions, fixtures and videos",
        responses=dict,
    )
    def get(self, request: Request, pk) -> Response:
        profile = _scout_profile(request, pk)
        sports = [
            {
                "key": row.sport,
                "label": catalog.SPORTS[row.sport]["label"],
                "position": row.primary_position,
            }
            for row in PlayerSport.objects.filter(profile=profile).order_by("-is_primary")
            if row.sport in catalog.SPORTS
        ]
        return Response(
            {
                "profile": {
                    "id": str(profile.id),
                    "name": f"{profile.first_name} {profile.last_name}".strip(),
                    "photo_url": profile.photo_url,
                    "code": short_code(profile),
                },
                "sports": sports,
                "fixtures": [
                    {
                        "id": str(fixture.id),
                        "label": fixture.label
                        or " v ".join(side.participant.name for side in fixture.sides.all()),
                        "competition": fixture.competition.name,
                        "scheduled_at": fixture.scheduled_at,
                        "status": fixture.status,
                    }
                    for fixture in ratings.player_fixtures(profile)
                ],
                "videos": [
                    {"id": str(row.id), "title": row.title}
                    for row in HighlightVideo.objects.filter(profile=profile)
                ],
                "organisations": [
                    {"id": str(row.id), "name": row.name}
                    for row in scout_organisations(request.user)
                ],
                "confidence": attributes.CONFIDENCE,
                "watched": attributes.WATCHED,
                "recommendations": attributes.RECOMMENDATIONS,
            }
        )


class ProfileLookupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Find a player by the short code under their QR code",
        parameters=[OpenApiParameter("code", str, required=True)],
        responses=dict,
    )
    def get(self, request: Request) -> Response:
        if not is_scout(request.user):
            raise PermissionDenied("Only scouts look players up by code.")
        code = "".join(
            ch for ch in str(request.query_params.get("code") or "") if ch.isalnum()
        ).lower()
        if len(code) < SHORT_CODE_LENGTH:
            raise ValidationError({"code": f"Type all {SHORT_CODE_LENGTH} characters of the code."})
        # The code is the first eight characters of the profile id.
        matches = [
            profile
            for profile in visible_profiles(request.user)
            if str(profile.id).replace("-", "").startswith(code[:SHORT_CODE_LENGTH])
            and access_level(profile, request.user) == "scout"
        ][:2]
        if not matches:
            raise NotFound("No visible player has that code.")
        if len(matches) > 1:
            raise ValidationError(
                {"code": "That code matches more than one player; search by name."}
            )
        profile = matches[0]
        return Response(
            {"id": str(profile.id), "name": f"{profile.first_name} {profile.last_name}".strip()}
        )


class ProfileQrView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=TAG,
        summary="A QR code (SVG) that opens the rate screen for this player",
        description="The code holds only the link and the profile id; scouts still need access.",
        responses={(200, "image/svg+xml"): bytes},
    )
    def get(self, request: Request, pk) -> HttpResponse:
        import segno

        profile = get_object_or_404(PlayerProfile, pk=pk)
        link = f"{settings.PUBLIC_APP_ORIGIN.rstrip('/')}/tabs/scouting/rate?profile={profile.id}"
        buffer = io.BytesIO()
        segno.make(link, error="m").save(buffer, kind="svg", scale=6, border=2, dark="#0b1f33")
        response = HttpResponse(buffer.getvalue(), content_type="image/svg+xml")
        response["Cache-Control"] = "public, max-age=86400"
        response["X-Profile-Code"] = short_code(profile)
        return response
