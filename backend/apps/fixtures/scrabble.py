"""Word-entry turns: the server recomputes every total and writes a score event."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.scrabble.scoring import apply_endgame, preview_move, score_move, validate_move
from apps.competitions.scrabble.tiles import default_tile_set, public_tiles
from apps.competitions.views import visible_competitions
from apps.core.bus import competition_room, fixture_room, publish_event

from .models import Fixture, FixtureSide, ScoreEvent, ScrabbleEndgame, ScrabbleMove
from .views import _log_amendment, _official_reason, _scores, user_can_score_fixture

TAG = ["Word entry"]


def _tile_set(fixture: Fixture) -> str:
    return default_tile_set(fixture.competition.settings_json)


def _used_blanks(fixture: Fixture, *, exclude=None) -> int:
    moves = fixture.scrabble_moves.all()
    if exclude is not None:
        moves = moves.exclude(pk=exclude.pk)
    return sum(
        1
        for move in moves
        for word in move.words or []
        for tile in word.get("tiles") or []
        if tile.get("blank") and tile.get("new", True)
    )


def _category(fixture: Fixture, code: str):
    return fixture.competition.scoring_categories.filter(code=code).first()


def _write_event(move: ScrabbleMove, *, quantity: int, code: str = "turn") -> ScoreEvent | None:
    category = _category(move.fixture, code)
    if category is None:
        return None
    if move.event_id:
        event = move.event
        event.quantity = Decimal(quantity)
        event.scoring_category = category
        event.side = move.side
        event.player_name = move.side.participant.name
        event.note = move.note
        event.save()
        return event
    event = ScoreEvent.objects.create(
        fixture=move.fixture,
        side=move.side,
        scoring_category=category,
        quantity=Decimal(quantity),
        player_name=move.side.participant.name,
        recorded_by=move.created_by,
        note=move.note,
    )
    move.event = event
    move.save(update_fields=["event"])
    return event


def _row(move: ScrabbleMove, tile_set: str) -> dict:
    preview = preview_move(
        {"type": move.kind, "words": move.words, "bingo": move.bingo},
        tile_set,
    )
    return {
        "id": str(move.id),
        "side": str(move.side_id),
        "player": move.side.participant.name,
        "turn_no": move.turn_no,
        "type": move.kind,
        "words": move.words,
        "total": move.total,
        "bingo": move.bingo,
        "breakdown": [word.get("breakdown") for word in preview["words"]],
        "created_at": move.created_at.isoformat(),
        "created_by": str(move.created_by_id) if move.created_by_id else None,
    }


def payload(fixture: Fixture, user) -> dict:
    tile_set = _tile_set(fixture)
    endgame = getattr(fixture, "scrabble_endgame", None)
    return {
        "tile_set": public_tiles(tile_set),
        "can_score": user_can_score_fixture(fixture, user) if getattr(user, "is_authenticated", False) else False,
        "moves": [_row(move, tile_set) for move in fixture.scrabble_moves.select_related("side__participant")],
        "endgame": (
            {"racks": endgame.racks, "went_out": str(endgame.went_out_id) if endgame.went_out_id else None}
            if endgame
            else None
        ),
    }


def _broadcast(fixture: Fixture, extra: dict | None = None) -> None:
    fixture.recalculate_scores()
    body = {"fixture_id": str(fixture.id), "competition_id": str(fixture.competition_id), "scores": _scores(fixture)}
    if extra:
        body.update(extra)
    publish_event("score.recorded", body, [competition_room(fixture.competition_id), fixture_room(fixture.id)])
    publish_event("fixture.updated", body, [competition_room(fixture.competition_id), fixture_room(fixture.id)])


class _BoardView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def _fixture(self, request: Request, competition_pk, fixture_pk) -> Fixture:
        return get_object_or_404(
            Fixture.objects.select_related("competition"),
            pk=fixture_pk,
            competition_id=competition_pk,
            competition__in=visible_competitions(request.user),
        )

    def _assert_can_score(self, fixture: Fixture, request: Request) -> None:
        if not user_can_score_fixture(fixture, request.user):
            raise PermissionDenied("You need to be an admin or this game's referee to score it.")


class ScrabbleBoardView(_BoardView):
    @extend_schema(tags=TAG, summary="Word-entry board: tiles, moves and remaining racks")
    def get(self, request: Request, competition_pk, fixture_pk) -> Response:
        return Response(payload(self._fixture(request, competition_pk, fixture_pk), request.user))


class ScrabblePreviewView(_BoardView):
    @extend_schema(tags=TAG, summary="Preview a word-entry total without saving")
    def post(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        return Response(preview_move(request.data, _tile_set(fixture)))


class ScrabbleMovesView(_BoardView):
    @extend_schema(tags=TAG, summary="Record a word-entry turn")
    def post(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        self._assert_can_score(fixture, request)
        if fixture.status in {Fixture.Status.CANCELLED, Fixture.Status.POSTPONED}:
            raise ValidationError("This match is not being scored.")
        side = get_object_or_404(FixtureSide, pk=request.data.get("side") or request.data.get("player"), fixture=fixture)
        tile_set = _tile_set(fixture)
        cleaned = validate_move(request.data, used_blanks=_used_blanks(fixture), tile_set=tile_set)
        total, bingo = score_move(cleaned, tile_set)
        turn_no = int(request.data.get("turn_no") or 0) or (
            (fixture.scrabble_moves.order_by("-turn_no").values_list("turn_no", flat=True).first() or 0) + 1
        )
        with transaction.atomic():
            move = ScrabbleMove.objects.create(
                fixture=fixture,
                side=side,
                turn_no=turn_no,
                kind=cleaned["type"],
                words=cleaned["words"],
                total=total,
                bingo=bingo,
                created_by=request.user,
            )
            if cleaned["type"] == "play" or total:
                _write_event(move, quantity=total)
            _broadcast(fixture, {"move_id": str(move.id)})
        return Response(payload(fixture, request.user), status=status.HTTP_201_CREATED)


class ScrabbleMoveView(_BoardView):
    def _move(self, request, competition_pk, fixture_pk, move_pk) -> tuple[Fixture, ScrabbleMove]:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        move = get_object_or_404(ScrabbleMove, pk=move_pk, fixture=fixture)
        return fixture, move

    @extend_schema(tags=TAG, summary="Correct a word-entry turn")
    def patch(self, request: Request, competition_pk, fixture_pk, move_pk) -> Response:
        fixture, move = self._move(request, competition_pk, fixture_pk, move_pk)
        self._assert_can_score(fixture, request)
        reason = _official_reason(fixture, request)
        before = _scores(fixture)
        tile_set = _tile_set(fixture)
        cleaned = validate_move(request.data, used_blanks=_used_blanks(fixture, exclude=move), tile_set=tile_set)
        total, bingo = score_move(cleaned, tile_set)
        with transaction.atomic():
            move.kind = cleaned["type"]
            move.words = cleaned["words"]
            move.total = total
            move.bingo = bingo
            if request.data.get("side") or request.data.get("player"):
                move.side = get_object_or_404(
                    FixtureSide, pk=request.data.get("side") or request.data.get("player"), fixture=fixture
                )
            if request.data.get("turn_no"):
                move.turn_no = int(request.data["turn_no"])
            move.note = str(request.data.get("note") or move.note)
            move.save()
            if cleaned["type"] == "play" or total:
                _write_event(move, quantity=total)
            elif move.event_id:
                move.event.delete()
                move.event = None
                move.save(update_fields=["event"])
            if reason:
                _log_amendment(fixture, request, reason, before, action="amended")
            _broadcast(fixture, {"move_id": str(move.id)})
        return Response(payload(fixture, request.user))

    @extend_schema(tags=TAG, summary="Undo a word-entry turn")
    def delete(self, request: Request, competition_pk, fixture_pk, move_pk) -> Response:
        fixture, move = self._move(request, competition_pk, fixture_pk, move_pk)
        self._assert_can_score(fixture, request)
        reason = _official_reason(fixture, request)
        before = _scores(fixture)
        with transaction.atomic():
            if move.event_id:
                move.event.delete()
            move.delete()
            if reason:
                _log_amendment(fixture, request, reason, before, action="removed")
            _broadcast(fixture)
        return Response(payload(fixture, request.user))


class ScrabbleRacksView(_BoardView):
    @extend_schema(tags=TAG, summary="Apply remaining racks at the end of the game")
    def post(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        self._assert_can_score(fixture, request)
        tile_set = _tile_set(fixture)
        raw = list(request.data.get("racks") or [])
        if not raw:
            raise ValidationError({"racks": "Give each player's remaining tiles."})
        sides = {str(side.id): side for side in fixture.sides.select_related("participant")}
        racks = []
        for row in raw:
            side_id = str(row.get("side") or "")
            if side_id not in sides:
                raise ValidationError({"racks": "Each rack belongs to a side in this match."})
            racks.append({"side": side_id, "letters": row.get("letters") or ""})
        adjustments = apply_endgame(racks, tile_set)
        unplayed = _category(fixture, "unplayed")
        tiles_out = _category(fixture, "tiles-out")
        if unplayed is None or tiles_out is None:
            raise ValidationError("This competition is missing unplayed-tile scoring categories.")
        with transaction.atomic():
            ScoreEvent.objects.filter(
                fixture=fixture, scoring_category__code__in={"unplayed", "tiles-out"}
            ).delete()
            went_out = None
            for row in adjustments:
                side = sides[str(row["side"])]
                if row["unplayed"]:
                    ScoreEvent.objects.create(
                        fixture=fixture,
                        side=side,
                        scoring_category=unplayed,
                        quantity=Decimal(abs(row["unplayed"])),
                        player_name=side.participant.name,
                        recorded_by=request.user,
                        note=row["letters"],
                    )
                if row["tiles_out"]:
                    ScoreEvent.objects.create(
                        fixture=fixture,
                        side=side,
                        scoring_category=tiles_out,
                        quantity=Decimal(row["tiles_out"]),
                        player_name=side.participant.name,
                        recorded_by=request.user,
                    )
                    went_out = side.id
            ScrabbleEndgame.objects.update_or_create(
                fixture=fixture,
                defaults={"racks": adjustments, "went_out_id": went_out, "applied_by": request.user},
            )
            _broadcast(fixture)
        return Response(payload(fixture, request.user))
