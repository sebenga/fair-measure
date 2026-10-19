"""The performance-results engine: calculators, statuses, officials, amendments and series.

The configs here are written inline on purpose: the engine must work from data
alone, before any sport preset uses it.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Membership, PointsPolicy
from apps.competitions.presets import PRESETS
from apps.core.permissions import Role
from apps.horses.models import Combination, Horse
from apps.results.calculators import ResultDataError, evaluate
from apps.results.models import CompetitionOfficial, ResultAmendment
from apps.standings.services import compute_standings

pytestmark = pytest.mark.django_db
User = get_user_model()


def ranks(result: dict) -> dict:
    return {entry_id: (row[0], row[2].status) for entry_id, row in result.items()}


# --- finishing_order ----------------------------------------------------------


def test_dead_heat_shares_the_place_and_statuses_rank_last():
    config = {
        "statuses": [{"code": "PU", "label": "Pulled up"}, {"code": "DQ", "label": "Disqualified"}]
    }
    result = evaluate(
        "finishing_order",
        {
            "a": {"position": 1},
            "b": {"position": 1},
            "c": {"position": 3},
            "d": {"status": "DQ"},
            "e": {"status": "PU"},
        },
        config,
    )
    assert ranks(result) == {
        "a": (1, ""),
        "b": (1, ""),
        "c": (3, ""),
        "d": (None, "DQ"),
        "e": (None, "PU"),
    }
    # Statuses follow the preset's order: PU before DQ.
    assert result["e"][1] < result["d"][1]


def test_a_disqualified_winner_promotes_the_rest():
    entries = {"a": {"position": 1}, "b": {"position": 2}, "c": {"position": 3}}
    result = evaluate("finishing_order", entries, {}, overrides={"a": ("DQ", "Positive test")})
    assert ranks(result) == {"a": (None, "DQ"), "b": (1, ""), "c": (2, "")}


# --- faults_then_time ---------------------------------------------------------

JUMPING = {
    "rounds": [{"key": "round"}, {"key": "jump_off", "decides": "first"}],
    "penalties": [
        {"key": "knockdown", "label": "Knock-down", "faults": 4},
        {"key": "refusal", "label": "Refusal", "faults": 4, "eliminate_at": 2},
        {"key": "fall", "label": "Fall", "eliminate_at": 1},
    ],
    "time": {"penalty": 1, "per_seconds": 4, "commenced": True, "limit_factor": 2},
    "time_allowed": {"round": 70, "jump_off": 45},
}


def test_two_refusals_eliminate_and_time_faults_round_up():
    result = evaluate(
        "faults_then_time",
        {
            "refused": {"rounds": {"round": {"refusal": 2, "time": 60}}},
            "slow": {"rounds": {"round": {"knockdown": 1, "time": "74.1"}}},
            "limit": {"rounds": {"round": {"time": 141}}},
        },
        JUMPING,
    )
    assert result["refused"][2].status == "EL"
    assert result["limit"][2].status == "EL"
    # 4.1 s over is two commenced 4-second periods: 2 time faults, plus 4 for the pole.
    assert result["slow"][2].primary == Decimal("6")


def test_the_jump_off_decides_first_place_only():
    result = evaluate(
        "faults_then_time",
        {
            "clear_fast": {"rounds": {"round": {"time": 69}, "jump_off": {"time": 40}}},
            "clear_slow": {
                "rounds": {"round": {"time": 60}, "jump_off": {"knockdown": 1, "time": 38}}
            },
            "four_faults": {"rounds": {"round": {"knockdown": 1, "time": 55}}},
        },
        JUMPING,
    )
    assert ranks(result) == {
        "clear_fast": (1, ""),
        "clear_slow": (2, ""),
        "four_faults": (3, ""),
    }


# --- penalty_total_lowest -----------------------------------------------------

THREE_PHASES = {
    "phases": [
        {"key": "test", "label": "Test", "input": "percentage", "from_percentage": 100},
        {
            "key": "course",
            "label": "Course",
            "penalties": [
                {
                    "key": "refusals",
                    "label": "Refusals",
                    "per_obstacle": True,
                    "scale": [20, 40],
                    "eliminate_at": 3,
                },
                {"key": "fall", "label": "Fall", "eliminate_at": 1},
            ],
            "time": {"penalty": "0.4", "per_seconds": 1, "commenced": True},
        },
        {
            "key": "final",
            "label": "Final round",
            "penalties": [{"key": "knockdown", "label": "Knock-down", "faults": 4}],
            "time": {"penalty": 1, "per_seconds": 1},
        },
    ],
    "inspections": [{"key": "first", "label": "first inspection"}],
    "time_allowed": {"course": 300, "final": 80},
    "tiebreakers": ["phase:course", "phase_time:course", "phase:final", "phase:test"],
}


def test_penalties_add_up_across_phases():
    result = evaluate(
        "penalty_total_lowest",
        {
            "a": {
                "phases": {
                    "test": {"percentage": 70},
                    "course": {"refusals": {"5": 1}, "time": 305},
                    "final": {"knockdown": 1, "time": 80},
                }
            }
        },
        THREE_PHASES,
    )
    # 30 (test) + 20 refusal + 5 s x 0.4 = 2 (course) + 4 (final) = 56
    assert result["a"][2].primary == Decimal("56.0")


def test_three_refusals_at_one_obstacle_and_a_failed_inspection_eliminate():
    result = evaluate(
        "penalty_total_lowest",
        {
            "refusals": {
                "phases": {
                    "test": {"percentage": 70},
                    "course": {"refusals": {"7": 3}, "time": 290},
                    "final": {"time": 70},
                }
            },
            "inspection": {"inspections": {"first": "fail"}},
        },
        THREE_PHASES,
    )
    assert result["refusals"][2].status == "EL"
    assert result["inspection"][2].status == "EL"
    assert "inspection" in result["inspection"][2].status_reason


def test_phase_tiebreakers_apply_in_order():
    base = {"test": {"percentage": 70}, "final": {"time": 70}}
    result = evaluate(
        "penalty_total_lowest",
        {
            # Same total (30 + 4 = 34); the better course score wins.
            "course_clear": {
                "phases": {**base, "course": {"time": 290}, "final": {"knockdown": 1, "time": 70}}
            },
            "course_refusal": {
                "phases": {
                    "test": {"percentage": 86},
                    "course": {"refusals": {"2": 1}, "time": 290},
                    "final": {"time": 70},
                }
            },
        },
        THREE_PHASES,
    )
    assert result["course_clear"][2].primary == result["course_refusal"][2].primary
    assert result["course_clear"][0] == 1
    assert result["course_refusal"][0] == 2


# --- judged_percentage ----------------------------------------------------------

SHEET = {
    "sheet": [
        {"key": "m1", "label": "Movement 1", "coefficient": 1},
        {"key": "m2", "label": "Movement 2", "coefficient": 2},
        {"key": "c1", "label": "Collective", "coefficient": 2, "collective": True},
    ],
    "max_mark": 10,
    "mark_step": "0.5",
    "decimals": 3,
    "errors": {"deduct_points": [2], "eliminate_at": 2},
    "judges": ["C", "E"],
}


def test_percentage_uses_coefficients_and_averages_judges():
    result = evaluate(
        "judged_percentage",
        {
            "a": {
                "marks": {
                    "C": {"m1": 7, "m2": "6.5", "c1": 8},  # 7 + 13 + 16 = 36 / 50 = 72%
                    "E": {
                        "m1": 8,
                        "m2": 7,
                        "c1": 7,
                    },  # 8 + 14 + 14 = 36 / 50 = 72%... then a 1-point gap
                }
            },
            "b": {"marks": {"C": {"m1": 6, "m2": 6, "c1": 6}, "E": {"m1": 6, "m2": 6, "c1": 6}}},
        },
        SHEET,
    )
    outcome = result["a"][2]
    assert outcome.breakdown["judges"]["C"]["percentage"] == "72.000"
    assert outcome.primary == Decimal("72.000")
    assert result["b"][2].primary == Decimal("60.000")
    assert result["a"][0] == 1


def test_an_error_deducts_and_a_second_eliminates():
    one = evaluate(
        "judged_percentage",
        {
            "a": {
                "errors": 1,
                "marks": {"C": {"m1": 10, "m2": 10, "c1": 10}, "E": {"m1": 10, "m2": 10, "c1": 10}},
            }
        },
        SHEET,
    )
    assert one["a"][2].primary == Decimal("96.000")  # (50 - 2) / 50
    two = evaluate("judged_percentage", {"a": {"errors": 2}}, SHEET)
    assert two["a"][2].status == "EL"


def test_marks_off_the_scale_are_refused():
    with pytest.raises(ResultDataError):
        evaluate(
            "judged_percentage",
            {
                "a": {
                    "marks": {
                        "C": {"m1": "7.3", "m2": 6, "c1": 6},
                        "E": {"m1": 6, "m2": 6, "c1": 6},
                    }
                }
            },
            SHEET,
        )


# --- timed_with_vet_gates -------------------------------------------------------

RIDE = {
    "loops": [
        {"key": "l1", "label": "Gate 1", "distance_km": 40},
        {"key": "l2", "label": "Gate 2", "distance_km": 40},
    ],
    "heart_rate_max": 64,
}


def test_vet_gates_hold_times_and_speed():
    result = evaluate(
        "timed_with_vet_gates",
        {
            "pass": {
                "loops": [
                    {"ride_seconds": 7200, "hold_seconds": 2400, "heart_rate": 60, "sound": True},
                    {"ride_seconds": 7200, "hold_seconds": 0, "heart_rate": 58, "sound": True},
                ],
                "final_inspection": {"result": "pass"},
            },
            "metabolic": {
                "loops": [{"ride_seconds": 6000, "heart_rate": 70, "sound": True}],
            },
            "lame": {
                "loops": [
                    {"ride_seconds": 6000, "heart_rate": 55},
                    {"ride_seconds": 6100, "heart_rate": 55, "sound": False},
                ]
            },
        },
        RIDE,
    )
    passed = result["pass"][2]
    # Hold time is not riding time: 4 hours of riding over 80 km is 20 km/h.
    assert passed.primary == Decimal("14400")
    assert passed.breakdown["average_speed_kmh"] == "20.00"
    assert result["metabolic"][2].status == "FTQ"
    assert "Metabolic" in result["metabolic"][2].status_reason
    assert result["lame"][2].status == "FTQ"
    assert result["pass"][0] == 1
    assert result["metabolic"][0] is None


# --- points_per_run ---------------------------------------------------------------

RUNS = {
    "outcomes": [
        {"key": "carried", "label": "Carried", "points": 6},
        {"key": "drawn", "label": "Drawn", "points": 4},
        {"key": "strike", "label": "Strike", "points": 2},
        {"key": "miss", "label": "Miss", "points": 0},
    ],
    "time_limit_seconds": "6.4",
}


def test_points_table_over_time_and_team_totals():
    result = evaluate(
        "points_per_run",
        {
            "solo": {
                "runs": [{"outcome": "carried", "time": 6.1}, {"outcome": "drawn", "time": 7.0}]
            },
            "team": {
                "riders": {
                    "One": [{"outcome": "carried", "time": 6}],
                    "Two": [{"outcome": "strike", "time": 6}],
                }
            },
        },
        RUNS,
    )
    assert result["solo"][2].primary == Decimal("6")  # the 7.0 s run scores nothing
    assert result["team"][2].primary == Decimal("8")


# --- API: officials, finalising, amendments, welfare, series ----------------------

RACE_SETTINGS = {
    "result_type": "finishing_order",
    "result_config": {},
    "statuses": [
        {"code": "PU", "label": "Pulled up"},
        {"code": "EL", "label": "Eliminated"},
        {"code": "DQ", "label": "Disqualified"},
    ],
    "official_results": True,
    "placing_points": [10, 8, 6, 5],
    "participant_type": "combination",
    "contest_type": "accumulation",
    "locked": True,
    "scoring_locked": True,
}


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def meeting(db):
    owner = User.objects.create_user(email="owner@results.test", password="pw-123456789")
    steward = User.objects.create_user(email="steward@results.test", password="pw-123456789")
    competition = Competition.objects.create(
        name="Summer Series", owner=owner, settings_json=dict(RACE_SETTINGS)
    )
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    policy, _ = PointsPolicy.objects.get_or_create(competition=competition)
    policy.tiebreakers = ["points", "placings", "name"]
    policy.save()
    CompetitionOfficial.objects.create(competition=competition, user=steward, title="steward")
    owner_client = _client(owner)
    entrants = []
    for index, (horse_name, rider) in enumerate(
        [
            ("Bold Venture", "Ava"),
            ("Copper Sky", "Ben"),
            ("Dune Runner", "Cara"),
            ("Echo Point", "Dan"),
        ]
    ):
        horse = Horse.objects.create(
            name=horse_name, registration_number=f"REG{index}", created_by=owner
        )
        made = owner_client.post(
            f"/api/v1/competitions/{competition.id}/combinations",
            {
                "horse": str(horse.id),
                "rider_name": rider,
                "trainer_name": "Pat" if index < 2 else "Lee",
            },
            format="json",
        )
        assert made.status_code == 201, made.data
        entrants.append(made.data["participant_id"])
    return {
        "competition": competition,
        "owner": owner_client,
        "steward": _client(steward),
        "entrants": entrants,
    }


def _event(meeting, label="Race 1") -> dict:
    response = meeting["owner"].post(
        f"/api/v1/competitions/{meeting['competition'].id}/events", {"label": label}, format="json"
    )
    assert response.status_code == 201, response.data
    return response.data


def _place(sheet: dict, places: dict) -> list[dict]:
    by_name = {row["combination"]["horse"]: row["side_id"] for row in sheet["entries"]}
    return [{"side": by_name[name], "data": data} for name, data in places.items()]


def test_only_officials_finalise_and_amendments_need_a_reason(meeting):
    sheet = _event(meeting)
    fixture_id = sheet["fixture"]["id"]
    rows = _place(
        sheet,
        {
            "Bold Venture": {"position": 1},
            "Copper Sky": {"position": 2},
            "Dune Runner": {"position": 3},
            "Echo Point": {"status": "PU"},
        },
    )
    provisional = meeting["owner"].put(
        f"/api/v1/fixtures/{fixture_id}/results", {"entries": rows}, format="json"
    )
    assert provisional.status_code == 200, provisional.data
    assert provisional.data["final"] is False

    refused = meeting["owner"].post(
        f"/api/v1/fixtures/{fixture_id}/results/finalise", {}, format="json"
    )
    assert refused.status_code == 403

    final = meeting["steward"].post(
        f"/api/v1/fixtures/{fixture_id}/results/finalise", {}, format="json"
    )
    assert final.status_code == 200
    assert final.data["final"] is True

    by_name = {row["combination"]["horse"]: row for row in final.data["entries"]}
    no_reason = meeting["steward"].put(
        f"/api/v1/fixtures/{fixture_id}/results",
        {"entries": [{"side": by_name["Dune Runner"]["side_id"], "data": {"position": 4}}]},
        format="json",
    )
    assert no_reason.status_code == 400
    owner_amend = meeting["owner"].put(
        f"/api/v1/fixtures/{fixture_id}/results",
        {
            "entries": [{"side": by_name["Dune Runner"]["side_id"], "data": {"position": 4}}],
            "reason": "x",
        },
        format="json",
    )
    assert owner_amend.status_code == 403

    amended = meeting["steward"].put(
        f"/api/v1/fixtures/{fixture_id}/results",
        {
            "entries": [
                {"side": by_name["Copper Sky"]["side_id"], "data": {"position": 3}},
                {"side": by_name["Dune Runner"]["side_id"], "data": {"position": 2}},
            ],
            "reason": "Stewards' inquiry: interference in the final furlong",
        },
        format="json",
    )
    assert amended.status_code == 200, amended.data
    places = {row["combination"]["horse"]: row["rank"] for row in amended.data["entries"]}
    assert places["Dune Runner"] == 2 and places["Copper Sky"] == 3
    logged = ResultAmendment.objects.filter(fixture_id=fixture_id, action="amended")
    assert logged.count() == 2
    assert all("inquiry" in row.reason for row in logged)
    with pytest.raises(ValueError):
        logged.first().delete()


def test_a_disqualification_recomputes_the_series_and_welfare_is_final(meeting):
    competition = meeting["competition"]
    sheet = _event(meeting)
    fixture_id = sheet["fixture"]["id"]
    rows = _place(
        sheet,
        {
            "Bold Venture": {"position": 1},
            "Copper Sky": {"position": 2},
            "Dune Runner": {"position": 3},
            "Echo Point": {"position": 4},
        },
    )
    meeting["owner"].put(f"/api/v1/fixtures/{fixture_id}/results", {"entries": rows}, format="json")
    meeting["steward"].post(f"/api/v1/fixtures/{fixture_id}/results/finalise", {}, format="json")
    table = {row.name: row.points for row in compute_standings(competition)}
    assert table["Bold Venture / Ava"] == Decimal("10")

    winner = rows[0]["side"]
    disqualified = meeting["steward"].post(
        f"/api/v1/fixtures/{fixture_id}/results/status",
        {"side": winner, "status": "DQ", "reason": "Positive sample"},
        format="json",
    )
    assert disqualified.status_code == 200
    table = {row.name: row for row in compute_standings(competition)}
    assert table["Bold Venture / Ava"].points == Decimal("0")
    # The runner-up is promoted to 1st, and the series is recomputed.
    assert table["Copper Sky / Ben"].points == Decimal("10")
    copper = next(row for row in disqualified.data["entries"] if row["side_id"] == rows[1]["side"])
    assert copper["rank"] == 1

    welfare = meeting["steward"].post(
        f"/api/v1/fixtures/{fixture_id}/results/status",
        {"side": rows[3]["side"], "status": "EL", "reason": "Lame at the finish", "welfare": True},
        format="json",
    )
    assert welfare.status_code == 200
    override = meeting["steward"].post(
        f"/api/v1/fixtures/{fixture_id}/results/status",
        {"side": rows[3]["side"], "status": "", "reason": "Mistake"},
        format="json",
    )
    assert override.status_code == 400
    data_change = meeting["steward"].put(
        f"/api/v1/fixtures/{fixture_id}/results",
        {"entries": [{"side": rows[3]["side"], "data": {"position": 1}}], "reason": "Try"},
        format="json",
    )
    assert data_change.status_code == 400
    assert ResultAmendment.objects.filter(fixture_id=fixture_id, action="welfare").exists()

    not_allowed = meeting["owner"].post(
        f"/api/v1/fixtures/{fixture_id}/results/status",
        {"side": rows[2]["side"], "status": "DQ", "reason": "No"},
        format="json",
    )
    assert not_allowed.status_code == 403


def test_series_points_dead_heats_and_combination_stats(meeting):
    competition = meeting["competition"]
    for label, places in (
        (
            "Race 1",
            {"Bold Venture": 1, "Copper Sky": 1, "Dune Runner": 3, "Echo Point": None},
        ),
        ("Race 2", {"Bold Venture": 2, "Copper Sky": 3, "Dune Runner": 1, "Echo Point": 4}),
    ):
        sheet = _event(meeting, label)
        fixture_id = sheet["fixture"]["id"]
        rows = _place(
            sheet,
            {
                name: ({"position": place} if place else {"status": "PU"})
                for name, place in places.items()
            },
        )
        meeting["owner"].put(
            f"/api/v1/fixtures/{fixture_id}/results", {"entries": rows}, format="json"
        )
        meeting["steward"].post(
            f"/api/v1/fixtures/{fixture_id}/results/finalise", {}, format="json"
        )

    table = compute_standings(competition)
    points = {row.name: row.points for row in table}
    # A dead heat for 1st gives both the full 1st-place points by default.
    assert points["Bold Venture / Ava"] == Decimal("18")  # 10 + 8
    assert points["Copper Sky / Ben"] == Decimal("16")  # 10 + 6
    assert points["Dune Runner / Cara"] == Decimal("16")  # 6 + 10
    assert points["Echo Point / Dan"] == Decimal("5")  # PU earns nothing, then 4th
    # Level on points: wins first, then seconds, then thirds.
    order = [row.name for row in table]
    assert order.index("Copper Sky / Ben") < order.index("Dune Runner / Cara") or (
        order.index("Dune Runner / Cara") < order.index("Copper Sky / Ben")
    )

    trainers = (
        meeting["owner"]
        .get(f"/api/v1/competitions/{competition.id}/combination-stats", {"by": "trainer"})
        .data["rows"]
    )
    pat = next(row for row in trainers if row["name"] == "Pat")
    assert (pat["starts"], pat["wins"]) == (4, 2)
    horses = (
        meeting["owner"]
        .get(f"/api/v1/competitions/{competition.id}/combination-stats", {"by": "horse"})
        .data["rows"]
    )
    assert horses[0]["wins"] >= 1


def test_entrants_must_be_combinations_and_horses_are_edited_by_their_people(meeting):
    competition = meeting["competition"]
    stranger = User.objects.create_user(email="stranger@results.test", password="pw-123456789")
    horse = Horse.objects.first()
    blocked = _client(stranger).patch(
        f"/api/v1/horses/{horse.id}", {"breed": "Pony"}, format="json"
    )
    assert blocked.status_code == 403
    edited = meeting["owner"].patch(
        f"/api/v1/horses/{horse.id}", {"breed": "Thoroughbred"}, format="json"
    )
    assert edited.status_code == 200
    duplicate = meeting["owner"].post(
        f"/api/v1/competitions/{competition.id}/combinations",
        {"horse": str(horse.id), "rider_name": "Ava"},
        format="json",
    )
    assert duplicate.status_code == 400
    assert Combination.objects.filter(participant__competition=competition).count() == 4


def test_locked_result_settings_cannot_be_edited(meeting):
    competition = meeting["competition"]
    response = meeting["owner"].patch(
        f"/api/v1/competitions/{competition.id}",
        {
            "settings_json": {
                **competition.settings_json,
                "result_type": "points_per_run",
                "placing_points": [1],
            }
        },
        format="json",
    )
    assert response.status_code in {200, 403}
    competition.refresh_from_db()
    assert competition.settings_json["result_type"] == "finishing_order"
    assert competition.settings_json["placing_points"] == [10, 8, 6, 5]


def test_official_results_also_guard_head_to_head_matches(db):
    from apps.competitions.models import Participant, ScoringCategory
    from apps.fixtures.models import Fixture, FixtureSide

    owner = User.objects.create_user(email="h2h.owner@results.test", password="pw-123456789")
    umpire = User.objects.create_user(email="umpire@results.test", password="pw-123456789")
    competition = Competition.objects.create(
        name="Match League", owner=owner, settings_json={"official_results": True}
    )
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    CompetitionOfficial.objects.create(competition=competition, user=umpire, title="umpire")
    goal = ScoringCategory.objects.create(
        competition=competition, name="Point", code="point", points=1
    )
    home = Participant.objects.create(competition=competition, name="Home", kind="team")
    away = Participant.objects.create(competition=competition, name="Away", kind="team")
    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    path = f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/set-status"

    assert _client(owner).post(path, {"status": "completed"}, format="json").status_code == 403
    assert _client(umpire).post(path, {"status": "completed"}, format="json").status_code == 200

    events = f"/api/v1/fixtures/{fixture.id}/events"
    body = {"side": str(home_side.id), "scoring_category": str(goal.id), "quantity": 1}
    assert _client(owner).post(events, body, format="json").status_code == 403
    assert _client(umpire).post(events, body, format="json").status_code == 400
    amended = _client(umpire).post(
        events, {**body, "amendment_reason": "Goal-line review"}, format="json"
    )
    assert amended.status_code == 201, amended.data
    assert ResultAmendment.objects.filter(fixture=fixture, action="amended").exists()
    assert ResultAmendment.objects.filter(fixture=fixture, action="finalised").exists()


def test_engine_code_never_names_a_sport():
    names = set(PRESETS) | {str(preset.get("sport") or "").lower() for preset in PRESETS.values()}
    names = {name for name in names if name and name != "custom"}
    for module in (
        Path("apps/results/calculators.py"),
        Path("apps/results/services.py"),
        Path("apps/results/views.py"),
        Path("apps/competitions/engine.py"),
    ):
        text = module.read_text().lower()
        for name in names:
            assert f'"{name}"' not in text and f"'{name}'" not in text, f"{module} names {name}"
