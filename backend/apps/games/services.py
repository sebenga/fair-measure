"""Games services: building events from the catalogue, entries, medals and tables.

Medals come from each event's own competition, in one of three general ways:
a confirmed result sheet (ranked performances), a knockout (final, then either a
bronze-medal match or both losing semi-finalists) or a final table. Nothing here
names a sport; the catalogue and presets are data.
"""

from __future__ import annotations

from collections import defaultdict

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.competitions.models import Competition, Membership, Participant
from apps.competitions.presets import FORMAT_TO_MODEL, PRESETS, apply_preset
from apps.core.permissions import Role

from . import olympic_catalog as catalog
from .models import NOC, Athlete, Entry, Games, GamesEvent, GamesOfficial, Medal, MedalChange

MEDAL_FOR_RANK = {1: Medal.Kind.GOLD, 2: Medal.Kind.SILVER, 3: Medal.Kind.BRONZE}
KNOCKOUT_FORMATS = {"knockout", "group_knockout"}


# --- Catalogue -----------------------------------------------------------------


def preset_ready(key: str) -> bool:
    return key in PRESETS


def catalog_payload(games: Games | None = None, season: str | None = None) -> list[dict]:
    added = set()
    if games is not None:
        added = {
            catalog.event_key(row.sport_key, row.discipline, row.name)
            for row in games.events.filter(custom=False)
        }
    rows = []
    for sport_row in catalog.all_sports():
        if season and sport_row["season"] != season:
            continue
        disciplines = []
        for discipline in sport_row["disciplines"]:
            events = []
            for event in discipline["events"]:
                key = catalog.event_key(sport_row["key"], discipline["name"], event["name"])
                preset = catalog.preset_for(sport_row, discipline, event)
                events.append(
                    {
                        "key": key,
                        "name": event["name"],
                        "gender": event["gender"],
                        "kind": event["kind"],
                        "preset": preset,
                        "available": preset_ready(preset),
                        "added": key in added,
                    }
                )
            disciplines.append(
                {
                    "name": discipline["name"],
                    "preset": catalog.preset_for(sport_row, discipline),
                    "available": any(item["available"] for item in events),
                    "events": events,
                }
            )
        rows.append(
            {
                "key": sport_row["key"],
                "label": sport_row["label"],
                "season": sport_row["season"],
                "federation": sport_row["federation"],
                "federation_name": sport_row["federation_name"],
                "note": sport_row["note"],
                "available": any(item["available"] for item in disciplines),
                "disciplines": disciplines,
            }
        )
    return rows


def _catalog_event(key: str) -> tuple[dict, dict, dict] | None:
    sport_key, _, rest = key.partition("|")
    discipline_name, _, event_name = rest.partition("|")
    sport_row = catalog.find_sport(sport_key)
    if sport_row is None:
        return None
    discipline = next(
        (item for item in sport_row["disciplines"] if item["name"] == discipline_name), None
    )
    if discipline is None:
        return None
    event = next((item for item in discipline["events"] if item["name"] == event_name), None)
    if event is None:
        return None
    return sport_row, discipline, event


def keys_for(*, sports: list[str] | None = None, season: str | None = None) -> list[str]:
    """Every catalogue event key for the chosen sports or season ("Select all")."""

    keys = []
    for sport_row in catalog.all_sports():
        if sports is not None and sport_row["key"] not in sports:
            continue
        if season and sport_row["season"] != season:
            continue
        for discipline in sport_row["disciplines"]:
            for event in discipline["events"]:
                keys.append(catalog.event_key(sport_row["key"], discipline["name"], event["name"]))
    return keys


# --- Events and their competitions --------------------------------------------------


def _event_format(preset: dict, round_format: str) -> str:
    allowed = [FORMAT_TO_MODEL.get(item, item) for item in preset.get("formats_allowed") or []]
    wanted = {
        "knockout": "knockout",
        "groups_knockout": "group_knockout",
        "pools_knockout": "group_knockout",
        "repechage_knockout": "knockout",
        "round_robin_knockout": "group_knockout",
        "ranking_round_knockout": "knockout",
        "heats_knockout": "knockout",
    }.get(round_format)
    if wanted and (not allowed or wanted in allowed):
        return wanted
    if wanted == "group_knockout" and "knockout" in allowed:
        return "knockout"
    return FORMAT_TO_MODEL.get(preset.get("format") or "league", "league")


def _competition_for(
    games: Games, *, title: str, preset_key: str, round_format: str
) -> Competition:
    preset = PRESETS[preset_key]
    competition = Competition.objects.create(
        name=f"{games.name} · {title}"[:200],
        owner=games.owner,
        sport=preset.get("sport", ""),
        is_private=games.is_private,
        status=Competition.Status.ACTIVE,
        format=_event_format(preset, round_format),
    )
    Membership.objects.get_or_create(
        competition=competition, user=games.owner, defaults={"role": Role.OWNER}
    )
    apply_preset(competition, preset_key)
    settings = dict(competition.settings_json or {})
    # Every Games event is official: technical delegates confirm and amend results.
    settings["official_results"] = True
    settings["games_id"] = str(games.id)
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])
    _sync_officials(games, competition)
    return competition


def _sync_officials(games: Games, competition: Competition) -> None:
    from apps.results.models import CompetitionOfficial

    for row in GamesOfficial.objects.filter(games=games):
        CompetitionOfficial.objects.get_or_create(
            competition=competition,
            user_id=row.user_id,
            title=CompetitionOfficial.Title.TECHNICAL_DELEGATE,
            defaults={"appointed_by": games.owner},
        )


@transaction.atomic
def add_catalog_events(games: Games, keys: list[str]) -> dict:
    existing = {
        catalog.event_key(row.sport_key, row.discipline, row.name)
        for row in games.events.filter(custom=False)
    }
    created, skipped, unavailable = [], [], []
    order = games.events.count()
    for key in keys:
        found = _catalog_event(key)
        if found is None:
            raise ValidationError({"events": f"'{key}' is not in the Olympic catalogue."})
        sport_row, discipline, event = found
        if key in existing:
            skipped.append(key)
            continue
        preset_key = catalog.preset_for(sport_row, discipline, event)
        if not preset_ready(preset_key):
            unavailable.append(key)
            continue
        round_format = discipline.get("round_format") or sport_row["round_format"]
        title = f"{sport_row['label']}: {event['name']}"
        competition = _competition_for(
            games, title=title, preset_key=preset_key, round_format=round_format
        )
        order += 1
        created.append(
            GamesEvent.objects.create(
                games=games,
                sport_key=sport_row["key"],
                sport_label=sport_row["label"],
                discipline=discipline["name"],
                name=event["name"],
                gender=event["gender"],
                kind=event["kind"],
                preset_key=preset_key,
                round_format=round_format,
                medal_type=discipline.get("medal_type") or sport_row["medal_type"],
                competition=competition,
                display_order=order,
            )
        )
        existing.add(key)
    return {"created": created, "skipped": skipped, "unavailable": unavailable}


@transaction.atomic
def add_custom_event(
    games: Games, *, sport_label: str, name: str, preset_key: str, **extra
) -> GamesEvent:
    if not preset_ready(preset_key):
        raise ValidationError({"preset": "Choose one of the available presets."})
    round_format = extra.get("round_format") or ""
    competition = _competition_for(
        games, title=f"{sport_label}: {name}", preset_key=preset_key, round_format=round_format
    )
    return GamesEvent.objects.create(
        games=games,
        sport_key=f"custom:{sport_label.lower()}"[:60],
        sport_label=sport_label,
        discipline=extra.get("discipline") or "",
        name=name,
        gender=extra.get("gender") or GamesEvent.Gender.OPEN,
        kind=extra.get("kind") or GamesEvent.Kind.INDIVIDUAL,
        preset_key=preset_key,
        round_format=round_format,
        medal_type=extra.get("medal_type") or GamesEvent.MedalType.STANDARD,
        custom=True,
        competition=competition,
        display_order=games.events.count() + 1,
    )


@transaction.atomic
def remove_event(event: GamesEvent) -> None:
    competition = event.competition
    event.delete()
    competition.delete()


@transaction.atomic
def add_entry(event: GamesEvent, noc: NOC, athlete: Athlete | None = None) -> Entry:
    if noc.games_id != event.games_id:
        raise ValidationError({"noc": "That NOC is in a different Games."})
    if event.kind == GamesEvent.Kind.INDIVIDUAL:
        if athlete is None:
            raise ValidationError({"athlete": "An individual event needs an athlete."})
        if athlete.noc_id != noc.id:
            raise ValidationError({"athlete": f"{athlete.name} competes for {athlete.noc.code}."})
        if event.entries.filter(athlete=athlete).exists():
            raise ValidationError({"athlete": f"{athlete.name} is already entered."})
        name = f"{athlete.name} ({noc.code})"
        kind = Participant.Kind.INDIVIDUAL
    else:
        if event.entries.filter(noc=noc).exists():
            raise ValidationError({"noc": f"{noc.code} already has a team in this event."})
        name = noc.name
        kind = Participant.Kind.TEAM
    participant = Participant.objects.create(
        competition=event.competition,
        name=name[:200],
        short_name=noc.code,
        kind=kind,
        logo_url=noc.flag_url,
        managed_by=athlete.user if athlete else None,
    )
    return Entry.objects.create(event=event, participant=participant, noc=noc, athlete=athlete)


# --- Podiums -------------------------------------------------------------------------


EARLY_ROUNDS = ("semi", "quarter", "repechage", "eighth", "1/8", "1/16", "heat", "qualif")


def is_final_label(label: str) -> bool:
    """ "Final" or "Final A", but not a semi-final, quarter-final or heat."""

    return "final" in (label or "").lower() and not is_early_label(label)


def is_early_label(label: str) -> bool:
    text = (label or "").lower()
    return any(word in text for word in EARLY_ROUNDS)


def is_bronze_label(label: str) -> bool:
    return "bronze" in (label or "").lower()


def _medal_round(event: GamesEvent, finalised: list):
    """Which finalised fixture decides the medals (latest first in ``finalised``): the
    one the organiser chose, the only fixture, or the one labelled as the final. A heat
    or a semi-final never awards medals."""

    if event.final_fixture_id:
        return next(
            (fixture for fixture in finalised if fixture.id == event.final_fixture_id), None
        )
    if event.competition.fixtures.count() == 1:
        only = finalised[0] if finalised else None
        if only is not None and not is_early_label(only.label):
            return only
        return None
    return next(
        (
            fixture
            for fixture in finalised
            if is_final_label(fixture.label) and not is_bronze_label(fixture.label)
        ),
        None,
    )


def _from_result_sheet(event: GamesEvent) -> list[tuple[int, int]] | None:
    from apps.fixtures.models import Fixture
    from apps.results.models import EntryResult

    finalised = list(
        Fixture.objects.filter(
            competition=event.competition, result_sheet__finalised_at__isnull=False
        ).order_by("-result_sheet__finalised_at")
    )
    fixture = _medal_round(event, finalised)
    if fixture is None:
        return None
    rows = EntryResult.objects.filter(side__fixture=fixture, rank__isnull=False).values_list(
        "side__participant_id", "rank"
    )
    return [(participant_id, rank) for participant_id, rank in rows]


def _from_bouts(event: GamesEvent) -> list[tuple[int, int]] | None:
    """Bouts scored on result sheets (one sheet per bout): gold and silver from the
    final, bronze from the bronze bout or the two semi-finalists who lost to a finalist."""

    from apps.results.models import EntryResult, ResultSheet

    sheets = list(
        ResultSheet.objects.filter(
            fixture__competition=event.competition, finalised_at__isnull=False
        )
        .select_related("fixture")
        .order_by("finalised_at")
    )
    ranks = defaultdict(dict)
    for participant_id, fixture_id, rank in EntryResult.objects.filter(
        side__fixture__competition=event.competition, rank__isnull=False
    ).values_list("side__participant_id", "side__fixture_id", "rank"):
        ranks[fixture_id][participant_id] = rank
    bouts = [sheet for sheet in sheets if len(ranks[sheet.fixture_id]) == 2]
    bronze_id = event.bronze_fixture_id or next(
        (sheet.fixture_id for sheet in reversed(bouts) if is_bronze_label(sheet.fixture.label)),
        None,
    )
    candidates = [sheet for sheet in bouts if sheet.fixture_id != bronze_id]
    chosen = _medal_round(event, [sheet.fixture for sheet in reversed(candidates)])
    final = next(
        (sheet for sheet in candidates if chosen is not None and sheet.fixture_id == chosen.id),
        None,
    )
    if final is None:
        return None
    placed = ranks[final.fixture_id]
    winner = next((pid for pid, rank in placed.items() if rank == 1), None)
    runner_up = next((pid for pid, rank in placed.items() if rank == 2), None)
    if winner is None or runner_up is None:
        return None
    podium = [(winner, 1), (runner_up, 2)]
    if event.medal_type == GamesEvent.MedalType.BRONZE_MATCH and bronze_id:
        bronze = ranks.get(bronze_id) or {}
        third = next((pid for pid, rank in bronze.items() if rank == 1), None)
        if third is not None and any(sheet.fixture_id == bronze_id for sheet in bouts):
            podium.append((third, 3))
    elif event.medal_type == GamesEvent.MedalType.TWO_BRONZE:
        earlier = [sheet for sheet in candidates if sheet.finalised_at < final.finalised_at]
        for finalist in (winner, runner_up):
            # The finalist's last win before the final was their semi-final.
            semi = next(
                (
                    sheet
                    for sheet in reversed(earlier)
                    if ranks[sheet.fixture_id].get(finalist) == 1
                ),
                None,
            )
            if semi is None:
                continue
            loser = next(
                (pid for pid, rank in ranks[semi.fixture_id].items() if pid != finalist), None
            )
            if loser is not None and loser not in {winner, runner_up}:
                podium.append((loser, 3))
    return podium


def _from_knockout(event: GamesEvent) -> list[tuple[int, int]] | None:
    from apps.fixtures.models import Fixture, FixtureSide

    competition = event.competition
    bracket = competition.fixtures.filter(round_number__isnull=False).exclude(
        pk=event.bronze_fixture_id
    )
    final = event.final_fixture
    if final is None:
        last_round = (
            bracket.order_by("-round_number").values_list("round_number", flat=True).first()
        )
        if last_round is None:
            return None
        candidates = [
            fixture
            for fixture in bracket.filter(round_number=last_round)
            if fixture.sides.count() == 2
        ]
        if len(candidates) != 1:
            return None
        final = candidates[0]
    if final.status not in {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}:
        return None
    sides = list(final.sides.all())
    winner = next((side for side in sides if side.outcome == FixtureSide.Outcome.WIN), None)
    loser = next((side for side in sides if side.outcome == FixtureSide.Outcome.LOSS), None)
    if winner is None or loser is None:
        return None
    podium = [(winner.participant_id, 1), (loser.participant_id, 2)]
    if event.medal_type == GamesEvent.MedalType.TWO_BRONZE and final.round_number:
        for fixture in bracket.filter(round_number=final.round_number - 1):
            if fixture.status not in {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}:
                continue
            for side in fixture.sides.all():
                if side.outcome == FixtureSide.Outcome.LOSS:
                    podium.append((side.participant_id, 3))
    elif event.medal_type == GamesEvent.MedalType.BRONZE_MATCH and event.bronze_fixture_id:
        bronze = Fixture.objects.get(pk=event.bronze_fixture_id)
        if bronze.status in {Fixture.Status.COMPLETED, Fixture.Status.FORFEIT}:
            third = next(
                (side for side in bronze.sides.all() if side.outcome == FixtureSide.Outcome.WIN),
                None,
            )
            if third is not None:
                podium.append((third.participant_id, 3))
    return podium


def _from_table(event: GamesEvent) -> list[tuple[int, int]] | None:
    from apps.fixtures.models import Fixture
    from apps.standings.services import compute_standings

    fixtures = event.competition.fixtures.all()
    if not fixtures.exists():
        return None
    open_states = {Fixture.Status.SCHEDULED, Fixture.Status.LIVE, Fixture.Status.POSTPONED}
    if fixtures.filter(status__in=open_states).exists():
        return None
    rows = compute_standings(event.competition)
    return [(row.participant_id, index + 1) for index, row in enumerate(rows[:3]) if row.played]


def ranking(event: GamesEvent) -> list[tuple[str, int]] | None:
    """(participant id, rank) for every placed entrant, or None while undecided."""

    competition = event.competition
    settings = competition.settings_json or {}
    if settings.get("result_type") and event.medal_type != GamesEvent.MedalType.STANDARD:
        ranked = _from_bouts(event)
    elif settings.get("result_type"):
        ranked = _from_result_sheet(event)
    elif competition.format in KNOCKOUT_FORMATS:
        ranked = _from_knockout(event)
    else:
        ranked = _from_table(event)
    if ranked is None:
        return None
    return [(str(pid), rank) for pid, rank in ranked]


def podium(event: GamesEvent) -> list[tuple[str, int]] | None:
    """(participant id, rank) for every medallist, or None while undecided."""

    ranked = ranking(event)
    if ranked is None:
        return None
    return [(pid, rank) for pid, rank in ranked if rank in MEDAL_FOR_RANK]


def _medal_rows(event: GamesEvent) -> list[dict]:
    return [
        {
            "medal": row.medal,
            "rank": row.rank,
            "noc": row.noc.code,
            "entrant": row.entry.participant.name,
        }
        for row in event.medals.select_related("noc", "entry__participant").order_by(
            "rank", "noc__code"
        )
    ]


@transaction.atomic
def sync_medals(event: GamesEvent, *, actor=None, reason: str = "") -> bool:
    """Award or reallocate an event's medals from its current confirmed result."""

    placed = podium(event)
    entries = {str(entry.participant_id): entry for entry in event.entries.select_related("noc")}
    wanted = []
    for participant_id, rank in placed or []:
        entry = entries.get(participant_id)
        if entry is not None:
            wanted.append((entry, rank))
    before = _medal_rows(event)
    target = sorted(
        (entry.participant.name, entry.noc.code, MEDAL_FOR_RANK[rank], rank)
        for entry, rank in wanted
    )
    current = sorted((row["entrant"], row["noc"], row["medal"], row["rank"]) for row in before)
    if target == current:
        return False
    event.medals.all().delete()
    Medal.objects.bulk_create(
        [
            Medal(event=event, noc=entry.noc, entry=entry, medal=MEDAL_FOR_RANK[rank], rank=rank)
            for entry, rank in wanted
        ]
    )
    after = _medal_rows(event)
    if not reason:
        reason = (
            "Medals awarded from the confirmed result"
            if not before
            else "Medals reallocated after a result change"
        )
        latest = _latest_amendment_reason(event)
        if before and latest:
            reason = f"{reason}: {latest}"
    change = MedalChange.objects.create(
        event=event, reason=reason[:500], before=before, after=after, actor=actor
    )
    event.status = GamesEvent.Status.MEDALS_AWARDED if wanted else GamesEvent.Status.IN_PROGRESS
    event.save(update_fields=["status", "updated_at"])
    from .experience import medals_changed

    medals_changed(event, change)
    return True


def _latest_amendment_reason(event: GamesEvent) -> str:
    from apps.results.models import ResultAmendment

    row = (
        ResultAmendment.objects.filter(fixture__competition=event.competition)
        .exclude(reason="")
        .order_by("-created_at")
        .first()
    )
    return row.reason if row else ""


# --- Medal table ------------------------------------------------------------------------


def medal_table(games: Games) -> list[dict]:
    counts = {
        noc.id: {
            "noc_id": str(noc.id),
            "code": noc.code,
            "name": noc.name,
            "flag_url": noc.flag_url,
            "colour": noc.colour,
            "gold": 0,
            "silver": 0,
            "bronze": 0,
        }
        for noc in games.nocs.all()
    }
    for medal in Medal.objects.filter(event__games=games).values("noc_id", "medal"):
        row = counts.get(medal["noc_id"])
        if row is not None:
            row[medal["medal"]] += 1
    rows = []
    for row in counts.values():
        row["total"] = row["gold"] + row["silver"] + row["bronze"]
        rows.append(row)

    def key(row: dict) -> tuple:
        if games.medal_table_ranking == Games.Ranking.TOTAL_FIRST:
            return (-row["total"], -row["gold"], -row["silver"], -row["bronze"])
        return (-row["gold"], -row["silver"], -row["bronze"])

    rows.sort(key=lambda row: (*key(row), row["code"]))
    previous = None
    for index, row in enumerate(rows):
        current = key(row)
        if current != previous:
            row["rank"] = index + 1
            previous = current
        else:
            row["rank"] = rows[index - 1]["rank"]
    return rows


def medal_feed(games: Games, limit: int = 20) -> list[dict]:
    return [
        {
            "event_id": str(medal.event_id),
            "event": f"{medal.event.sport_label}: {medal.event.name}",
            "medal": medal.medal,
            "noc": medal.noc.code,
            "entrant": medal.entry.participant.name,
            "awarded_at": medal.created_at,
        }
        for medal in Medal.objects.filter(event__games=games)
        .select_related("event", "noc", "entry__participant")
        .order_by("-created_at", "rank")[:limit]
    ]


def touch_games_status(games: Games) -> None:
    if games.status == Games.Status.DRAFT and Medal.objects.filter(event__games=games).exists():
        games.status = Games.Status.LIVE
        games.save(update_fields=["status", "updated_at"])
