"""Match-day paperwork: team sheets, substitutions and the post-match report.

The preset's ``team_sheet`` names how many start, how big the bench may be, how
many substitutions are allowed and which formations exist. Team competitions
without one still get a free-form sheet. Nothing here names a sport.
"""

from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.competitions.models import RosterMember
from apps.competitions.views import visible_competitions
from apps.core.bus import competition_room, fixture_room, publish_event
from apps.core.permissions import Role, has_at_least

from .awards import _award_rows
from .models import (
    Fixture,
    FixtureLineup,
    FixtureSide,
    LineupEntry,
    MatchReport,
    PlayerAppearance,
    PlayerMatchRating,
    ScoreEvent,
    Substitution,
)

TAG = ["Match day"]
FREE_FORM = {
    "starters": None,
    "bench_max": None,
    "max_substitutions": None,
    "rolling_substitutions": False,
    "keeper": "",
    "lines": [],
    "formations": [],
}
FINISHED = {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}
BEFORE_KICKOFF = {Fixture.Status.SCHEDULED, Fixture.Status.POSTPONED}


def team_sheet_config(competition) -> dict | None:
    """The competition's team sheet rules, or None where entrants are not teams."""

    from apps.competitions.presets import PRESETS

    settings = competition.settings_json or {}
    config = settings.get("team_sheet") or (PRESETS.get(settings.get("preset") or "") or {}).get(
        "team_sheet"
    )
    if config:
        return {**FREE_FORM, **config}
    if settings.get("participant_type", "team") != "team":
        return None
    if settings.get("contest_type", "head_to_head") != "head_to_head":
        return None
    return dict(FREE_FORM)


DEFAULT_SHEET_MINIMUM = 11


def team_sheet_minimum(config: dict) -> int:
    """How many named starters a side must list before the game can start."""

    starters = config.get("starters")
    try:
        return int(starters) if starters else DEFAULT_SHEET_MINIMUM
    except (TypeError, ValueError):
        return DEFAULT_SHEET_MINIMUM


def team_sheet_kickoff_problems(fixture) -> list[str]:
    """Team-sheet gaps that still block kickoff. Empty when sheets do not apply."""

    config = team_sheet_config(fixture.competition)
    if config is None:
        return []
    needed = team_sheet_minimum(config)
    problems = []
    for side in fixture.sides.all():
        name = side.participant.name
        try:
            lineup = side.lineup
        except ObjectDoesNotExist:
            problems.append(f"Submit {name}'s team sheet before kickoff.")
            continue
        starters = sum(1 for entry in lineup.entries.all() if entry.role == LineupEntry.Role.STARTER)
        if starters < needed:
            problems.append(f"{name}'s team sheet needs at least {needed} named players.")
    return problems


def formation_slots(formation: str, config: dict) -> list[dict]:
    """Starting positions for a formation such as "4-3-3", keeper first, back to front."""

    if not formation:
        return []
    try:
        rows = [int(part) for part in formation.split("-") if part.strip()]
    except ValueError as exc:
        raise ValidationError({"formation": "Write the formation as numbers, e.g. 4-4-2."}) from exc
    if not rows or any(count < 1 for count in rows):
        raise ValidationError({"formation": "Each line needs at least one player."})

    keeper = config.get("keeper") or ""
    starters = config.get("starters")
    total = sum(rows) + (1 if keeper else 0)
    if starters and total != starters:
        raise ValidationError({"formation": f"A formation must place {starters} starters."})

    lines = list(config.get("lines") or [])
    slots: list[dict] = []
    if keeper:
        slots.append({"index": 0, "row": 0, "column": 0, "columns": 1, "label": keeper})
    for row_index, count in enumerate(rows):
        if not lines:
            label = ""
        elif row_index == 0:
            label = lines[0]
        elif row_index == len(rows) - 1:
            label = lines[-1]
        else:
            label = lines[min(1, len(lines) - 1)] if len(lines) > 2 else lines[0]
        for column in range(count):
            slots.append(
                {
                    "index": len(slots),
                    "row": row_index + (1 if keeper else 0),
                    "column": column,
                    "columns": count,
                    "label": label,
                }
            )
    return slots


def can_manage_sheet(fixture: Fixture, side: FixtureSide, user) -> bool:
    """Admins always; before kickoff also the team's manager and the match's scorers."""

    from .views import user_can_score_fixture

    if not getattr(user, "is_authenticated", False):
        return False
    if fixture.status == Fixture.Status.CANCELLED:
        return False
    if has_at_least(fixture.competition, user, Role.ADMIN):
        return True
    if fixture.status not in BEFORE_KICKOFF:
        return False
    if side.participant.managed_by_id == user.id:
        return True
    return user_can_score_fixture(fixture, user)


def can_substitute(fixture: Fixture, user) -> bool:
    from apps.results.services import can_record

    if not getattr(user, "is_authenticated", False):
        return False
    return can_record(fixture, user)


def can_write_report(fixture: Fixture, user) -> bool:
    from apps.results.services import can_decide

    return can_substitute(fixture, user) or (
        getattr(user, "is_authenticated", False) and can_decide(fixture.competition, user)
    )


def _member(member: RosterMember | None, number=None) -> dict | None:
    if member is None:
        return None
    return {
        "player_id": str(member.id),
        "user_id": str(member.user_id) if member.user_id else None,
        "name": member.name,
        "number": number if number is not None else member.number,
    }


def _field_state(
    lineup: FixtureLineup | None, subs: list[Substitution], sent_off: set | None = None
) -> tuple[set, set, set]:
    """Who is on, who can still come on, and who has gone off, after these substitutions."""

    if lineup is None:
        return set(), set(), set()
    entries = list(lineup.entries.all())
    on = {entry.player_id for entry in entries if entry.role == LineupEntry.Role.STARTER}
    bench = {entry.player_id for entry in entries if entry.role == LineupEntry.Role.BENCH}
    off: set = set()
    for sub in subs:
        on.discard(sub.player_off_id)
        off.add(sub.player_off_id)
        bench.discard(sub.player_on_id)
        on.add(sub.player_on_id)
    for player_id in sent_off or ():
        if player_id in on or player_id in bench:
            on.discard(player_id)
            bench.discard(player_id)
            off.add(player_id)
    return on, bench, off


def _minutes_map(fixture: Fixture) -> dict:
    return {
        row.player_id: row.minutes
        for row in PlayerAppearance.objects.filter(fixture=fixture)
        if row.minutes is not None
    }


def _ratings_map(fixture: Fixture) -> dict:
    return {row.player_id: format(row.rating, "f") for row in PlayerMatchRating.objects.filter(fixture=fixture)}


def _side_payload(
    fixture: Fixture, side: FixtureSide, config: dict, user, subs, minutes: dict, ratings: dict
) -> dict:
    lineup = getattr(side, "lineup", None)
    side_subs = [sub for sub in subs if sub.side_id == side.id]
    from .cards import sent_off_ids

    dismissed = sent_off_ids(fixture)
    on, bench_left, off = _field_state(lineup, side_subs, dismissed)
    entries = list(lineup.entries.select_related("player").all()) if lineup else []
    squad = [
        {
            "player_id": str(member.id),
            "user_id": str(member.user_id) if member.user_id else None,
            "name": member.name,
            "number": member.number,
            "position": member.position,
        }
        for member in side.participant.roster.filter(is_active=True).order_by("number", "name")
    ]

    def entry_row(entry: LineupEntry) -> dict:
        return {
            **_member(entry.player, entry.number),
            "slot": entry.slot,
            "position": entry.position,
            "on_field": entry.player_id in on,
            "subbed_off": entry.player_id in off,
            "sent_off": entry.player_id in dismissed,
            "minutes": minutes.get(entry.player_id),
            "rating": ratings.get(entry.player_id),
        }

    used = len(side_subs)
    limit = config.get("max_substitutions")
    return {
        "side_id": str(side.id),
        "participant_id": str(side.participant_id),
        "name": side.participant.name,
        "can_edit": can_manage_sheet(fixture, side, user),
        "squad": squad,
        "lineup": None
        if lineup is None
        else {
            "formation": lineup.formation,
            "slots": formation_slots(lineup.formation, config) if lineup.formation else [],
            "captain_id": str(lineup.captain_id) if lineup.captain_id else None,
            "starters": [entry_row(e) for e in entries if e.role == LineupEntry.Role.STARTER],
            "bench": [entry_row(e) for e in entries if e.role == LineupEntry.Role.BENCH],
            "updated_at": lineup.updated_at.isoformat(),
        },
        "on_field": [str(pk) for pk in on],
        "available_subs": [str(pk) for pk in bench_left],
        "substitutions_used": used,
        "substitutions_left": None if limit is None else max(0, limit - used),
    }


def _sub_row(sub: Substitution) -> dict:
    return {
        "id": str(sub.id),
        "side_id": str(sub.side_id),
        "team": sub.side.participant.name,
        "player_off": _member(sub.player_off),
        "player_on": _member(sub.player_on),
        "minute": sub.minute,
        "reason": sub.reason,
        "note": sub.note,
        "created_at": sub.created_at.isoformat(),
    }


def _subs(fixture: Fixture) -> list[Substitution]:
    return list(
        Substitution.objects.filter(fixture=fixture)
        .select_related("player_off", "player_on", "side__participant")
        .order_by("created_at")
    )


def match_day(fixture: Fixture, user) -> dict:
    config = team_sheet_config(fixture.competition)
    if config is None:
        return {"enabled": False}
    subs = _subs(fixture)
    sides = list(
        fixture.sides.select_related("participant", "lineup", "lineup__captain").order_by(
            "position"
        )
    )
    minutes = _minutes_map(fixture)
    ratings = _ratings_map(fixture)
    return {
        "enabled": True,
        "config": {**config, "min_personnel": team_sheet_minimum(config)},
        "formations": [
            {"key": key, "slots": formation_slots(key, config)}
            for key in config.get("formations") or []
        ],
        "status": fixture.status,
        "sides": [
            _side_payload(fixture, side, config, user, subs, minutes, ratings)
            for side in sides
        ],
        "substitutions": [_sub_row(sub) for sub in subs],
        "can_substitute": fixture.status in {Fixture.Status.LIVE, *FINISHED}
        and can_substitute(fixture, user),
        "reasons": [{"key": key, "label": label} for key, label in Substitution.Reason.choices],
    }


def _duration(fixture: Fixture) -> int | None:
    settings = fixture.competition.settings_json or {}
    value = fixture.duration_minutes or settings.get("time_limit_minutes")
    return int(value) if value else None


def sync_minutes(fixture: Fixture) -> None:
    """Write each named player's minutes from the team sheet and the substitutions."""

    duration = _duration(fixture)
    if not duration:
        return
    subs = _subs(fixture)
    for lineup in FixtureLineup.objects.filter(fixture=fixture).prefetch_related("entries"):
        entered = {
            entry.player_id: 0
            for entry in lineup.entries.all()
            if entry.role == LineupEntry.Role.STARTER
        }
        left: dict = {}
        unknown: set = set()
        for sub in subs:
            if sub.side_id != lineup.side_id:
                continue
            if sub.minute is None:
                unknown.update({sub.player_off_id, sub.player_on_id})
                entered.setdefault(sub.player_on_id, 0)
                continue
            left[sub.player_off_id] = min(sub.minute, duration)
            entered[sub.player_on_id] = min(sub.minute, duration)
        squad = set(
            RosterMember.objects.filter(participant_id=lineup.side.participant_id).values_list(
                "id", flat=True
            )
        )
        PlayerAppearance.objects.filter(fixture=fixture, player_id__in=squad - set(entered)).delete()
        for player_id, start in entered.items():
            if player_id in unknown:
                continue
            PlayerAppearance.objects.update_or_create(
                fixture=fixture,
                player_id=player_id,
                defaults={"minutes": max(0, left.get(player_id, duration) - start)},
            )


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


class TeamSheetsView(_FixtureView):
    @extend_schema(tags=TAG, summary="Both team sheets and the substitutions", responses=dict)
    def get(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        return Response(match_day(fixture, request.user))


class TeamSheetView(_FixtureView):
    @extend_schema(
        tags=TAG,
        summary="Save one side's team sheet",
        description=(
            "Body: {formation, captain, starters: [{player, slot, number}], "
            "bench: [{player, number}]}."
        ),
        request=dict,
        responses=dict,
    )
    def put(self, request: Request, competition_pk, fixture_pk, side_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        side = get_object_or_404(
            FixtureSide.objects.select_related("participant"), pk=side_pk, fixture=fixture
        )
        config = team_sheet_config(fixture.competition)
        if config is None:
            raise ValidationError("This competition does not use team sheets.")
        if not can_manage_sheet(fixture, side, request.user):
            if fixture.status in BEFORE_KICKOFF:
                raise PermissionDenied("Only the team's manager, the referee or an admin picks the team.")
            raise PermissionDenied("The team sheet is locked after kickoff. Record substitutions instead.")

        formation = str(request.data.get("formation") or "").strip()[:40]
        if config.get("formations") and formation and formation not in config["formations"]:
            raise ValidationError({"formation": "Choose one of this competition's formations."})
        slots = formation_slots(formation, config)
        starters = list(request.data.get("starters") or [])
        bench = list(request.data.get("bench") or [])

        squad = {
            str(member.id): member
            for member in RosterMember.objects.filter(participant=side.participant, is_active=True)
        }
        seen: set[str] = set()

        def clean(row, role: str) -> dict:
            player_id = str((row or {}).get("player") or "")
            if player_id not in squad:
                raise ValidationError({role: "Pick players from this team's squad."})
            if player_id in seen:
                raise ValidationError({role: f"{squad[player_id].name} is named twice."})
            seen.add(player_id)
            number = (row or {}).get("number")
            if number in ("", None):
                number = None
            else:
                try:
                    number = int(number)
                except (TypeError, ValueError) as exc:
                    raise ValidationError({role: "Shirt numbers are whole numbers."}) from exc
            return {"player": squad[player_id], "number": number, "slot": (row or {}).get("slot")}

        starting = [clean(row, "starters") for row in starters]
        benched = [clean(row, "bench") for row in bench]

        needed = team_sheet_minimum(config)
        if len(starting) < needed:
            raise ValidationError({"starters": f"Name at least {needed} players on the team sheet."})
        limit = config.get("starters")
        if limit and len(starting) > limit:
            raise ValidationError({"starters": f"Name at most {limit} starters."})
        bench_max = config.get("bench_max")
        if bench_max is not None and len(benched) > bench_max:
            raise ValidationError({"bench": f"Name at most {bench_max} substitutes."})
        numbers = [row["number"] for row in starting + benched if row["number"] is not None]
        if len(numbers) != len(set(numbers)):
            raise ValidationError({"starters": "Two players have the same shirt number."})

        taken: set[int] = set()
        for row in starting:
            slot = row["slot"]
            if slot in ("", None):
                row["slot"] = None
                continue
            try:
                slot = int(slot)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"starters": "Unknown position."}) from exc
            if slots and not 0 <= slot < len(slots):
                raise ValidationError({"starters": "That position is not in the formation."})
            if slot in taken:
                raise ValidationError({"starters": "Two players are in the same position."})
            taken.add(slot)
            row["slot"] = slot

        captain_id = str(request.data.get("captain") or "")
        captain = None
        if captain_id:
            captain = next((row["player"] for row in starting if str(row["player"].id) == captain_id), None)
            if captain is None:
                raise ValidationError({"captain": "The captain must be in the starting line-up."})

        with transaction.atomic():
            lineup, _ = FixtureLineup.objects.update_or_create(
                side=side,
                defaults={
                    "fixture": fixture,
                    "formation": formation,
                    "captain": captain,
                    "submitted_by": request.user,
                },
            )
            kept = {row["player"].id for row in starting + benched}
            if Substitution.objects.filter(side=side).exclude(
                player_off_id__in=kept, player_on_id__in=kept
            ).exists():
                raise ValidationError(
                    "A substituted player is missing from the sheet. Delete that substitution first."
                )
            lineup.entries.all().delete()
            LineupEntry.objects.bulk_create(
                [
                    LineupEntry(
                        lineup=lineup,
                        player=row["player"],
                        role=LineupEntry.Role.STARTER,
                        slot=row["slot"],
                        position=slots[row["slot"]]["label"]
                        if slots and row["slot"] is not None
                        else row["player"].position[:20],
                        number=row["number"],
                        order=index,
                    )
                    for index, row in enumerate(starting)
                ]
                + [
                    LineupEntry(
                        lineup=lineup,
                        player=row["player"],
                        role=LineupEntry.Role.BENCH,
                        number=row["number"],
                        order=index,
                    )
                    for index, row in enumerate(benched)
                ]
            )
            if fixture.status not in BEFORE_KICKOFF:
                sync_minutes(fixture)
        _broadcast(fixture)
        return Response(match_day(fixture, request.user))


class SubstitutionsView(_FixtureView):
    @extend_schema(
        tags=TAG,
        summary="Record a substitution",
        description="Body: {side, player_off, player_on, minute?, reason?, note?}.",
        request=dict,
        responses=dict,
    )
    def post(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        config = team_sheet_config(fixture.competition)
        if config is None:
            raise ValidationError("This competition does not use team sheets.")
        if not can_substitute(fixture, request.user):
            raise PermissionDenied("Only the referee, a scorer or an admin records substitutions.")
        if fixture.status not in {Fixture.Status.LIVE, *FINISHED}:
            raise ValidationError("Substitutions are recorded once the match has kicked off.")

        side = get_object_or_404(
            FixtureSide.objects.select_related("participant"),
            pk=request.data.get("side"),
            fixture=fixture,
        )
        lineup = FixtureLineup.objects.filter(side=side).prefetch_related("entries").first()
        if lineup is None:
            raise ValidationError({"side": "Pick this team's sheet before recording substitutions."})

        with transaction.atomic():
            subs = list(
                Substitution.objects.select_for_update().filter(side=side).order_by("created_at")
            )
            on, bench, off = _field_state(lineup, subs)
            limit = config.get("max_substitutions")
            if limit is not None and len(subs) >= limit:
                raise ValidationError(f"{side.participant.name} have used all {limit} substitutions.")

            off_id = str(request.data.get("player_off") or "")
            on_id = str(request.data.get("player_on") or "")
            if not off_id or not on_id:
                raise ValidationError("Choose who comes off and who comes on.")
            if off_id == on_id:
                raise ValidationError("A player cannot replace themselves.")
            if off_id not in {str(pk) for pk in on}:
                raise ValidationError({"player_off": "That player is not on the field."})
            coming_on = {str(pk) for pk in bench}
            if config.get("rolling_substitutions"):
                coming_on |= {str(pk) for pk in off}
            if on_id not in coming_on:
                if on_id in {str(pk) for pk in off}:
                    raise ValidationError({"player_on": "A player taken off cannot come back on."})
                raise ValidationError({"player_on": "Choose a substitute named on the bench."})

            minute = request.data.get("minute")
            if minute in ("", None):
                minute = None
            else:
                try:
                    minute = max(0, int(minute))
                except (TypeError, ValueError) as exc:
                    raise ValidationError({"minute": "The minute is a whole number."}) from exc
            reason = request.data.get("reason") or Substitution.Reason.TACTICAL
            if reason not in Substitution.Reason.values:
                raise ValidationError({"reason": "Unknown reason."})

            Substitution.objects.create(
                fixture=fixture,
                side=side,
                player_off_id=off_id,
                player_on_id=on_id,
                minute=minute,
                reason=reason,
                note=str(request.data.get("note") or "")[:280],
                recorded_by=request.user,
            )
            sync_minutes(fixture)
        _broadcast(fixture)
        return Response(match_day(fixture, request.user), status=status.HTTP_201_CREATED)


class SubstitutionView(_FixtureView):
    @extend_schema(tags=TAG, summary="Delete a substitution recorded by mistake", responses=dict)
    def delete(self, request: Request, competition_pk, fixture_pk, sub_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        if not can_substitute(fixture, request.user):
            raise PermissionDenied("Only the referee, a scorer or an admin changes substitutions.")
        sub = get_object_or_404(Substitution, pk=sub_pk, fixture=fixture)
        later = Substitution.objects.filter(side=sub.side, created_at__gt=sub.created_at)
        if later.filter(player_off=sub.player_on).exists() or later.filter(
            player_on=sub.player_off
        ).exists():
            raise ValidationError(
                "A later substitution involves these players. Delete that one first."
            )
        with transaction.atomic():
            sub.delete()
            sync_minutes(fixture)
        _broadcast(fixture)
        return Response(match_day(fixture, request.user))


def _event_rows(fixture: Fixture) -> tuple[list[dict], list[dict], list[dict]]:
    goals, cards, other = [], [], []
    events = (
        ScoreEvent.objects.filter(fixture=fixture)
        .select_related("scoring_category", "side__participant", "player")
        .order_by("minute", "created_at")
    )
    for event in events:
        code = (event.scoring_category.code or "").lower()
        row = {
            "minute": event.minute,
            "team": event.side.participant.name,
            "player": event.player.name if event.player_id else event.player_name,
            "label": event.scoring_category.name,
            "quantity": format(event.quantity.normalize(), "f"),
            "points": format(event.points.normalize(), "f"),
        }
        if code.endswith("-card"):
            cards.append({**row, "kind": code.removesuffix("-card")})
        elif event.scoring_category.affects_score:
            goals.append(row)
        else:
            other.append(row)
    return goals, cards, other


def report_payload(fixture: Fixture, user) -> dict:
    report = MatchReport.objects.filter(fixture=fixture).select_related("written_by").first()
    day = match_day(fixture, user)
    goals, cards, other = _event_rows(fixture)
    sides = list(fixture.sides.select_related("participant").order_by("position"))
    sheets = {row["side_id"]: row for row in day.get("sides") or []}
    return {
        "fixture": {
            "id": str(fixture.id),
            "label": fixture.label,
            "competition": fixture.competition.name,
            "status": fixture.status,
            "scheduled_at": fixture.scheduled_at.isoformat() if fixture.scheduled_at else None,
            "started_at": fixture.started_at.isoformat() if fixture.started_at else None,
            "completed_at": fixture.completed_at.isoformat() if fixture.completed_at else None,
            "location": fixture.location,
            "duration_minutes": fixture.duration_minutes,
        },
        "sides": [
            {
                "side_id": str(side.id),
                "name": side.participant.name,
                "score": format(side.score.normalize(), "f"),
                "outcome": side.outcome,
                "forfeited": side.forfeited,
                "lineup": (sheets.get(str(side.id)) or {}).get("lineup"),
            }
            for side in sides
        ],
        "goals": goals,
        "cards": cards,
        "other_events": other,
        "substitutions": day.get("substitutions") or [],
        "awards": [
            {"label": row["label"], "winner": row["winner"]}
            for row in _award_rows(fixture)
            if row["winner"]
        ],
        "referees": [
            referee.user.get_full_name() or referee.user.email
            for referee in fixture.referees.select_related("user")
        ],
        "report": None
        if report is None
        else {
            "summary": report.summary,
            "attendance": report.attendance,
            "conditions": report.conditions,
            "incidents": report.incidents,
            "injuries": report.injuries,
            "written_by": (report.written_by.get_full_name() or report.written_by.email)
            if report.written_by_id
            else "",
            "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        },
        "finished": fixture.status in FINISHED,
        "can_edit": fixture.status in FINISHED and can_write_report(fixture, user),
    }


class MatchReportView(_FixtureView):
    @extend_schema(tags=TAG, summary="The post-match report", responses=dict)
    def get(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        return Response(report_payload(fixture, request.user))

    @extend_schema(
        tags=TAG,
        summary="Write the post-match report (officials)",
        description="Body: {summary, attendance?, conditions?, incidents?, injuries?}.",
        request=dict,
        responses=dict,
    )
    def put(self, request: Request, competition_pk, fixture_pk) -> Response:
        fixture = self._fixture(request, competition_pk, fixture_pk)
        if fixture.status not in FINISHED:
            raise ValidationError("The report is written after the result is in.")
        if not can_write_report(fixture, request.user):
            raise PermissionDenied("Only the match officials write the report.")

        attendance = request.data.get("attendance")
        if attendance in ("", None):
            attendance = None
        else:
            try:
                attendance = int(attendance)
            except (TypeError, ValueError) as exc:
                raise ValidationError({"attendance": "Attendance is a whole number."}) from exc
            if attendance < 0:
                raise ValidationError({"attendance": "Attendance cannot be negative."})
        summary = str(request.data.get("summary") or "").strip()
        if not summary:
            raise ValidationError({"summary": "Write a short summary of the match."})

        MatchReport.objects.update_or_create(
            fixture=fixture,
            defaults={
                "summary": summary[:5000],
                "attendance": attendance,
                "conditions": str(request.data.get("conditions") or "").strip()[:240],
                "incidents": str(request.data.get("incidents") or "").strip()[:5000],
                "injuries": str(request.data.get("injuries") or "").strip()[:5000],
                "written_by": request.user,
                "submitted_at": timezone.now(),
            },
        )
        _broadcast(fixture)
        return Response(report_payload(fixture, request.user))
