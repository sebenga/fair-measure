"""Every locked preset: one full contest, the result, and the tie-breakers."""

from decimal import Decimal
from pathlib import Path

import pytest

from apps.competitions.catalog import CATALOG
from apps.competitions.models import Competition, Participant
from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent
from apps.standings.services import compute_standings

pytestmark = pytest.mark.django_db

ENGINE_FILES = [
    Path("apps/competitions/engine.py"),
    Path("apps/standings/services.py"),
]
SPORT_NAMES = [
    "rugby",
    "basketball",
    "netball",
    "hockey",
    "volleyball",
    "cricket",
    "tennis",
    "squash",
    "badminton",
    "padel",
    "darts",
    "snooker",
    "pool",
    "chess",
    "scrabble",
    "backgammon",
    "dominoes",
    "golf",
    "bowling",
    "archery",
    "athletics",
    "quiz",
    "yahtzee",
    "soccer",
    "football",
]


def test_padel_reuses_the_tennis_structure():
    assert CATALOG["padel"]["match_structure"] is CATALOG["tennis"]["match_structure"]
    assert CATALOG["padel"]["score_types"] is CATALOG["tennis"]["score_types"]


def test_engine_files_do_not_name_a_sport():
    for path in ENGINE_FILES:
        text = path.read_text().lower()
        for name in SPORT_NAMES:
            assert name not in text, f"{path} contains {name}"


def _open(api, key, names, fmt="league"):
    created = api.post(
        "/api/v1/competitions",
        {"name": key, "preset": key, "format": fmt},
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    kind = (
        "team"
        if competition.settings_json.get("participant_type") in {"team", "pair"}
        else "individual"
    )
    people = {
        name: Participant.objects.create(competition=competition, name=name, kind=kind)
        for name in names
    }
    return competition, people


def _play(competition, entries):
    """entries: list of (participant, [(code, quantity, unit_index), ...])."""

    fixture = Fixture.objects.create(
        competition=competition,
        round_number=1,
        status=Fixture.Status.COMPLETED,
    )
    categories = {item.code: item for item in competition.scoring_categories.all()}
    for index, (person, _events) in enumerate(entries):
        side = FixtureSide.objects.create(
            fixture=fixture,
            participant=person,
            position=index,
            is_home=index == 0,
        )
        for code, quantity, unit in _events:
            ScoreEvent.objects.create(
                fixture=fixture,
                side=side,
                scoring_category=categories[code],
                quantity=Decimal(str(quantity)),
                unit_index=unit,
            )
    fixture.recalculate_scores()
    fixture.refresh_from_db()
    return fixture


def _score(fixture, name):
    return fixture.sides.get(participant__name=name).score


def _outcome(fixture, name):
    return fixture.sides.get(participant__name=name).outcome


def _table(competition):
    return {row.name: row for row in compute_standings(competition)}


def _order(competition):
    return [row.name for row in compute_standings(competition)]


def test_soccer_own_goal_counts_for_the_other_side(api):
    competition, p = _open(api, "soccer", ["Home", "Away"])
    fixture = _play(
        competition,
        [
            (p["Home"], [("goal", 1, 0), ("own-goal", 1, 0), ("yellow-card", 1, 0), ("red-card", 1, 0)]),
            (p["Away"], []),
        ],
    )
    assert _score(fixture, "Home") == Decimal("1")
    assert _score(fixture, "Away") == Decimal("1")
    assert _outcome(fixture, "Home") == "draw"


def test_rugby_union_tries_and_kicking(api):
    competition, p = _open(api, "rugby_union", ["Ada", "Bo", "Cy", "Dee"])
    league = _play(
        competition,
        [
            (p["Ada"], [("try", 1, 0), ("conversion", 1, 0)]),
            (p["Cy"], []),
        ],
    )
    _play(competition, [(p["Bo"], [("penalty-try", 1, 0)]), (p["Dee"], [])])
    assert _outcome(league, "Ada") == "win"
    assert _score(league, "Ada") == Decimal("7")
    rows = _table(competition)
    assert rows["Ada"].points == rows["Bo"].points == Decimal("3")
    assert rows["Ada"].score_difference == rows["Bo"].score_difference == Decimal("7")
    assert _order(competition).index("Ada") < _order(competition).index("Bo")

    knockout, k = _open(api, "rugby_union", ["Home", "Away"], fmt="knockout")
    decided = _play(
        knockout,
        [
            (k["Home"], [("try", 1, 0), ("penalty-goal", 2, 5)]),
            (k["Away"], [("try", 1, 1), ("penalty-goal", 1, 5)]),
        ],
    )
    assert _score(decided, "Home") == Decimal("5")
    assert _score(decided, "Away") == Decimal("5")
    assert _outcome(decided, "Home") == "win"
    assert _table(knockout)["Home"].points == Decimal("3")


def test_rugby_league_points_for_and_golden_point(api):
    competition, p = _open(api, "rugby_league", ["Ada", "Bo", "Cy", "Dee"])
    _play(
        competition,
        [(p["Ada"], [("try", 3, 0)]), (p["Cy"], [("try", 1, 0), ("conversion", 1, 0)])],
    )
    _play(
        competition,
        [(p["Bo"], [("try", 2, 0)]), (p["Dee"], [("penalty-goal", 1, 1)])],
    )
    rows = _table(competition)
    assert rows["Ada"].points == rows["Bo"].points == Decimal("3")
    assert rows["Ada"].score_difference == rows["Bo"].score_difference == Decimal("6")
    assert rows["Ada"].score_for == Decimal("12")
    assert _order(competition).index("Ada") < _order(competition).index("Bo")

    knockout, k = _open(api, "rugby_league", ["Home", "Away"], fmt="knockout")
    decided = _play(
        knockout,
        [
            (k["Home"], [("try", 1, 0), ("conversion", 1, 0), ("field-goal", 1, 2)]),
            (k["Away"], [("try", 1, 1), ("conversion", 1, 1)]),
        ],
    )
    assert _score(decided, "Home") == Decimal("7")
    assert _score(decided, "Away") == Decimal("6")
    assert _outcome(decided, "Home") == "win"


def test_american_football_uses_three_one_zero(api):
    competition, p = _open(api, "american_football", ["Ada", "Bo", "Cy", "Dee"])
    played = _play(
        competition,
        [
            (p["Ada"], [("touchdown", 1, 0), ("extra-point", 1, 0), ("penalty", 1, 0)]),
            (p["Cy"], [("field-goal", 1, 1), ("safety", 1, 2)]),
        ],
    )
    assert _score(played, "Ada") == Decimal("7")
    assert _score(played, "Cy") == Decimal("5")
    assert _outcome(played, "Ada") == "win"
    _play(
        competition,
        [(p["Bo"], [("touchdown", 1, 0)]), (p["Dee"], [("touchdown", 1, 1)])],
    )
    rows = _table(competition)
    assert rows["Ada"].points == Decimal("3")
    assert rows["Bo"].points == rows["Dee"].points == Decimal("1")
    assert _order(competition).index("Ada") < _order(competition).index("Bo")

    knockout, k = _open(api, "american_football", ["Home", "Away"], fmt="knockout")
    decided = _play(
        knockout,
        [
            (k["Home"], [("touchdown", 1, 0), ("field-goal", 1, 4)]),
            (k["Away"], [("touchdown", 1, 1)]),
        ],
    )
    assert _score(decided, "Home") == Decimal("9")
    assert _score(decided, "Away") == Decimal("6")
    assert _outcome(decided, "Home") == "win"


def test_baseball_runs_and_extra_innings(api):
    competition, p = _open(api, "baseball", ["Ada", "Bo", "Cy", "Dee"])
    played = _play(
        competition,
        [
            (p["Ada"], [("run", 2, 0), ("home-run", 1, 3), ("hit", 2, 0), ("strikeout", 1, 1)]),
            (p["Cy"], [("run", 1, 8)]),
        ],
    )
    assert _score(played, "Ada") == Decimal("3")
    assert _score(played, "Cy") == Decimal("1")
    assert _outcome(played, "Ada") == "win"
    _play(competition, [(p["Bo"], [("run", 6, 0)]), (p["Dee"], [("run", 2, 1)])])
    rows = _table(competition)
    assert rows["Ada"].points == rows["Bo"].points == Decimal("3")
    assert rows["Bo"].score_difference > rows["Ada"].score_difference
    assert _order(competition).index("Bo") < _order(competition).index("Ada")

    extra, sides = _open(api, "baseball", ["Home", "Away"])
    decided = _play(
        extra,
        [
            (sides["Home"], [("run", 1, 0), ("run", 1, 9)]),
            (sides["Away"], [("run", 1, 0)]),
        ],
    )
    assert _score(decided, "Home") == Decimal("2")
    assert _score(decided, "Away") == Decimal("1")
    assert _outcome(decided, "Home") == "win"


def test_basketball_overtime_then_head_to_head(api):
    competition, p = _open(api, "basketball", ["Ada", "Bo", "Cy", "Dee"])
    overtime = _play(
        competition,
        [
            (p["Ada"], [("field-goal", 8, 0), ("field-goal", 8, 1), ("field-goal", 8, 2), ("field-goal", 8, 3), ("field-goal", 2, 4), ("three-pointer", 1, 5), ("foul", 1, 0)]),
            (p["Bo"], [("field-goal", 8, 0), ("field-goal", 8, 1), ("field-goal", 8, 2), ("field-goal", 8, 3), ("field-goal", 2, 4), ("foul", 1, 1)]),
        ],
    )
    assert _score(overtime, "Ada") == Decimal("71")
    assert _score(overtime, "Bo") == Decimal("68")
    assert _outcome(overtime, "Ada") == "win"
    _play(competition, [(p["Ada"], [("field-goal", 30, 0)]), (p["Cy"], [("field-goal", 25, 0)])])
    _play(competition, [(p["Dee"], [("field-goal", 40, 0)]), (p["Ada"], [("field-goal", 25, 0)])])
    _play(competition, [(p["Bo"], [("field-goal", 45, 0)]), (p["Dee"], [("field-goal", 30, 0)])])
    _play(competition, [(p["Bo"], [("field-goal", 40, 0)]), (p["Cy"], [("field-goal", 35, 0)])])
    rows = _table(competition)
    assert rows["Ada"].points == rows["Bo"].points == Decimal("6")
    assert rows["Ada"].score_difference < rows["Bo"].score_difference
    assert _order(competition).index("Ada") < _order(competition).index("Bo")


def test_netball_goals_for_and_golden_goal(api):
    competition, p = _open(api, "netball", ["Ada", "Bo", "Cy", "Dee"])
    _play(competition, [(p["Ada"], [("goal", 15, 0)]), (p["Cy"], [("goal", 10, 1)])])
    _play(competition, [(p["Bo"], [("goal", 12, 0)]), (p["Dee"], [("goal", 7, 1)])])
    rows = _table(competition)
    assert rows["Ada"].points == rows["Bo"].points == Decimal("3")
    assert rows["Ada"].score_difference == rows["Bo"].score_difference == Decimal("5")
    assert _order(competition).index("Ada") < _order(competition).index("Bo")

    knockout, k = _open(api, "netball", ["Home", "Away"], fmt="knockout")
    decided = _play(
        knockout,
        [(k["Home"], [("goal", 8, 0), ("goal", 1, 6)]), (k["Away"], [("goal", 8, 1)])],
    )
    assert _score(decided, "Home") == Decimal("9")
    assert _outcome(decided, "Home") == "win"


def test_field_hockey_goals_for_and_shootout(api):
    competition, p = _open(api, "field_hockey", ["Ada", "Bo", "Cy", "Dee"])
    _play(
        competition,
        [
            (p["Ada"], [("field-goal", 1, 0), ("penalty-corner", 1, 1), ("green-card", 1, 0)]),
            (p["Cy"], [("penalty-stroke", 1, 2)]),
        ],
    )
    _play(
        competition,
        [
            (p["Bo"], [("field-goal", 3, 0)]),
            (p["Dee"], [("field-goal", 2, 1)]),
        ],
    )
    rows = _table(competition)
    assert rows["Ada"].points == rows["Bo"].points == Decimal("3")
    assert rows["Ada"].score_difference == rows["Bo"].score_difference == Decimal("1")
    assert _order(competition).index("Bo") < _order(competition).index("Ada")

    knockout, k = _open(api, "field_hockey", ["Home", "Away"], fmt="knockout")
    decided = _play(
        knockout,
        [
            (k["Home"], [("field-goal", 1, 0), ("penalty-stroke", 3, 4)]),
            (k["Away"], [("field-goal", 1, 1), ("penalty-stroke", 1, 4)]),
        ],
    )
    assert _score(decided, "Home") == Decimal("1")
    assert _score(decided, "Away") == Decimal("1")
    assert _outcome(decided, "Home") == "win"


def test_volleyball_set_and_point_ratio(api):
    competition, p = _open(api, "volleyball", ["Ada", "Bo", "Cy", "Dee"])
    match = _play(
        competition,
        [
            (p["Ada"], [("point", 25, 0), ("point", 25, 1), ("point", 25, 2)]),
            (p["Cy"], [("point", 10, 0), ("point", 10, 1), ("point", 10, 2)]),
        ],
    )
    assert _outcome(match, "Ada") == "win"
    assert _score(match, "Ada") == Decimal("75")
    _play(
        competition,
        [
            (p["Bo"], [("point", 25, 0), ("point", 25, 1), ("point", 25, 2)]),
            (p["Dee"], [("point", 20, 0), ("point", 20, 1), ("point", 20, 2)]),
        ],
    )
    rows = _table(competition)
    assert rows["Ada"].points == rows["Bo"].points == Decimal("3")
    assert rows["Ada"].wins == rows["Bo"].wins == 1
    assert rows["Ada"].units_for == rows["Bo"].units_for == Decimal("3")
    assert _order(competition).index("Ada") < _order(competition).index("Bo")


def test_cricket_t20_rate_super_over_and_no_result(api):
    competition, p = _open(api, "cricket_t20", ["Ada", "Bo", "Cy", "Dee", "Eve", "Fay", "Gus", "Hal"])
    innings = _play(
        competition,
        [
            (p["Ada"], [("run", 30, 0), ("ball", 12, 0), ("wicket", 2, 0)]),
            (p["Cy"], [("run", 18, 1), ("ball", 12, 1)]),
        ],
    )
    assert _score(innings, "Ada") == Decimal("30")
    assert _outcome(innings, "Ada") == "win"
    _play(
        competition,
        [
            (p["Bo"], [("run", 24, 0), ("ball", 24, 0)]),
            (p["Dee"], [("run", 12, 1), ("ball", 24, 1)]),
        ],
    )
    tied = _play(
        competition,
        [
            (p["Eve"], [("run", 20, 0), ("ball", 12, 0), ("run", 8, 2)]),
            (p["Fay"], [("run", 20, 1), ("ball", 12, 1), ("run", 4, 2)]),
        ],
    )
    assert _score(tied, "Eve") == Decimal("20")
    assert _outcome(tied, "Eve") == "win"
    _play(competition, [(p["Gus"], [("no-result", 1, 0)]), (p["Hal"], [])])
    rows = _table(competition)
    assert rows["Ada"].points == rows["Bo"].points == rows["Eve"].points == Decimal("3")
    assert rows["Ada"].rate > rows["Bo"].rate > rows["Eve"].rate
    assert rows["Eve"].rate == Decimal("0")
    assert rows["Gus"].points == rows["Hal"].points == Decimal("1")
    assert _order(competition).index("Ada") < _order(competition).index("Bo")


def test_tennis_tiebreak_and_games_difference(api):
    competition, p = _open(api, "tennis", ["Ada", "Bo", "Cy", "Dee"])
    match = _play(
        competition,
        [
            (p["Ada"], [("game", 6, 0), ("game", 6, 1), ("tiebreak", 7, 1)]),
            (p["Bo"], [("game", 4, 0), ("game", 6, 1), ("tiebreak", 5, 1)]),
        ],
    )
    assert _outcome(match, "Ada") == "win"
    assert _score(match, "Ada") == Decimal("13")
    assert _score(match, "Bo") == Decimal("10")
    _play(
        competition,
        [(p["Cy"], [("game", 6, 0), ("game", 6, 1)]), (p["Dee"], [])],
    )
    rows = _table(competition)
    assert rows["Ada"].points == rows["Cy"].points == Decimal("3")
    assert rows["Ada"].units_difference == rows["Cy"].units_difference == Decimal("2")
    assert rows["Cy"].score_difference > rows["Ada"].score_difference
    assert _order(competition).index("Cy") < _order(competition).index("Ada")


def test_squash_games_and_points_difference(api):
    competition, p = _open(api, "squash", ["Ada", "Bo", "Cy", "Dee"])
    match = _play(
        competition,
        [
            (p["Ada"], [("point", 11, 0), ("point", 11, 1), ("point", 11, 2)]),
            (p["Bo"], [("point", 5, 0), ("point", 7, 1), ("point", 9, 2)]),
        ],
    )
    assert _outcome(match, "Ada") == "win"
    assert match.sides.get(participant__name="Ada").outcome == "win"
    _play(
        competition,
        [
            (p["Cy"], [("point", 11, 0), ("point", 11, 1), ("point", 12, 2)]),
            (p["Dee"], [("point", 9, 0), ("point", 9, 1), ("point", 10, 2)]),
        ],
    )
    rows = _table(competition)
    assert rows["Ada"].points == rows["Cy"].points == Decimal("3")
    assert rows["Ada"].units_difference == rows["Cy"].units_difference
    assert _order(competition).index("Ada") < _order(competition).index("Cy")


def test_badminton_cap_and_points_difference(api):
    competition, p = _open(api, "badminton", ["Ada", "Bo", "Cy", "Dee"])
    match = _play(
        competition,
        [
            (p["Ada"], [("point", 30, 0), ("point", 21, 1)]),
            (p["Bo"], [("point", 29, 0), ("point", 15, 1)]),
        ],
    )
    assert _outcome(match, "Ada") == "win"
    _play(
        competition,
        [
            (p["Cy"], [("point", 21, 0), ("point", 21, 1)]),
            (p["Dee"], [("point", 19, 0), ("point", 19, 1)]),
        ],
    )
    rows = _table(competition)
    assert rows["Ada"].units_difference == rows["Cy"].units_difference == Decimal("2")
    assert _order(competition).index("Ada") < _order(competition).index("Cy")


def test_table_tennis_ratios(api):
    competition, p = _open(api, "table_tennis", ["Ada", "Bo", "Cy", "Dee"])
    match = _play(
        competition,
        [
            (p["Ada"], [("point", 11, 0), ("point", 11, 1), ("point", 11, 2)]),
            (p["Bo"], [("point", 1, 0), ("point", 1, 1), ("point", 1, 2)]),
        ],
    )
    assert _outcome(match, "Ada") == "win"
    _play(
        competition,
        [
            (p["Cy"], [("point", 11, 0), ("point", 11, 1), ("point", 11, 2)]),
            (p["Dee"], [("point", 9, 0), ("point", 9, 1), ("point", 9, 2)]),
        ],
    )
    rows = _table(competition)
    assert rows["Ada"].points == rows["Cy"].points == Decimal("3")
    assert rows["Ada"].units_for == rows["Cy"].units_for
    assert _order(competition).index("Ada") < _order(competition).index("Cy")


def test_padel_uses_tennis_scoring(api):
    competition, p = _open(api, "padel", ["Ada", "Bo"])
    match = _play(
        competition,
        [
            (p["Ada"], [("game", 6, 0), ("game", 6, 1), ("tiebreak", 7, 1)]),
            (p["Bo"], [("game", 4, 0), ("game", 6, 1), ("tiebreak", 4, 1)]),
        ],
    )
    assert _outcome(match, "Ada") == "win"
    assert _score(match, "Ada") == Decimal("13")
    assert _table(competition)["Ada"].points == Decimal("3")
    assert _order(competition)[0] == "Ada"


def test_darts_countdown_bust_and_legs(api):
    competition, p = _open(api, "darts_501", ["Ada", "Bo"])
    match = _play(
        competition,
        [
            (
                p["Ada"],
                [
                    ("visit", 500, 0),
                    ("bust", 1, 0),
                    ("one-eighty", 1, 0),
                    ("visit", 501, 0),
                    ("visit", 501, 1),
                    ("visit", 501, 2),
                    ("checkout", 1, 2),
                ],
            ),
            (p["Bo"], [("visit", 501, 3)]),
        ],
    )
    assert _outcome(match, "Ada") == "win"
    assert _score(match, "Ada") == Decimal("1503")
    rows = _table(competition)
    assert rows["Ada"].points == Decimal("3")
    assert rows["Ada"].units_for == Decimal("3")
    assert rows["Ada"].units_difference == Decimal("2")
    assert _order(competition)[0] == "Ada"


def test_snooker_frames_foul_and_respotted_black(api):
    competition, p = _open(api, "snooker", ["Ada", "Bo"])
    match = _play(
        competition,
        [
            (
                p["Ada"],
                [("red", 8, 0), ("century", 1, 0), ("black", 1, 1), ("red", 10, 2), ("respotted-black", 1, 2), ("blue", 1, 3)],
            ),
            (p["Bo"], [("foul", 1, 0), ("red", 10, 2)]),
        ],
    )
    assert _outcome(match, "Ada") == "win"
    assert _score(match, "Ada") == Decimal("12") + Decimal("7") + Decimal("17") + Decimal("5")
    rows = _table(competition)
    assert rows["Ada"].points == Decimal("3")
    assert rows["Ada"].units_difference == Decimal("4")
    assert rows["Ada"].category_totals["century"] == Decimal("1")
    assert _order(competition)[0] == "Ada"


def test_pool_race(api):
    competition, p = _open(api, "pool_8ball", ["Ada", "Bo"])
    match = _play(
        competition,
        [
            (p["Ada"], [("rack", 1, 0), ("rack", 1, 1), ("rack", 1, 2), ("rack", 1, 3), ("rack", 1, 4)]),
            (p["Bo"], [("rack", 1, 5), ("rack", 1, 6), ("rack", 1, 7)]),
        ],
    )
    assert _outcome(match, "Ada") == "win"
    rows = _table(competition)
    assert rows["Ada"].units_difference == Decimal("2")
    assert rows["Ada"].points == Decimal("3")
    assert _order(competition)[0] == "Ada"


def test_chess_sonneborn_and_armageddon(api):
    competition, p = _open(api, "chess", ["Ada", "Bo", "Cy", "Dee"])
    _play(competition, [(p["Ada"], [("game-point", 1, 0)]), (p["Dee"], [])])
    _play(competition, [(p["Cy"], [("game-point", 1, 0)]), (p["Bo"], [])])
    _play(competition, [(p["Bo"], [("game-point", 1, 0)]), (p["Dee"], [])])
    drawn = _play(
        competition,
        [(p["Ada"], [("draw-point", 1, 0)]), (p["Cy"], [("draw-point", 1, 0)])],
    )
    assert _outcome(drawn, "Ada") == "draw"
    assert _score(drawn, "Ada") == Decimal("0.5")
    rows = _table(competition)
    assert rows["Ada"].points == rows["Cy"].points == Decimal("4")
    assert rows["Cy"].sonneborn > rows["Ada"].sonneborn
    assert _order(competition).index("Cy") < _order(competition).index("Ada")

    knockout, k = _open(api, "chess", ["Home", "Away"], fmt="knockout")
    decided = _play(
        knockout,
        [
            (k["Home"], [("draw-point", 1, 0), ("game-point", 1, 1), ("game-point", 1, 2)]),
            (k["Away"], [("draw-point", 1, 0), ("game-point", 1, 1)]),
        ],
    )
    assert _score(decided, "Home") == Decimal("0.5")
    assert _outcome(decided, "Home") == "win"


def test_scrabble_spread(api):
    competition, p = _open(api, "scrabble", ["Ada", "Bo", "Cy", "Dee"])
    match = _play(
        competition,
        [
            (p["Ada"], [("turn", 40, 0), ("bingo", 1, 0), ("tiles-out", 8, 0)]),
            (p["Bo"], [("turn", 55, 0), ("unplayed", 12, 0)]),
        ],
    )
    assert _score(match, "Ada") == Decimal("98")
    assert _score(match, "Bo") == Decimal("43")
    assert _outcome(match, "Ada") == "win"
    _play(competition, [(p["Cy"], [("turn", 80, 0)]), (p["Dee"], [("turn", 70, 0)])])
    rows = _table(competition)
    assert rows["Ada"].points == rows["Cy"].points == Decimal("3")
    assert rows["Ada"].score_difference > rows["Cy"].score_difference
    assert _order(competition).index("Ada") < _order(competition).index("Cy")

    knockout, k = _open(api, "scrabble", ["Home", "Away"], fmt="knockout")
    pending = _play(knockout, [(k["Home"], [("turn", 50, 0)]), (k["Away"], [("turn", 50, 0)])])
    assert _outcome(pending, "Home") == "pending"


def test_backgammon_cube_and_target(api):
    competition, p = _open(api, "backgammon", ["Ada", "Bo"])
    match = _play(
        competition,
        [
            (p["Ada"], [("gammon", 2, 0), ("single", 3, 0)]),
            (p["Bo"], [("single", 4, 0)]),
        ],
    )
    assert _score(match, "Ada") == Decimal("7")
    assert _score(match, "Bo") == Decimal("4")
    assert _outcome(match, "Ada") == "win"
    rows = _table(competition)
    assert rows["Ada"].points == Decimal("3")
    assert rows["Ada"].score_difference == Decimal("3")
    assert _order(competition)[0] == "Ada"


def test_dominoes_first_to_target(api):
    competition, p = _open(api, "dominoes_fives", ["Ada", "Bo", "Cy", "Dee"])
    match = _play(competition, [(p["Ada"], [("fives", 250, 0)]), (p["Bo"], [("fives", 180, 0)])])
    assert _outcome(match, "Ada") == "win"
    _play(competition, [(p["Cy"], [("fives", 250, 0)]), (p["Dee"], [("fives", 100, 0)])])
    rows = _table(competition)
    assert rows["Ada"].points == rows["Cy"].points == Decimal("3")
    assert rows["Cy"].score_difference > rows["Ada"].score_difference
    assert _order(competition).index("Cy") < _order(competition).index("Ada")


def test_golf_stableford_countback_and_handicap(api):
    competition, p = _open(api, "golf_stableford", ["Ada", "Bo"])
    ada = [("birdie", 1, 0)] + [("par", 1, hole) for hole in range(1, 18)]
    bo = [("par", 1, hole) for hole in range(17)] + [("birdie", 1, 17)]
    event = _play(competition, [(p["Ada"], ada), (p["Bo"], bo)])
    assert _score(event, "Ada") == Decimal("37")
    assert _score(event, "Bo") == Decimal("37")
    assert _order(competition)[0] == "Bo"
    p["Ada"].metadata = {"handicap": 5}
    p["Ada"].save(update_fields=["metadata"])
    assert _order(competition)[0] == "Ada"
    assert _table(competition)["Ada"].score_for == Decimal("42")


def test_bowling_bonus_balls_and_best_game(api):
    strike, p = _open(api, "bowling", ["Ada", "Bo"])
    game = _play(
        strike,
        [
            (p["Ada"], [("strike", 1, 0), ("pins", 3, 1), ("pins", 4, 2)]),
            (p["Bo"], [("pins", 20, 0)]),
        ],
    )
    assert _score(game, "Ada") == Decimal("24")
    assert _outcome(game, "Ada") == "win" or _score(game, "Ada") > _score(game, "Bo")

    competition, people = _open(api, "bowling", ["Ada", "Bo"])
    _play(competition, [(people["Ada"], [("pins", 100, 0)]), (people["Bo"], [("pins", 80, 0)])])
    _play(competition, [(people["Ada"], [("pins", 90, 0)]), (people["Bo"], [("pins", 90, 0)])])
    _play(competition, [(people["Ada"], [("pins", 60, 0)]), (people["Bo"], [("pins", 80, 0)])])
    rows = _table(competition)
    assert rows["Ada"].score_for == rows["Bo"].score_for == Decimal("250")
    assert rows["Ada"].best_single == Decimal("100")
    assert rows["Bo"].best_single == Decimal("90")
    assert _order(competition)[0] == "Ada"


def test_bowling_bonus_only_pays_the_same_side(api):
    competition, p = _open(api, "bowling", ["Ada", "Bo"])
    game = _play(
        competition,
        [
            (p["Ada"], [("strike", 1, 0), ("pins", 3, 1), ("pins", 4, 2)]),
            (p["Bo"], [("pins", 9, 0)]),
        ],
    )
    # Ada: 10 + 3 + 4 bonus, then the 3 and 4 as their own frames = 24.
    assert _score(game, "Ada") == Decimal("24")
    assert _score(game, "Bo") == Decimal("9")


def test_bowling_perfect_game_is_300(api):
    competition, p = _open(api, "bowling", ["Ada", "Bo"])
    strikes = [("strike", 1, frame) for frame in range(10)]
    bonus = [("bonus-ball", 10, 9), ("bonus-ball", 10, 9)]
    game = _play(competition, [(p["Ada"], strikes + bonus), (p["Bo"], [("pins", 1, 0)])])
    assert _score(game, "Ada") == Decimal("300")


def test_bowling_spare_counts_the_closing_ball_once(api):
    competition, p = _open(api, "bowling", ["Ada", "Bo"])
    game = _play(
        competition,
        [
            # Frame 1: a 7, then a spare closed with 3 pins. Frame 2: a 5 and a 2.
            # The 5 after the spare is also its one bonus ball.
            (p["Ada"], [("pins", 7, 0), ("spare", 3, 0), ("pins", 5, 1), ("pins", 2, 1)]),
            (p["Bo"], [("pins", 1, 0)]),
        ],
    )
    # 7 + (3 + bonus 5) + 5 + 2 = 22
    assert _score(game, "Ada") == Decimal("22")


def test_archery_tens_then_xs(api):
    competition, p = _open(api, "archery", ["Ada", "Bo"])
    event = _play(
        competition,
        [
            (p["Ada"], [("ring-5", 70, 0), ("x", 1, 1), ("ring-8", 1, 1)]),
            (p["Bo"], [("ring-5", 70, 0), ("ring-10", 1, 1), ("ring-8", 1, 1)]),
        ],
    )
    assert _score(event, "Ada") == _score(event, "Bo") == Decimal("368")
    rows = _table(competition)
    assert rows["Bo"].category_totals["ring-10"] == Decimal("1")
    assert rows["Ada"].category_totals["x"] == Decimal("1")
    # An X is a ten, so the tens tie (1 each) and the Xs decide it.
    assert _order(competition)[0] == "Ada"


def test_archery_counts_xs_among_the_tens(api):
    competition, p = _open(api, "archery", ["Ada", "Bo"])
    _play(
        competition,
        [
            # Both score 30. Ada has three tens (one an X); Bo has one ten.
            (p["Ada"], [("ring-10", 2, 0), ("x", 1, 0)]),
            (p["Bo"], [("ring-10", 1, 0), ("ring-9", 2, 0), ("ring-2", 1, 0)]),
        ],
    )
    # More tens wins, even though Bo has no X to lose on and Ada's X is "extra".
    assert _order(competition)[0] == "Ada"


def test_athletics_track_and_field_directions(api):
    track, p = _open(api, "athletics", ["Ada", "Bo", "Cy"])
    race = _play(
        track,
        [
            (p["Ada"], [("time", "10.50", 0), ("time", "10.80", 1)]),
            (p["Bo"], [("time", "10.51", 0), ("time", "10.90", 1)]),
            (p["Cy"], [("time", "11.20", 0)]),
        ],
    )
    assert _score(race, "Ada") == Decimal("10.50")
    assert _outcome(race, "Ada") == "win"
    rows = _table(track)
    assert rows["Ada"].points == Decimal("8")
    assert rows["Bo"].points == Decimal("7")
    assert rows["Cy"].points == Decimal("6")
    assert rows["Ada"].next_attempt == Decimal("10.80")
    assert _order(track)[:3] == ["Ada", "Bo", "Cy"]

    field, people = _open(api, "athletics", ["Ada", "Bo"])
    throw = _play(
        field,
        [
            (people["Ada"], [("distance", "68.40", 0), ("distance", "67.10", 1)]),
            (people["Bo"], [("distance", "68.10", 0), ("distance", "67.90", 1)]),
        ],
    )
    assert _score(throw, "Ada") == Decimal("68.40")
    assert _outcome(throw, "Ada") == "win"
    assert _table(field)["Ada"].points == Decimal("8")
    assert _order(field)[0] == "Ada"


def test_quiz_joker_and_nearest(api):
    competition, p = _open(api, "quiz", ["Ada", "Bo"])
    event = _play(
        competition,
        [
            (p["Ada"], [("answer", 4, 0), ("answer", 3, 1), ("joker", 1, 1), ("nearest", 1, 7)]),
            (p["Bo"], [("answer", 6, 0), ("answer", 4, 1), ("nearest", 5, 7)]),
        ],
    )
    assert _score(event, "Ada") == _score(event, "Bo") == Decimal("10")
    assert _order(competition)[0] == "Ada"


def test_yahtzee_upper_bonus(api):
    competition, p = _open(api, "yahtzee", ["Ada", "Bo"])
    event = _play(
        competition,
        [
            (p["Ada"], [("sixes", 36, 0), ("fives", 15, 0), ("fours", 12, 0), ("yahtzee", 1, 0), ("extra-yahtzee", 1, 0)]),
            (p["Bo"], [("chance", 40, 0)]),
        ],
    )
    assert _score(event, "Ada") == Decimal("248")
    assert _table(competition)["Ada"].score_for == Decimal("248")
    assert _order(competition)[0] == "Ada"


def test_kpi_locks_after_start_and_uses_recent_activity(api):
    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Sales floor",
            "preset": "kpi",
            "scoring_categories": [
                {"name": "Sale closed", "points": "10", "description": "A signed deal."},
                {"name": "Call made", "points": "1", "description": "An outbound call."},
            ],
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    detail = api.get(f"/api/v1/competitions/{competition.id}")
    by_code = {item["code"]: item for item in detail.data["scoring_categories"]}
    assert by_code["sale-closed"]["description"] == "A signed deal."
    assert by_code["call-made"]["points"] == "1.00"
    edited = api.patch(
        f"/api/v1/competitions/{competition.id}/scoring-categories/{by_code['sale-closed']['id']}",
        {"points": "12"},
        format="json",
    )
    assert edited.status_code == 200
    ada = Participant.objects.create(competition=competition, name="Ada", kind="individual")
    bo = Participant.objects.create(competition=competition, name="Bo", kind="individual")
    _play(competition, [(ada, [("sale-closed", 1, None)]), (bo, [("sale-closed", 1, None)])])
    assert _table(competition)["Ada"].score_for == _table(competition)["Bo"].score_for
    assert _order(competition)[0] == "Bo"
    started = api.patch(
        f"/api/v1/competitions/{competition.id}",
        {"status": "active"},
        format="json",
    )
    assert started.status_code == 200
    locked = api.patch(
        f"/api/v1/competitions/{competition.id}/scoring-categories/{by_code['sale-closed']['id']}",
        {"points": "4"},
        format="json",
    )
    assert locked.status_code == 403


def test_cleaning_describes_tasks_and_locks_after_start(api):
    competition, p = _open(api, "cleaning", ["Ada", "Bo"])
    detail = api.get(f"/api/v1/competitions/{competition.id}")
    bathroom = next(item for item in detail.data["scoring_categories"] if item["code"] == "bathroom")
    assert "Sink" in bathroom["description"]
    week = _play(
        competition,
        [
            (p["Ada"], [("dishes", 1, 0), ("bathroom", 1, 0), ("on-time", 1, 0)]),
            (p["Bo"], [("laundry", 1, 0)]),
        ],
    )
    assert _score(week, "Ada") == Decimal("8")
    assert _score(week, "Bo") == Decimal("3")
    assert _order(competition)[0] == "Ada"
    edited = api.patch(
        f"/api/v1/competitions/{competition.id}/scoring-categories/{bathroom['id']}",
        {"points": "9"},
        format="json",
    )
    assert edited.status_code == 200
    started = api.patch(f"/api/v1/competitions/{competition.id}", {"status": "active"}, format="json")
    assert started.status_code == 200
    locked = api.patch(
        f"/api/v1/competitions/{competition.id}/scoring-categories/{bathroom['id']}",
        {"points": "1"},
        format="json",
    )
    assert locked.status_code == 403


@pytest.mark.parametrize("key", [key for key, preset in CATALOG.items() if preset.get("locked")])
def test_locked_preset_refuses_scoring_edits(api, key):
    created = api.post("/api/v1/competitions", {"name": key, "preset": key}, format="json")
    assert created.status_code == 201, created.data
    competition_id = created.data["id"]
    edited = api.patch(
        f"/api/v1/competitions/{competition_id}/points-policy",
        {"win_points": "9"},
        format="json",
    )
    assert edited.status_code == 403
