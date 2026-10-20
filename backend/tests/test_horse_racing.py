"""Locked flat and jumps racing presets: finishing order and championships by wins."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

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


def _config(key: str) -> dict:
    preset = PRESETS[key]
    return {**preset["result_config"], "statuses": preset["statuses"]}


def test_flat_and_jumps_presets_follow_the_ifha_and_stay_locked():
    flat = PRESETS["horse_racing_flat"]
    jumps = PRESETS["horse_racing_jumps"]
    for preset in (flat, jumps):
        assert preset["locked"] is True
        assert preset["official_results"] is True
        assert preset["result_type"] == "finishing_order"
        assert preset["participant_type"] == "combination"
        assert preset["governing_body"] == "IFHA"
        assert "International Agreement" in preset["rulebook"]
        assert "NHA" in preset["local_body"]
        assert preset["tiebreakers"][:3] == ["wins", "seconds", "thirds"]
        assert any(rule["name"] == "No wagering" for rule in preset["rules"])
        codes = [item["code"] for item in preset["statuses"]]
        for code in ("PU", "F", "UR", "BD", "R", "DNF", "DQ"):
            assert code in codes
    flat_runners = {field["key"] for field in flat["result_config"]["runner_fields"]}
    jump_runners = {field["key"] for field in jumps["result_config"]["runner_fields"]}
    assert "draw" in flat_runners
    assert "draw" not in jump_runners
    flat_surface = next(
        field for field in flat["result_config"]["card_fields"] if field["key"] == "surface"
    )
    jump_surface = next(
        field for field in jumps["result_config"]["card_fields"] if field["key"] == "surface"
    )
    assert flat_surface["options"] == ["Turf", "Sand", "All-weather"]
    assert jump_surface["options"] == ["Hurdle", "Steeplechase"]


def test_a_dead_heat_shares_first_and_non_finishers_rank_below():
    result = evaluate(
        "finishing_order",
        {
            "a": {"position": 1, "margin": "", "time": "71.42"},
            "b": {"position": 1, "margin": "dead heat"},
            "c": {"position": 3, "margin": "neck"},
            "d": {"status": "PU"},
        },
        _config("horse_racing_flat"),
    )
    assert result["a"][0] == 1
    assert result["b"][0] == 1
    assert result["c"][0] == 3
    assert result["d"][0] is None
    assert result["d"][2].status == "PU"
    assert result["d"][1] > result["c"][1]


def _meeting():
    owner = User.objects.create_user(email="racing.owner@test", password="pw-123456789")
    steward = User.objects.create_user(email="racing.steward@test", password="pw-123456789")
    competition = Competition.objects.create(
        name="Flat series", owner=owner, sport="horse racing", status="active"
    )
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    apply_preset(competition, "horse_racing_flat")
    CompetitionOfficial.objects.create(
        competition=competition, user=steward, title="steward", appointed_by=owner
    )
    horses = []
    for index, name in enumerate(("Alpha", "Bravo", "Charlie", "Delta")):
        horse = Horse.objects.create(name=name, created_by=owner)
        participant = competition.participants.create(name=f"{name} / J{index}")
        Combination.objects.create(
            participant=participant,
            horse=horse,
            rider_name=f"Jockey {index}",
            trainer_name="Pat" if index < 2 else "Lee",
        )
        horses.append(horse)
    return competition, steward, horses


def _race(competition, steward, places: dict[str, dict]):
    fixture = services.create_event(competition, label="Race", actor=steward)
    rows = []
    by_horse = {
        combo.horse.name: combo.participant_id
        for combo in Combination.objects.filter(participant__competition=competition)
    }
    sides = {side.participant_id: side for side in fixture.sides.all()}
    for horse_name, data in places.items():
        rows.append({"side": str(sides[by_horse[horse_name]].id), "data": data})
    services.save_results(fixture, rows, steward)
    services.finalise(fixture, steward, reason="Weighed in")
    return fixture


def test_disqualifying_the_winner_recomputes_the_championship():
    competition, steward, _horses = _meeting()
    fixture = _race(
        competition,
        steward,
        {
            "Alpha": {"position": 1, "prize": "50000"},
            "Bravo": {"position": 2, "prize": "20000"},
            "Charlie": {"position": 3, "prize": "10000"},
            "Delta": {"status": "PU"},
        },
    )
    table = {row.name: row for row in compute_standings(competition)}
    assert table["Alpha / J0"].wins == 1
    assert table["Delta / J3"].wins == 0
    assert table["Delta / J3"].points == 0

    alpha_side = fixture.sides.get(participant__name="Alpha / J0")
    services.set_status(fixture, alpha_side.id, "DQ", steward, reason="Inquiry: interference")
    table = {row.name: row for row in compute_standings(competition)}
    assert table["Alpha / J0"].wins == 0
    assert table["Bravo / J1"].wins == 1
    assert fixture.sides.get(participant__name="Bravo / J1").entry_result.rank == 1
    assert fixture.sides.get(participant__name="Charlie / J2").entry_result.rank == 2

    horses = services.combination_stats(competition, "horse")
    bravo = next(row for row in horses if row["name"] == "Bravo")
    delta = next(row for row in horses if row["name"] == "Delta")
    assert bravo["wins"] == 1
    assert bravo["prize"] == "20000"
    assert delta["wins"] == 0
    assert delta["prize"] == "0"
    assert horses[0]["name"] == "Bravo"


def test_the_racing_preset_refuses_a_change_to_its_result_type():
    competition, _steward, _horses = _meeting()
    owner = competition.owner
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.patch(
        f"/api/v1/competitions/{competition.id}",
        {"settings_json": {**competition.settings_json, "result_type": "points_per_run"}},
        format="json",
    )
    assert response.status_code == 200
    competition.refresh_from_db()
    assert competition.settings_json["result_type"] == "finishing_order"
    assert competition.settings_json["governing_body"] == "IFHA"
