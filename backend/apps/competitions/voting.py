"""Member voting that accumulates points on custom criteria boards.

Requires ``settings_json.points_by_voting``. Each member has a per-round vote
budget (``settings_json.votes_per_member``, default 1) they may split across
entrants. Visibility is ``secret`` / private (tallies hidden until the round
closes) or ``visible`` / public (live tallies). Only competition members may
cast a ballot; admins open and close rounds, and may override visibility per
round.
"""

from __future__ import annotations

from collections import Counter

from django.db import transaction
from django.db.models import Sum
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

VOTES_PER_MEMBER_MIN = 1
VOTES_PER_MEMBER_MAX = 100


def points_by_voting_enabled(competition: Competition) -> bool:
    return bool((competition.settings_json or {}).get("points_by_voting"))


def votes_per_member(competition: Competition) -> int:
    raw = (competition.settings_json or {}).get("votes_per_member")
    try:
        value = int(raw) if raw is not None and raw != "" else VOTES_PER_MEMBER_MIN
    except (TypeError, ValueError):
        value = VOTES_PER_MEMBER_MIN
    return max(VOTES_PER_MEMBER_MIN, min(VOTES_PER_MEMBER_MAX, value))


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
        .annotate(votes=Sum("quantity"))
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
            "votes": int(row["votes"] or 0),
        }
        for row in rows
    ]


def _my_allocations(round_row: VotingRound, user) -> list[dict]:
    rows = (
        Vote.objects.filter(round=round_row, voter=user)
        .select_related("participant")
        .order_by("created_at")
    )
    return [
        {
            "participant_id": str(row.participant_id),
            "participant_name": row.participant.name,
            "votes": row.quantity,
        }
        for row in rows
    ]


def _vote_total(round_row: VotingRound) -> int:
    total = Vote.objects.filter(round=round_row).aggregate(total=Sum("quantity"))["total"]
    return int(total or 0)


def _round_payload(round_row: VotingRound, user) -> dict:
    budget = votes_per_member(round_row.competition)
    my_votes = _my_allocations(round_row, user)
    votes_used = sum(row["votes"] for row in my_votes)
    show_tallies = _can_see_tallies(round_row, user)
    first = my_votes[0] if my_votes else None
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
        "votes_per_member": budget,
        "vote_count": _vote_total(round_row),
        "my_votes": my_votes,
        "votes_used": votes_used,
        "votes_remaining": max(0, budget - votes_used),
        # Legacy single-pick shape for clients that still read my_vote.
        "my_vote": (
            {
                "participant_id": first["participant_id"],
                "participant_name": first["participant_name"],
            }
            if first
            else None
        ),
        "tallies": _tallies(round_row) if show_tallies else None,
        "tallies_hidden": not show_tallies,
    }


def _parse_allocations(data, budget: int) -> list[tuple[str, int]]:
    """Return [(participant_id, votes), ...] validated against the budget."""
    raw_allocations = data.get("allocations")
    if raw_allocations is None:
        participant_id = data.get("participant")
        if participant_id in (None, ""):
            raise ValidationError(
                {"allocations": "Provide allocations, or a single participant for a one-vote ballot."}
            )
        # Legacy: one vote when budget is 1, otherwise the full budget on that entrant.
        votes = 1 if budget == 1 else budget
        raw_allocations = [{"participant": participant_id, "votes": votes}]

    if not isinstance(raw_allocations, list):
        raise ValidationError({"allocations": "Send a list of {participant, votes} objects."})
    if not raw_allocations:
        raise ValidationError({"allocations": "Allocate at least one vote."})

    parsed: list[tuple[str, int]] = []
    seen: set[str] = set()
    total = 0
    for index, row in enumerate(raw_allocations):
        if not isinstance(row, dict):
            raise ValidationError({"allocations": f"Item {index} must be an object."})
        participant_id = row.get("participant")
        if participant_id in (None, ""):
            raise ValidationError({"allocations": f"Item {index} needs a participant."})
        key = str(participant_id)
        if key in seen:
            raise ValidationError({"allocations": "Each entrant may appear only once."})
        seen.add(key)
        try:
            votes = int(row.get("votes"))
        except (TypeError, ValueError):
            raise ValidationError({"allocations": f"Item {index} needs a whole-number votes count."})
        if votes < 1:
            raise ValidationError({"allocations": "Each allocation must be at least 1 vote."})
        total += votes
        parsed.append((key, votes))

    if total > budget:
        raise ValidationError(
            {
                "allocations": (
                    f"You have {budget} vote{'s' if budget != 1 else ''} this round; "
                    f"you tried to use {total}."
                )
            }
        )
    return parsed


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
        raw_visibility = request.data.get("visibility")
        if raw_visibility in {
            VotingRound.Visibility.SECRET,
            VotingRound.Visibility.VISIBLE,
        }:
            visibility = raw_visibility
        elif raw_visibility in (None, ""):
            visibility = voting_visibility_setting(competition)
        else:
            raise ValidationError(
                {"visibility": "Use secret (private) or visible (public)."}
            )
        round_row = VotingRound.objects.create(
            competition=competition,
            category=category,
            title=title,
            note=note,
            visibility=visibility,
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

    @extend_schema(tags=TAG, summary="Cast or change your vote allocation")
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

        budget = votes_per_member(competition)
        allocations = _parse_allocations(request.data, budget)
        participant_ids = [pid for pid, _votes in allocations]
        participants = {
            str(p.id): p
            for p in Participant.objects.filter(
                competition=competition, id__in=participant_ids, is_active=True
            )
        }
        missing = [pid for pid in participant_ids if pid not in participants]
        if missing:
            raise ValidationError({"allocations": "One or more entrants are not in this competition."})

        with transaction.atomic():
            Vote.objects.filter(round=round_row, voter=request.user).delete()
            Vote.objects.bulk_create(
                [
                    Vote(
                        round=round_row,
                        voter=request.user,
                        participant=participants[pid],
                        quantity=votes,
                    )
                    for pid, votes in allocations
                ]
            )

        publish_event(
            competition_room(str(competition.id)),
            "voting.vote_cast",
            {"round_id": str(round_row.id), "vote_count": _vote_total(round_row)},
        )
        payload = _round_payload(round_row, request.user)
        return Response(
            {
                "round": payload,
                "vote": (
                    {
                        "id": None,
                        "participant_id": payload["my_vote"]["participant_id"],
                        "participant_name": payload["my_vote"]["participant_name"],
                    }
                    if payload["my_vote"]
                    else None
                ),
                "allocations": payload["my_votes"],
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

        counts: Counter[str] = Counter()
        for vote in votes:
            counts[str(vote.participant_id)] += vote.quantity
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
