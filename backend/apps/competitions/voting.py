"""Member voting that accumulates points on custom criteria boards.

Requires ``settings_json.points_by_voting``. Visibility is ``secret`` (tallies
hidden until the round closes) or ``visible`` (live tallies). Only competition
members may cast a ballot; admins open and close rounds.
"""

from __future__ import annotations

from collections import Counter

from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.bus import competition_room, publish_event
from apps.core.permissions import Role, has_at_least
from apps.fixtures.services import award_criterion

from .models import Competition, Membership, Participant, ScoringCategory, Vote, VotingRound
from .views import visible_competitions

TAG = ["Voting"]


def points_by_voting_enabled(competition: Competition) -> bool:
    return bool((competition.settings_json or {}).get("points_by_voting"))


def voting_visibility_setting(competition: Competition) -> str:
    raw = (competition.settings_json or {}).get("voting_visibility") or "secret"
    return (
        VotingRound.Visibility.VISIBLE
        if raw == VotingRound.Visibility.VISIBLE
        else VotingRound.Visibility.SECRET
    )


def _competition(user, competition_pk) -> Competition:
    return get_object_or_404(visible_competitions(user), pk=competition_pk)


def _require_member(competition: Competition, user) -> Membership:
    membership = Membership.objects.filter(competition=competition, user=user).first()
    if membership is None:
        raise PermissionDenied("Join this competition before voting.")
    return membership


def _require_admin(competition: Competition, user) -> None:
    if not has_at_least(competition, user, Role.ADMIN):
        raise PermissionDenied("Only an admin can manage voting rounds.")


def _can_see_tallies(round_row: VotingRound, user) -> bool:
    if round_row.visibility == VotingRound.Visibility.VISIBLE:
        return True
    if round_row.status == VotingRound.Status.CLOSED:
        return True
    return has_at_least(round_row.competition, user, Role.ADMIN)


def _tallies(round_row: VotingRound) -> list[dict]:
    rows = (
        Vote.objects.filter(round=round_row)
        .values("participant_id")
        .annotate(votes=Count("id"))
        .order_by("-votes")
    )
    names = {
        str(p.id): p.name
        for p in Participant.objects.filter(competition=round_row.competition, is_active=True)
    }
    return [
        {
            "participant_id": str(row["participant_id"]),
            "participant_name": names.get(str(row["participant_id"]), ""),
            "votes": row["votes"],
        }
        for row in rows
    ]


def _round_payload(round_row: VotingRound, user) -> dict:
    my_vote = Vote.objects.filter(round=round_row, voter=user).select_related("participant").first()
    show_tallies = _can_see_tallies(round_row, user)
    return {
        "id": str(round_row.id),
        "competition_id": str(round_row.competition_id),
        "category_id": str(round_row.category_id),
        "category_name": round_row.category.name,
        "category_points": str(round_row.category.points),
        "title": round_row.title or round_row.category.name,
        "status": round_row.status,
        "visibility": round_row.visibility,
        "note": round_row.note,
        "created_at": round_row.created_at.isoformat(),
        "closed_at": round_row.closed_at.isoformat() if round_row.closed_at else None,
        "vote_count": Vote.objects.filter(round=round_row).count(),
        "my_vote": (
            {
                "participant_id": str(my_vote.participant_id),
                "participant_name": my_vote.participant.name,
            }
            if my_vote
            else None
        ),
        "tallies": _tallies(round_row) if show_tallies else None,
        "tallies_hidden": not show_tallies,
    }


class VotingRoundListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="List voting rounds")
    def get(self, request: Request, competition_pk) -> Response:
        competition = _competition(request.user, competition_pk)
        _require_member(competition, request.user)
        if not points_by_voting_enabled(competition):
            return Response([])
        rounds = (
            VotingRound.objects.filter(competition=competition)
            .select_related("category")
            .order_by("-created_at")[:50]
        )
        return Response([_round_payload(row, request.user) for row in rounds])

    @extend_schema(tags=TAG, summary="Open a voting round")
    def post(self, request: Request, competition_pk) -> Response:
        competition = _competition(request.user, competition_pk)
        _require_admin(competition, request.user)
        if not points_by_voting_enabled(competition):
            raise ValidationError(
                {"points_by_voting": "Turn on points by voting in this competition's scoring options."}
            )
        category_id = request.data.get("scoring_category") or request.data.get("category")
        category = get_object_or_404(
            ScoringCategory, pk=category_id, competition=competition, affects_score=True
        )
        title = str(request.data.get("title") or "").strip()[:200]
        note = str(request.data.get("note") or "").strip()[:280]
        round_row = VotingRound.objects.create(
            competition=competition,
            category=category,
            title=title,
            note=note,
            visibility=voting_visibility_setting(competition),
            created_by=request.user,
        )
        publish_event(
            competition_room(str(competition.id)),
            "voting.round_opened",
            {"round_id": str(round_row.id)},
        )
        return Response(_round_payload(round_row, request.user), status=status.HTTP_201_CREATED)


class VotingRoundDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Get a voting round")
    def get(self, request: Request, competition_pk, round_pk) -> Response:
        competition = _competition(request.user, competition_pk)
        _require_member(competition, request.user)
        round_row = get_object_or_404(
            VotingRound.objects.select_related("category", "competition"),
            pk=round_pk,
            competition=competition,
        )
        return Response(_round_payload(round_row, request.user))


class VoteCastView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Cast or change your vote")
    def put(self, request: Request, competition_pk, round_pk) -> Response:
        competition = _competition(request.user, competition_pk)
        _require_member(competition, request.user)
        if not points_by_voting_enabled(competition):
            raise ValidationError({"points_by_voting": "Voting is not enabled for this competition."})
        round_row = get_object_or_404(
            VotingRound.objects.select_related("category", "competition"),
            pk=round_pk,
            competition=competition,
        )
        if round_row.status != VotingRound.Status.OPEN:
            raise ValidationError({"round": "This voting round is closed."})
        participant_id = request.data.get("participant")
        participant = get_object_or_404(
            Participant, pk=participant_id, competition=competition, is_active=True
        )
        vote, _created = Vote.objects.update_or_create(
            round=round_row,
            voter=request.user,
            defaults={"participant": participant},
        )
        publish_event(
            competition_room(str(competition.id)),
            "voting.vote_cast",
            {"round_id": str(round_row.id), "vote_count": Vote.objects.filter(round=round_row).count()},
        )
        return Response(
            {
                "round": _round_payload(round_row, request.user),
                "vote": {
                    "id": str(vote.id),
                    "participant_id": str(vote.participant_id),
                    "participant_name": participant.name,
                },
            }
        )


class VotingRoundCloseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Close a voting round and award points")
    def post(self, request: Request, competition_pk, round_pk) -> Response:
        competition = _competition(request.user, competition_pk)
        _require_admin(competition, request.user)
        round_row = get_object_or_404(
            VotingRound.objects.select_related("category", "competition"),
            pk=round_pk,
            competition=competition,
        )
        if round_row.status == VotingRound.Status.CLOSED:
            return Response(_round_payload(round_row, request.user))

        votes = list(Vote.objects.filter(round=round_row).select_related("participant"))
        if not votes:
            raise ValidationError({"votes": "No votes to award yet."})

        counts = Counter(str(vote.participant_id) for vote in votes)
        participants = {
            str(p.id): p
            for p in Participant.objects.filter(
                competition=competition, id__in=counts.keys(), is_active=True
            )
        }
        label = round_row.title or round_row.category.name
        note = (round_row.note or f"Voting round: {label}").strip()[:280]

        with transaction.atomic():
            for participant_id, quantity in counts.items():
                participant = participants.get(participant_id)
                if participant is None:
                    continue
                award_criterion(
                    competition=competition,
                    participant=participant,
                    category=round_row.category,
                    quantity=quantity,
                    note=note,
                    user=request.user,
                )
            round_row.status = VotingRound.Status.CLOSED
            round_row.closed_at = timezone.now()
            round_row.closed_by = request.user
            round_row.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])

        publish_event(
            competition_room(str(competition.id)),
            "voting.round_closed",
            {"round_id": str(round_row.id)},
        )
        publish_event(
            competition_room(str(competition.id)),
            "standings.updated",
            {"competition_id": str(competition.id)},
        )
        return Response(_round_payload(round_row, request.user))
