"""Games API: catalogue, events, NOCs, athletes, entries, officials and medals."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.presets import PRESETS

from . import experience, reports, services
from .models import (
    NOC,
    Athlete,
    Entry,
    Games,
    GamesEvent,
    GamesFollow,
    GamesOfficial,
    GamesRecord,
    MedalChange,
)

User = get_user_model()
TAG = ["Games"]


def visible_games(user):
    games = Games.objects.select_related("owner")
    if not user or not user.is_authenticated:
        return games.filter(is_private=False)
    return games.filter(Q(is_private=False) | Q(owner=user) | Q(officials__user=user)).distinct()


def _games(request: Request, pk) -> Games:
    return get_object_or_404(visible_games(request.user), pk=pk)


def _assert_owner(games: Games, user) -> None:
    if games.owner_id != getattr(user, "id", None):
        raise PermissionDenied("Only the Games organiser can do that.")


class GamesSerializer(serializers.ModelSerializer):
    can_manage = serializers.SerializerMethodField()
    event_count = serializers.SerializerMethodField()
    noc_count = serializers.SerializerMethodField()

    class Meta:
        model = Games
        fields = [
            "id",
            "name",
            "edition",
            "kind",
            "host",
            "starts_on",
            "ends_on",
            "logo_url",
            "medal_table_ranking",
            "status",
            "is_private",
            "team_label",
            "placing_points",
            "can_manage",
            "event_count",
            "noc_count",
            "created_at",
        ]
        read_only_fields = ["id", "status", "can_manage", "event_count", "noc_count", "created_at"]

    def get_can_manage(self, obj: Games) -> bool:
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)

    def get_event_count(self, obj: Games) -> int:
        return obj.events.count()

    def get_noc_count(self, obj: Games) -> int:
        return obj.nocs.count()

    def validate_placing_points(self, value):
        if not isinstance(value, list) or len(value) > 20:
            raise ValidationError("Give up to 20 points values, best place first.")
        cleaned = []
        for item in value:
            try:
                number = float(item)
            except (TypeError, ValueError) as error:
                raise ValidationError("Placing points must be numbers, e.g. [5, 3, 1].") from error
            if number < 0:
                raise ValidationError("Placing points cannot be negative.")
            cleaned.append(int(number) if number.is_integer() else number)
        return cleaned

    def validate(self, attrs: dict) -> dict:
        if self.instance is not None and "medal_table_ranking" in attrs:
            if attrs["medal_table_ranking"] != self.instance.medal_table_ranking:
                raise ValidationError(
                    {
                        "medal_table_ranking": (
                            "The medal-table ranking is locked once the Games is created."
                        )
                    }
                )
        starts, ends = attrs.get("starts_on"), attrs.get("ends_on")
        if starts and ends and ends < starts:
            raise ValidationError({"ends_on": "The Games end before they start."})
        return attrs


class GamesListView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(tags=TAG, summary="Games I can see", responses=GamesSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(
            GamesSerializer(
                visible_games(request.user), many=True, context={"request": request}
            ).data
        )

    @extend_schema(
        tags=TAG,
        summary="Create a Games",
        request=GamesSerializer,
        responses={201: GamesSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = GamesSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        games = serializer.save(owner=request.user)
        return Response(
            GamesSerializer(games, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class GamesDetailView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(tags=TAG, summary="A Games", responses=GamesSerializer)
    def get(self, request: Request, pk) -> Response:
        return Response(GamesSerializer(_games(request, pk), context={"request": request}).data)

    @extend_schema(
        tags=TAG,
        summary="Edit a Games (ranking stays locked)",
        request=GamesSerializer,
        responses=GamesSerializer,
    )
    def patch(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        _assert_owner(games, request.user)
        serializer = GamesSerializer(
            games, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CatalogView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=TAG,
        summary="The Olympic catalogue: sports, disciplines and events",
        parameters=[
            OpenApiParameter("season", str, description="summer | winter"),
            OpenApiParameter("games", str, description="Mark events already added to this Games."),
        ],
        responses=dict,
    )
    def get(self, request: Request) -> Response:
        games = None
        if request.query_params.get("games"):
            games = visible_games(request.user).filter(pk=request.query_params["games"]).first()
        return Response(services.catalog_payload(games, request.query_params.get("season") or None))


def _event_row(event: GamesEvent) -> dict:
    return {
        "id": str(event.id),
        "sport_key": event.sport_key,
        "sport": event.sport_label,
        "discipline": event.discipline,
        "name": event.name,
        "gender": event.gender,
        "kind": event.kind,
        "venue": event.venue,
        "scheduled_at": event.scheduled_at,
        "preset_key": event.preset_key,
        "round_format": event.round_format,
        "medal_type": event.medal_type,
        "custom": event.custom,
        "status": event.status,
        "competition_id": str(event.competition_id),
        "entries": event.entries.count(),
    }


class GamesSportsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Add sports and events from the catalogue",
        description=(
            "Body: {events: [keys]} or {sports: [sport keys]} or "
            "{season: 'summer'|'winter'|'all'}. "
            "Events whose locked preset is not built yet are reported as unavailable."
        ),
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        _assert_owner(games, request.user)
        keys = list(request.data.get("events") or [])
        if request.data.get("sports"):
            keys += services.keys_for(sports=list(request.data["sports"]))
        season = request.data.get("season")
        if season in {"summer", "winter"}:
            keys += services.keys_for(season=season)
        elif season == "all":
            keys += services.keys_for()
        if not keys:
            raise ValidationError({"events": "Choose at least one sport or event."})
        result = services.add_catalog_events(games, list(dict.fromkeys(keys)))
        return Response(
            {
                "created": [_event_row(event) for event in result["created"]],
                "skipped": result["skipped"],
                "unavailable": result["unavailable"],
            },
            status=status.HTTP_201_CREATED,
        )


class GamesEventsView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(tags=TAG, summary="The Games' events", responses=dict)
    def get(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        events = games.events.all()
        if sport := request.query_params.get("sport"):
            events = events.filter(sport_key=sport)
        return Response([_event_row(event) for event in events])

    @extend_schema(
        tags=TAG,
        summary="Add a custom (non-Olympic) event from any available preset",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        _assert_owner(games, request.user)
        name = str(request.data.get("name") or "").strip()
        sport_label = str(request.data.get("sport") or "").strip()
        if not name or not sport_label:
            raise ValidationError("Give the sport and the event name.")
        event = services.add_custom_event(
            games,
            sport_label=sport_label,
            name=name,
            preset_key=str(request.data.get("preset") or ""),
            gender=request.data.get("gender"),
            kind=request.data.get("kind"),
            medal_type=request.data.get("medal_type"),
            round_format=request.data.get("round_format"),
        )
        return Response(_event_row(event), status=status.HTTP_201_CREATED)


def _event(request: Request, pk, event_id) -> GamesEvent:
    games = _games(request, pk)
    return get_object_or_404(
        GamesEvent.objects.select_related("games", "competition"), pk=event_id, games=games
    )


def _can_add_records(event: GamesEvent, user) -> bool:
    from apps.results.services import is_official

    if not getattr(user, "is_authenticated", False):
        return False
    return (
        event.games.owner_id == user.id
        or GamesOfficial.objects.filter(games=event.games, user=user).exists()
        or is_official(event.competition, user)
    )


def _entry_row(entry: Entry) -> dict:
    return {
        "id": str(entry.id),
        "participant_id": str(entry.participant_id),
        "name": entry.participant.name,
        "noc": entry.noc.code,
        "noc_id": str(entry.noc_id),
        "athlete_id": str(entry.athlete_id) if entry.athlete_id else None,
    }


class GamesEventDetailView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=TAG, summary="An event: entries, fixtures, medals and the medal log", responses=dict
    )
    def get(self, request: Request, pk, event_id) -> Response:
        event = _event(request, pk, event_id)
        services.sync_medals(event)
        fixtures = event.competition.fixtures.prefetch_related("sides__participant").order_by(
            "round_number", "scheduled_at", "created_at"
        )
        return Response(
            {
                **_event_row(event),
                "games_id": str(event.games_id),
                "preset_label": (PRESETS.get(event.preset_key) or {}).get(
                    "label", event.preset_key
                ),
                "governing_body": (event.competition.settings_json or {}).get("governing_body", ""),
                "rulebook": (event.competition.settings_json or {}).get("rulebook", ""),
                "locked": bool((event.competition.settings_json or {}).get("locked")),
                "result_type": (event.competition.settings_json or {}).get("result_type"),
                "format": event.competition.format,
                "final_fixture": str(event.final_fixture_id) if event.final_fixture_id else None,
                "bronze_fixture": str(event.bronze_fixture_id) if event.bronze_fixture_id else None,
                "entries": [
                    _entry_row(entry)
                    for entry in event.entries.select_related("participant", "noc").order_by(
                        "noc__code"
                    )
                ],
                "fixtures": [
                    {
                        "id": str(fixture.id),
                        "label": fixture.label,
                        "round": fixture.round_number,
                        "status": fixture.status,
                        "scheduled_at": fixture.scheduled_at,
                        "sides": [
                            {
                                "name": side.participant.name,
                                "score": str(side.score),
                                "outcome": side.outcome,
                            }
                            for side in fixture.sides.all()
                        ],
                    }
                    for fixture in fixtures
                ],
                "medals": services._medal_rows(event),
                "qualification_rule": event.qualification_rule,
                "qualification_mark": event.qualification_mark,
                "rounds": experience.event_rounds(event),
                "records": [
                    experience.record_row(row)
                    for row in event.records.select_related("event", "noc")
                ],
                "can_add_records": _can_add_records(event, request.user),
                "medal_log": [
                    {
                        "reason": row.reason,
                        "before": row.before,
                        "after": row.after,
                        "created_at": row.created_at,
                    }
                    for row in MedalChange.objects.filter(event=event)[:20]
                ],
                "can_manage": event.games.owner_id == request.user.id,
            }
        )

    @extend_schema(
        tags=TAG,
        summary="Edit an event's venue, time, or deciding fixtures",
        request=dict,
        responses=dict,
    )
    def patch(self, request: Request, pk, event_id) -> Response:
        event = _event(request, pk, event_id)
        _assert_owner(event.games, request.user)
        for field, limit in (
            ("venue", 160),
            ("qualification_rule", 240),
            ("qualification_mark", 40),
        ):
            if field in request.data:
                setattr(event, field, str(request.data[field] or "")[:limit])
        if "scheduled_at" in request.data:
            event.scheduled_at = request.data["scheduled_at"] or None
        for field in ("final_fixture", "bronze_fixture"):
            if field in request.data:
                value = request.data[field]
                if value and not event.competition.fixtures.filter(pk=value).exists():
                    raise ValidationError({field: "That fixture is not part of this event."})
                setattr(event, f"{field}_id", value or None)
        event.save()
        services.sync_medals(event, actor=request.user)
        return self.get(request, pk, event_id)

    @extend_schema(
        tags=TAG, summary="Remove an event and its competition", request=None, responses={204: None}
    )
    def delete(self, request: Request, pk, event_id) -> Response:
        event = _event(request, pk, event_id)
        _assert_owner(event.games, request.user)
        if event.medals.exists():
            raise ValidationError("Medals were awarded in this event; it cannot be removed.")
        services.remove_event(event)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventEntriesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Enter an NOC (team event) or an athlete (individual)",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, pk, event_id) -> Response:
        event = _event(request, pk, event_id)
        _assert_owner(event.games, request.user)
        noc = get_object_or_404(NOC, pk=request.data.get("noc"), games=event.games)
        athlete = None
        if request.data.get("athlete"):
            athlete = get_object_or_404(Athlete, pk=request.data["athlete"], games=event.games)
        entry = services.add_entry(event, noc, athlete)
        return Response(_entry_row(entry), status=status.HTTP_201_CREATED)


class BronzeMatchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Create the bronze-medal match between the losing semi-finalists",
        request=None,
        responses=dict,
    )
    def post(self, request: Request, pk, event_id) -> Response:
        from apps.fixtures.models import Fixture, FixtureSide

        event = _event(request, pk, event_id)
        _assert_owner(event.games, request.user)
        if event.medal_type != GamesEvent.MedalType.BRONZE_MATCH:
            raise ValidationError("This event does not play a bronze-medal match.")
        if event.bronze_fixture_id:
            raise ValidationError("The bronze-medal match already exists.")
        bracket = event.competition.fixtures.filter(round_number__isnull=False)
        last_round = (
            bracket.order_by("-round_number").values_list("round_number", flat=True).first()
        )
        if last_round is None:
            raise ValidationError("Play the bracket first.")
        # Once the final exists it is the only match in the last round; the
        # semi-finals are then the round before it.
        semi_round = (
            last_round - 1 if bracket.filter(round_number=last_round).count() == 1 else last_round
        )
        semis = list(bracket.filter(round_number=semi_round))
        losers = [
            side.participant
            for fixture in semis
            if fixture.status in {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}
            for side in fixture.sides.all()
            if side.outcome == FixtureSide.Outcome.LOSS
        ]
        if len(losers) != 2:
            raise ValidationError("Finish both semi-finals first.")
        fixture = Fixture.objects.create(competition=event.competition, label="Bronze medal match")
        FixtureSide.objects.bulk_create(
            [
                FixtureSide(fixture=fixture, participant=losers[0], position=0, is_home=True),
                FixtureSide(fixture=fixture, participant=losers[1], position=1),
            ]
        )
        event.bronze_fixture = fixture
        event.save(update_fields=["bronze_fixture", "updated_at"])
        return Response({"fixture_id": str(fixture.id)}, status=status.HTTP_201_CREATED)


class NOCSerializer(serializers.ModelSerializer):
    class Meta:
        model = NOC
        fields = ["id", "name", "code", "flag_url", "colour"]
        read_only_fields = ["id"]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Use a three-letter code, e.g. RSA.")
        games = self.context["games"]
        clash = NOC.objects.filter(games=games, code=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("Another NOC in this Games already uses that code.")
        return value


class NOCListView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=TAG, summary="NOCs (or houses, schools, provinces)", responses=NOCSerializer(many=True)
    )
    def get(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        return Response(NOCSerializer(games.nocs.all(), many=True).data)

    @extend_schema(
        tags=TAG, summary="Add an NOC", request=NOCSerializer, responses={201: NOCSerializer}
    )
    def post(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        _assert_owner(games, request.user)
        serializer = NOCSerializer(data=request.data, context={"games": games})
        serializer.is_valid(raise_exception=True)
        noc = serializer.save(games=games)
        return Response(NOCSerializer(noc).data, status=status.HTTP_201_CREATED)


class NOCDetailView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=TAG, summary="An NOC: athletes, entries and medals by sport", responses=dict
    )
    def get(self, request: Request, pk, noc_id) -> Response:
        games = _games(request, pk)
        noc = get_object_or_404(NOC, pk=noc_id, games=games)
        return Response(experience.noc_page(noc))

    @extend_schema(tags=TAG, summary="Edit an NOC", request=NOCSerializer, responses=NOCSerializer)
    def patch(self, request: Request, pk, noc_id) -> Response:
        games = _games(request, pk)
        _assert_owner(games, request.user)
        noc = get_object_or_404(NOC, pk=noc_id, games=games)
        serializer = NOCSerializer(noc, data=request.data, partial=True, context={"games": games})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AthleteListView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(tags=TAG, summary="Athletes", responses=dict)
    def get(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        return Response(
            [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "noc": row.noc.code,
                    "noc_id": str(row.noc_id),
                }
                for row in games.athletes.select_related("noc")
            ]
        )

    @extend_schema(
        tags=TAG, summary="Add an athlete to an NOC", request=dict, responses={201: dict}
    )
    def post(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        _assert_owner(games, request.user)
        noc = get_object_or_404(NOC, pk=request.data.get("noc"), games=games)
        name = str(request.data.get("name") or "").strip()
        if not name:
            raise ValidationError({"name": "Give the athlete's name."})
        user = None
        if request.data.get("user"):
            user = get_object_or_404(User, pk=request.data["user"], is_active=True)
            if Athlete.objects.filter(games=games, user=user).exists():
                raise ValidationError(
                    {"user": "That profile already competes for an NOC in this Games."}
                )
        athlete = Athlete.objects.create(games=games, noc=noc, name=name[:160], user=user)
        return Response(
            {"id": str(athlete.id), "name": athlete.name, "noc": noc.code, "noc_id": str(noc.id)},
            status=status.HTTP_201_CREATED,
        )


class MedalsView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=TAG, summary="Medal table, medals by sport and the latest medals", responses=dict
    )
    def get(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        by_sport: dict = defaultdict(
            lambda: defaultdict(lambda: {"gold": 0, "silver": 0, "bronze": 0})
        )
        from .models import Medal

        for medal in Medal.objects.filter(event__games=games).select_related("event", "noc"):
            by_sport[medal.event.sport_label][medal.noc.code][medal.medal] += 1
        return Response(
            {
                "ranking": games.medal_table_ranking,
                "table": services.medal_table(games),
                "by_sport": [
                    {
                        "sport": sport,
                        "nocs": [{"code": code, **counts} for code, counts in sorted(rows.items())],
                    }
                    for sport, rows in sorted(by_sport.items())
                ],
                "feed": services.medal_feed(games),
                "points_table": experience.points_table(games) if games.placing_points else [],
            }
        )


class ScheduleView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(tags=TAG, summary="Events by day and venue", responses=dict)
    def get(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        days: dict = defaultdict(list)
        for event in games.events.order_by("scheduled_at", "venue", "sport_label"):
            day = event.scheduled_at.date().isoformat() if event.scheduled_at else "unscheduled"
            days[day].append(_event_row(event))
        return Response([{"day": day, "events": rows} for day, rows in days.items()])


class GamesOfficialsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Technical delegates for the whole Games", responses=dict)
    def get(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        return Response(
            [
                {
                    "id": str(row.id),
                    "user_id": str(row.user_id),
                    "name": row.user.get_full_name() or row.user.display_name,
                }
                for row in GamesOfficial.objects.filter(games=games).select_related("user")
            ]
        )

    @extend_schema(
        tags=TAG,
        summary="Appoint a technical delegate to every event",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        _assert_owner(games, request.user)
        person = get_object_or_404(User, pk=request.data.get("user"), is_active=True)
        GamesOfficial.objects.get_or_create(games=games, user=person)
        for event in games.events.select_related("competition"):
            services._sync_officials(games, event.competition)
        return self.get(request, pk)


class OverviewView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=TAG,
        summary="Opening screen: countdown, today's schedule, live events, medals",
        responses=dict,
    )
    def get(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        return Response(
            {
                **GamesSerializer(games, context={"request": request}).data,
                **experience.overview(games),
                "following": [
                    experience.follow_row(row)
                    for row in GamesFollow.objects.filter(games=games, user_id=request.user.id)
                ]
                if request.user.is_authenticated
                else [],
            }
        )


class AthleteDetailView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=TAG,
        summary="An athlete: events, results, personal bests, medals and records",
        responses=dict,
    )
    def get(self, request: Request, pk, athlete_id) -> Response:
        games = _games(request, pk)
        athlete = get_object_or_404(
            Athlete.objects.select_related("noc"), pk=athlete_id, games=games
        )
        return Response(
            {
                **experience.athlete_page(athlete, request.user),
                "can_manage": games.owner_id == request.user.id,
            }
        )

    @extend_schema(
        tags=TAG, summary="Edit an athlete's name or personal bests", request=dict, responses=dict
    )
    def patch(self, request: Request, pk, athlete_id) -> Response:
        games = _games(request, pk)
        _assert_owner(games, request.user)
        athlete = get_object_or_404(Athlete, pk=athlete_id, games=games)
        if "name" in request.data:
            name = str(request.data["name"] or "").strip()
            if not name:
                raise ValidationError({"name": "Give the athlete's name."})
            athlete.name = name[:160]
        if "personal_bests" in request.data:
            rows = request.data["personal_bests"]
            if not isinstance(rows, list) or len(rows) > 30:
                raise ValidationError({"personal_bests": "Give a list of up to 30 marks."})
            cleaned = []
            for row in rows:
                if not isinstance(row, dict) or not row.get("event") or not row.get("mark"):
                    raise ValidationError(
                        {"personal_bests": "Each best needs an event and a mark."}
                    )
                cleaned.append(
                    {
                        "event": str(row["event"])[:120],
                        "mark": str(row["mark"])[:40],
                        "date": str(row.get("date") or "")[:10],
                    }
                )
            athlete.personal_bests = cleaned
        athlete.save()
        return self.get(request, pk, athlete_id)


class RecordsView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(tags=TAG, summary="Records set at the Games", responses=dict)
    def get(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        rows = games.records.select_related("event", "noc")
        if scope := request.query_params.get("scope"):
            rows = rows.filter(scope=scope)
        return Response([experience.record_row(row) for row in rows])


class EventRecordsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=TAG,
        summary="Record a Games, national or world record set in this event",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, pk, event_id) -> Response:
        event = _event(request, pk, event_id)
        if not _can_add_records(event, request.user):
            raise PermissionDenied("Only the organiser or the event's officials record records.")
        record = experience.add_record(event, request.data, request.user)
        return Response(experience.record_row(record), status=status.HTTP_201_CREATED)


class RecordDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Remove a record entered by mistake", responses={204: None})
    def delete(self, request: Request, pk, record_id) -> Response:
        games = _games(request, pk)
        record = get_object_or_404(GamesRecord, pk=record_id, games=games)
        if not _can_add_records(record.event, request.user):
            raise PermissionDenied("Only the organiser or the event's officials remove records.")
        record.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="What I follow in this Games", responses=dict)
    def get(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        return Response(
            [
                experience.follow_row(row)
                for row in GamesFollow.objects.filter(
                    games=games, user=request.user
                ).select_related("noc", "athlete", "games")
            ]
        )

    @extend_schema(
        tags=TAG,
        summary="Follow an NOC, a sport or an athlete for start-time and result alerts",
        request=dict,
        responses={201: dict},
    )
    def post(self, request: Request, pk) -> Response:
        games = _games(request, pk)
        follow = experience.add_follow(games, request.user, request.data)
        return Response(experience.follow_row(follow), status=status.HTTP_201_CREATED)


class FollowDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=TAG, summary="Stop following", responses={204: None})
    def delete(self, request: Request, pk, follow_id) -> Response:
        games = _games(request, pk)
        get_object_or_404(GamesFollow, pk=follow_id, games=games, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=TAG,
        summary="A report: medal-table, results-book, noc-summary or daily",
        parameters=[
            OpenApiParameter("export", str, description="csv for a download"),
            OpenApiParameter("sport", str, description="results-book: one sport key"),
            OpenApiParameter("noc", str, description="noc-summary: the NOC id"),
            OpenApiParameter("date", str, description="daily: YYYY-MM-DD (default today)"),
        ],
        responses=dict,
    )
    def get(self, request: Request, pk, kind: str) -> Response:
        games = _games(request, pk)
        report = reports.build(games, kind, request.query_params)
        if request.query_params.get("export") == "csv":
            response = HttpResponse(reports.to_csv(report), content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{games.name[:60]} {kind}.csv"'
            return response
        return Response(report)
