"""Result types for Olympic-style sports, each with its tie-break rule.

Configs are inline: the engine is data-driven and must work before any locked
sport preset uses these types.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.results.calculators import ResultDataError, _event_points, evaluate
from apps.results.tables import COMBINED_EVENT_TABLES


def ranks(result: dict) -> dict:
    return {key: (row[0], row[2].status) for key, row in result.items()}


# --- timed_lowest ----------------------------------------------------------------


def test_times_round_up_ties_share_and_false_starts_are_disqualified():
    config = {"decimals": 2, "reaction_limit": "0.100"}
    result = evaluate(
        "timed_lowest",
        {
            "a": {"time": "9.581", "reaction_time": "0.145"},
            "b": {"time": "10.001"},
            "c": {"time": "10.009"},
            "early": {"time": "9.40", "reaction_time": "0.081"},
        },
        config,
    )
    assert result["a"][2].primary == Decimal("9.59")  # rounded up to the next hundredth
    assert ranks(result) == {"a": (1, ""), "b": (2, ""), "c": (2, ""), "early": (None, "DQ")}

    finer = evaluate(
        "timed_lowest", {"b": {"time": "10.001"}, "c": {"time": "10.009"}}, {"decimals": 3}
    )
    assert ranks(finer) == {"b": (1, ""), "c": (2, "")}


# --- measured_highest -----------------------------------------------------------------


def test_best_attempt_then_next_best_and_no_mark():
    result = evaluate(
        "measured_highest",
        {
            "one_mark": {"attempts": ["8.10", "x", "7.90"]},
            "two_marks": {"attempts": ["8.10", "8.00", "x"]},
            "fouls": {"attempts": ["x", "x", "x"]},
        },
        {"max_attempts": 6},
    )
    assert ranks(result) == {"two_marks": (1, ""), "one_mark": (2, ""), "fouls": (None, "NM")}


def test_height_countback_uses_failures():
    config = {"mode": "heights"}
    result = evaluate(
        "measured_highest",
        {
            "first_time": {"heights": {"2.20": "o", "2.25": "xo", "2.30": "o", "2.33": "xxx"}},
            "second_time": {"heights": {"2.20": "o", "2.25": "o", "2.30": "xo", "2.33": "xxx"}},
            "cleaner": {"heights": {"2.20": "o", "2.25": "o", "2.30": "o", "2.33": "xxx"}},
            "nothing": {"heights": {"2.20": "xxx"}},
        },
        config,
    )
    # All clear 2.30. Failures at 2.30 decide first; then total failures.
    assert ranks(result) == {
        "cleaner": (1, ""),
        "first_time": (2, ""),
        "second_time": (3, ""),
        "nothing": (None, "NM"),
    }


# --- judged_score -------------------------------------------------------------------------


def test_drop_high_and_low_then_multiply_by_difficulty():
    config = {
        "judges": 7,
        "drop_high": 2,
        "drop_low": 2,
        "multiply_by_difficulty": True,
        "max_score": 10,
        "score_step": "0.5",
    }
    result = evaluate(
        "judged_score",
        {
            "a": {"attempts": [{"scores": [7, "7.5", 8, 8, "8.5", 9, "9.5"], "difficulty": "3.2"}]},
            "b": {"attempts": [{"scores": [8, 8, 8, 8, 8, 8, 8], "difficulty": "3.0"}]},
        },
        config,
    )
    assert result["a"][2].primary == Decimal("78.40")  # (8 + 8 + 8.5) x 3.2
    assert result["b"][2].primary == Decimal("72.00")
    assert result["a"][0] == 1
    with pytest.raises(ResultDataError):
        evaluate("judged_score", {"x": {"attempts": [{"scores": [8, 8], "difficulty": 2}]}}, config)


def test_difficulty_plus_execution_and_best_single_breaks_ties():
    config = {"drop_high": 1, "drop_low": 1, "combine": "average", "decimals": 3}
    result = evaluate(
        "judged_score",
        {
            "steady": {
                "attempts": [
                    {"d": "5.5", "scores": [8, 8, 8, 8], "penalty": 0},
                    {"d": "5.5", "scores": [8, 8, 8, 8]},
                ]
            },
            "peaky": {
                "attempts": [
                    {"d": "6.0", "scores": [8, 8, 8, 8]},
                    {"d": "5.0", "scores": [8, 8, 8, 8]},
                ]
            },
        },
        config,
    )
    assert result["steady"][2].primary == result["peaky"][2].primary == Decimal("27.000")
    assert ranks(result) == {"peaky": (1, ""), "steady": (2, "")}


# --- points ----------------------------------------------------------------------------------


def test_lowest_points_with_a_discard_and_a_double_medal_race():
    config = {"discard_worst": 1, "double_last": True, "tie_break": "last_round"}
    result = evaluate(
        "points_lowest",
        {
            "a": {"rounds": [1, 5, 3, 8, 2]},  # 1+5+3 (8 discarded) + 2x2 = 13
            "b": {"rounds": [2, 2, 4, 9, 1]},  # 2+2+4 + 1x2 = 10
            "c": {"rounds": [3, 4, 3, 7, "0.5"]},  # 3+4+3 + 1 = 11
        },
        config,
    )
    assert result["a"][2].primary == Decimal("13")
    assert ranks(result) == {"b": (1, ""), "c": (2, ""), "a": (3, "")}


def test_highest_points_tie_broken_by_inner_counts():
    result = evaluate(
        "points_highest",
        {
            "a": {"rounds": [340, 335], "tiebreak": [30, 12]},
            "b": {"rounds": [338, 337], "tiebreak": [30, 14]},
        },
        {"tie_break": "none"},
    )
    assert result["a"][2].primary == result["b"][2].primary
    assert ranks(result) == {"b": (1, ""), "a": (2, "")}


# --- combat_decision ---------------------------------------------------------------------------

COMBAT = {
    "decide_by": "cards",
    "methods": [
        {"code": "DEC", "label": "Judges' decision"},
        {"code": "KO", "label": "Knockout"},
        {"code": "RSC", "label": "Referee stops contest"},
        {"code": "DQ", "label": "Disqualification"},
    ],
}


def test_a_split_decision_from_the_cards():
    result = evaluate(
        "combat_decision",
        {
            "red": {"cards": [29, 28, 29, 27, 28]},
            "blue": {"cards": [28, 29, 28, 30, 29]},
        },
        COMBAT,
    )
    # Red wins on judges 1 and 3 only; blue wins three cards.
    assert ranks(result) == {"blue": (1, ""), "red": (2, "")}
    assert result["blue"][2].breakdown["decision"] == "Judges 3-2"


def test_a_stoppage_and_a_level_bout():
    stopped = evaluate(
        "combat_decision", {"red": {"winner": True, "method": "KO"}, "blue": {}}, COMBAT
    )
    assert ranks(stopped) == {"red": (1, ""), "blue": (2, "")}
    level = evaluate(
        "combat_decision", {"red": {"cards": [10, 9]}, "blue": {"cards": [9, 10]}}, COMBAT
    )
    assert ranks(level) == {"red": (None, ""), "blue": (None, "")}
    with pytest.raises(ResultDataError):
        evaluate("combat_decision", {"red": {"winner": True, "method": "TKO?"}, "blue": {}}, COMBAT)


# --- multi_run_aggregate --------------------------------------------------------------------------


def test_runs_add_up_and_ties_share():
    result = evaluate(
        "multi_run_aggregate",
        {
            "a": {"runs": ["52.10", "51.95"]},
            "b": {"runs": ["52.00", "52.05"]},
            "c": {"runs": ["51.80"]},
        },
        {"runs": 2, "decimals": 2},
    )
    assert ranks(result) == {"a": (1, ""), "b": (1, ""), "c": (None, "")}


def test_best_run_with_penalty_seconds():
    config = {
        "aggregate": "best",
        "penalties": [{"key": "touches", "seconds": 2}, {"key": "missed", "seconds": 50}],
    }
    result = evaluate(
        "multi_run_aggregate",
        {
            "clean": {
                "runs": [{"time": "95.10"}, {"time": "93.00", "touches": 2}]
            },  # best 95.10 v 97.00
            "missed": {"runs": [{"time": "88.00", "missed": 1}, {"time": "96.00"}]},  # best 96.00
        },
        config,
    )
    assert result["clean"][2].primary == Decimal("95.10")
    assert ranks(result) == {"clean": (1, ""), "missed": (2, "")}


# --- combined_events ------------------------------------------------------------------------------


def test_points_tables_match_the_reference_marks():
    table = {spec["key"]: spec for spec in COMBINED_EVENT_TABLES["decathlon"]}
    assert _event_points(table["100m"], "10.395") == 1000
    assert _event_points(table["long_jump"], "7.76") == 1000
    assert _event_points(table["high_jump"], "2.21") >= 1000
    assert _event_points(table["1500m"], "600") == 0


def test_combined_total_and_its_tie_break():
    config = {
        "events": [
            {"key": "run", "label": "Run", "kind": "track", "a": "1", "b": "20", "c": "1"},
            {"key": "jump", "label": "Jump", "kind": "field", "a": "1", "b": "0", "c": "1"},
            {"key": "throw", "label": "Throw", "kind": "field", "a": "1", "b": "0", "c": "1"},
        ]
    }
    result = evaluate(
        "combined_events",
        {
            # Both total 30. "a" scores more in two of the three events.
            "a": {"marks": {"run": 10, "jump": 11, "throw": 9}},
            "b": {"marks": {"run": 15, "jump": 10, "throw": 15}},
        },
        config,
    )
    assert result["a"][2].primary == result["b"][2].primary == Decimal("30")
    assert ranks(result) == {"a": (1, ""), "b": (2, "")}


# --- A full event through the API, into Games medals ----------------------------------------------


@pytest.mark.django_db
def test_a_timed_final_awards_shared_silver_in_a_games():
    from django.contrib.auth import get_user_model

    from apps.competitions.presets import PRESETS
    from apps.games import services as games_services
    from apps.games.models import NOC, Athlete, Games, Medal
    from apps.results import services as results
    from apps.results.models import CompetitionOfficial

    user_model = get_user_model()
    owner = user_model.objects.create_user(email="owner@types.test", password="pw-123456789")
    official = user_model.objects.create_user(email="td@types.test", password="pw-123456789")
    games = Games.objects.create(name="Types Games", owner=owner)
    preset = next(key for key in ("soccer", "basketball") if key in PRESETS)
    event = games_services.add_custom_event(
        games, sport_label="Sprint", name="100 m", preset_key=preset
    )
    competition = event.competition
    competition.settings_json = {
        **competition.settings_json,
        "result_type": "timed_lowest",
        "result_config": {"decimals": 2},
        "statuses": [
            {"code": "DQ", "label": "Disqualified"},
            {"code": "DNS", "label": "Did not start"},
        ],
        "official_results": True,
    }
    competition.save()
    CompetitionOfficial.objects.create(
        competition=competition, user=official, title="technical_delegate"
    )
    entries = []
    for code in ("RSA", "KEN", "BRA", "JPN"):
        noc = NOC.objects.create(games=games, code=code, name=code)
        athlete = Athlete.objects.create(games=games, noc=noc, name=f"Runner {code}")
        entries.append(games_services.add_entry(event, noc, athlete))
    fixture = results.create_event(competition, label="Final", actor=owner)
    sides = {side.participant_id: side for side in fixture.sides.all()}
    times = ["9.85", "9.91", "9.906", "10.20"]  # KEN and BRA both round up to 9.91
    results.save_results(
        fixture,
        [
            {"side": str(sides[entry.participant_id].id), "data": {"time": value}}
            for entry, value in zip(entries, times, strict=True)
        ],
        owner,
    )
    results.finalise(fixture, official)
    medals = sorted((row.noc.code, row.medal) for row in Medal.objects.filter(event=event))
    # Two silvers and no bronze: the next place after a shared second is fourth.
    assert medals == [("BRA", "silver"), ("KEN", "silver"), ("RSA", "gold")]
