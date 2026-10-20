"""Locked show jumping presets: FEI Table A, jump-off, two-phase, Table C and the series."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.competitions.models import Competition, Membership
from apps.competitions.presets import PRESETS, apply_preset
from apps.core.permissions import Role
from apps.horses.models import Combination, Horse
from apps.results import services
from apps.results.calculators import evaluate
from apps.results.models import CompetitionOfficial
from apps.standings.services import compute_standings

pytestmark = pytest.mark.django_db
User = get_user_model()

KEYS = ("show_jumping", "show_jumping_table_a", "show_jumping_two_phase", "show_jumping_table_c")


def _config(key: str, **event) -> dict:
    preset = PRESETS[key]
    return {**preset["result_config"], "statuses": preset["statuses"], **event}


def ranks(result: dict) -> dict:
    return {entry_id: (row[0], row[2].status) for entry_id, row in result.items()}


def test_every_jumping_preset_is_locked_under_the_fei():
    for key in KEYS:
        preset = PRESETS[key]
        assert preset["locked"] is True
        assert preset["official_results"] is True
        assert preset["result_type"] == "faults_then_time"
        assert preset["participant_type"] == "combination"
        assert preset["governing_body"] == "FEI"
        assert "Jumping Rules" in preset["rulebook"]
        assert "SAEF" in preset["local_body"]
        assert preset["placing_points"][:3] == [10, 8, 6]
        assert len(preset["description"]) > 60


def test_two_refusals_eliminate_and_one_costs_four_faults():
    config = _config("show_jumping", time_allowed={"round": 72})
    result = evaluate(
        "faults_then_time",
        {
            "one": {"rounds": {"round": {"refusal": 1, "time": 70}}},
            "two": {"rounds": {"round": {"refusal": 2, "time": 70}}},
            "fell": {"rounds": {"round": {"fall": 1, "time": 40}}},
            "lost": {"rounds": {"round": {"wrong_course": 1, "time": 65}}},
        },
        config,
    )
    assert result["one"][2].primary == Decimal("4")
    assert result["two"][2].status == "EL"
    assert result["fell"][2].status == "EL"
    assert result["lost"][2].status == "EL"


def test_time_faults_are_one_per_commenced_four_seconds_and_twice_the_time_eliminates():
    config = _config("show_jumping_table_a", time_allowed={"round": 72})
    result = evaluate(
        "faults_then_time",
        {
            "just_over": {"rounds": {"round": {"time": "72.01"}}},
            "four_over": {"rounds": {"round": {"time": 76}}},
            "nine_over": {"rounds": {"round": {"time": 81}}},
            "too_slow": {"rounds": {"round": {"time": "144.5"}}},
        },
        config,
    )
    assert result["just_over"][2].primary == Decimal("1")
    assert result["four_over"][2].primary == Decimal("1")
    assert result["nine_over"][2].primary == Decimal("3")
    assert result["too_slow"][2].status == "EL"


def test_the_jump_off_decides_first_place_and_other_ties_go_to_time():
    config = _config("show_jumping", time_allowed={"round": 72, "jump_off": 45})
    result = evaluate(
        "faults_then_time",
        {
            "clear_slow_jo": {"rounds": {"round": {"time": 60}, "jump_off": {"time": 41}}},
            "clear_fast_jo": {"rounds": {"round": {"time": 70}, "jump_off": {"time": 38}}},
            "clear_jo_pole": {"rounds": {"round": {"time": 55}, "jump_off": {"knockdown": 1, "time": 35}}},
            "four_fast": {"rounds": {"round": {"knockdown": 1, "time": 58}}},
            "four_slow": {"rounds": {"round": {"knockdown": 1, "time": 66}}},
        },
        config,
    )
    assert ranks(result) == {
        "clear_fast_jo": (1, ""),
        "clear_slow_jo": (2, ""),
        "clear_jo_pole": (3, ""),
        "four_fast": (4, ""),
        "four_slow": (5, ""),
    }


def test_two_phase_puts_phase_two_riders_ahead_and_ranks_them_on_phase_two_time():
    config = _config("show_jumping_two_phase", time_allowed={"phase_1": 60, "phase_2": 40})
    result = evaluate(
        "faults_then_time",
        {
            "clear_clear_fast": {"rounds": {"phase_1": {"time": 58}, "phase_2": {"time": 33}}},
            "clear_clear_slow": {"rounds": {"phase_1": {"time": 50}, "phase_2": {"time": 36}}},
            "clear_four": {"rounds": {"phase_1": {"time": 55}, "phase_2": {"knockdown": 1, "time": 30}}},
            "clear_out": {"rounds": {"phase_1": {"time": 52}, "phase_2": {"fall": 1, "time": 20}}},
            "four_in_one": {"rounds": {"phase_1": {"knockdown": 1, "time": 45}}},
            "waiting": {"rounds": {"phase_1": {"time": 59}}},
        },
        config,
    )
    assert ranks(result) == {
        "clear_clear_fast": (1, ""),
        "clear_clear_slow": (2, ""),
        "clear_four": (3, ""),
        "clear_out": (4, ""),
        "four_in_one": (5, ""),
        "waiting": (None, ""),
    }
    assert result["clear_out"][2].breakdown["phase_out"].startswith("Eliminated in Phase 2")
    assert "phase_out" not in result["clear_four"][2].breakdown


def test_table_c_converts_faults_to_seconds():
    config = _config("show_jumping_table_c")
    result = evaluate(
        "faults_then_time",
        {
            "fast_pole": {"rounds": {"round": {"knockdown": 1, "time": 60}}},
            "clean": {"rounds": {"round": {"time": 63}}},
            "refused_once": {"rounds": {"round": {"refusal": 1, "time": 62}}},
            "refused_twice": {"rounds": {"round": {"refusal": 2, "time": 50}}},
        },
        config,
    )
    assert result["fast_pole"][2].primary == Decimal("64")
    assert ranks(result) == {
        "refused_once": (1, ""),
        "clean": (2, ""),
        "fast_pole": (3, ""),
        "refused_twice": (None, "EL"),
    }


def test_a_season_series_awards_placing_points_per_show():
    owner = User.objects.create_user(email="sj.owner@test", password="pw-123456789")
    judge = User.objects.create_user(email="sj.judge@test", password="pw-123456789")
    competition = Competition.objects.create(
        name="Jumping series", owner=owner, sport="show jumping", status="active"
    )
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    apply_preset(competition, "show_jumping_table_a")
    CompetitionOfficial.objects.create(
        competition=competition, user=judge, title="ground_jury", appointed_by=owner
    )
    for name in ("Alpha", "Bravo", "Charlie"):
        participant = competition.participants.create(name=name)
        Combination.objects.create(
            participant=participant,
            horse=Horse.objects.create(name=f"{name} horse", created_by=owner),
            rider_name=f"{name} rider",
        )

    def show(times: dict[str, dict]):
        fixture = services.create_event(competition, label="Show", actor=judge)
        sides = {side.participant.name: side for side in fixture.sides.select_related("participant")}
        services.save_results(
            fixture,
            [{"side": str(sides[name].id), "data": {"rounds": {"round": sheet}}} for name, sheet in times.items()],
            judge,
            config={"time_allowed": {"round": 70}},
        )
        services.finalise(fixture, judge, reason="Ground jury confirmed")

    show({"Alpha": {"time": 60}, "Bravo": {"time": 65}, "Charlie": {"refusal": 2, "time": 50}})
    show({"Alpha": {"knockdown": 1, "time": 55}, "Bravo": {"time": 68}, "Charlie": {"time": 62}})
    table = {row.name: row for row in compute_standings(competition)}
    # Show 1: Alpha, Bravo, Charlie eliminated. Show 2: Charlie, Bravo, Alpha (4 faults).
    assert table["Alpha"].points == 10 + 6
    assert table["Bravo"].points == 8 + 8
    assert table["Charlie"].points == 0 + 10
    assert table["Charlie"].statuses == 1
    # Alpha and Bravo are level on points; Alpha has the win.
    order = [row.name for row in compute_standings(competition)]
    assert order == ["Alpha", "Bravo", "Charlie"]
