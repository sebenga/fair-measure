"""A one-hour demo competition that fills every step a human would otherwise do."""

from __future__ import annotations

import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.competitions.models import Competition, Membership, Participant, RosterMember, TeamPick
from apps.competitions.presets import default_game_time
from apps.competitions.serializers import squad_size_for, team_entry_mode
from apps.core.bus import Queues, enqueue_job
from apps.core.permissions import Role
from apps.fixtures.matchday import team_sheet_config, team_sheet_minimum
from apps.fixtures.models import (
    Fixture,
    FixtureLineup,
    FixtureRater,
    FixtureReferee,
    LineupEntry,
    PlayerAppearance,
    RaterScore,
    ScoreEvent,
)
from apps.fixtures.services import (
    ScheduleOptions,
    generate_knockout,
    generate_league_and_knockout,
    generate_round_robin,
)
from apps.results.models import CompetitionOfficial
from apps.standings.services import refresh_standings

User = get_user_model()

DEMO_TTL = timedelta(hours=1)
# How long the demo's live match has already been running when the demo starts.
LIVE_FOR_MINUTES = 18
DEMO_EMAIL_DOMAIN = "fairmeasure.demo"

# Every demo fills 16 entrants: enough for a full cup (round of 16 to the final).
DEMO_SIZE = 16

DEMO_TEAMS = [
    ("Harbour Hawks", "Hawks"),
    ("Northside Nomads", "Nomads"),
    ("Riverbend Rovers", "Rovers"),
    ("Kingsley Kestrels", "Kestrels"),
    ("Old Quarry Oaks", "Oaks"),
    ("Seaview Sharks", "Sharks"),
    ("Eastgate Eagles", "Eagles"),
    ("Westbrook Wolves", "Wolves"),
    ("Hilltop Hornets", "Hornets"),
    ("Lakeside Lions", "Lions"),
    ("Southpark Spartans", "Spartans"),
    ("Mill Lane Mustangs", "Mustangs"),
    ("Cedar Vale Cobras", "Cobras"),
    ("Dockside Dolphins", "Dolphins"),
    ("Granite Peak Griffins", "Griffins"),
    ("Valley View Vipers", "Vipers"),
]

DEMO_PAIRS = [
    (f"{FAMILY_A} / {FAMILY_B}", f"{FAMILY_A[0]}/{FAMILY_B[0]}")
    for FAMILY_A, FAMILY_B in [
        ("Mensah", "Cruz"),
        ("Okeke", "Alvarez"),
        ("Voss", "Nasser"),
        ("Ito", "Bello"),
        ("Moreau", "Blake"),
        ("Novak", "Osei"),
        ("Silva", "Rahman"),
        ("Chen", "Nowak"),
        ("Cruz", "Okeke"),
        ("Alvarez", "Voss"),
        ("Nasser", "Ito"),
        ("Bello", "Moreau"),
        ("Blake", "Novak"),
        ("Osei", "Silva"),
        ("Rahman", "Chen"),
        ("Nowak", "Mensah"),
    ]
]

DEMO_COMBOS = [
    (f"{horse} / {rider}", horse)
    for horse, rider in [
        ("Harbour Star", "Ada Mensah"),
        ("Northwind", "Benito Cruz"),
        ("River Song", "Chioma Okeke"),
        ("Kestrel", "Diego Alvarez"),
        ("Quarry", "Elena Voss"),
        ("Seaview", "Farid Nasser"),
        ("Eastgate", "Grace Ito"),
        ("Westbrook", "Hassan Bello"),
        ("Hilltop", "Ines Moreau"),
        ("Lakeside", "Jonah Blake"),
        ("Southpark", "Kira Novak"),
        ("Mill Lane", "Liam Osei"),
        ("Cedar Vale", "Marta Silva"),
        ("Dockside", "Nabil Rahman"),
        ("Granite", "Olivia Chen"),
        ("Valley View", "Piotr Nowak"),
    ]
]

GIVEN_NAMES = [
    "Ada",
    "Benito",
    "Chioma",
    "Diego",
    "Elena",
    "Farid",
    "Grace",
    "Hassan",
    "Ines",
    "Jonah",
    "Kira",
    "Liam",
    "Marta",
    "Nabil",
    "Olivia",
    "Piotr",
]

FAMILY_NAMES = [
    "Mensah",
    "Cruz",
    "Okeke",
    "Alvarez",
    "Voss",
    "Nasser",
    "Ito",
    "Bello",
    "Moreau",
    "Blake",
    "Novak",
    "Osei",
    "Silva",
    "Rahman",
    "Chen",
    "Nowak",
]

PLAYER_NAMES = [f"{given} {family}" for given, family in zip(GIVEN_NAMES, FAMILY_NAMES)]

DEMO_BLURB = (
    "Demo entrant. This whole competition is a one-hour demo and deletes itself."
)

OFFICIALS = [
    ("Sam", "Steward", CompetitionOfficial.Title.STEWARD),
    ("Riley", "Referee", CompetitionOfficial.Title.REFEREE),
    ("Jordan", "Judge", CompetitionOfficial.Title.JUDGE),
]

# Shirt numbers and catalogue position keys. Enough for a soccer XI, league squad
# groups and a 15-man fantasy squad (2 GK, 5 DEF, 5 MID, 2 FWD per club).
DEMO_SHIRTS = [
    (1, "goalkeeper"),
    (13, "goalkeeper"),
    (2, "full-back"),
    (3, "centre-back"),
    (4, "centre-back"),
    (5, "full-back"),
    (6, "centre-back"),
    (8, "defensive-midfield"),
    (7, "winger"),
    (10, "attacking-midfield"),
    (11, "winger"),
    (14, "central-midfield"),
    (9, "striker"),
    (19, "striker"),
]


def demo_is_active(competition: Competition) -> bool:
    settings = getattr(competition, "settings_json", None) or {}
    return bool((settings.get("demo_league") or {}).get("active"))


def demo_expires_at(competition: Competition):
    raw = ((getattr(competition, "settings_json", None) or {}).get("demo_league") or {}).get(
        "expires_at"
    )
    return _parse_when(raw)


def demo_participants(competition: Competition):
    stored = ((getattr(competition, "settings_json", None) or {}).get("demo_league") or {}).get(
        "participant_ids"
    ) or []
    flagged = competition.participants.filter(metadata__demo=True)
    if stored:
        return competition.participants.filter(Q(metadata__demo=True) | Q(id__in=stored))
    return flagged


def generate_demo_league(competition: Competition, actor) -> dict:
    real = competition.participants.filter(is_active=True).exclude(
        pk__in=demo_participants(competition).values("pk")
    )
    if real.exists():
        raise ValidationError(
            {
                "demo": (
                    "This competition already has your own entrants. A demo has to start empty "
                    "so it can fill every step and then delete itself."
                )
            }
        )
    with transaction.atomic():
        # Two taps on "demo" deadlock on Postgres unless the runs take turns.
        locked = Competition.objects.select_for_update().filter(pk=competition.pk).first()
        if locked is not None:
            competition.settings_json = locked.settings_json
        _clear_demo(competition)
        users: list = []
        entrants = _create_entrants(competition, users)
        picks = _pick_squads(competition, entrants, actor, users)
        officials = _appoint_officials(competition, actor, users)
        _open_team_entry(competition)
        cup_stage = _prepare_cup(competition)
        fixtures = _schedule(competition, entrants)
        if cup_stage is not False:
            fixtures = _drop_generated_cup(competition, fixtures, cup_stage)
        # Every team's players, read once and shared by the steps below.
        rosters = _rosters(competition)
        _staff_fixtures(competition, fixtures, officials, actor, rosters)
        _ensure_stat_categories(competition)
        played, live = _play_past_fixtures(competition, fixtures, actor, rosters)
        cup = (
            _build_cup(competition, entrants, cup_stage, officials, actor, rosters)
            if cup_stage is not False
            else {}
        )
        fixtures = fixtures + cup.get("fixtures", [])
        played += cup.get("played", 0)
        played += _award_sample_points(competition, entrants, actor)
        starters = _starters(fixtures, rosters)
        ratings = _rate_players(fixtures, starters)
        stats = _record_player_stats(competition, fixtures, actor, starters)
        _ensure_player_profiles(competition)
        squad_picks = _pick_league_squad(competition, actor)
        _mark_unavailable(competition)
        fantasy_teams = _fill_fantasy(competition, actor)
        refresh_standings(competition)
        expires = timezone.now() + DEMO_TTL
        settings = dict(competition.settings_json or {})
        settings["demo_league"] = {
            "active": True,
            "expires_at": expires.isoformat(),
            "participant_ids": [str(row.id) for row in entrants],
            "user_ids": [str(user.id) for user in users],
            "fixture_count": len(fixtures),
            "played": played,
            "officials": len(officials),
            "picks": picks,
            "ratings": ratings,
            "stats": stats,
            "squad": squad_picks,
            "fantasy": fantasy_teams,
            # The guided tour opens these matches. A cup-only demo has no league match,
            # so its cup tie in play is the live one.
            "live_fixture": str(live.id) if live is not None else cup.get("live"),
            "live_cup_fixture": cup.get("live"),
            "penalty_fixture": cup.get("penalties"),
            "cup_stage": cup.get("stage"),
        }
        competition.settings_json = settings
        fields = ["settings_json", "updated_at"]
        if competition.status == Competition.Status.DRAFT:
            competition.status = Competition.Status.ACTIVE
            fields.append("status")
        if squad_picks and not competition.open_to_scouts:
            competition.open_to_scouts = True
            fields.append("open_to_scouts")
        competition.save(update_fields=fields)
        enqueue_job(
            Queues.SEARCH,
            "purge-demos",
            {"competition_id": str(competition.id)},
            delay_ms=int(DEMO_TTL.total_seconds() * 1000),
        )
    return {
        "active": True,
        "deleted": False,
        "expires_at": expires.isoformat(),
        "teams": len(entrants),
        "entrants": len(entrants),
        "fixtures": len(fixtures),
        "played": played,
        "officials": len(officials),
        "picks": picks,
        "ratings": ratings,
        "stats": stats,
        "squad": squad_picks,
        "fantasy": fantasy_teams,
    }


def clear_demo_league(competition: Competition) -> dict:
    if not demo_participants(competition).exists() and not demo_is_active(competition):
        raise ValidationError({"demo": "There is no demo competition to remove."})
    return _delete_demo_competition(competition)


def purge_expired_demos() -> int:
    removed = 0
    for competition in Competition.objects.filter(settings_json__demo_league__active=True):
        if _demo_has_expired(competition):
            _delete_demo_competition(competition)
            removed += 1
    return removed


def delete_demo_if_expired(competition_id) -> bool:
    competition = Competition.objects.filter(pk=competition_id).first()
    if competition is None or not demo_is_active(competition):
        return False
    if not _demo_has_expired(competition):
        return False
    _delete_demo_competition(competition)
    return True


def _demo_has_expired(competition: Competition) -> bool:
    when = demo_expires_at(competition)
    return when is not None and when <= timezone.now()


def _parse_when(raw):
    if raw is None:
        return None
    when = parse_datetime(raw) if isinstance(raw, str) else raw
    if when is None:
        return None
    if timezone.is_naive(when):
        return timezone.make_aware(when, timezone.get_current_timezone())
    return when


def _delete_demo_competition(competition: Competition) -> dict:
    info = (competition.settings_json or {}).get("demo_league") or {}
    user_ids = list(info.get("user_ids") or [])
    team_count = competition.participants.count()
    fixture_count = competition.fixtures.count()
    ScoreEvent.objects.filter(scoring_category__competition=competition).delete()
    competition.delete()
    _delete_orphan_demo_users(user_ids)
    return {
        "active": False,
        "deleted": True,
        "teams": team_count,
        "fixtures": fixture_count,
    }


def _clear_demo(competition: Competition) -> dict:
    info = (competition.settings_json or {}).get("demo_league") or {}
    user_ids = list(info.get("user_ids") or [])
    fixtures = Fixture.objects.filter(competition=competition)
    fixture_count = fixtures.count()
    fixtures.delete()
    _, removed = demo_participants(competition).delete()
    team_count = removed.get(Participant._meta.label, 0)
    CompetitionOfficial.objects.filter(competition=competition).delete()
    from apps.fantasy.models import FantasyTeam
    from apps.scouting.models import LeagueSquad

    LeagueSquad.objects.filter(competition=competition).delete()
    FantasyTeam.objects.filter(competition=competition).delete()
    settings = dict(competition.settings_json or {})
    settings.pop("demo_league", None)
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])
    _delete_orphan_demo_users(user_ids, competition)
    return {"teams": team_count, "fixtures": fixture_count}


def _delete_orphan_demo_users(user_ids, competition: Competition | None = None) -> None:
    if not user_ids:
        return
    leftovers = User.objects.filter(id__in=user_ids, email__iendswith=f"@{DEMO_EMAIL_DOMAIN}")
    if competition is not None:
        Membership.objects.filter(user__in=leftovers, competition=competition).delete()
    # Accounts still used elsewhere stay. The rest go in one sweep: deleting them one
    # by one walks every related table per account, hundreds of times over.
    busy = set(Membership.objects.filter(user__in=leftovers).values_list("user_id", flat=True))
    busy |= set(
        CompetitionOfficial.objects.filter(user__in=leftovers).values_list("user_id", flat=True)
    )
    leftovers.exclude(pk__in=busy).delete()


def _participant_type(competition: Competition) -> str:
    settings = competition.settings_json or {}
    if settings.get("scoring_basis") == "criteria" or settings.get("table_mode") == "points":
        raw = settings.get("participant_type")
        if raw in {"team", "individual", "pair", "combination"}:
            return str(raw)
        return "individual"
    return str(settings.get("participant_type") or "team")


def _is_points_table(competition: Competition) -> bool:
    settings = competition.settings_json or {}
    return settings.get("scoring_basis") == "criteria" or settings.get("table_mode") == "points"


def _name_at(index: int) -> tuple[str, str]:
    given = GIVEN_NAMES[index % len(GIVEN_NAMES)]
    family = FAMILY_NAMES[(index + index // len(GIVEN_NAMES)) % len(FAMILY_NAMES)]
    return given, family


def _demo_users(competition: Competition, wanted: list[tuple[str, str, str]], users: list) -> list:
    """Demo accounts for every (given, family, suffix), made in one round trip each way.

    The demo is generated while the person waits, so every row is created in bulk
    rather than one query at a time: on the live server each round trip to the
    database costs far more than the work itself.
    """

    short = str(competition.id).replace("-", "")[:12]
    emails = [f"demo.{short}.{suffix}@{DEMO_EMAIL_DOMAIN}" for _, _, suffix in wanted]
    existing = {user.email: user for user in User.objects.filter(email__in=emails)}
    fresh, renamed = [], []
    for (given, family, _), email in zip(wanted, emails, strict=True):
        display = f"{given} {family}"
        user = existing.get(email)
        if user is None:
            fresh.append(
                User(
                    email=email,
                    display_name=display,
                    given_name=given,
                    family_name=family,
                    headline="Demo profile",
                )
            )
        elif (user.display_name, user.given_name, user.family_name) != (display, given, family):
            user.display_name = display
            user.given_name = given
            user.family_name = family
            renamed.append(user)
    if fresh:
        User.objects.bulk_create(fresh, batch_size=200)
        existing.update({user.email: user for user in fresh})
    if renamed:
        for user in renamed:
            user.updated_at = timezone.now()
        User.objects.bulk_update(
            renamed, ["display_name", "given_name", "family_name", "updated_at"], batch_size=200
        )
    made = [existing[email] for email in emails]
    users.extend(made)
    return made


def _demo_user(competition: Competition, given: str, family: str, suffix: str, users: list):
    return _demo_users(competition, [(given, family, suffix)], users)[0]


def _join_all(competition: Competition, people: list) -> None:
    """Make every one of these people a member of the competition (one query each way)."""

    if not people:
        return
    already = set(
        Membership.objects.filter(
            competition=competition, user__in=[user.pk for user in people]
        ).values_list("user_id", flat=True)
    )
    rows = [
        Membership(competition=competition, user=user, role=Role.MEMBER)
        for user in people
        if user.pk not in already
    ]
    if rows:
        Membership.objects.bulk_create(rows, batch_size=200, ignore_conflicts=True)


def _rosters(competition: Competition) -> dict:
    """Every team's active players, in shirt order, keyed by participant id."""

    rosters: dict = {}
    members = (
        RosterMember.objects.filter(participant__competition=competition, is_active=True)
        .select_related("user")
        .order_by("number", "created_at")
    )
    for member in members:
        rosters.setdefault(member.participant_id, []).append(member)
    return rosters


def _sides_by_fixture(fixtures: list[Fixture]) -> dict:
    """Each fixture's sides (with participants) from a single query."""

    from apps.fixtures.models import FixtureSide

    by_fixture: dict = {fixture.id: [] for fixture in fixtures}
    if not fixtures:
        return by_fixture
    sides = (
        FixtureSide.objects.filter(fixture_id__in=list(by_fixture))
        .select_related("participant")
        .order_by("position", "created_at")
    )
    for side in sides:
        by_fixture[side.fixture_id].append(side)
    return by_fixture


def _create_entrants(competition: Competition, users: list) -> list[Participant]:
    kind_key = _participant_type(competition)
    if kind_key == "individual":
        names = [(f"{given} {family}", family) for given, family in (_name_at(i) for i in range(DEMO_SIZE))]
        kind = Participant.Kind.INDIVIDUAL
    elif kind_key == "pair":
        names = DEMO_PAIRS
        kind = Participant.Kind.TEAM
    elif kind_key == "combination":
        names = DEMO_COMBOS
        kind = Participant.Kind.TEAM
    else:
        names = DEMO_TEAMS
        kind = Participant.Kind.TEAM
    people: list = []
    if kind == Participant.Kind.INDIVIDUAL:
        people = _demo_users(
            competition,
            [(*_name_at(index), f"player.{index}") for index in range(len(names))],
            users,
        )
        _join_all(competition, people)
    created = [
        Participant(
            competition=competition,
            name=name,
            short_name=short,
            kind=kind,
            seed=index + 1,
            description=DEMO_BLURB,
            managed_by=people[index] if people else None,
            metadata={"demo": True},
        )
        for index, (name, short) in enumerate(names)
    ]
    Participant.objects.bulk_create(created)
    return created


def _squad_needed(competition: Competition) -> int:
    kind = _participant_type(competition)
    if kind == "individual":
        return 0
    if kind in {"pair", "combination"}:
        return 2
    needed = max(2, squad_size_for(competition))
    config = team_sheet_config(competition)
    if config:
        needed = max(needed, team_sheet_minimum(config))
    return needed


def _pick_squads(competition: Competition, teams: list[Participant], actor, users: list) -> int:
    needed = _squad_needed(competition)
    if needed == 0:
        return 0
    # Same outcome as a pick that was sent and accepted (see `confirm_team_pick`), but
    # for every player at once: one batch of accounts, memberships, picks and roster rows.
    wanted = [
        (*_name_at(DEMO_SIZE + index), f"squad.{DEMO_SIZE + index}")
        for index in range(len(teams) * needed)
    ]
    people = _demo_users(competition, wanted, users)
    _join_all(competition, people)
    now = timezone.now()
    invited_by = actor if getattr(actor, "is_authenticated", False) else None
    picks, members = [], []
    for team_index, team in enumerate(teams):
        for offset in range(needed):
            user = people[team_index * needed + offset]
            number, position = DEMO_SHIRTS[offset % len(DEMO_SHIRTS)]
            picks.append(
                TeamPick(
                    participant=team,
                    user=user,
                    invited_by=invited_by,
                    status=TeamPick.Status.ACCEPTED,
                    responded_at=now,
                )
            )
            members.append(
                RosterMember(
                    participant=team,
                    user=user,
                    name=user.get_full_name(),
                    number=number,
                    position=position,
                )
            )
    TeamPick.objects.bulk_create(picks, batch_size=200)
    RosterMember.objects.bulk_create(members, batch_size=200)
    return len(picks)


def _open_team_entry(competition: Competition) -> None:
    if _participant_type(competition) != "team":
        return
    settings = dict(competition.settings_json or {})
    if team_entry_mode(competition) not in {"pick", "draft"}:
        settings["team_entry"] = "pick"
    settings["team_entry_open"] = True
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])


def _appoint_officials(competition: Competition, actor, users: list) -> list:
    appointed = []
    people = _demo_users(
        competition,
        [
            (given, family, f"official.{index}")
            for index, (given, family, _) in enumerate(OFFICIALS)
        ],
        users,
    )
    _join_all(competition, people)
    for user, (_, _, title) in zip(people, OFFICIALS, strict=True):
        official, _ = CompetitionOfficial.objects.get_or_create(
            competition=competition,
            user=user,
            title=title,
            defaults={"appointed_by": actor if getattr(actor, "is_authenticated", False) else None},
        )
        appointed.append(official)
    return appointed


def _schedule(competition: Competition, teams: list[Participant]) -> list[Fixture]:
    if _is_points_table(competition):
        return []
    weekdays = list(competition.match_weekdays or [5])
    every = int((competition.settings_json or {}).get("cup_every_league_rounds") or 3)
    options = ScheduleOptions(
        starts_on=date.today() - timedelta(days=28),
        weekdays=weekdays,
        kickoff=time(hour=15),
        minutes_between_fixtures=0,
        location="Demo venue",
        cup_every_league_rounds=every,
    )
    if competition.format == Competition.Format.KNOCKOUT:
        return generate_knockout(competition, teams, options)
    if competition.format == Competition.Format.LEAGUE_KNOCKOUT:
        return generate_league_and_knockout(competition, teams, options)
    if competition.format == Competition.Format.FREEFORM:
        return generate_round_robin(competition, teams[:4], options)
    return generate_round_robin(competition, teams, options)


def _staff_fixtures(
    competition: Competition,
    fixtures: list[Fixture],
    officials: list,
    actor,
    rosters: dict | None = None,
) -> None:
    if not fixtures:
        return
    if rosters is None:
        rosters = _rosters(competition)
    assigned_by = actor if getattr(actor, "is_authenticated", False) else None
    duration, overtime = default_game_time(competition.settings_json)
    referee = next(
        (row.user for row in officials if row.title == CompetitionOfficial.Title.REFEREE),
        officials[0].user if officials else None,
    )
    raters = [
        row.user
        for row in officials
        if row.title in {CompetitionOfficial.Title.REFEREE, CompetitionOfficial.Title.JUDGE}
    ]
    if len(raters) < 2 and officials:
        raters = [row.user for row in officials[:2]]
    sheet = team_sheet_config(competition)
    starters_needed = team_sheet_minimum(sheet) if sheet else 0
    # Team sheets for what has been played and the next week and a half; later rounds
    # are picked nearer the day, as a real league would.
    sheets_until = timezone.now() + timedelta(days=10)
    timed = []
    for fixture in fixtures:
        changed = False
        if duration and not fixture.duration_minutes:
            fixture.duration_minutes = duration
            changed = True
        if overtime and fixture.overtime_minutes is None:
            fixture.overtime_minutes = overtime
            changed = True
        if changed:
            fixture.updated_at = timezone.now()
            timed.append(fixture)
    if timed:
        Fixture.objects.bulk_update(
            timed, ["duration_minutes", "overtime_minutes", "updated_at"], batch_size=200
        )
    if referee is not None:
        FixtureReferee.objects.bulk_create(
            [FixtureReferee(fixture=fixture, user=referee) for fixture in fixtures],
            batch_size=200,
            ignore_conflicts=True,
        )
    if raters:
        FixtureRater.objects.bulk_create(
            [
                FixtureRater(fixture=fixture, user=rater, assigned_by=assigned_by)
                for fixture in fixtures
                for rater in raters
            ],
            batch_size=200,
            ignore_conflicts=True,
        )
    if starters_needed:
        soon = [
            fixture
            for fixture in fixtures
            if fixture.scheduled_at is None or fixture.scheduled_at <= sheets_until
        ]
        _submit_team_sheets(soon, starters_needed, actor, sheet, rosters)


def _demo_formation(starters_needed: int, sheet: dict | None, fixture: Fixture) -> str:
    formations = list((sheet or {}).get("formations") or [])
    if starters_needed >= 11:
        formations = formations or ["4-3-3", "4-4-2", "3-5-2"]
    elif starters_needed == 5:
        formations = formations or ["1-2-1", "2-2", "1-3"]
    if not formations:
        return "4-3-3" if starters_needed >= 11 else ""
    return formations[hash(str(fixture.id)) % len(formations)]


def _submit_team_sheets(
    fixtures: list[Fixture],
    starters_needed: int,
    actor,
    sheet: dict | None,
    rosters: dict,
) -> None:
    """Name every side's team for these fixtures: a handful of queries, not one per side."""

    from apps.fixtures.matchday import formation_slots

    if not fixtures:
        return
    submitted_by = actor if getattr(actor, "is_authenticated", False) else None
    sides = _sides_by_fixture(fixtures)
    slot_cache: dict[str, list] = {}

    def slots_for(formation: str) -> list:
        if formation not in slot_cache:
            try:
                slot_cache[formation] = (
                    formation_slots(formation, {**(sheet or {}), "starters": None})
                    if formation
                    else []
                )
            except ValidationError:
                slot_cache[formation] = []
        return slot_cache[formation]

    lineups, entries = [], []
    for fixture in fixtures:
        formation = _demo_formation(starters_needed, sheet, fixture)
        slots = slots_for(formation)
        for side in sides.get(fixture.id, []):
            members = rosters.get(side.participant_id, [])
            if len(members) < starters_needed:
                continue
            lineup = FixtureLineup(
                fixture=fixture,
                side=side,
                formation=formation,
                captain=members[0],
                submitted_by=submitted_by,
            )
            lineups.append(lineup)
            for index, member in enumerate(members):
                starter = index < starters_needed
                shirt = ""
                if starter and slots and index < len(slots):
                    shirt = slots[index].get("label") or ""
                entries.append(
                    LineupEntry(
                        lineup=lineup,
                        player=member,
                        role=LineupEntry.Role.STARTER if starter else LineupEntry.Role.BENCH,
                        slot=index if starter else None,
                        position=(shirt or member.position or "")[:20],
                        number=member.number or (index + 1),
                        order=index,
                    )
                )
    if not lineups:
        return
    # The demo writes each sheet once; anything older for these sides goes first.
    FixtureLineup.objects.filter(side_id__in=[lineup.side_id for lineup in lineups]).delete()
    FixtureLineup.objects.bulk_create(lineups, batch_size=200)
    LineupEntry.objects.bulk_create(entries, batch_size=500)


def _award_sample_points(competition: Competition, entrants: list[Participant], actor) -> int:
    if not _is_points_table(competition):
        return 0
    from apps.fixtures.services import award_criterion

    categories = list(competition.scoring_categories.order_by("display_order"))
    if not categories:
        return 0
    rng = random.Random(str(competition.id))
    awarded = 0
    for person in entrants:
        category = categories[awarded % len(categories)]
        award_criterion(
            competition=competition,
            participant=person,
            category=category,
            quantity=Decimal(str(rng.randint(1, 4))),
            note="Demo result so the table is not empty.",
            user=actor,
        )
        awarded += 1
    return awarded


def _live_candidate(fixtures: list[Fixture], now, sides: dict) -> Fixture | None:
    """The one demo match shown live: the next fixture with both sides known."""

    def ready(fixture: Fixture) -> bool:
        return (
            fixture.status == Fixture.Status.SCHEDULED
            and sum(1 for side in sides.get(fixture.id, []) if side.participant_id) >= 2
        )

    upcoming = sorted(
        (f for f in fixtures if f.scheduled_at and f.scheduled_at > now and ready(f)),
        key=lambda f: f.scheduled_at,
    )
    if upcoming:
        return upcoming[0]
    # A knockout's later rounds have no sides yet: keep the latest tie with both sides live.
    return next((f for f in reversed(fixtures) if ready(f)), None)


def _play_past_fixtures(
    competition: Competition, fixtures: list[Fixture], actor, rosters: dict
) -> tuple[int, Fixture | None]:
    category = (
        competition.scoring_categories.filter(affects_score=True).order_by("display_order").first()
        or competition.scoring_categories.order_by("display_order").first()
    )
    if category is None:
        return 0, None
    now = timezone.now()
    rng = random.Random(str(competition.id))
    sides = _sides_by_fixture(fixtures)
    live = _live_candidate(fixtures, now, sides)
    finished, goals = [], []
    for fixture in fixtures:
        if fixture.status == Fixture.Status.COMPLETED or fixture is live:
            continue
        if fixture.scheduled_at is None or fixture.scheduled_at > now:
            continue
        for side in sides.get(fixture.id, []):
            squad = rosters.get(side.participant_id, [])
            for _ in range(rng.randint(0, 3)):
                player = squad[rng.randrange(len(squad))] if squad else None
                goals.append(
                    ScoreEvent(
                        fixture=fixture,
                        side=side,
                        scoring_category=category,
                        player=player,
                        player_name=player.name if player is not None else "",
                        quantity=Decimal("1"),
                        minute=rng.randint(1, 90),
                        recorded_by=actor,
                    )
                )
        fixture.status = Fixture.Status.COMPLETED
        fixture.started_at = fixture.scheduled_at
        fixture.completed_at = fixture.scheduled_at + timedelta(minutes=95)
        fixture.updated_at = now
        finished.append(fixture)
    ScoreEvent.objects.bulk_create(goals, batch_size=500)
    if finished:
        Fixture.objects.bulk_update(
            finished, ["status", "started_at", "completed_at", "updated_at"], batch_size=200
        )
        for fixture in finished:
            fixture.recalculate_scores()
    played = len(finished)
    if live is not None:
        # Kicked off a few minutes ago, so the match is in play for the whole hour the demo lives.
        kickoff = now - timedelta(minutes=LIVE_FOR_MINUTES)
        live.status = Fixture.Status.LIVE
        live.phase = "first_half"
        live.scheduled_at = kickoff
        live.started_at = kickoff
        live.save(update_fields=["status", "phase", "scheduled_at", "started_at", "updated_at"])
        side = next(iter(sides.get(live.id, [])), None)
        if side is not None:
            squad = rosters.get(side.participant_id, [])
            player = squad[0] if squad else None
            ScoreEvent.objects.create(
                fixture=live,
                side=side,
                scoring_category=category,
                player=player,
                player_name=player.name if player is not None else "",
                quantity=Decimal("1"),
                minute=12,
                recorded_by=actor,
            )
            live.recalculate_scores()
    return played, live


def _starters(fixtures: list[Fixture], rosters: dict) -> dict:
    """Who started for each side of each rateable fixture: {fixture_id: [(side, players)]}.

    Named team sheets win; a side without one fields its first eleven. Three
    queries for the whole demo instead of three per side.
    """

    from apps.fixtures.raters import RATEABLE

    rateable = [fixture for fixture in fixtures if fixture.status in RATEABLE]
    sides = _sides_by_fixture(rateable)
    side_ids = [side.id for rows in sides.values() for side in rows]
    named: dict = {}
    if side_ids:
        entries = (
            LineupEntry.objects.filter(lineup__side_id__in=side_ids, role=LineupEntry.Role.STARTER)
            .select_related("player", "lineup")
            .order_by("order", "created_at")
        )
        for entry in entries:
            named.setdefault(entry.lineup.side_id, []).append(entry.player)
    out: dict = {}
    for fixture in rateable:
        rows = []
        for side in sides.get(fixture.id, []):
            if side.id in named:
                players = named[side.id]
            else:
                players = rosters.get(side.participant_id, [])[:11]
            rows.append((side, players))
        out[fixture.id] = rows
    return out


def _rate_players(fixtures: list[Fixture], starters: dict) -> int:
    from decimal import ROUND_HALF_UP

    from django.db.models import Avg, Count

    from apps.fixtures.models import PlayerMatchRating
    from apps.fixtures.raters import MIN_RATERS

    raters_by_fixture: dict = {}
    for rater in FixtureRater.objects.filter(fixture_id__in=list(starters)):
        raters_by_fixture.setdefault(rater.fixture_id, []).append(rater)
    appearances, scores, rated_fixtures = [], [], []
    for fixture in fixtures:
        if fixture.id not in starters:
            continue
        raters = raters_by_fixture.get(fixture.id, [])
        if len(raters) < 2:
            continue
        players = [player for _, side_players in starters[fixture.id] for player in side_players]
        if not players:
            continue
        rated_fixtures.append(fixture)
        appearances.extend(
            PlayerAppearance(fixture=fixture, player=member, minutes=90) for member in players
        )
        rng = random.Random(str(fixture.id))
        scores.extend(
            RaterScore(
                fixture=fixture,
                rater=rater,
                player=player,
                rating=Decimal(str(rng.randint(55, 90) / 10)),
            )
            for rater in raters
            for player in players
        )
    if not rated_fixtures:
        return 0
    PlayerAppearance.objects.bulk_create(appearances, batch_size=500, ignore_conflicts=True)
    RaterScore.objects.bulk_create(scores, batch_size=500, ignore_conflicts=True)
    # Publish each player's average, as `raters.recompute` does, for all fixtures at once.
    ids = [fixture.id for fixture in rated_fixtures]
    rows = (
        RaterScore.objects.filter(fixture_id__in=ids)
        .values("fixture_id", "player_id")
        .annotate(average=Avg("rating"), raters=Count("rater", distinct=True))
    )
    ratings = [
        PlayerMatchRating(
            fixture_id=row["fixture_id"],
            player_id=row["player_id"],
            rating=Decimal(row["average"]).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP),
        )
        for row in rows
        if row["raters"] >= MIN_RATERS
    ]
    PlayerMatchRating.objects.filter(fixture_id__in=ids).delete()
    PlayerMatchRating.objects.bulk_create(ratings, batch_size=500)
    return len(ratings)


def _is_keeper(player) -> bool:
    position = (getattr(player, "position", "") or "").lower()
    return "goalkeep" in position or position == "gk"


def _ensure_stat_categories(competition: Competition) -> None:
    """Older competitions only had goals and cards. Demos need the player-stat types too."""

    from apps.competitions.models import ScoringCategory
    from apps.competitions.stat_types import STAT_SCORE_TYPES

    settings = dict(competition.settings_json or {})
    rows = STAT_SCORE_TYPES.get(settings.get("preset") or "") or []
    if not rows:
        return
    have = set(competition.scoring_categories.values_list("code", flat=True))
    types = list(settings.get("score_types") or [])
    typed = {item.get("key") for item in types if isinstance(item, dict)}
    order = competition.scoring_categories.count()
    changed = False
    for row in rows:
        if row["key"] not in have:
            order += 1
            ScoringCategory.objects.create(
                competition=competition,
                code=row["key"],
                name=row["label"],
                points=row["value"],
                affects_score=False,
                description=row.get("description", ""),
                display_order=order,
            )
            changed = True
        if row["key"] not in typed:
            types.append(row)
            changed = True
    if changed:
        settings["score_types"] = types
        competition.settings_json = settings
        competition.save(update_fields=["settings_json", "updated_at"])


def _record_player_stats(
    competition: Competition, fixtures: list[Fixture], actor, starters: dict
) -> int:
    """Give every starter assists, tackles, saves and the other match stats."""

    _ensure_stat_categories(competition)
    categories = list(competition.scoring_categories.order_by("display_order"))
    stats = [
        category
        for category in categories
        if not category.affects_score and "card" not in (category.code or "")
    ]
    cards = [category for category in categories if "card" in (category.code or "")]
    if not stats and not cards:
        return 0
    keeper_pool = [category for category in stats if "save" in (category.code or "")] or stats
    outfield_pool = [category for category in stats if "save" not in (category.code or "")] or stats
    events = []
    for fixture in fixtures:
        if fixture.id not in starters:
            continue
        rng = random.Random(f"{fixture.id}-stats")
        for side, players in starters[fixture.id]:
            if not players:
                continue
            keepers = [player for player in players if _is_keeper(player)]
            for player in players:
                pool = keeper_pool if _is_keeper(player) else outfield_pool
                chosen = rng.sample(pool, k=min(len(pool), max(2, min(4, len(pool)))))
                for category in chosen:
                    quantity = Decimal(
                        str(rng.randint(2, 5 if category.code in {"shot", "tackle", "save"} else 3))
                    )
                    events.append(
                        ScoreEvent(
                            fixture=fixture,
                            side=side,
                            scoring_category=category,
                            player=player,
                            player_name=player.name,
                            quantity=quantity,
                            minute=rng.randint(1, 90),
                            recorded_by=actor,
                        )
                    )
            if cards and rng.random() < 0.45:
                outfield = [player for player in players if player not in keepers]
                booked = rng.choice(outfield or players)
                events.append(
                    ScoreEvent(
                        fixture=fixture,
                        side=side,
                        scoring_category=cards[0],
                        player=booked,
                        player_name=booked.name,
                        quantity=Decimal("1"),
                        minute=rng.randint(20, 85),
                        recorded_by=actor,
                    )
                )
    ScoreEvent.objects.bulk_create(events, batch_size=500)
    return len(events)


def _ensure_player_profiles(competition: Competition) -> int:
    from apps.scouting.catalog import sport_for_competition
    from apps.scouting.models import PlayerProfile, PlayerSport
    from apps.scouting.sample import (
        SAMPLE_ACCOUNT_FIELDS,
        fill_sample_profile,
        sample_account_details,
    )
    from apps.scouting.services import ensure_player_profile

    sport_key = sport_for_competition(competition.sport) or "soccer"
    members = list(
        RosterMember.objects.filter(
            participant__competition=competition,
            is_active=True,
            user__isnull=False,
        )
        .select_related("user", "participant")
        .order_by("participant__seed", "number", "created_at")
    )
    if not members:
        return 0
    have = {
        profile.user_id: profile
        for profile in PlayerProfile.objects.filter(user_id__in=[m.user_id for m in members])
    }
    now = timezone.now()
    users, fresh, teams, sports = [], [], [], []
    for index, member in enumerate(members):
        user = member.user
        user.date_of_birth = date(2001, 1 + index % 12, 1 + index % 27)
        if user.pk in have:
            continue
        # A complete, public, scout-ready profile in one row (what `ensure_player_profile`
        # followed by `fill_sample_profile` would arrive at, without the round trips).
        sample_account_details(user, sport=sport_key)
        user.updated_at = now
        users.append(user)
        profile = PlayerProfile(
            user=user,
            first_name=user.given_name or (user.email or "Player").split("@")[0][:80],
            last_name=user.family_name,
            date_of_birth=user.date_of_birth,
            photo_url=user.avatar_url,
            bio=user.bio,
            nationality=user.country,
            gender_category="men",
            region="gauteng",
            school_or_club=member.participant.name[:160],
            visibility=PlayerProfile.Visibility.PUBLIC,
            availability=PlayerProfile.Availability.AVAILABLE,
        )
        fresh.append(profile)
        teams.append(
            PlayerProfile.teams.through(playerprofile=profile, participant=member.participant)
        )
        sports.append(
            PlayerSport(
                profile=profile,
                sport=sport_key,
                primary_position=member.position or "central-midfield",
                is_primary=True,
            )
        )
    if users:
        User.objects.bulk_update(
            users,
            ["date_of_birth", *SAMPLE_ACCOUNT_FIELDS, "updated_at"],
            batch_size=100,
        )
    if fresh:
        PlayerProfile.objects.bulk_create(fresh, batch_size=200)
        PlayerProfile.teams.through.objects.bulk_create(
            teams, batch_size=200, ignore_conflicts=True
        )
        PlayerSport.objects.bulk_create(sports, batch_size=200)
    # Players who already had a profile (a demo re-run, or a real account) keep theirs
    # and are only topped up, the slow way, one by one.
    for member in members:
        profile = have.get(member.user_id)
        if profile is None:
            continue
        user = member.user
        user.save(update_fields=["date_of_birth", "updated_at"])
        profile = ensure_player_profile(user)
        if profile.visibility != PlayerProfile.Visibility.PUBLIC:
            profile.visibility = PlayerProfile.Visibility.PUBLIC
            profile.availability = PlayerProfile.Availability.AVAILABLE
            profile.save(update_fields=["visibility", "availability", "updated_at"])
        profile.teams.add(member.participant)
        if member.position:
            PlayerSport.objects.get_or_create(
                profile=profile,
                sport=sport_key,
                defaults={"primary_position": member.position, "is_primary": True},
            )
        fill_sample_profile(profile, sport=sport_key, club=member.participant.name)
    return len(fresh)


def _pick_league_squad(competition: Competition, actor) -> int:
    if _participant_type(competition) != "team" or _is_points_table(competition):
        return 0
    from apps.scouting import selection
    from apps.scouting.models import LeagueSquad

    template = selection.template_for(competition)
    squad, _ = LeagueSquad.objects.get_or_create(
        competition=competition,
        defaults={
            "size": template["size"],
            "name": f"{competition.name} squad",
        },
    )
    selection.generate(squad, by=actor if getattr(actor, "is_authenticated", False) else None)
    if not squad.picks.exists():
        return 0
    squad.status = LeagueSquad.Status.PUBLISHED
    squad.published_at = timezone.now()
    squad.notified_users = [str(user_id) for user_id in squad.picks.values_list("user_id", flat=True)]
    squad.save(update_fields=["status", "published_at", "notified_users", "updated_at"])
    return squad.picks.count()


def _mark_unavailable(competition: Competition) -> None:
    """One injured and one suspended substitute, taken off every upcoming team sheet."""

    upcoming = LineupEntry.objects.filter(
        lineup__fixture__competition=competition, lineup__fixture__status=Fixture.Status.SCHEDULED
    )
    busy = LineupEntry.objects.filter(
        Q(lineup__fixture__status=Fixture.Status.LIVE)
        | Q(lineup__fixture__status=Fixture.Status.SCHEDULED, role=LineupEntry.Role.STARTER),
        lineup__fixture__competition=competition,
    ).values_list("player_id", flat=True)
    spare = list(
        RosterMember.objects.filter(participant__competition=competition, is_active=True)
        .exclude(pk__in=busy)
        .order_by("participant__name", "number", "name")[:2]
    )
    upcoming.filter(player__in=spare).delete()
    today = timezone.localdate()
    marks = [
        (RosterMember.Availability.INJURED, "Hamstring strain", today + timedelta(days=10)),
        (RosterMember.Availability.SUSPENDED, "Red card — one-match ban", today + timedelta(days=7)),
    ]
    for member, (status, note, back) in zip(spare, marks):
        member.availability = status
        member.availability_note = note
        member.available_from = back
        member.save(update_fields=["availability", "availability_note", "available_from", "updated_at"])


def _fill_fantasy(competition: Competition, actor) -> int:
    from apps.fantasy.services import available

    if not available(competition):
        return 0
    from rest_framework.exceptions import ValidationError as ApiValidationError

    from apps.fantasy.models import FantasyTeam
    from apps.fantasy.scoring import season_totals
    from apps.fantasy.services import auto_pick, save_team

    managers = []
    if getattr(actor, "is_authenticated", False):
        managers.append(actor)
    for member in RosterMember.objects.filter(
        participant__competition=competition,
        is_active=True,
        user__isnull=False,
    ).select_related("user")[:6]:
        if member.user_id == getattr(actor, "id", None):
            continue
        managers.append(member.user)
        if len(managers) >= 3:
            break
    if not managers:
        return 0
    # Worked out once for the auto-pick and every squad saved from it.
    totals = season_totals(competition)
    try:
        picks = auto_pick(competition, totals)
    except ApiValidationError:
        return 0
    made = 0
    for index, user in enumerate(managers):
        name = "Demo XI" if index == 0 else f"{user.get_short_name()}'s XI"
        try:
            save_team(competition, user, name=name, raw_picks=picks, totals=totals)
        except ApiValidationError:
            continue
        made += 1
    return FantasyTeam.objects.filter(competition=competition).count() or made


# --- The demo cup -------------------------------------------------------------
#
# A full 16-team bracket, every round scheduled: the round of 16 played two weeks
# ago (one tie settled on penalties), quarter-finals today with one in play and
# one in a shootout, then the semi-finals and final ahead. Ties whose teams are
# not known yet wait without sides until the bracket is advanced.

CUP_ROUND_NAMES = ["Round of 16", "Quarter-finals", "Semi-finals", "Final"]


def _prepare_cup(competition: Competition):
    """The cup stage for the demo bracket: a Stage, None for a pure knockout, or False for none."""

    if _is_points_table(competition):
        return False
    if competition.format == Competition.Format.KNOCKOUT:
        return None
    if competition.format == Competition.Format.LEAGUE:
        # A demo shows everything, so a plain league also gets a cup.
        competition.format = Competition.Format.LEAGUE_KNOCKOUT
        competition.save(update_fields=["format", "updated_at"])
    if competition.format != Competition.Format.LEAGUE_KNOCKOUT:
        return False
    from .cups import ensure_league_and_cup_stages

    _, cups = ensure_league_and_cup_stages(competition)
    return cups[0] if cups else False


def _drop_generated_cup(competition: Competition, fixtures: list[Fixture], stage) -> list[Fixture]:
    """The schedulers write cup round 1 only; the demo writes the whole bracket itself."""

    if competition.format == Competition.Format.KNOCKOUT:
        Fixture.objects.filter(id__in=[f.id for f in fixtures]).delete()
        return []
    cup_ids = {f.id for f in fixtures if stage is not None and f.stage_id == stage.id}
    Fixture.objects.filter(id__in=cup_ids).delete()
    settings = dict(competition.settings_json or {})
    settings["cup_slot_datetimes"] = []
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])
    return [f for f in fixtures if f.id not in cup_ids]


def _cup_fixture(competition, stage, round_number: int, index: int, when, pair=None) -> Fixture:
    from apps.fixtures.models import FixtureSide

    prefix = stage.name if stage is not None else "Cup"
    fixture = Fixture.objects.create(
        competition=competition,
        stage=stage,
        round_number=round_number,
        label=f"{prefix} {CUP_ROUND_NAMES[round_number - 1].lower()} — match {index + 1}",
        scheduled_at=when,
        location="Demo stadium",
    )
    if pair is not None:
        home, away = pair
        FixtureSide.objects.create(fixture=fixture, participant=home, position=0, is_home=True)
        FixtureSide.objects.create(fixture=fixture, participant=away, position=1, is_home=False)
    return fixture


def _goal_category(competition: Competition):
    return (
        competition.scoring_categories.filter(affects_score=True).order_by("display_order").first()
    )


def _score_goals(
    fixture: Fixture, side, goals: int, rng, actor, category, rosters: dict, minutes=(1, 90)
) -> None:
    squad = rosters.get(side.participant_id, [])
    outfield = [p for p in squad if not _is_keeper(p)] or squad
    ScoreEvent.objects.bulk_create(
        [
            ScoreEvent(
                fixture=fixture,
                side=side,
                scoring_category=category,
                player=player,
                player_name=player.name if player is not None else "",
                quantity=Decimal("1"),
                minute=rng.randint(*minutes),
                recorded_by=actor,
            )
            for player in (rng.choice(outfield) if outfield else None for _ in range(goals))
        ]
    )


def _shootout_kicks(fixture: Fixture, rng, pattern: list[tuple[bool, bool]]) -> list[dict]:
    """Kicks in turn from each side's players on the pitch, one (home, away) pair per round."""

    from apps.fixtures.phases import eligible_kickers

    home, away = list(fixture.sides.order_by("position"))
    pools = {side.id: eligible_kickers(fixture, side) for side in (home, away)}
    kicks = []
    for round_index, (home_scores, away_scores) in enumerate(pattern):
        for side, scored in ((home, home_scores), (away, away_scores)):
            pool = pools[side.id]
            if not pool:
                continue
            taker = pool[(len(pool) - 1 - round_index) % len(pool)]
            kicks.append(
                {"side": str(side.id), "player": taker["player_id"], "name": taker["name"],
                 "scored": scored}
            )
    return kicks


def _finish(fixture: Fixture, kickoff) -> None:
    fixture.status = Fixture.Status.COMPLETED
    fixture.phase = "full_time"
    fixture.started_at = kickoff
    fixture.completed_at = kickoff + timedelta(minutes=110)
    fixture.save(
        update_fields=["status", "phase", "shootout", "started_at", "completed_at", "updated_at"]
    )
    fixture.recalculate_scores()


def _play_to(
    fixture: Fixture, home_goals: int, away_goals: int, rng, actor, category, rosters: dict
) -> None:
    home, away = list(fixture.sides.order_by("position"))
    _score_goals(fixture, home, home_goals, rng, actor, category, rosters)
    _score_goals(fixture, away, away_goals, rng, actor, category, rosters)


def _winner(fixture: Fixture):
    fixture.refresh_from_db()
    side = fixture.sides.filter(outcome="win").select_related("participant").first()
    return side.participant if side is not None else None


def _build_cup(
    competition: Competition, teams: list[Participant], stage, officials, actor, rosters: dict
) -> dict:
    from apps.fixtures.services import knockout_slots

    category = _goal_category(competition)
    pairs = [pair for pair in knockout_slots(teams) if pair[1] is not None]
    if category is None or len(pairs) < 8:
        return {}
    rng = random.Random(f"{competition.id}-cup")
    now = timezone.now()
    today_three = now.replace(hour=15, minute=0, second=0, microsecond=0)
    round_one_at = today_three - timedelta(days=14)
    staffed = []

    # Round of 16, two weeks ago. Match 3 is level and goes to penalties.
    round_one = [
        _cup_fixture(competition, stage, 1, index, round_one_at + timedelta(minutes=30 * (index % 2)), pair)
        for index, pair in enumerate(pairs[:8])
    ]
    _staff_fixtures(competition, round_one, officials, actor, rosters)
    staffed += round_one
    for index, fixture in enumerate(round_one):
        if index == 2:
            _play_to(fixture, 1, 1, rng, actor, category, rosters)
            fixture.shootout = _shootout_kicks(
                fixture, rng, [(True, True), (True, False), (True, True), (True, True), (True, True)]
            )
        else:
            home_goals = rng.randint(1, 4)
            away_goals = rng.randint(0, home_goals - 1)
            _play_to(fixture, home_goals, away_goals, rng, actor, category, rosters)
        _finish(fixture, fixture.scheduled_at)
    winners = [_winner(fixture) for fixture in round_one]

    # Quarter-finals today: two finished, one in play, one in a penalty shootout.
    quarter_pairs = [(winners[i], winners[i + 1]) for i in range(0, 8, 2)]
    kickoffs = [
        now - timedelta(hours=5),
        now - timedelta(hours=3, minutes=30),
        now - timedelta(minutes=72),
        now - timedelta(minutes=138),
    ]
    quarters = [
        _cup_fixture(competition, stage, 2, index, kickoffs[index], pair)
        for index, pair in enumerate(quarter_pairs)
    ]
    _staff_fixtures(competition, quarters, officials, actor, rosters)
    staffed += quarters
    played = 8
    for fixture in quarters[:2]:
        _play_to(fixture, 2, 1, rng, actor, category, rosters)
        _finish(fixture, fixture.scheduled_at)
        played += 1

    live_cup = quarters[2]
    _play_to(live_cup, 1, 0, rng, actor, category, rosters)
    live_cup.status = Fixture.Status.LIVE
    live_cup.phase = "second_half"
    live_cup.started_at = live_cup.scheduled_at
    live_cup.save(update_fields=["status", "phase", "started_at", "updated_at"])
    live_cup.recalculate_scores()

    penalties = quarters[3]
    _play_to(penalties, 2, 2, rng, actor, category, rosters)
    penalties.shootout = _shootout_kicks(
        penalties, rng, [(True, True), (False, True), (True, False)]
    )
    penalties.status = Fixture.Status.LIVE
    penalties.phase = "penalties"
    penalties.started_at = penalties.scheduled_at
    penalties.save(update_fields=["status", "phase", "shootout", "started_at", "updated_at"])
    penalties.recalculate_scores()

    # Semi-finals next week (the first already has its teams), final the week after.
    semi_one = _cup_fixture(
        competition,
        stage,
        3,
        0,
        today_three + timedelta(days=7),
        (_winner(quarters[0]), _winner(quarters[1])),
    )
    semi_two = _cup_fixture(competition, stage, 3, 1, today_three + timedelta(days=7, hours=2))
    final = _cup_fixture(competition, stage, 4, 0, today_three + timedelta(days=14))
    _staff_fixtures(competition, [semi_one, semi_two, final], officials, actor, rosters)

    return {
        "fixtures": [*round_one, *quarters, semi_one, semi_two, final],
        "played": played,
        "live": str(live_cup.id),
        "penalties": str(penalties.id),
        "stage": str(stage.id) if stage is not None else None,
    }
