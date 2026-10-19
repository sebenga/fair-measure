"""Winter Olympic locked presets: every Winter event is available, one full event per
sport group runs through a Games into the medal table, and ice hockey keeps the
IIHF 3-2-1-0 points."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.competitions.models import Competition, Participant
from apps.competitions.olympic_presets import WINTER_PRESETS
from apps.competitions.presets import PRESETS, apply_preset
from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent
from apps.games import olympic_catalog as catalog
from apps.games import services
from apps.games.models import NOC, Athlete, Games, GamesOfficial, Medal
from apps.results import services as results
from apps.results.calculators import evaluate
from apps.standings.services import compute_standings

User = get_user_model()
CODES = ("NOR", "GER", "ITA", "CAN")
PODIUM = [("bronze", "ITA"), ("gold", "GER"), ("silver", "NOR")]


def test_every_winter_event_has_a_locked_preset():
    for sport_row in catalog.WINTER:
        for discipline in sport_row["disciplines"]:
            for event in discipline["events"]:
                key = catalog.preset_for(sport_row, discipline, event)
                assert key in PRESETS, (sport_row["key"], event["name"], key)
    for key, preset in WINTER_PRESETS.items():
        assert preset["governing_body"] and preset["rulebook"], key
        assert preset["locked"] and preset["official_results"], key


@pytest.fixture
def games(db):
    owner = User.objects.create_user(email="owner@winter.test", password="pw-123456789")
    games = Games.objects.create(name="Winter Games", owner=owner, kind=Games.Kind.WINTER)
    delegate = User.objects.create_user(email="td@winter.test", password="pw-123456789")
    GamesOfficial.objects.create(games=games, user=delegate)
    for code in CODES:
        NOC.objects.create(games=games, code=code, name=code)
    games.delegate = delegate
    return games


def _medals_for(games, sport_key, discipline, event_name, data):
    key = catalog.event_key(sport_key, discipline, event_name)
    created = services.add_catalog_events(games, [key])["created"]
    assert created, f"{key} should be available"
    event = created[0]
    entries = []
    for code in CODES[: len(data)]:
        noc = games.nocs.get(code=code)
        if event.kind == "team":
            entries.append(services.add_entry(event, noc))
        else:
            athlete = Athlete.objects.create(games=games, noc=noc, name=f"{event_name} {code}")
            entries.append(services.add_entry(event, noc, athlete))
    fixture = results.create_event(event.competition, label="Final", actor=games.owner)
    sides = {side.participant_id: side for side in fixture.sides.all()}
    results.save_results(
        fixture,
        [
            {"side": str(sides[entry.participant_id].id), "data": row}
            for entry, row in zip(entries, data, strict=True)
        ],
        games.owner,
    )
    results.finalise(fixture, games.delegate)
    return sorted((row.medal, row.noc.code) for row in Medal.objects.filter(event=event))


def _judged(*runs):
    return {"attempts": [{"scores": [value] * 5} for value in runs]}


EVENTS = [
    (
        "alpine downhill",
        ("alpine_skiing", "Speed", "Men's Downhill"),
        [{"time": "103.10"}, {"time": "102.95"}, {"time": "103.42"}, {"status": "DNF"}],
    ),
    (
        "alpine giant slalom",
        ("alpine_skiing", "Technical", "Women's Giant slalom"),
        [
            {"runs": ["61.20", "60.10"]},
            {"runs": ["60.90", "60.20"]},
            {"runs": ["61.50", "60.30"]},
            {"status": "DNF"},  # missed a gate in run 2
        ],
    ),
    (
        "biathlon individual",
        ("biathlon", "Biathlon", "Men's Individual"),
        [
            {"time": "2950.0", "misses": 1},  # 2950 + 60 = 3010
            {"time": "2990.0", "misses": 0},  # fastest total
            {"time": "2900.0", "misses": 3},  # fastest skier, but 2900 + 180 = 3080
            {"time": "3200.0", "misses": 0},
        ],
    ),
    (
        "biathlon pursuit",
        ("biathlon", "Biathlon", "Women's Pursuit"),
        [{"position": 2, "misses": 1}, {"position": 1}, {"position": 3}, {"position": 4}],
    ),
    (
        "bobsleigh",
        ("bobsleigh", "Skeleton", "Women's Skeleton"),
        [
            {"runs": ["57.10", "57.20", "57.05", "57.30"]},
            {"runs": ["57.00", "57.10", "57.00", "57.20"]},
            {"runs": ["57.40", "57.30", "57.20", "57.30"]},
            {"runs": ["57.50", "57.60", "57.70", "57.80"]},
        ],
    ),
    (
        "luge",
        ("luge", "Luge", "Men's Singles"),
        [
            {"runs": ["47.101", "47.200", "47.150", "47.300"]},
            {"runs": ["47.100", "47.200", "47.150", "47.300"]},
            {"runs": ["47.300", "47.400", "47.350", "47.500"]},
            {"runs": ["47.500", "47.600", "47.650", "47.700"]},
        ],
    ),
    (
        "cross-country mass start",
        ("cross_country", "Cross-country", "Women's Mass start"),
        [{"position": 2}, {"position": 1}, {"position": 3}, {"position": 4}],
    ),
    (
        "nordic combined",
        ("nordic_combined", "Nordic combined", "Individual normal hill"),
        [
            {"position": 2, "jump_points": 120, "start_gap": "0:00"},
            {"position": 1, "jump_points": 115, "start_gap": "0:20"},
            {"position": 3},
            {"position": 4},
        ],
    ),
    (
        "short track",
        ("short_track", "Short track", "Men's 500 m"),
        [{"position": 3}, {"position": 2}, {"position": 4}, {"status": "PEN"}],
    ),
    (
        "speed skating",
        ("speed_skating", "Speed skating", "Women's 500 m"),
        [{"time": "37.10"}, {"time": "36.95"}, {"time": "37.40"}, {"time": "37.90"}],
    ),
    (
        "speed skating mass start",
        ("speed_skating", "Speed skating", "Men's Mass start"),
        [{"rounds": [3, 40]}, {"rounds": [1, 60]}, {"rounds": [5, 20]}, {"rounds": [6]}],
    ),
    (
        "figure skating",
        ("figure_skating", "Figure skating", "Women's Singles"),
        [
            {
                "attempts": [
                    {"extras": {"tes": "40.10", "pcs": "34.00"}},
                    {"extras": {"tes": "75.0", "pcs": "70.0"}, "penalty": 1},
                ]
            },
            {
                "attempts": [
                    {"extras": {"tes": "42.00", "pcs": "35.00"}},
                    {"extras": {"tes": "78.0", "pcs": "71.0"}},
                ]
            },
            {
                "attempts": [
                    {"extras": {"tes": "38.00", "pcs": "33.00"}},
                    {"extras": {"tes": "72.0", "pcs": "68.0"}},
                ]
            },
            {
                "attempts": [
                    {"extras": {"tes": "30.00", "pcs": "30.00"}},
                    {"extras": {"tes": "60.0", "pcs": "60.0"}},
                ]
            },
        ],
    ),
    (
        "freestyle halfpipe",
        ("freestyle", "Freestyle skiing", "Men's Halfpipe"),
        [_judged(80, 88), _judged(92, 40), _judged(85, 70), _judged(60, 61)],
    ),
    (
        "snowboard big air",
        ("freestyle", "Snowboard", "Women's Big air"),
        [_judged(90, 80, 10), _judged(88, 86, 30), _judged(95, 60, 20), _judged(70, 70, 70)],
    ),
    (
        "ski and snowboard cross",
        ("freestyle", "Snowboard", "Men's Snowboard cross"),
        [{"position": 2}, {"position": 1}, {"position": 3}, {"position": 4}],
    ),
    (
        "ski jumping",
        ("ski_jumping", "Ski jumping", "Women's Normal hill"),
        [
            # 60 + (100 - 98) x 2 = 64 distance points + 3 x 18 style = 118 per jump
            {
                "attempts": [
                    {"distance": 100, "scores": [18] * 5},
                    {"distance": 100, "scores": [18] * 5},
                ]
            },
            {
                "attempts": [
                    {"distance": 102, "scores": [18] * 5},
                    {"distance": 101, "scores": [18] * 5},
                ]
            },
            {
                "attempts": [
                    {"distance": 101, "scores": [17] * 5, "extras": {"wind": "-2.5"}},
                    {"distance": 100, "scores": [17] * 5},
                ]
            },
            {
                "attempts": [
                    {"distance": 90, "scores": [16] * 5},
                    {"distance": 92, "scores": [16] * 5},
                ]
            },
        ],
    ),
    (
        "ski mountaineering",
        ("ski_mountaineering", "Ski mountaineering", "Women's Sprint"),
        [{"position": 2}, {"position": 1}, {"position": 3}, {"position": 4}],
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize("where, data", [row[1:] for row in EVENTS], ids=[row[0] for row in EVENTS])
def test_a_full_winter_event_awards_medals(games, where, data):
    assert _medals_for(games, *where, data) == PODIUM


@pytest.mark.django_db
def test_winter_medals_roll_into_the_medal_table(games):
    _medals_for(games, *EVENTS[0][1], EVENTS[0][2])
    _medals_for(games, *EVENTS[9][1], EVENTS[9][2])
    table = {row["code"]: row for row in services.medal_table(games)}
    assert (table["GER"]["gold"], table["NOR"]["silver"], table["ITA"]["bronze"]) == (2, 2, 2)
    assert table["GER"]["rank"] == 1


def test_biathlon_adds_a_minute_per_miss_and_ski_jumping_scores_distance():
    biathlon = evaluate(
        "timed_lowest",
        {"a": {"time": "2950.0", "misses": 2}},
        PRESETS["biathlon_individual"]["result_config"],
    )["a"][2]
    assert biathlon.primary == Decimal("3070.0")
    assert biathlon.breakdown["penalty_seconds"] == "120"
    jump = evaluate(
        "judged_score",
        {"a": {"attempts": [{"distance": "104.5", "scores": [18, "18.5", 19, 17, 20]}]}},
        {**PRESETS["ski_jumping"]["result_config"], "attempts": 1},
    )["a"][2]
    # 60 + 6.5 x 2.0 = 73 distance points; style drops 17 and 20: 18 + 18.5 + 19 = 55.5
    assert jump.primary == Decimal("128.5")


# --- Ice hockey and curling: head-to-head through standings ----------------------------


def _team_competition(key: str, names: list[str]):
    owner = User.objects.create_user(email=f"{key}@winter.test", password="pw-123456789")
    competition = Competition.objects.create(name=key, owner=owner, sport="x")
    apply_preset(competition, key)
    teams = [
        Participant.objects.create(competition=competition, name=name, kind=Participant.Kind.TEAM)
        for name in names
    ]
    return competition, teams


def _play(competition, home, away, scores: list[tuple]):
    """``scores`` is a list of (side 0 or 1, unit index, score type)."""

    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    sides = [
        FixtureSide.objects.create(fixture=fixture, participant=home, position=0, is_home=True),
        FixtureSide.objects.create(fixture=fixture, participant=away, position=1),
    ]
    for side_index, unit, code in scores:
        ScoreEvent.objects.create(
            fixture=fixture,
            side=sides[side_index],
            scoring_category=competition.scoring_categories.get(code=code),
            unit_index=unit,
        )
    fixture.status = Fixture.Status.COMPLETED
    fixture.completed_at = timezone.now()
    fixture.save()
    fixture.recalculate_scores()
    return fixture


@pytest.mark.django_db
def test_ice_hockey_gives_three_two_one_zero():
    competition, (can, swe, fin) = _team_competition("ice_hockey", ["CAN", "SWE", "FIN"])
    assert competition.settings_json["league_points"]["extra_time_win"] == 2
    goal, shootout = "goal", "shootout-goal"
    _play(competition, can, swe, [(0, 0, goal), (0, 1, goal), (1, 2, goal)])  # CAN 2-1
    _play(competition, swe, fin, [(0, 0, goal), (1, 1, goal), (0, 3, goal)])  # SWE in OT
    _play(competition, fin, can, [(0, 0, goal), (1, 2, goal), (0, 4, shootout)])  # FIN, SO
    rows = {row.name: row.points for row in compute_standings(competition)}
    # CAN: regulation win 3 + shoot-out loss 1; SWE: regulation loss 0 + OT win 2;
    # FIN: OT loss 1 + shoot-out win 2.
    assert rows == {"CAN": Decimal("4"), "SWE": Decimal("2"), "FIN": Decimal("3")}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "key, decider",
    [("ice_hockey", "shootout-goal"), ("water_polo", "shootout-goal"), ("handball", "seven-metre")],
)
def test_a_shoot_out_decides_a_level_game(key, decider):
    competition, (home, away) = _team_competition(key, ["Home", "Away"])
    competition.format = "knockout"
    competition.save(update_fields=["format"])
    # Level 1-1; the away side wins the shoot-out (unit 4 in each of these presets).
    fixture = _play(competition, home, away, [(0, 0, "goal"), (1, 1, "goal"), (1, 4, decider)])
    assert {side.participant.name: str(side.score) for side in fixture.sides.all()} == {
        "Home": "1.00",
        "Away": "1.00",
    }
    assert fixture.sides.get(outcome=FixtureSide.Outcome.WIN).participant == away


@pytest.mark.django_db
def test_curling_extra_end_decides_a_level_game():
    competition, (ita, gbr) = _team_competition("curling", ["ITA", "GBR"])
    # Level 2-2 after ten ends; ITA steals one in the extra end (unit 10).
    ends = [(0, 1), (1, 3), (0, 6), (1, 8), (0, 10)]
    fixture = _play(competition, ita, gbr, [(side, end, "stone") for side, end in ends])
    winner = fixture.sides.get(outcome=FixtureSide.Outcome.WIN)
    assert winner.participant == ita
    rows = {row.name: row.points for row in compute_standings(competition)}
    assert rows == {"ITA": Decimal("1"), "GBR": Decimal("0")}
