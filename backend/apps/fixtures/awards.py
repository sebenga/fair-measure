"""Per-match awards and season player stats, both named by the competition's preset.

A preset lists its awards (``match_awards``) and the player columns it keeps
(``player_stats``). Nothing here names a sport.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.models import RosterMember
from apps.competitions.views import visible_competitions
from apps.core.bus import competition_room, fixture_room, publish_event

from .models import Fixture, FixtureAward, ScoreEvent

TAG = ["Fixtures"]


def _award_rows(fixture: Fixture) -> list[dict]:
    settings = fixture.competition.settings_json or {}
    given = {
        award.key: award
        for award in FixtureAward.objects.filter(fixture=fixture).select_related(
            "player__participant", "horse"
        )
    }
    rows = []
    for item in settings.get("match_awards") or []:
        award = given.get(item["key"])
        rows.append(
            {
                "key": item["key"],
                "label": item["label"],
                "kind": item.get("kind", "player"),
                "description": item.get("description", ""),
                "winner": None
                if award is None
                else {
                    "player_id": str(award.player_id) if award.player_id else None,
                    "player_name": award.player.name if award.player_id else "",
                    "team": award.player.participant.name if award.player_id else "",
                    "horse_id": str(award.horse_id) if award.horse_id else None,
                    "name": award.name,
                },
            }
        )
    return rows


def _can_award(fixture: Fixture, user) -> bool:
    from apps.results.services import can_decide

    return can_decide(fixture.competition, user)


class FixtureAwardsView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def _fixture(self, request: Request, competition_pk, fixture_pk) -> Fixture:
        return get_object_or_404(
            Fixture.objects.select_related("competition"),
            pk=fixture_pk,
            competition_id=competition_pk,
            competition__in=visible_competitions(request.user),
        )

    @extend_schema(tags=TAG, summary="This match's awards", responses=dict)
    def get(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        return Response(
            {"awards": _award_rows(fixture), "can_award": _can_award(fixture, request.user)}
        )

    @extend_schema(
        tags=TAG,
        summary="Give or clear one award (officials)",
        description="Body: {key, player?, horse?, name?}. Send only the key to clear it.",
        request=dict,
        responses=dict,
    )
    def put(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        if not _can_award(fixture, request.user):
            raise PermissionDenied("Only this match's officials give its awards.")
        settings = fixture.competition.settings_json or {}
        spec = next(
            (item for item in settings.get("match_awards") or [] if item["key"] == request.data.get("key")),
            None,
        )
        if spec is None:
            raise ValidationError({"key": "This competition does not give that award."})

        player_id = request.data.get("player") or None
        horse_id = request.data.get("horse") or None
        name = str(request.data.get("name") or "").strip()[:160]
        if not (player_id or horse_id or name):
            FixtureAward.objects.filter(fixture=fixture, key=spec["key"]).delete()
            return self._done(fixture, request)

        player = None
        if player_id:
            player = RosterMember.objects.filter(
                pk=player_id, participant__fixture_sides__fixture=fixture
            ).first()
            if player is None:
                raise ValidationError({"player": "Choose a player from one of the two teams."})
        kind = spec.get("kind", "player")
        if kind == "player" and player is None:
            raise ValidationError({"player": "Choose the player who earned it."})
        if kind == "horse" and not (name or horse_id):
            raise ValidationError({"name": "Give the horse's name."})
        horse = None
        if horse_id:
            from apps.horses.models import Horse

            horse = Horse.objects.filter(pk=horse_id).first()
            if horse is None:
                raise ValidationError({"horse": "That horse is not in the registry."})
            name = name or horse.name
        if kind == "player" and not name:
            name = player.name

        FixtureAward.objects.update_or_create(
            fixture=fixture,
            key=spec["key"],
            defaults={"player": player, "horse": horse, "name": name, "awarded_by": request.user},
        )
        return self._done(fixture, request)

    def _done(self, fixture: Fixture, request: Request) -> Response:
        publish_event(
            "fixture.updated",
            {"fixture_id": str(fixture.id), "competition_id": str(fixture.competition_id)},
            [competition_room(fixture.competition_id), fixture_room(fixture.id)],
        )
        return Response({"awards": _award_rows(fixture), "can_award": True})


def player_stats(competition) -> dict:
    """Season totals per player for the columns the preset names."""

    columns = list((competition.settings_json or {}).get("player_stats") or [])
    counted = [Fixture.Status.COMPLETED, Fixture.Status.FORFEIT]
    rows: dict = {}

    def row_for(member: RosterMember) -> dict:
        return rows.setdefault(
            member.id,
            {
                "player_id": str(member.id),
                "user_id": str(member.user_id) if member.user_id else None,
                "name": member.name,
                "team": member.participant.name,
                "values": defaultdict(Decimal),
            },
        )

    codes = {code: column["key"] for column in columns for code in column.get("codes") or []}
    if codes:
        events = ScoreEvent.objects.filter(
            fixture__competition=competition,
            fixture__status__in=counted,
            player__isnull=False,
            scoring_category__code__in=list(codes),
        ).select_related("player__participant", "scoring_category")
        for event in events:
            for column in columns:
                if event.scoring_category.code in (column.get("codes") or []):
                    row_for(event.player)["values"][column["key"]] += Decimal(event.quantity)

    awards = {column["award"]: column["key"] for column in columns if column.get("award")}
    if awards:
        for award in FixtureAward.objects.filter(
            fixture__competition=competition,
            fixture__status__in=counted,
            key__in=list(awards),
            player__isnull=False,
        ).select_related("player__participant"):
            row_for(award.player)["values"][awards[award.key]] += 1

    ordered = sorted(
        rows.values(),
        key=lambda row: tuple(-row["values"].get(column["key"], 0) for column in columns)
        + (row["name"].lower(),),
    )
    return {
        "columns": [{"key": column["key"], "label": column["label"]} for column in columns],
        "rows": [
            {
                **row,
                "values": {
                    column["key"]: format(row["values"].get(column["key"], Decimal(0)).normalize(), "f")
                    for column in columns
                },
            }
            for row in ordered
        ],
    }


class PlayerStatsView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(tags=TAG, summary="Season player stats the preset keeps", responses=dict)
    def get(self, request: Request, competition_pk) -> Response:
        competition = get_object_or_404(visible_competitions(request.user), pk=competition_pk)
        return Response(player_stats(competition))
