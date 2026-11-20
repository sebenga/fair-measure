"""Which fixtures count for the table, stats, season close and champion.

Sports with a team sheet (soccer and similar) need referee match-card sign-off:
only ``confirmed`` (and ``forfeit``) results move the table. ``completed`` means
full time has been called but the referee has not signed yet.
"""

from __future__ import annotations

from django.db.models import QuerySet

from apps.competitions.models import Competition, Stage

from .models import Fixture


def requires_match_card(competition: Competition) -> bool:
    """True when results need an accepted referee's confirm before they count.

    Association football (soccer) always uses the match card. Other sports keep
    counting ``completed`` fixtures unless the organiser opts in.
    """

    settings = competition.settings_json or {}
    if settings.get("require_match_card") is False:
        return False
    if settings.get("require_match_card") is True:
        return True
    preset = str(settings.get("preset") or "").lower()
    sport = str(getattr(competition, "sport", "") or settings.get("sport") or "").lower()
    family = str(settings.get("family") or "").lower()
    variant = str(settings.get("variant") or "").lower()
    if preset.startswith("soccer") or sport in {"soccer", "football"}:
        return True
    if family == "football" and variant in {"association", "", "11-a-side", "11_a_side"}:
        return True
    return False


def counted_statuses(competition: Competition) -> frozenset[str]:
    """Statuses that affect the league table and player stats."""

    if requires_match_card(competition):
        return frozenset({Fixture.Status.CONFIRMED, Fixture.Status.FORFEIT})
    return frozenset(
        {
            Fixture.Status.COMPLETED,
            Fixture.Status.CONFIRMED,
            Fixture.Status.FORFEIT,
        }
    )


def fixture_is_counted(fixture: Fixture) -> bool:
    return fixture.status in counted_statuses(fixture.competition)


def counted_fixtures(
    competition: Competition,
    stage: Stage | None = None,
) -> QuerySet[Fixture]:
    """Fixtures that feed standings / stats for this competition (and stage)."""

    qs = Fixture.objects.filter(
        competition=competition,
        status__in=counted_statuses(competition),
    )
    if stage is not None:
        qs = qs.filter(stage=stage)
    return qs


def current_stage(competition: Competition) -> Stage | None:
    """Latest unfinished stage, else the latest league stage (for default standings).

    Prefer a league stage over a knockout final so the table still has rows after
    a finished league+cup season.
    """

    stages = list(competition.stages.order_by("display_order", "created_at"))
    if not stages:
        return None
    from apps.competitions.models import Stage
    from apps.competitions.season import stage_is_finished

    unfinished = [stage for stage in reversed(stages) if not stage_is_finished(stage)]
    if unfinished:
        return unfinished[0]
    league = [stage for stage in reversed(stages) if stage.kind == Stage.Kind.LEAGUE]
    if league:
        return league[0]
    return stages[-1]
