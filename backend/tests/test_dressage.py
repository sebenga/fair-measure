"""Locked dressage presets: test sheets, judges' percentages, errors and freestyle."""

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


def _test_config(key: str, test: str | None = None, **event) -> dict:
    preset = PRESETS[key]
    config = {**preset["result_config"], "statuses": preset["statuses"], **event}
    if test or config.get("test"):
        config = {**config, **config["tests"][test or config["test"]]}
    return config


def _marks(sheet: list[dict], judges: list[str], value, overrides: dict | None = None) -> dict:
    marks = {judge: {item["key"]: value for item in sheet} for judge in judges}
    for judge, rows in (overrides or {}).items():
        marks[judge].update(rows)
    return {"marks": marks}


def test_dressage_presets_are_locked_under_the_fei():
    for key in ("dressage", "dressage_freestyle"):
        preset = PRESETS[key]
        assert preset["locked"] is True
        assert preset["official_results"] is True
        assert preset["result_type"] == "judged_percentage"
        assert preset["governing_body"] == "FEI"
        assert "Dressage Rules" in preset["rulebook"]
        assert "Dressage SA" in preset["local_body"]
    tests = PRESETS["dressage"]["result_config"]["tests"]
    assert set(tests) == {"prix_st_georges", "grand_prix"}
    for test in tests.values():
        coefficients = {item["coefficient"] for item in test["sheet"]}
        assert coefficients <= {1, 2}
        assert any(item.get("collective") for item in test["sheet"])


def test_the_percentage_uses_coefficients_and_averages_the_judges():
    config = _test_config("dressage")
    sheet = config["sheet"]
    judges = config["judges"]
    maximum = sum(10 * item["coefficient"] for item in sheet)
    # Judge C gives 9 on a coefficient-2 movement instead of 7: +4 points for that judge only.
    data = _marks(sheet, judges, 7, {"C": {"collected_walk": 9}})
    result = evaluate("judged_percentage", {"a": data}, config)
    outcome = result["a"][2]
    c_pct = (Decimal(7) * (maximum // 10) + 4) / maximum * 100
    assert outcome.breakdown["judges"]["E"]["percentage"] == "70.000"
    assert Decimal(outcome.breakdown["judges"]["C"]["percentage"]) == c_pct.quantize(Decimal("0.001"))
    expected = ((Decimal(70) * 4 + c_pct.quantize(Decimal("0.001"))) / 5).quantize(Decimal("0.001"))
    assert outcome.primary == expected
    assert len(outcome.breakdown["judges"]) == 5


def test_the_first_error_costs_two_points_per_judge_and_the_second_eliminates():
    config = _test_config("dressage")
    sheet = config["sheet"]
    maximum = sum(10 * item["coefficient"] for item in sheet)
    clean = _marks(sheet, config["judges"], 10)
    one = evaluate("judged_percentage", {"a": {**clean, "errors": 1}}, config)
    assert one["a"][2].primary == (Decimal(maximum - 2) / maximum * 100).quantize(Decimal("0.001"))
    two = evaluate("judged_percentage", {"a": {**clean, "errors": 2}}, config)
    assert two["a"][2].status == "EL"


def test_a_tie_on_percentage_goes_to_the_collective_marks():
    config = _test_config("dressage")
    sheet = config["sheet"]
    judges = config["judges"]
    # Same total: one gains 2 on the collective (x2 = 4), the other 4 on a coefficient-1 movement.
    better_collective = _marks(sheet, judges, 7, {judge: {"harmony": 9} for judge in judges})
    better_movement = _marks(sheet, judges, 7, {judge: {"entry": 10, "final": 8} for judge in judges})
    result = evaluate(
        "judged_percentage", {"collective": better_collective, "movement": better_movement}, config
    )
    assert result["collective"][2].primary == result["movement"][2].primary
    assert result["collective"][0] == 1
    assert result["movement"][0] == 2


def test_freestyle_counts_technical_and_artistic_half_each_and_ties_go_to_artistic():
    config = _test_config("dressage_freestyle")
    sheet = config["sheet"]
    judges = config["judges"]
    technical = [item for item in sheet if item["section"] == "technical"]
    artistic = [item for item in sheet if item["section"] == "artistic"]
    mixed = _marks(sheet, judges, 8)
    for judge in judges:
        for item in artistic:
            mixed["marks"][judge][item["key"]] = 6
    result = evaluate("judged_percentage", {"a": mixed}, config)
    assert result["a"][2].primary == Decimal("70.000")  # (80 + 60) / 2

    artistic_strong = _marks(sheet, judges, 7)
    technical_strong = _marks(sheet, judges, 7)
    for judge in judges:
        for item in artistic:
            artistic_strong["marks"][judge][item["key"]] = 8
            technical_strong["marks"][judge][item["key"]] = 6
        for item in technical:
            artistic_strong["marks"][judge][item["key"]] = 6
            technical_strong["marks"][judge][item["key"]] = 8
    tied = evaluate("judged_percentage", {"art": artistic_strong, "tech": technical_strong}, config)
    assert tied["art"][2].primary == tied["tech"][2].primary == Decimal("70.000")
    assert tied["art"][0] == 1 and tied["tech"][0] == 2


def _show():
    owner = User.objects.create_user(email="dr.owner@test", password="pw-123456789")
    judge = User.objects.create_user(email="dr.judge@test", password="pw-123456789")
    competition = Competition.objects.create(name="Dressage", owner=owner, sport="dressage", status="active")
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    apply_preset(competition, "dressage")
    CompetitionOfficial.objects.create(competition=competition, user=judge, title="judge", appointed_by=owner)
    participant = competition.participants.create(name="Echo / Ava")
    Combination.objects.create(
        participant=participant, horse=Horse.objects.create(name="Echo", created_by=owner), rider_name="Ava"
    )
    fixture = services.create_event(competition, label="Class 1", actor=judge)
    return competition, judge, fixture


def test_an_event_picks_its_test_and_judges_but_cannot_change_the_scoring():
    competition, judge, fixture = _show()
    side = fixture.sides.get()
    services.save_results(fixture, [], judge, config={"test": "grand_prix", "judges": ["C", "E", "B"]})
    config = services.sheet_config(fixture)
    assert {item["key"] for item in config["sheet"]} >= {"piaffe_1", "passage_1"}
    assert config["judges"] == ["C", "E", "B"]
    data = _marks(config["sheet"], ["C", "E", "B"], 6)
    entries = services.save_results(fixture, [{"side": str(side.id), "data": data}], judge)
    assert entries[0].primary == Decimal("60.000")

    for bad in (
        {"judges": ["C", "E"]},
        {"judges": ["C", "E", "X"]},
        {"judges": ["C", "C", "E"]},
        {"test": "novice"},
        {"sheet": [{"key": "m", "label": "Easy", "coefficient": 1}]},
        {"errors": {"deduct_points": [0]}},
    ):
        with pytest.raises(ValidationError):
            services.save_results(fixture, [], judge, config=bad)


def test_officials_eliminate_for_lameness_and_that_cannot_be_overridden():
    competition, judge, fixture = _show()
    side = fixture.sides.get()
    services.set_status(fixture, side.id, "EL", judge, reason="Lameness at the final halt", welfare=True)
    with pytest.raises(ValidationError):
        services.set_status(fixture, side.id, "", judge, reason="Changed my mind")
    assert fixture.sides.get().entry_result.effective_status == "EL"
