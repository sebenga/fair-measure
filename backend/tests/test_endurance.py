"""Locked endurance preset: vet gates, FTQ codes, holds, speed and Best Condition."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from apps.competitions.models import Competition, Membership
from apps.competitions.presets import PRESETS, apply_preset
from apps.core.permissions import Role
from apps.horses.models import Combination, Horse
from apps.results import services
from apps.results.calculators import evaluate
from apps.results.models import CompetitionOfficial

pytestmark = pytest.mark.django_db
User = get_user_model()


def _config(test: str = "cei1_80") -> dict:
    preset = PRESETS["endurance"]
    config = {**preset["result_config"], "statuses": preset["statuses"]}
    return {**config, **config["tests"][test]}


def _ride(*seconds, hold=2400, heart_rate=58, final="pass", **extra) -> dict:
    loops = [
        {"ride_seconds": value, "hold_seconds": hold, "heart_rate": heart_rate, "sound": True, "presentation_seconds": 300}
        for value in seconds
    ]
    data = {"loops": loops, "final_inspection": {"result": final}}
    data.update(extra)
    return data


def test_endurance_is_locked_under_the_fei_with_ride_classes():
    preset = PRESETS["endurance"]
    assert preset["locked"] is True
    assert preset["official_results"] is True
    assert preset["result_type"] == "timed_with_vet_gates"
    assert preset["governing_body"] == "FEI"
    assert "Endurance Rules" in preset["rulebook"]
    assert "Endurance Ride Association" in preset["local_body"]
    tests = preset["result_config"]["tests"]
    assert {key: sum(loop["distance_km"] for loop in test["loops"]) for key, test in tests.items()} == {
        "intro_40": 40,
        "cei1_80": 80,
        "cei2_120": 120,
        "cei3_160": 160,
    }


def test_holds_are_excluded_and_average_speed_is_correct():
    # 80 km in 2 h 40 min of riding = 30 km/h; the 80 minutes of holds do not count.
    result = evaluate("timed_with_vet_gates", {"a": _ride(3600, 3600, 2400)}, _config())
    outcome = result["a"][2]
    assert outcome.primary == Decimal("9600")
    assert outcome.breakdown["hold_seconds"] == "7200"
    assert outcome.breakdown["average_speed_kmh"] == "30.00"
    assert result["a"][0] == 1


def test_a_failure_at_any_gate_removes_the_horse_from_the_ranking():
    lame = _ride(3000, 3000, 2000)
    lame["loops"][1]["sound"] = False
    high = _ride(3000, 3000, 2000)
    high["loops"][0]["heart_rate"] = 66
    coded = _ride(3000, 3000, 2000)
    coded["loops"][2]["ftq_code"] = "ME"
    late = _ride(3000, 3000, 2000)
    late["loops"][0]["presentation_seconds"] = 960
    result = evaluate(
        "timed_with_vet_gates",
        {
            "fast_but_lame": lame,
            "heart_rate": high,
            "metabolic": coded,
            "late": late,
            "clean": _ride(3500, 3500, 2500),
            "final_fail": _ride(3000, 3000, 2000, final="ftq"),
        },
        _config(),
    )
    assert result["clean"][0] == 1
    for name, reason in (
        ("fast_but_lame", "Lameness"),
        ("heart_rate", "heart rate"),
        ("metabolic", "ME · Metabolic"),
        ("late", "Not presented in time"),
        ("final_fail", "Final inspection"),
    ):
        assert result[name][0] is None, name
        assert result[name][2].status == "FTQ", name
        assert reason in result[name][2].status_reason, name


def test_a_speed_limit_eliminates_a_ride_outside_it():
    # 40 km in 2 h = 20 km/h, above the 16 km/h national limit.
    result = evaluate(
        "timed_with_vet_gates",
        {"too_fast": _ride(3600, 3600), "steady": _ride(4800, 4800)},
        _config("intro_40"),
    )
    assert result["too_fast"][2].status == "EL"
    assert "above the 16 km/h limit" in result["too_fast"][2].status_reason
    assert result["steady"][0] == 1


def test_best_condition_adds_vet_marks_time_and_weight():
    vet = {"recovery": 9, "hydration": 9, "lesions": 10, "soundness": 9, "movement": 9}
    tired = {"recovery": 6, "hydration": 7, "lesions": 9, "soundness": 8, "movement": 7}
    result = evaluate(
        "timed_with_vet_gates",
        {
            "winner": _ride(3000, 3000, 2000, best_condition={"marks": tired, "weight_kg": 70}),
            "second": _ride(3000, 3300, 2100, best_condition={"marks": vet, "weight_kg": 80}),
            "no_bc": _ride(3100, 3300, 2200),
        },
        _config(),
    )
    winner = result["winner"][2].breakdown["best_condition"]
    second = result["second"][2].breakdown["best_condition"]
    # Winner: vet 370, time 200, weight 100 - 10 = 90 -> 660.
    assert winner == {
        "rank": 2,
        "score": "660.00",
        "vet": "370.00",
        "time_points": "200.00",
        "weight_points": "90.00",
    }
    # Second: 400 seconds behind = 6.67 min -> 193.33 time points; vet 460; heaviest 100 -> 753.33.
    assert second["rank"] == 1
    assert second["score"] == "753.33"
    assert "best_condition" not in result["no_bc"][2].breakdown
    # Best Condition never changes the race order.
    assert result["winner"][0] == 1 and result["second"][0] == 2


def test_an_event_picks_its_ride_class():
    owner = User.objects.create_user(email="end.owner@test", password="pw-123456789")
    vet = User.objects.create_user(email="end.vet@test", password="pw-123456789")
    competition = Competition.objects.create(name="Endurance", owner=owner, sport="endurance", status="active")
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    apply_preset(competition, "endurance")
    CompetitionOfficial.objects.create(competition=competition, user=vet, title="vet", appointed_by=owner)
    participant = competition.participants.create(name="Karoo / Esi")
    Combination.objects.create(
        participant=participant, horse=Horse.objects.create(name="Karoo", created_by=owner), rider_name="Esi"
    )
    fixture = services.create_event(competition, label="Ride", actor=vet)
    assert len(services.sheet_config(fixture)["loops"]) == 3
    services.save_results(fixture, [], vet, config={"test": "cei3_160"})
    assert len(services.sheet_config(fixture)["loops"]) == 5
    with pytest.raises(ValidationError):
        services.save_results(fixture, [], vet, config={"heart_rate_max": 80})
