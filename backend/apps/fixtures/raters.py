"""Match raters: profiles appointed to rate the players in one match.

A rater is never an active player in the competition. A player's match rating
is the average of the raters' marks, and only counts once at least
``MIN_RATERS`` raters have marked them.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.models import Membership, RosterMember, ScoringCategory
from apps.competitions.views import visible_competitions
from apps.core.bus import competition_room, fixture_room, publish_event
from apps.core.permissions import Role, has_at_least

from .models import (
    Fixture,
    FixtureLineup,
    FixtureRater,
    FixtureSide,
    LineupEntry,
    PlayerAppearance,
    PlayerMatchRating,
    RaterScore,
    ScoreEvent,
    Substitution,
)

TAG = ["Match raters"]
MIN_RATERS = 2
RATEABLE = {Fixture.Status.LIVE, Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}


def player_stat_codes(competition) -> set[str]:
    """Score types the preset records as player stats (assists, tackles), not the score."""

    types = (getattr(competition, "settings_json", None) or {}).get("score_types") or []
    return {
        item["key"]
        for item in types
        if isinstance(item, dict) and item.get("stat") and item.get("key")
    }


def _can_record_stats(fixture: Fixture, user) -> bool:
    if not getattr(user, "is_authenticated", False) or fixture.status not in RATEABLE:
        return False
    if has_at_least(fixture.competition, user, Role.ADMIN):
        return True
    return (
        FixtureRater.objects.filter(fixture=fixture, user=user).exists()
        and fixture.raters.count() >= MIN_RATERS
    )


def _name(user) -> str:
    return getattr(user, "display_name", "") or user.get_full_name() or user.email


def active_player_ids(fixture: Fixture) -> set:
    """Profiles on an active roster anywhere in this competition."""

    return set(
        RosterMember.objects.filter(
            participant__competition=fixture.competition,
            participant__is_active=True,
            is_active=True,
            user__isnull=False,
        ).values_list("user_id", flat=True)
    )


def _players(fixture: Fixture) -> list[dict]:
    """Who can be rated, per side: those who played on the team sheet, else the squad."""

    groups = []
    for side in fixture.sides.select_related("participant").order_by("position"):
        lineup = FixtureLineup.objects.filter(side=side).first()
        if lineup is not None:
            entries = LineupEntry.objects.filter(lineup=lineup).select_related("player")
            came_on = set(
                Substitution.objects.filter(side=side).values_list("player_on_id", flat=True)
            )
            members = [
                (entry.player, entry.number)
                for entry in entries
                if entry.role == LineupEntry.Role.STARTER or entry.player_id in came_on
            ]
        else:
            members = [
                (member, member.number)
                for member in side.participant.roster.filter(is_active=True).order_by("number", "name")
            ]
        groups.append({"side": side, "members": members})
    return groups


def recompute(fixture: Fixture) -> None:
    """Publish each player's average once enough raters have marked them."""

    rows = (
        RaterScore.objects.filter(fixture=fixture)
        .values("player_id")
        .annotate(average=Avg("rating"), raters=Count("rater", distinct=True))
    )
    ready = {}
    for row in rows:
        if row["raters"] >= MIN_RATERS:
            ready[row["player_id"]] = Decimal(row["average"]).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
    PlayerMatchRating.objects.filter(fixture=fixture).exclude(player_id__in=ready).delete()
    for player_id, rating in ready.items():
        PlayerMatchRating.objects.update_or_create(
            fixture=fixture, player_id=player_id, defaults={"rating": rating}
        )


def _kind(category) -> str:
    code = getattr(category, "code", "") or ""
    if "card" in code:
        return "card"
    if getattr(category, "affects_score", False):
        return "score"
    return "stat"


def _stat_item(code: str, label: str, count, kind: str) -> dict:
    value = Decimal(str(count))
    text = format(value.normalize(), "f") if value else "0"
    return {
        "code": code,
        "label": label,
        "count": text,
        "kind": kind,
        "recorded": value != 0,
        "editable": kind in {"stat", "minutes"},
    }


def _lineup_facts(fixture: Fixture) -> dict:
    """Started or came on, shirt position, and substitution minutes."""

    facts: dict = {}
    lineups = FixtureLineup.objects.filter(fixture=fixture).select_related("captain")
    entries = LineupEntry.objects.filter(lineup__fixture=fixture)
    for entry in entries:
        facts[entry.player_id] = {
            "role": "Started" if entry.role == LineupEntry.Role.STARTER else "Bench",
            "position": entry.position,
            "captain": False,
        }
    for lineup in lineups:
        if lineup.captain_id and lineup.captain_id in facts:
            facts[lineup.captain_id]["captain"] = True
    for sub in Substitution.objects.filter(fixture=fixture):
        incoming = facts.setdefault(
            sub.player_on_id, {"role": "Bench", "position": "", "captain": False}
        )
        incoming["role"] = f"On {sub.minute}'" if sub.minute is not None else "Came on"
        outgoing = facts.get(sub.player_off_id)
        if outgoing is not None:
            stamp = f"Off {sub.minute}'" if sub.minute is not None else "Subbed off"
            outgoing["role"] = f"{outgoing['role']} · {stamp}"
    return facts


def _stat_lines(fixture: Fixture) -> dict[object, list[dict]]:
    """Each player's match sheet: minutes plus every scoring and player-stat category."""

    categories = list(fixture.competition.scoring_categories.order_by("name"))
    counts: dict[object, dict] = {}
    events = ScoreEvent.objects.filter(fixture=fixture, player__isnull=False).select_related(
        "scoring_category"
    )
    for event in events:
        bucket = counts.setdefault(event.player_id, {})
        bucket[event.scoring_category_id] = (
            bucket.get(event.scoring_category_id, Decimal("0")) + event.quantity
        )
    minutes = {
        row.player_id: row.minutes
        for row in PlayerAppearance.objects.filter(fixture=fixture)
        if row.minutes is not None
    }
    player_ids = {member.id for group in _players(fixture) for member, _ in group["members"]}
    player_ids.update(counts)
    player_ids.update(minutes)

    result: dict[object, list[dict]] = {}
    for player_id in player_ids:
        stats = [_stat_item("minutes", "Minutes", minutes.get(player_id, 0), "minutes")]
        got = counts.get(player_id, {})
        for category in categories:
            stats.append(
                _stat_item(
                    category.code,
                    category.name,
                    got.get(category.id, Decimal("0")),
                    _kind(category),
                )
            )
        result[player_id] = stats
    return result


def payload(fixture: Fixture, user, query: str = "") -> dict:
    raters = list(FixtureRater.objects.filter(fixture=fixture).select_related("user"))
    mine = next((rater for rater in raters if rater.user_id == getattr(user, "id", None)), None)
    can_manage = getattr(user, "is_authenticated", False) and has_at_least(
        fixture.competition, user, Role.ADMIN
    )
    scores = list(RaterScore.objects.filter(fixture=fixture))
    stats = _stat_lines(fixture)
    by_player: dict = {}
    for score in scores:
        by_player.setdefault(score.player_id, []).append(score)
    rated_counts: dict = {}
    for score in scores:
        rated_counts[score.rater_id] = rated_counts.get(score.rater_id, 0) + 1

    facts = _lineup_facts(fixture)
    from .cards import is_sent_off

    teams = []
    for group in _players(fixture):
        players = []
        for member, number in group["members"]:
            marks = by_player.get(member.id, [])
            average = None
            if len(marks) >= MIN_RATERS:
                average = format(
                    (sum(mark.rating for mark in marks) / len(marks)).quantize(
                        Decimal("0.1"), rounding=ROUND_HALF_UP
                    ),
                    "f",
                )
            own = next((mark for mark in marks if mine and mark.rater_id == mine.id), None)
            fact = facts.get(member.id) or {}
            dismissed = is_sent_off(fixture, member.id)
            players.append(
                {
                    "player_id": str(member.id),
                    "user_id": str(member.user_id) if member.user_id else None,
                    "name": member.name,
                    "number": number,
                    "role": fact.get("role") or "",
                    "position": fact.get("position") or "",
                    "captain": bool(fact.get("captain")),
                    "sent_off": dismissed,
                    "rating_locked": dismissed,
                    "average": average,
                    "count": len(marks),
                    "mine": format(own.rating, "f") if own else None,
                    "stats": stats.get(member.id, []),
                }
            )
        teams.append(
            {
                "side_id": str(group["side"].id),
                "team": group["side"].participant.name,
                "players": players,
            }
        )

    candidates = []
    if can_manage and query.strip():
        taken = {rater.user_id for rater in raters}
        excluded = taken | active_player_ids(fixture)
        users = (
            get_user_model()
            .objects.filter(is_active=True)
            .filter(Q(display_name__icontains=query) | Q(email__icontains=query))
            .exclude(id__in=excluded)
            .order_by("display_name", "email")[:8]
        )
        candidates = [{"id": str(person.id), "name": _name(person), "email": person.email} for person in users]

    return {
        "minimum": MIN_RATERS,
        "raters": [
            {
                "id": str(rater.id),
                "user_id": str(rater.user_id),
                "name": _name(rater.user),
                "email": rater.user.email,
                "rated": rated_counts.get(rater.id, 0),
            }
            for rater in raters
        ],
        "enough": len(raters) >= MIN_RATERS,
        "can_manage": bool(can_manage),
        "is_rater": mine is not None,
        "can_rate": mine is not None and len(raters) >= MIN_RATERS and fixture.status in RATEABLE,
        "can_record_stats": _can_record_stats(fixture, user),
        "status": fixture.status,
        "teams": teams,
        "candidates": candidates,
    }


def _broadcast(fixture: Fixture) -> None:
    publish_event(
        "fixture.updated",
        {"fixture_id": str(fixture.id), "competition_id": str(fixture.competition_id)},
        [competition_room(fixture.competition_id), fixture_room(fixture.id)],
    )


class _FixtureView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def _fixture(self, request: Request, competition_pk, fixture_pk) -> Fixture:
        return get_object_or_404(
            Fixture.objects.select_related("competition"),
            pk=fixture_pk,
            competition_id=competition_pk,
            competition__in=visible_competitions(request.user),
        )


class FixtureRatersView(_FixtureView):
    @extend_schema(
        tags=TAG,
        summary="This match's raters and the players they rate",
        description="Admins may pass ?q= to search profiles who can be appointed.",
        responses=dict,
    )
    def get(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        return Response(payload(fixture, request.user, request.query_params.get("q", "")))

    @extend_schema(tags=TAG, summary="Appoint a rater (admins)", request=dict, responses=dict)
    def post(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        if not has_at_least(fixture.competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only an admin appoints the raters.")
        user = get_object_or_404(get_user_model(), pk=request.data.get("user"), is_active=True)
        if user.id in active_player_ids(fixture):
            raise ValidationError({"user": "Active players cannot rate players. Choose someone who is not playing."})
        if FixtureRater.objects.filter(fixture=fixture, user=user).exists():
            raise ValidationError({"user": f"{_name(user)} is already rating this match."})
        if not Membership.objects.filter(competition=fixture.competition, user=user).exists():
            Membership.objects.create(
                competition=fixture.competition, user=user, role=Role.MEMBER, invited_by=request.user
            )
        FixtureRater.objects.create(fixture=fixture, user=user, assigned_by=request.user)
        _broadcast(fixture)
        return Response(payload(fixture, request.user), status=status.HTTP_201_CREATED)

    @extend_schema(tags=TAG, summary="Remove a rater (admins)", responses=dict)
    def delete(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        if not has_at_least(fixture.competition, request.user, Role.ADMIN):
            raise PermissionDenied("Only an admin changes the raters.")
        with transaction.atomic():
            FixtureRater.objects.filter(fixture=fixture, user_id=request.query_params.get("user")).delete()
            recompute(fixture)
        _broadcast(fixture)
        return Response(payload(fixture, request.user))


class RaterScoresView(_FixtureView):
    @extend_schema(
        tags=TAG,
        summary="Submit my ratings (appointed raters)",
        description="Body: {ratings: [{player, rating}]}. An empty rating clears my mark.",
        request=dict,
        responses=dict,
    )
    def put(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        rater = FixtureRater.objects.filter(fixture=fixture, user=request.user).first()
        if rater is None:
            raise PermissionDenied("Only this match's appointed raters rate its players.")
        if fixture.raters.count() < MIN_RATERS:
            raise ValidationError(f"Appoint at least {MIN_RATERS} raters before rating starts.")
        if fixture.status not in RATEABLE:
            raise ValidationError("Ratings open at kickoff.")

        allowed = {
            str(member.id): member for group in _players(fixture) for member, _ in group["members"]
        }
        changes = []
        for row in request.data.get("ratings") or []:
            player_id = str((row or {}).get("player") or "")
            if player_id not in allowed:
                raise ValidationError({"ratings": "Rate players who took part in this match."})
            value = (row or {}).get("rating")
            if value in ("", None):
                changes.append((allowed[player_id], None))
                continue
            try:
                rating = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            except (InvalidOperation, ValueError) as exc:
                raise ValidationError({"ratings": "Ratings are numbers from 0 to 10."}) from exc
            if not Decimal("0") <= rating <= Decimal("10"):
                raise ValidationError({"ratings": "Ratings are from 0 to 10."})
            changes.append((allowed[player_id], rating))

        from .cards import is_sent_off

        with transaction.atomic():
            for player, rating in changes:
                if is_sent_off(fixture, player.id):
                    raise ValidationError(
                        {"ratings": f"{player.name}'s rating stopped when they were sent off."}
                    )
                if rating is None:
                    RaterScore.objects.filter(rater=rater, player=player).delete()
                else:
                    RaterScore.objects.update_or_create(
                        rater=rater, player=player, defaults={"fixture": fixture, "rating": rating}
                    )
            recompute(fixture)
        _broadcast(fixture)
        return Response(payload(fixture, request.user))


class RaterPlayerStatsView(_FixtureView):
    """Record assists, tackles and other player stats used to rate this match."""

    @extend_schema(
        tags=TAG,
        summary="Record a player stat (Raters tab)",
        description="Body: {player, code, delta} to add or remove one, or {player, minutes}.",
        request=dict,
        responses=dict,
    )
    def post(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        if not _can_record_stats(fixture, request.user):
            raise PermissionDenied("Player stats are recorded on the Raters tab after kickoff.")
        player = get_object_or_404(
            RosterMember,
            pk=request.data.get("player"),
            participant__competition=fixture.competition,
        )
        side = FixtureSide.objects.filter(fixture=fixture, participant_id=player.participant_id).first()
        if side is None:
            raise ValidationError({"player": "That player is not in this match."})
        from .cards import is_sent_off

        if is_sent_off(fixture, player.id):
            raise ValidationError({"player": "That player was sent off. Their stats have stopped."})

        if "minutes" in request.data:
            try:
                minutes = int(request.data.get("minutes"))
            except (TypeError, ValueError) as exc:
                raise ValidationError({"minutes": "Minutes played must be a whole number."}) from exc
            if minutes < 0 or minutes > 300:
                raise ValidationError({"minutes": "Minutes played must be a whole number."})
            PlayerAppearance.objects.update_or_create(
                fixture=fixture, player=player, defaults={"minutes": minutes}
            )
            _broadcast(fixture)
            return Response(payload(fixture, request.user))

        codes = player_stat_codes(fixture.competition)
        code = str(request.data.get("code") or "").strip()
        if code not in codes:
            raise ValidationError({"code": "That is a score, not a player stat. Record scores on the Live tab."})
        category = get_object_or_404(
            ScoringCategory, competition=fixture.competition, code=code
        )
        try:
            delta = int(request.data.get("delta", 1))
        except (TypeError, ValueError) as exc:
            raise ValidationError({"delta": "Add or remove one."}) from exc
        if delta not in (1, -1):
            raise ValidationError({"delta": "Add or remove one."})

        with transaction.atomic():
            if delta == 1:
                ScoreEvent.objects.create(
                    fixture=fixture,
                    side=side,
                    scoring_category=category,
                    player=player,
                    player_name=player.name,
                    quantity=Decimal("1"),
                    recorded_by=request.user,
                )
            else:
                event = (
                    ScoreEvent.objects.filter(
                        fixture=fixture, player=player, scoring_category=category
                    )
                    .order_by("-created_at")
                    .first()
                )
                if event is None:
                    raise ValidationError({"code": f"{category.name} is already at zero."})
                if event.quantity > 1:
                    event.quantity -= 1
                    event.save(update_fields=["quantity", "updated_at"])
                else:
                    event.delete()
        _broadcast(fixture)
        return Response(payload(fixture, request.user))
