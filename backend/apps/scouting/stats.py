"""Per-player match stats from the competition engine, and percentiles.

Stats follow the catalogue's match_stats definitions: a score type (summed from
the events tagged to the player), an engine value (outcomes, result marks,
profile measurements) or a formula over other stats. Rows are cached in
PlayerStatLine per sport, season and competition, plus one row per season for
all competitions together. Formulas use the season totals, so a rate is never an
average of averages.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from . import attributes, catalog
from .formulas import evaluate
from .models import PhysicalTestResult, PlayerProfile, PlayerSport, PlayerStatLine
from .services import age_group, effective_visibility

MIN_SAMPLE = 20
LOWER_RESULT_TYPES = {
    "timed_lowest",
    "multi_run_aggregate",
    "points_lowest",
    "penalty_total_lowest",
    "faults_then_time",
}
COUNTED = ("completed", "forfeit")


def _number(value) -> float | None:
    if value is None:
        return None
    return round(float(value), 3)


def season_of(fixture) -> int:
    moment = fixture.scheduled_at or fixture.completed_at or fixture.created_at
    return timezone.localtime(moment).year if moment else timezone.localdate().year


def _regulation_minutes(fixture) -> int:
    settings = fixture.competition.settings_json or {}
    return int(fixture.duration_minutes or settings.get("time_limit_minutes") or 0)


class _Totals:
    """Raw inputs for one player, sport, season and competition (or all of them)."""

    def __init__(self) -> None:
        self.matches = 0
        self.minutes = 0
        self.counts: dict[str, Decimal] = defaultdict(Decimal)
        self.points = Decimal("0")
        self.outcomes: dict[str, int] = defaultdict(int)
        self.opponent_ranks: list[int] = []
        self.marks: list[tuple] = []  # (date, value, result_type, wind)
        self.handicap = None

    def add(self, other: _Totals) -> None:
        self.matches += other.matches
        self.minutes += other.minutes
        for key, value in other.counts.items():
            self.counts[key] += value
        self.points += other.points
        for key, value in other.outcomes.items():
            self.outcomes[key] += value
        self.opponent_ranks += other.opponent_ranks
        self.marks += other.marks
        if other.handicap is not None:
            self.handicap = other.handicap


class _Shared:
    """Fixture data several players read: each league table, each fixture's sides,
    events and result, loaded once per job rather than once per player.

    A competition-wide rebuild covers hundreds of players over the same fixtures;
    without this every player recomputed the table and re-read every match.
    """

    def __init__(self) -> None:
        self.positions: dict = {}
        self.sides: dict = defaultdict(list)  # fixture id -> [(side id, participant id)]
        self.events: dict = defaultdict(list)  # fixture id -> [(side, player, code, qty, pts)]
        self.results: dict = {}  # side id -> EntryResult
        self.loaded: set = set()
        self.competitions: dict = {}

    def competition(self, competition_id):
        # Settings are large JSON; reading them once per fixture row was most of the CPU.
        if competition_id not in self.competitions:
            from apps.competitions.models import Competition

            self.competitions[competition_id] = Competition.objects.get(pk=competition_id)
        return self.competitions[competition_id]

    def load(self, fixture_ids) -> None:
        from apps.fixtures.models import FixtureSide, ScoreEvent
        from apps.results.models import EntryResult

        wanted = set(fixture_ids) - self.loaded
        if not wanted:
            return
        self.loaded |= wanted
        for fixture_id, side_id, participant_id in FixtureSide.objects.filter(
            fixture_id__in=wanted
        ).values_list("fixture_id", "id", "participant_id"):
            self.sides[fixture_id].append((side_id, participant_id))
        for row in ScoreEvent.objects.filter(fixture_id__in=wanted).values_list(
            "fixture_id",
            "side_id",
            "player_id",
            "scoring_category__code",
            "quantity",
            "scoring_category__points",
            "scoring_category__affects_score",
        ):
            fixture_id, side_id, player_id, code, quantity, points, counts = row
            scored = quantity * points if counts else Decimal("0")
            self.events[fixture_id].append((side_id, player_id, code, quantity, scored))
        for result in EntryResult.objects.filter(side__fixture_id__in=wanted):
            self.results[result.side_id] = result


def _standings_positions(competition, cache: dict) -> dict:
    if competition.id not in cache:
        from apps.standings.services import compute_standings

        try:
            rows = compute_standings(competition)
        except Exception:  # a broken table must not stop the stats
            rows = []
        cache[competition.id] = {
            str(row.participant_id): index + 1 for index, row in enumerate(rows)
        }
    return cache[competition.id]


def _collect(user, shared: _Shared | None = None) -> dict[tuple[str, int, object], _Totals]:
    """Totals keyed by (sport, season, competition id) from every counted fixture."""

    from apps.competitions.models import Participant, RosterMember
    from apps.fixtures.models import FixtureSide, PlayerAppearance, PlayerMatchRating, ScoreEvent

    shared = shared or _Shared()
    totals: dict[tuple, _Totals] = defaultdict(_Totals)
    positions_cache = shared.positions
    members = list(RosterMember.objects.filter(user=user).only("id", "participant_id"))
    member_ids = [member.id for member in members]
    individual = list(Participant.objects.filter(managed_by=user).only("id"))
    try:
        from apps.games.models import Athlete

        individual += [
            entry.participant
            for athlete in Athlete.objects.filter(user=user).prefetch_related(
                "entries__participant__competition"
            )
            for entry in athlete.entries.all()
        ]
    except ImportError:  # pragma: no cover - games is optional
        pass
    team_ids = {member.participant_id for member in members}
    own_ids = {participant.id for participant in individual}

    sides = list(
        FixtureSide.objects.filter(
            Q(participant_id__in=team_ids) | Q(participant_id__in=own_ids),
            fixture__status__in=COUNTED,
        )
        .select_related("fixture", "participant")
        .distinct()
    )
    shared.load(side.fixture_id for side in sides)
    member_set = set(member_ids)
    tagged = set(
        ScoreEvent.objects.filter(player_id__in=member_ids).values_list("fixture_id", flat=True)
    ) | set(
        PlayerMatchRating.objects.filter(player_id__in=member_ids).values_list(
            "fixture_id", flat=True
        )
    )
    minutes = {
        row.fixture_id: row.minutes
        for row in PlayerAppearance.objects.filter(player_id__in=member_ids)
    }
    tagged |= set(minutes)

    for side in sides:
        fixture = side.fixture
        competition = fixture.competition = shared.competition(fixture.competition_id)
        sport = catalog.sport_for_competition(competition.sport)
        if sport is None:
            continue
        if (
            side.participant_id in team_ids
            and side.participant_id not in own_ids
            and fixture.id not in tagged
        ):
            continue  # the team played, but this player did not appear
        row = totals[(sport, season_of(fixture), competition.id)]
        row.matches += 1
        row.minutes += minutes.get(fixture.id) or _regulation_minutes(fixture)
        if side.forfeited:
            row.outcomes["losses"] += 1
        elif side.outcome in ("win", "loss", "draw"):
            row.outcomes[{"win": "wins", "loss": "losses", "draw": "draws"}[side.outcome]] += 1
        if side.outcome in ("win", "loss", "draw") or side.forfeited:
            row.outcomes["played"] += 1
            positions = _standings_positions(competition, positions_cache)
            own = positions.get(str(side.participant_id))
            for other_id, other_participant in shared.sides.get(fixture.id, []):
                if other_id == side.id:
                    continue
                theirs = positions.get(str(other_participant))
                if theirs is None:
                    continue
                row.opponent_ranks.append(theirs)
                if own is not None and theirs < own:
                    row.outcomes["played_vs_higher"] += 1
                    if side.outcome == "win":
                        row.outcomes["wins_vs_higher"] += 1
        handicap = (side.participant.metadata or {}).get("handicap")
        if handicap is not None:
            row.handicap = Decimal(str(handicap))

        own_side = side.participant_id in own_ids
        for side_id, player_id, code, quantity, scored in shared.events.get(fixture.id, []):
            if (side_id == side.id) if own_side else (player_id in member_set):
                row.counts[code] += quantity
                row.points += scored

        result = shared.results.get(side.id)
        if result is not None and result.primary is not None and not result.effective_status:
            result_type = (competition.settings_json or {}).get("result_type") or ""
            wind = (result.data or {}).get("wind")
            row.marks.append(
                (fixture.completed_at or fixture.created_at, result.primary, result_type, wind)
            )
    return totals


def _best(marks: list[tuple]) -> Decimal | None:
    if not marks:
        return None
    lower = marks[0][2] in LOWER_RESULT_TYPES
    values = [mark[1] for mark in marks]
    return min(values) if lower else max(values)


def _values(sport: str, row: _Totals, previous: _Totals | None, profile) -> dict:
    """Every catalogue stat for one set of totals."""

    definitions = (attributes.SPORT_ATTRIBUTES.get(sport) or {}).get("match_stats") or []
    best = _best(row.marks)
    previous_best = _best(previous.marks) if previous else None
    engine = {
        "points": row.points,
        "outcome.played": row.outcomes["played"],
        "outcome.wins": row.outcomes["wins"],
        "outcome.losses": row.outcomes["losses"],
        "outcome.draws": row.outcomes["draws"],
        "outcome.played_vs_higher": row.outcomes["played_vs_higher"],
        "outcome.wins_vs_higher": row.outcomes["wins_vs_higher"],
        "outcome.opponent_rank": (
            Decimal(sum(row.opponent_ranks)) / len(row.opponent_ranks)
            if row.opponent_ranks
            else None
        ),
        "result.best": best,
        "result.season_best": best,
        "result.latest": max(row.marks)[1] if row.marks else None,
        "result.progress": (
            (best - previous_best) / previous_best * 100
            if best is not None and previous_best
            else None
        ),
        "result.wind_legal": (
            Decimal(
                sum(1 for mark in row.marks if mark[3] is not None and Decimal(str(mark[3])) <= 2)
            )
            / sum(1 for mark in row.marks if mark[3] is not None)
            * 100
            if any(mark[3] is not None for mark in row.marks)
            else None
        ),
        "participant.handicap": row.handicap,
    }
    # Measurements cost a query each; only sports that show them read them.
    sources = {definition.get("source") for definition in definitions}
    for kind in ("weight", "reach"):
        if f"profile.{kind}" in sources:
            engine[f"profile.{kind}"] = _measurement(profile, kind)
    values: dict[str, dict] = {}
    known = {"matches": row.matches, "minutes": row.minutes, "rounds": row.matches}
    for definition in definitions:
        source = definition.get("source")
        if not source:
            continue
        if source in engine:
            value = engine[source]
            per_match = None
        else:
            value = row.counts.get(source, Decimal("0"))
            per_match = value / row.matches if row.matches else None
        known[definition["key"]] = value
        values[definition["key"]] = {"value": _number(value), "per_match": _number(per_match)}
    for _ in range(3):  # formulas may build on other formulas
        for definition in definitions:
            if definition.get("formula"):
                value = evaluate(definition["formula"], known)
                known[definition["key"]] = value
                values[definition["key"]] = {"value": _number(value), "per_match": None}
    return values


def _measurement(profile, kind: str):
    if profile is None:
        return None
    row = (
        profile.measurements.filter(kind=kind, value__isnull=False).order_by("-measured_on").first()
    )
    return row.value if row else None


def recompute_user(user, shared: _Shared | None = None) -> int:
    """Rebuild every cached stat line for one player. Returns the number of rows."""

    profile = PlayerProfile.objects.filter(user=user).first()
    totals = _collect(user, shared)
    seasons: dict[tuple[str, int], _Totals] = defaultdict(_Totals)
    for (sport, season, _competition), row in totals.items():
        seasons[(sport, season)].add(row)
    now = timezone.now()
    wanted = {
        (sport, season, competition_id): (row, seasons.get((sport, season - 1)))
        for (sport, season, competition_id), row in totals.items()
    }
    for (sport, season), row in seasons.items():
        wanted[(sport, season, None)] = (row, seasons.get((sport, season - 1)))
    existing = {
        (line.sport, line.season, line.competition_id): line
        for line in PlayerStatLine.objects.filter(user=user)
    }
    changed, fresh = [], []
    for key, (row, previous) in wanted.items():
        sport, season, competition_id = key
        line = existing.pop(key, None)
        if line is None:
            line = PlayerStatLine(
                user=user, sport=sport, season=season, competition_id=competition_id
            )
            fresh.append(line)
        else:
            changed.append(line)
        line.matches = row.matches
        line.minutes = row.minutes
        line.values = _values(sport, row, previous, profile)
        line.computed_at = now
        line.updated_at = now
    if changed:
        PlayerStatLine.objects.bulk_update(
            changed, ["matches", "minutes", "values", "computed_at", "updated_at"]
        )
    if fresh:
        PlayerStatLine.objects.bulk_create(fresh)
    if existing:
        PlayerStatLine.objects.filter(id__in=[line.id for line in existing.values()]).delete()
    return len(wanted)


def players_in_competition(competition) -> list:
    from django.contrib.auth import get_user_model

    from apps.competitions.models import RosterMember

    ids = set(
        RosterMember.objects.filter(
            participant__competition=competition, user__isnull=False
        ).values_list("user_id", flat=True)
    )
    ids |= set(
        competition.participants.filter(managed_by__isnull=False).values_list(
            "managed_by_id", flat=True
        )
    )
    return list(get_user_model().objects.filter(id__in=ids))


def recompute_competition(competition) -> int:
    """The stats job: rebuild the players of one competition."""

    from apps.fixtures.models import Fixture

    if catalog.sport_for_competition(competition.sport) is None:
        return 0
    shared = _Shared()
    shared.load(
        Fixture.objects.filter(competition=competition, status__in=COUNTED).values_list(
            "id", flat=True
        )
    )
    return sum(recompute_user(user, shared) for user in players_in_competition(competition))


# --- Percentiles ---------------------------------------------------------------------


def _position(profile, sport: str) -> str:
    row = PlayerSport.objects.filter(profile=profile, sport=sport).first()
    return row.primary_position if row else ""


def cohort(profile, sport: str) -> list:
    """Profiles in the same sport, position, age group and gender category that scouts
    may see (plus the player). Private profiles never feed anyone's percentile."""

    group = (age_group(profile.date_of_birth) or {}).get("key")
    position = _position(profile, sport)
    candidates = PlayerProfile.objects.filter(
        sports__sport=sport,
        sports__primary_position=position,
        gender_category=profile.gender_category,
    ).distinct()
    rows = []
    for other in candidates:
        if (age_group(other.date_of_birth) or {}).get("key") != group:
            continue
        if (
            other.pk != profile.pk
            and effective_visibility(other) == PlayerProfile.Visibility.PRIVATE
        ):
            continue
        rows.append(other)
    return rows


def percentile(value, others: list, better: str | None) -> float | None:
    """Share of the cohort this value beats (ties count half), or None when hidden."""

    if value is None or better is None or len(others) < MIN_SAMPLE:
        return None
    value = float(value)
    worse = sum(1 for other in others if (other < value if better == "higher" else other > value))
    equal = sum(1 for other in others if other == value)
    return round((worse + 0.5 * equal) / len(others) * 100, 1)


def stat_percentiles(
    profile, sport: str, season: int, values: dict, peers: list | None = None
) -> dict:
    """Percentile and sample size for each stat in a season line."""

    peers = peers if peers is not None else cohort(profile, sport)
    lines = {
        line.user_id: line.values
        for line in PlayerStatLine.objects.filter(
            sport=sport,
            season=season,
            competition=None,
            user_id__in=[peer.user_id for peer in peers],
        )
    }
    result = {}
    for key, entry in values.items():
        sample = [
            float(row[key]["value"])
            for row in lines.values()
            if key in row and row[key].get("value") is not None
        ]
        better = attributes.stat_better(sport, key)
        result[key] = {
            "percentile": percentile(entry.get("value"), sample, better),
            "sample": len(sample),
        }
    return result


def test_summary(profile, sport: str, peers: list | None = None) -> list[dict]:
    """Personal best, latest and trend for every catalogue test, with percentiles."""

    definitions = (attributes.SPORT_ATTRIBUTES.get(sport) or {}).get("physical_tests") or []
    rows = list(
        PhysicalTestResult.objects.filter(profile=profile, sport=sport).order_by(
            "tested_on", "created_at"
        )
    )
    peers = peers if peers is not None else None
    summary = []
    for definition in definitions:
        mine = [row for row in rows if row.test_key == definition["key"]]
        if not mine:
            continue
        lower = definition["better"] == "lower"
        best = (
            min(mine, key=lambda row: row.value) if lower else max(mine, key=lambda row: row.value)
        )
        latest = mine[-1]
        if peers is None:
            peers = cohort(profile, sport)
        peer_bests = []
        for peer in peers:
            values = list(
                PhysicalTestResult.objects.filter(
                    profile=peer, sport=sport, test_key=definition["key"]
                ).values_list("value", flat=True)
            )
            if values:
                peer_bests.append(float(min(values) if lower else max(values)))
        trend = None
        if len(mine) >= 2:
            change = mine[-1].value - mine[0].value
            improving = change < 0 if lower else change > 0
            trend = "improving" if improving and change else ("declining" if change else "steady")
        summary.append(
            {
                **definition,
                "personal_best": result_row(best),
                "latest": result_row(latest),
                "history": [result_row(row) for row in mine],
                "trend": trend,
                "percentile": percentile(best.value, peer_bests, definition["better"]),
                "sample": len(peer_bests),
            }
        )
    return summary


def result_row(row: PhysicalTestResult) -> dict:
    return {
        "id": str(row.id),
        "value": _number(row.value),
        "unit": row.unit,
        "tested_on": row.tested_on,
        "venue": row.venue,
        "source": row.source,
        "verified": row.is_verified,
        "label": "Verified" if row.is_verified else "Self-reported",
    }
