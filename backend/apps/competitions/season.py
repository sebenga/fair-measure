"""When a season is finished: mark it complete, then start the next one."""

from __future__ import annotations

from datetime import date, time

from django.db import transaction
from django.db.models import Max
from rest_framework.exceptions import ValidationError

from apps.competitions.models import Competition, Stage
from apps.competitions.presets import format_allowed
from apps.fixtures.models import Fixture
from apps.fixtures.services import ScheduleOptions, generate_knockout, generate_round_robin

OPEN = {Fixture.Status.SCHEDULED, Fixture.Status.LIVE, Fixture.Status.POSTPONED}
COUNTED = {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}


def uses_match_seasons(competition: Competition) -> bool:
    """Whether this contest runs a fixture season that can finish and restart."""

    settings = competition.settings_json or {}
    if settings.get("table_mode") == "points" or settings.get("result_type"):
        return False
    return competition.format != Competition.Format.FREEFORM


def season_is_finished(competition: Competition) -> bool:
    """True when every remaining fixture is done and at least one result exists."""

    if not uses_match_seasons(competition):
        return False
    fixtures = competition.fixtures.exclude(status=Fixture.Status.CANCELLED)
    if not fixtures.filter(status__in=COUNTED).exists():
        return False
    return not fixtures.filter(status__in=OPEN).exists()


def maybe_finish_competition(competition: Competition) -> bool:
    """Mark an active competition completed once its last fixture is done."""

    if competition.status != Competition.Status.ACTIVE:
        return False
    if not season_is_finished(competition):
        return False
    competition.status = Competition.Status.COMPLETED
    competition.save(update_fields=["status", "updated_at"])
    return True


def _next_season_name(competition: Competition) -> str:
    league_stages = competition.stages.filter(kind=Stage.Kind.LEAGUE).count()
    if league_stages:
        return f"Season {league_stages + 1}"
    return "Season 2"


def _next_knockout_name(competition: Competition) -> str:
    count = competition.stages.filter(kind=Stage.Kind.KNOCKOUT).count()
    return "Play-offs" if count == 0 else f"Knockout {count + 1}"


def _ordered_for_knockout(competition: Competition, participants: list, advance: int | None):
    """Table order for a playoff. Seed is set in memory so 1 plays last."""

    from apps.standings.services import compute_standings

    by_id = {str(person.id): person for person in participants}
    ordered = []
    for row in compute_standings(competition):
        person = by_id.pop(row.participant_id, None)
        if person is not None:
            ordered.append(person)
    ordered.extend(by_id.values())
    if advance is not None:
        if advance < 2:
            raise ValidationError("A knockout needs at least two sides.")
        if advance > len(ordered):
            raise ValidationError(f"Only {len(ordered)} sides can advance.")
        ordered = ordered[:advance]
    for index, person in enumerate(ordered, start=1):
        person.seed = index
    return ordered


@transaction.atomic
def schedule_next(
    competition: Competition,
    *,
    kind: str,
    starts_on: date,
    kickoff: time,
    weekdays: list[int] | None = None,
    minutes_between_fixtures: int = 0,
    double_round: bool = False,
    location: str = "",
    advance: int | None = None,
) -> tuple[Stage, list]:
    """Create the next season or knockout after the current one has finished."""

    if not season_is_finished(competition):
        raise ValidationError("Finish every remaining fixture before scheduling the next season.")

    from apps.competitions.serializers import squad_size_for, team_entry_mode

    participants = list(competition.participants.filter(is_active=True).order_by("seed", "name"))
    if len(participants) < 2:
        raise ValidationError("Add at least two participants before scheduling the next season.")
    if team_entry_mode(competition) in {"pick", "draft"}:
        needed = squad_size_for(competition)
        short = [
            person.name
            for person in participants
            if person.roster.filter(is_active=True).count() < needed
        ]
        if short:
            raise ValidationError(
                f"Each team needs {needed} accepted players before a schedule. Still short: {', '.join(short)}."
            )

    settings = competition.settings_json or {}
    method = "knockout" if kind == "knockout" else "round_robin"
    if kind == "season" and competition.format == Competition.Format.KNOCKOUT:
        method = "knockout"

    if method == "knockout":
        if not (
            format_allowed(settings, "knockout")
            or competition.format
            in {
                Competition.Format.LEAGUE,
                Competition.Format.GROUP_KNOCKOUT,
                Competition.Format.LADDER,
                Competition.Format.KNOCKOUT,
            }
        ):
            raise ValidationError("This competition cannot add a knockout.")
        participants = _ordered_for_knockout(competition, participants, advance)
        stage_kind = Stage.Kind.KNOCKOUT
        stage_name = _next_knockout_name(competition)
    else:
        if not (
            format_allowed(settings, "league")
            or competition.format
            in {
                Competition.Format.LEAGUE,
                Competition.Format.GROUP_KNOCKOUT,
                Competition.Format.LADDER,
            }
        ):
            raise ValidationError("This competition cannot start a league season.")
        stage_kind = Stage.Kind.LEAGUE
        stage_name = _next_season_name(competition)

    next_order = (competition.stages.aggregate(highest=Max("display_order"))["highest"] or 0) + 1
    stage = Stage.objects.create(
        competition=competition,
        name=stage_name,
        kind=stage_kind,
        display_order=next_order,
        starts_on=starts_on,
        advances_count=advance or 0,
    )
    stage.participants.set(participants)

    if method == "knockout" and competition.format == Competition.Format.LEAGUE:
        competition.format = Competition.Format.GROUP_KNOCKOUT
    if competition.status != Competition.Status.ACTIVE:
        competition.status = Competition.Status.ACTIVE
    competition.save(update_fields=["format", "status", "updated_at"])

    options = ScheduleOptions(
        starts_on=starts_on,
        weekdays=weekdays or competition.match_weekdays or [],
        kickoff=kickoff,
        minutes_between_fixtures=minutes_between_fixtures,
        double_round=double_round if method == "round_robin" else False,
        location=location,
        stage=stage,
    )
    created = (
        generate_knockout(competition, participants, options)
        if method == "knockout"
        else generate_round_robin(competition, participants, options)
    )
    return stage, created
