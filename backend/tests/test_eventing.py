"""Locked eventing preset: three phases, inspections, eliminations and tie-breakers."""

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

TIMES = {"cross_country": 360, "jumping": 80}


def _config() -> dict:
    preset = PRESETS["eventing"]
    return {**preset["result_config"], "statuses": preset["statuses"], "time_allowed": TIMES}


def _run(dressage, cross_country=None, jumping=None, inspections=None) -> dict:
    data = {
        "phases": {
            "dressage": {"percentage": dressage},
            "cross_country": cross_country or {"time": 355},
            "jumping": jumping or {"time": 78},
        }
    }
    if inspections:
        data["inspections"] = inspections
    return data


def test_eventing_is_locked_under_the_fei_with_three_phases():
    preset = PRESETS["eventing"]
    assert preset["locked"] is True
    assert preset["official_results"] is True
    assert preset["result_type"] == "penalty_total_lowest"
    assert preset["governing_body"] == "FEI"
    assert "Eventing Rules" in preset["rulebook"]
    assert "Eventing SA" in preset["local_body"]
    phases = [phase["key"] for phase in preset["result_config"]["phases"]]
    assert phases == ["dressage", "cross_country", "jumping"]
    inspections = [item["key"] for item in preset["result_config"]["inspections"]]
    assert inspections == ["before_cross_country", "before_jumping"]


def test_penalties_add_up_across_the_three_phases():
    result = evaluate(
        "penalty_total_lowest",
        {
            "a": _run(
                "68.5",
                cross_country={"refusals": {"7": 2}, "time": "366.2"},
                jumping={"knockdown": 1, "refusal": 1, "time": "81.5"},
            )
        },
        _config(),
    )
    outcome = result["a"][2]
    # Dressage 31.5. Cross-country: 20 + 40 at fence 7, 7 commenced seconds x 0.4 = 2.8.
    # Jumping: 4 + 4, 2 commenced seconds x 0.4 = 0.8.
    phases = outcome.breakdown["phases"]
    assert Decimal(phases["dressage"]["penalties"]) == Decimal("31.5")
    assert Decimal(phases["cross_country"]["penalties"]) == Decimal("62.8")
    assert Decimal(phases["jumping"]["penalties"]) == Decimal("8.8")
    assert outcome.primary == Decimal("103.1")


def test_three_refusals_at_one_fence_or_four_on_the_course_eliminate():
    result = evaluate(
        "penalty_total_lowest",
        {
            "same_fence": _run(70, cross_country={"refusals": {"9": 3}, "time": 350}),
            "four_fences": _run(70, cross_country={"refusals": {"3": 1, "5": 1, "9": 1, "12": 1}, "time": 350}),
            "two_fences": _run(70, cross_country={"refusals": {"3": 1, "5": 1}, "time": 350}),
            "fell": _run(70, cross_country={"rider_fall": 1, "time": 200}),
            "too_slow": _run(70, cross_country={"time": 721}),
        },
        _config(),
    )
    assert result["same_fence"][2].status == "EL"
    assert result["four_fences"][2].status == "EL"
    assert result["two_fences"][2].status == ""
    assert result["fell"][2].status == "EL"
    assert result["too_slow"][2].status == "EL"


def test_a_failed_horse_inspection_eliminates():
    result = evaluate(
        "penalty_total_lowest",
        {
            "passed": _run(70, inspections={"before_cross_country": "pass", "before_jumping": "pass"}),
            "failed": _run(70, inspections={"before_cross_country": "pass", "before_jumping": "fail"}),
        },
        _config(),
    )
    assert result["passed"][2].status == ""
    assert result["failed"][2].status == "EL"
    assert "before jumping" in result["failed"][2].status_reason


def test_tie_breakers_apply_in_order():
    result = evaluate(
        "penalty_total_lowest",
        {
            # Level on 34.0. Better cross-country score wins.
            "xc_clear": _run(70, jumping={"knockdown": 1, "time": 78}),
            "xc_refusal": _run(86, cross_country={"refusals": {"4": 1}, "time": 355}),
            # Level on 30.0 and both clear cross-country: the faster cross-country time wins.
            "xc_fast": _run(70, cross_country={"time": 340}),
            "xc_slow": _run(70, cross_country={"time": 358}),
        },
        _config(),
    )
    assert result["xc_fast"][0] == 1 and result["xc_slow"][0] == 2
    assert result["xc_clear"][2].primary == result["xc_refusal"][2].primary == Decimal("34.0")
    assert result["xc_clear"][0] == 3 and result["xc_refusal"][0] == 4


def test_a_season_of_events_awards_placing_points():
    owner = User.objects.create_user(email="ev.owner@test", password="pw-123456789")
    jury = User.objects.create_user(email="ev.jury@test", password="pw-123456789")
    competition = Competition.objects.create(name="Eventing", owner=owner, sport="eventing", status="active")
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    apply_preset(competition, "eventing")
    CompetitionOfficial.objects.create(competition=competition, user=jury, title="ground_jury", appointed_by=owner)
    for name in ("Alpha", "Bravo"):
        participant = competition.participants.create(name=name)
        Combination.objects.create(
            participant=participant,
            horse=Horse.objects.create(name=f"{name} horse", created_by=owner),
            rider_name=name,
        )
    fixture = services.create_event(competition, label="Horse trials", actor=jury)
    sides = {side.participant.name: side for side in fixture.sides.select_related("participant")}
    services.save_results(
        fixture,
        [
            {"side": str(sides["Alpha"].id), "data": _run(72)},
            {"side": str(sides["Bravo"].id), "data": _run(75, jumping={"knockdown": 1, "time": 78})},
        ],
        jury,
        config={"time_allowed": TIMES},
    )
    services.finalise(fixture, jury, reason="Ground jury confirmed")
    table = {row.name: row.points for row in compute_standings(competition)}
    assert table == {"Alpha": 10, "Bravo": 8}
