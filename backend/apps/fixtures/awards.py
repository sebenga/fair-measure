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


DEFAULT_EVENT_COLUMNS = [
    {"key": "goals", "label": "Goals", "codes": ["goal", "penalty-goal"]},
    {"key": "penalty_goals", "label": "Penalty goals", "codes": ["penalty-goal"]},
    {"key": "own_goals", "label": "Own goals", "codes": ["own-goal"]},
    {"key": "yellow_cards", "label": "Yellow cards", "codes": ["yellow-card"]},
    {"key": "red_cards", "label": "Red cards", "codes": ["red-card", "second-yellow"]},
]


def _stats_columns(competition) -> list[dict]:
    configured = list((competition.settings_json or {}).get("player_stats") or [])
    if configured:
        return configured
    codes = {
        item.get("key") or item.get("code")
        for item in ((competition.settings_json or {}).get("score_types") or [])
        if isinstance(item, dict)
    }
    if not codes:
        codes = set(competition.scoring_categories.values_list("code", flat=True))
    return [
        column
        for column in DEFAULT_EVENT_COLUMNS
        if any(code in codes for code in column["codes"])
    ]


def player_stats(competition, stage=None) -> dict:
    """Totals per player from counted match events (default: current stage)."""

    from .counted import counted_statuses

    columns = _stats_columns(competition)
    statuses = counted_statuses(competition)
    rows: dict = {}

    def row_for(*, member: RosterMember | None = None, user_id=None, name="", team="") -> dict:
        key = str(member.id) if member is not None else f"user:{user_id}:{name}"
        return rows.setdefault(
            key,
            {
                "player_id": str(member.id) if member is not None else None,
                "user_id": str(user_id or (member.user_id if member else "") or "") or None,
                "name": name or (member.name if member else ""),
                "team": team or (member.participant.name if member else ""),
                "values": defaultdict(Decimal),
            },
        )

    codes = {code for column in columns for code in column.get("codes") or []}
    if codes:
        events = ScoreEvent.objects.filter(
            fixture__competition=competition,
            fixture__status__in=statuses,
            scoring_category__code__in=list(codes),
        ).select_related(
            "player__participant", "player_user", "scoring_category", "side__participant"
        )
        if stage is not None:
            events = events.filter(fixture__stage=stage)
        for event in events:
            member = event.player
            team = event.team_name or (
                event.side.participant.name if event.side_id else ""
            )
            name = event.player_name or (member.name if member else "")
            user_id = event.player_user_id or (member.user_id if member else None)
            if member is None and not user_id and not name:
                continue
            bucket = row_for(member=member, user_id=user_id, name=name, team=team)
            for column in columns:
                if event.scoring_category.code in (column.get("codes") or []):
                    bucket["values"][column["key"]] += Decimal(event.quantity)

    awards = {column["award"]: column["key"] for column in columns if column.get("award")}
    if awards:
        award_qs = FixtureAward.objects.filter(
            fixture__competition=competition,
            fixture__status__in=statuses,
            key__in=list(awards),
            player__isnull=False,
        ).select_related("player__participant")
        if stage is not None:
            award_qs = award_qs.filter(fixture__stage=stage)
        for award in award_qs:
            row_for(member=award.player)["values"][awards[award.key]] += 1

    ordered = sorted(
        rows.values(),
        key=lambda row: tuple(-row["values"].get(column["key"], 0) for column in columns)
        + (row["name"].lower(),),
    )
    return {
        "columns": [{"key": column["key"], "label": column["label"]} for column in columns],
        "rows": [
            {
                **{k: v for k, v in row.items() if k != "values"},
                "values": {
                    column["key"]: format(
                        row["values"].get(column["key"], Decimal(0)).normalize(), "f"
                    )
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
        from apps.competitions.models import Stage

        from .counted import current_stage

        competition = get_object_or_404(visible_competitions(request.user), pk=competition_pk)
        stage_param = request.query_params.get("stage")
        if stage_param == "all":
            stage = None
        elif stage_param:
            stage = get_object_or_404(Stage, pk=stage_param, competition=competition)
        else:
            stage = current_stage(competition)
        return Response(player_stats(competition, stage))
