"""Summer Olympic locked presets: governance on every preset, the catalogue linked to
them, and one full event per result type through a Games into medals."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.competitions.olympic_presets import GOVERNANCE, OLYMPIC_PRESETS
from apps.competitions.presets import PRESETS, apply_preset
from apps.games import olympic_catalog as catalog
from apps.games import services
from apps.games.models import NOC, Athlete, Games, GamesOfficial, Medal
from apps.results import services as results
from apps.results.calculators import CALCULATORS

User = get_user_model()

# Every FEI discipline now has its locked equestrian preset.
EQUESTRIAN: set[str] = set()


def _summer_presets() -> set[str]:
    keys = set()
    for sport_row in catalog.SUMMER:
        for discipline in sport_row["disciplines"]:
            for event in discipline["events"]:
                keys.add(catalog.preset_for(sport_row, discipline, event))
    return keys


def test_every_olympic_preset_names_its_federation_rulebook_and_scoring():
    for key in [*OLYMPIC_PRESETS, *GOVERNANCE]:
        preset = PRESETS[key]
        assert preset.get("governing_body"), key
        assert preset.get("rulebook"), key
        assert len(preset.get("description") or "") > 30, key
        assert preset.get("locked") is True, key
    for key, preset in OLYMPIC_PRESETS.items():
        assert preset.get("official_results") is True, key
        if preset.get("result_type"):
            assert preset["result_type"] in CALCULATORS, key
            assert preset["statuses"], key
        else:
            assert preset["contest_type"] == "head_to_head" and preset["score_types"], key


def test_every_summer_event_has_a_locked_preset_except_the_fei_disciplines():
    missing = {key for key in _summer_presets() if key not in PRESETS}
    assert missing == EQUESTRIAN


def test_presets_cover_every_olympic_result_type():
    used = {preset.get("result_type") for preset in OLYMPIC_PRESETS.values()}
    for result_type in (
        "timed_lowest",
        "measured_highest",
        "judged_score",
        "points_highest",
        "points_lowest",
        "combat_decision",
        "multi_run_aggregate",
        "combined_events",
        "finishing_order",
    ):
        assert result_type in used, result_type


@pytest.mark.django_db
def test_head_to_head_presets_apply_with_their_scoring():
    from apps.competitions.models import Competition

    owner = User.objects.create_user(email="h2h@olympic.test", password="pw-123456789")
    for key in ("water_polo", "handball", "beach_volleyball", "fencing", "rugby_sevens"):
        competition = Competition.objects.create(name=key, owner=owner, sport="x")
        apply_preset(competition, key)
        settings = competition.settings_json
        assert settings["locked"] is True and settings["official_results"] is True
        assert settings["governing_body"] == PRESETS[key]["governing_body"]
        codes = set(competition.scoring_categories.values_list("code", flat=True))
        assert {item["key"] for item in PRESETS[key]["score_types"]} <= codes
    fencing = Competition.objects.get(name="fencing")
    assert fencing.settings_json["target"] == 15
    assert fencing.settings_json["win_condition"] == "first_to_target"


# --- One full event per result type, through a Games ------------------------------------

CODES = ("RSA", "KEN", "BRA", "JPN")


@pytest.fixture
def games(db):
    owner = User.objects.create_user(email="owner@olympic.test", password="pw-123456789")
    games = Games.objects.create(name="Preset Games", owner=owner, kind=Games.Kind.SUMMER)
    delegate = User.objects.create_user(email="td@olympic.test", password="pw-123456789")
    GamesOfficial.objects.create(games=games, user=delegate)
    for code in CODES:
        NOC.objects.create(games=games, code=code, name=code)
    games.delegate = delegate
    return games


def _medals_for(games, sport_key: str, discipline: str, event_name: str, data: list[dict]):
    key = catalog.event_key(sport_key, discipline, event_name)
    created = services.add_catalog_events(games, [key])["created"]
    assert created, f"{key} should be available"
    event = created[0]
    entries = []
    for code in CODES[: len(data)]:
        noc = games.nocs.get(code=code)
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


GOLD_KEN_SILVER_RSA_BRONZE_JPN = [("bronze", "JPN"), ("gold", "KEN"), ("silver", "RSA")]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "where, data",
    [
        (
            ("aquatics", "Swimming", "Men's 100 m freestyle"),
            [{"time": "47.80"}, {"time": "47.51"}, {"time": "48.90"}, {"time": "48.02"}],
        ),
        (
            ("athletics", "Throws", "Women's Javelin throw"),
            [
                {"attempts": ["61.10", "x", "62.00"]},
                {"attempts": ["64.50"]},
                {"attempts": ["x", "x", "x"]},
                {"attempts": ["60.00", "61.80"]},
            ],
        ),
        (
            ("athletics", "Vertical jumps", "Men's High jump"),
            [
                {"heights": {"2.30": "o", "2.33": "xo", "2.36": "xxx"}},
                {"heights": {"2.30": "o", "2.33": "o", "2.36": "xxx"}},
                {"heights": {"2.30": "xxx"}},
                {"heights": {"2.30": "xo", "2.33": "xxx"}},
            ],
        ),
        (
            ("aquatics", "Diving", "Women's 10 m platform"),
            [
                {"attempts": [{"scores": [8, 8, 8, 8, 8, 8, 8], "difficulty": "3.0"}]},
                {"attempts": [{"scores": [9, 9, 9, 9, 9, 9, 9], "difficulty": "3.0"}]},
                {"attempts": [{"scores": [5, 5, 5, 5, 5, 5, 5], "difficulty": "3.0"}]},
                {"attempts": [{"scores": [7, 7, 7, 7, 7, 7, 7], "difficulty": "3.0"}]},
            ],
        ),
        (
            ("shooting", "Shooting", "Men's 10 m air rifle"),
            [
                {"rounds": ["104.5", "105.1"]},
                {"rounds": ["105.9", "106.0"]},
                {"rounds": ["100.2"]},
                {"rounds": ["103.0", "104.4"]},
            ],
        ),
        (
            ("sailing", "Sailing", "Women's ILCA dinghy"),
            [
                {"rounds": [2, 2, 3, 2]},
                {"rounds": [1, 1, 9, 1]},
                {"rounds": [5, 6, 5, 6]},
                {"rounds": [3, 4, 2, 3]},
            ],
        ),
        (
            ("canoe", "Canoe slalom", "Men's K1"),
            [
                {"runs": [{"time": "90.10", "touches": 1}]},
                {"runs": [{"time": "89.00"}]},
                {"runs": [{"time": "85.00", "missed": 1}]},
                {"runs": [{"time": "92.40"}]},
            ],
        ),
        (
            ("triathlon", "Triathlon", "Women's Individual"),
            [{"position": 2}, {"position": 1}, {"position": 4}, {"position": 3}],
        ),
        (
            ("weightlifting", "Weightlifting", "Men's -89 kg / -71 kg"),
            [
                {
                    "lifts": {"snatch": ["170", "175"], "clean_jerk": ["205", "x"]},
                    "total_reached_at": 4,
                },
                {"lifts": {"snatch": ["172", "176"], "clean_jerk": ["210"]}, "total_reached_at": 2},
                {"lifts": {"snatch": ["180"], "clean_jerk": ["x", "x", "x"]}},
                {"lifts": {"snatch": ["170", "175"], "clean_jerk": ["205"]}, "total_reached_at": 7},
            ],
        ),
    ],
    ids=lambda value: value[1] if isinstance(value, tuple) else None,
)
def test_a_full_event_awards_medals(games, where, data):
    assert _medals_for(games, *where, data) == GOLD_KEN_SILVER_RSA_BRONZE_JPN


@pytest.mark.django_db
def test_a_full_heptathlon_uses_the_heptathlon_table(games):
    strong = {
        "100m_hurdles": "13.00",
        "high_jump": "1.86",
        "shot_put": "14.50",
        "200m": "23.50",
        "long_jump": "6.60",
        "javelin": "48.00",
        "800m": "128.00",
    }
    weaker = {**strong, "800m": "136.00"}
    weakest = {**strong, "800m": "140.00", "javelin": "40.00"}
    data = [
        {"marks": weaker},
        {"marks": strong},
        {"marks": {**weakest, "high_jump": "1.60"}},
        {"marks": weakest},
    ]
    assert (
        _medals_for(games, "athletics", "Combined events", "Women's heptathlon", data)
        == GOLD_KEN_SILVER_RSA_BRONZE_JPN
    )
    event = games.events.get(name="Women's heptathlon")
    assert event.preset_key == "combined_events_heptathlon"


@pytest.mark.django_db
def test_a_boxing_final_on_the_cards(games):
    medals = _medals_for(
        games,
        "boxing",
        "Boxing",
        "Men's Flyweight",
        [{"cards": [28, 28, 29, 27, 28]}, {"cards": [29, 29, 28, 30, 29]}],
    )
    assert medals == [("gold", "KEN"), ("silver", "RSA")]


@pytest.mark.django_db
def test_a_weightlifter_without_a_clean_and_jerk_has_no_total(games):
    from apps.results.calculators import evaluate

    config = PRESETS["weightlifting"]["result_config"]
    outcome = evaluate(
        "measured_highest",
        {"a": {"lifts": {"snatch": ["180"], "clean_jerk": ["x", "x", "x"]}}},
        config,
    )
    assert outcome["a"][2].status == "NM"


def test_trampoline_adds_time_of_flight_and_displacement():
    from decimal import Decimal

    from apps.results.calculators import evaluate

    config = PRESETS["trampoline"]["result_config"]
    result = evaluate(
        "judged_score",
        {
            "a": {
                "attempts": [
                    {
                        "d": "15.0",
                        "scores": ["8.0", "8.2", "8.4", "8.6"],
                        "extras": {"time_of_flight": "16.500", "horizontal_displacement": "9.300"},
                    }
                ]
            }
        },
        config,
    )
    # 15.0 + (8.2 + 8.4) + 16.5 + 9.3: the middle two execution marks add up.
    assert result["a"][2].primary == Decimal("57.400")
