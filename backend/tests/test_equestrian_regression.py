"""Equestrian regression: every locked horse-sport preset, end to end through the API.

For each preset: create the competition, enter combinations (or teams), appoint an
official, record a full event with at least one elimination and one tie, confirm the
ranking and tie-breakers, finalise, and check the series table. Then: the preset is
locked, it names its governing body and rulebook, only officials confirm or amend,
every amendment carries a reason, and no engine module names a sport.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.equestrian_presets import EQUESTRIAN_PRESETS
from apps.competitions.models import Competition, Participant, RosterMember
from apps.competitions.presets import PRESETS
from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide
from apps.horses.models import Horse
from apps.results.models import ResultAmendment
from apps.results.services import placing_points_for
from apps.standings.services import compute_standings

pytestmark = pytest.mark.django_db
User = get_user_model()

NAMES = ["A", "B", "C", "D"]


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --- Event data per result preset: (event settings, data per entrant, official status, expected) ---
# expected: entrant -> rank (int) or a status code. Every case has a tie or a tie-break and an elimination.


def _rounds(**rounds):
    return {"rounds": rounds}


def _dressage_marks(key: str, value, overrides=None) -> dict:
    config = PRESETS[key]["result_config"]
    if "tests" in config:
        sheet = config["tests"][config["test"]]["sheet"]
    else:
        sheet = config["sheet"]
    marks = {judge: {item["key"]: value for item in sheet} for judge in config["judges"]}
    for judge in marks:
        marks[judge].update(overrides or {})
    return {"marks": marks}


def _freestyle(technical, artistic) -> dict:
    config = PRESETS["dressage_freestyle"]["result_config"]
    return {
        "marks": {
            judge: {
                item["key"]: (artistic if item["section"] == "artistic" else technical)
                for item in config["sheet"]
            }
            for judge in config["judges"]
        }
    }


def _phases(dressage, cross_country=None, jumping=None, inspections=None) -> dict:
    data = {
        "inspections": inspections or {"before_cross_country": "pass", "before_jumping": "pass"},
        "phases": {
            "dressage": {"percentage": dressage},
            "cross_country": cross_country or {"time": 355},
            "jumping": jumping or {"time": 78},
        },
    }
    return data


def _gates(*seconds, **last) -> dict:
    loops = [
        {"ride_seconds": value, "hold_seconds": 2400, "heart_rate": 58, "sound": True, "presentation_seconds": 300}
        for value in seconds
    ]
    if last:
        loops[-1].update(last)
    return {"loops": loops, "final_inspection": {"result": "pass"}}


def _pegs(*outcomes, run_off=None) -> dict:
    data = {"runs": [{"outcome": outcome, "time": "6.1"} for outcome in outcomes]}
    if run_off:
        data["run_off"] = [{"outcome": run_off, "time": "6.0"}]
    return data


CASES = {
    "horse_racing_flat": (
        {"card": {"grade": "Listed", "distance_m": 1600, "surface": "Turf", "going": "Good"}},
        {"A": {"position": 1, "prize": "50000"}, "B": {"position": 1, "margin": "dead heat"}, "C": {"position": 3}, "D": {"status": "PU"}},
        None,
        {"A": 1, "B": 1, "C": 3, "D": "PU"},
    ),
    "horse_racing_jumps": (
        {"card": {"surface": "Hurdle"}},
        {"A": {"position": 1}, "B": {"position": 1}, "C": {"position": 3}, "D": {"status": "F"}},
        None,
        {"A": 1, "B": 1, "C": 3, "D": "F"},
    ),
    "show_jumping": (
        {"time_allowed": {"round": 72, "jump_off": 45}},
        {
            "A": _rounds(round={"time": 60}, jump_off={"time": 38}),
            "B": _rounds(round={"time": 58}, jump_off={"time": 40}),
            "C": _rounds(round={"knockdown": 1, "time": 55}),
            "D": _rounds(round={"refusal": 2, "time": 50}),
        },
        None,
        {"A": 1, "B": 2, "C": 3, "D": "EL"},
    ),
    "show_jumping_table_a": (
        {"time_allowed": {"round": 72}},
        {
            "A": _rounds(round={"time": 60}),
            "B": _rounds(round={"time": 60}),
            "C": _rounds(round={"knockdown": 1, "time": 55}),
            "D": _rounds(round={"fall": 1, "time": 30}),
        },
        None,
        {"A": 1, "B": 1, "C": 3, "D": "EL"},
    ),
    "show_jumping_two_phase": (
        {"time_allowed": {"phase_1": 60, "phase_2": 40}},
        {
            "A": _rounds(phase_1={"time": 55}, phase_2={"time": 33}),
            "B": _rounds(phase_1={"time": 50}, phase_2={"time": 33}),
            "C": _rounds(phase_1={"knockdown": 1, "time": 45}),
            "D": _rounds(phase_1={"wrong_course": 1, "time": 40}),
        },
        None,
        {"A": 1, "B": 1, "C": 3, "D": "EL"},
    ),
    "show_jumping_table_c": (
        {},
        {
            "A": _rounds(round={"knockdown": 1, "time": 60}),
            "B": _rounds(round={"time": 64}),
            "C": _rounds(round={"time": 70}),
            "D": _rounds(round={"refusal": 2, "time": 50}),
        },
        None,
        {"A": 1, "B": 1, "C": 3, "D": "EL"},
    ),
    "dressage": (
        {"test": "prix_st_georges"},
        {
            "A": _dressage_marks("dressage", 7, {"harmony": 9}),
            "B": _dressage_marks("dressage", 7, {"entry": 10, "final": 8}),
            "C": _dressage_marks("dressage", 6),
            "D": {**_dressage_marks("dressage", 8), "errors": 2},
        },
        None,
        {"A": 1, "B": 2, "C": 3, "D": "EL"},
    ),
    "dressage_freestyle": (
        {},
        {"A": _freestyle(6, 8), "B": _freestyle(8, 6), "C": _freestyle(6, 6), "D": _freestyle(9, 9)},
        ("D", "EL", "Lameness at the final halt"),
        {"A": 1, "B": 2, "C": 3, "D": "EL"},
    ),
    # C 40.0 alone; A and B level on 34.0, and A wins on the cross-country score.
    "eventing": (
        {"time_allowed": {"cross_country": 360, "jumping": 80}},
        {
            "A": _phases(70, jumping={"knockdown": 1, "time": 78}),
            "B": _phases(86, cross_country={"refusals": {"4": 1}, "time": 355}),
            "C": _phases(60),
            "D": _phases(75, inspections={"before_cross_country": "pass", "before_jumping": "fail"}),
        },
        None,
        {"A": 1, "B": 2, "C": 3, "D": "EL"},
    ),
    "endurance": (
        {"test": "cei1_80"},
        {
            "A": _gates(3600, 3600, 2400),
            "B": _gates(3600, 3600, 2400),
            "C": _gates(3700, 3700, 2500),
            "D": _gates(3500, 3500, 2300, ftq_code="GA"),
        },
        None,
        {"A": 1, "B": 1, "C": 3, "D": "FTQ"},
    ),
    "tent_pegging": (
        {"test": "lance"},
        {
            "A": _pegs("carried", "carried", "drawn", run_off="carried"),
            "B": _pegs("carried", "drawn", "carried", run_off="strike"),
            "C": _pegs("strike", "strike", "drawn"),
            "D": _pegs("carried", "carried", "carried"),
        },
        ("D", "EL", "Horse lame after run 3"),
        {"A": 1, "B": 2, "C": 3, "D": "EL"},
    ),
    "tent_pegging_team": (
        {"test": "lance"},
        {
            "A": {"riders": {f"Rider {n}": [{"outcome": "carried", "time": "6"}] for n in range(1, 5)}, "run_off": [{"outcome": "drawn", "time": "6"}]},
            "B": {"riders": {f"Rider {n}": [{"outcome": "carried", "time": "6"}] for n in range(1, 5)}},
            "C": {"riders": {f"Rider {n}": [{"outcome": "strike", "time": "6"}] for n in range(1, 5)}},
            "D": {"riders": {f"Rider {n}": [{"outcome": "carried", "time": "6"}] for n in range(1, 5)}},
        },
        ("D", "DQ", "Team rider not registered"),
        {"A": 1, "B": 2, "C": 3, "D": "DQ"},
    ),
}

HEAD_TO_HEAD = ("polo_handicap", "polo_open", "horseball")


def test_every_equestrian_preset_is_covered_here():
    assert set(EQUESTRIAN_PRESETS) == set(CASES) | set(HEAD_TO_HEAD)


@pytest.fixture
def people(db):
    return {
        "owner": User.objects.create_user(email="owner@eq.test", password="pw-123456789"),
        "official": User.objects.create_user(email="official@eq.test", password="pw-123456789"),
    }


def _create(owner, key) -> Competition:
    response = _client(owner).post(
        "/api/v1/competitions", {"name": f"Regression {key}", "preset": key}, format="json"
    )
    assert response.status_code == 201, response.data
    return Competition.objects.get(pk=response.data["id"])


def _assert_locked_and_governed(owner, competition, key):
    client = _client(owner)
    preset = PRESETS[key]
    detail = client.get(f"/api/v1/competitions/{competition.id}").data
    settings = detail["settings_json"]
    assert settings["locked"] is True and settings["scoring_locked"] is True, key
    assert settings["official_results"] is True, key
    assert settings["governing_body"] == preset["governing_body"], key
    assert settings["rulebook"] == preset["rulebook"], key
    assert settings["description"], key
    assert detail["rules"], key
    base = f"/api/v1/competitions/{competition.id}"
    assert client.post(f"{base}/scoring-categories", {"name": "Bonus", "code": "b", "points": "1"}, format="json").status_code == 403, key
    assert client.patch(f"{base}/points-policy", {"win_points": "10"}, format="json").status_code == 403, key
    assert client.post(f"{base}/apply-preset", {"preset": "custom"}, format="json").status_code == 403, key
    tampered = {**settings, "result_type": "points_per_run", "result_config": {}, "league_points": {"win": 99}}
    client.patch(base, {"settings_json": tampered}, format="json")
    competition.refresh_from_db()
    for field in ("result_type", "result_config", "league_points", "statuses", "tiebreakers"):
        assert competition.settings_json.get(field) == settings.get(field), (key, field)


def _entrants(owner, competition, key) -> dict:
    client = _client(owner)
    if PRESETS[key]["participant_type"] == "combination":
        entrants = {}
        for name in NAMES:
            horse = Horse.objects.create(name=f"{key} {name}", created_by=owner)
            response = client.post(
                f"/api/v1/competitions/{competition.id}/combinations",
                {"horse": str(horse.id), "rider_name": f"Rider {name}", "trainer_name": "Pat"},
                format="json",
            )
            assert response.status_code == 201, (key, response.data)
            entrants[name] = response.data["participant_id"]
        return entrants
    entrants = {}
    for name in NAMES:
        response = client.post(
            f"/api/v1/competitions/{competition.id}/participants",
            {"name": f"Team {name}", "kind": "team"},
            format="json",
        )
        assert response.status_code == 201, (key, response.data)
        entrants[name] = response.data["id"]
    return entrants


def _appoint(owner, official, competition, title) -> None:
    response = _client(owner).post(
        f"/api/v1/competitions/{competition.id}/officials",
        {"user": str(official.id), "title": title},
        format="json",
    )
    assert response.status_code == 201, response.data


@pytest.mark.parametrize("key", sorted(CASES))
def test_a_full_event_for_every_result_preset(people, key):
    owner, official = people["owner"], people["official"]
    competition = _create(owner, key)
    _assert_locked_and_governed(owner, competition, key)
    entrants = _entrants(owner, competition, key)
    _appoint(owner, official, competition, "steward" if "racing" in key else "judge")

    event_settings, data, official_status, expected = CASES[key]
    created = _client(owner).post(
        f"/api/v1/competitions/{competition.id}/events", {"label": "Event 1"}, format="json"
    )
    assert created.status_code == 201, (key, created.data)
    fixture_id = created.data["fixture"]["id"]
    side_of = {entry["participant_id"]: entry["side_id"] for entry in created.data["entries"]}
    sides = {name: side_of[participant] for name, participant in entrants.items()}

    # The owner records provisional results; the event's settings are open, the scoring is not.
    sheet_path = f"/api/v1/fixtures/{fixture_id}/results"
    rows = [{"side": sides[name], "data": data[name]} for name in NAMES]
    saved = _client(owner).put(sheet_path, {"entries": rows, "config": event_settings}, format="json")
    assert saved.status_code == 200, (key, saved.data)
    assert _client(owner).put(sheet_path, {"entries": [], "config": {"statuses": []}}, format="json").status_code == 400, key

    if official_status:
        name, code, reason = official_status
        # Only an official can eliminate, and every decision needs a reason.
        assert _client(owner).post(f"{sheet_path}/status", {"side": sides[name], "status": code, "reason": reason}, format="json").status_code == 403, key
        assert _client(official).post(f"{sheet_path}/status", {"side": sides[name], "status": code}, format="json").status_code == 400, key
        decided = _client(official).post(
            f"{sheet_path}/status", {"side": sides[name], "status": code, "reason": reason, "welfare": code == "EL"}, format="json"
        )
        assert decided.status_code == 200, (key, decided.data)

    # Only an official finalises.
    assert _client(owner).post(f"{sheet_path}/finalise", {}, format="json").status_code == 403, key
    final = _client(official).post(f"{sheet_path}/finalise", {"reason": "Confirmed"}, format="json")
    assert final.status_code == 200, (key, final.data)
    by_side = {entry["side_id"]: entry for entry in final.data["entries"]}
    for name, want in expected.items():
        entry = by_side[sides[name]]
        if isinstance(want, int):
            assert entry["rank"] == want, (key, name, entry["rank"], entry["breakdown"])
        else:
            assert entry["rank"] is None and entry["effective_status"] == want, (key, name, entry)

    # Amending a final result: officials only, and only with a reason that is logged.
    tweak = [{"side": sides["C"], "data": data["C"] | {"note": "amended"}}]
    assert _client(owner).put(sheet_path, {"entries": tweak, "reason": "Typo"}, format="json").status_code == 403, key
    assert _client(official).put(sheet_path, {"entries": tweak}, format="json").status_code == 400, key
    amended = _client(official).put(sheet_path, {"entries": tweak, "reason": "Corrected the sheet"}, format="json")
    assert amended.status_code == 200, (key, amended.data)
    log = ResultAmendment.objects.filter(fixture_id=fixture_id)
    assert log.filter(action="finalised").exists(), key
    assert log.filter(action="amended", reason="Corrected the sheet").exists(), key
    assert all(row.reason for row in log.exclude(action__in=["finalised", "provisional"])), key

    # Series table: placing points per rank, shared ties, nothing for an elimination.
    settings = Competition.objects.get(pk=competition.id).settings_json
    ranks = [want for want in expected.values() if isinstance(want, int)]
    table = {row.participant_id: row for row in compute_standings(competition)}
    for name, want in expected.items():
        row = table[entrants[name]]
        if isinstance(want, int):
            assert row.points == placing_points_for(settings, want, ranks.count(want)), (key, name)
        else:
            assert row.points == 0 and row.statuses == 1, (key, name)
    leader = compute_standings(competition)[0]
    assert leader.participant_id in {entrants[name] for name, want in expected.items() if want == 1}, key


def _teams(competition, handicaps):
    teams = []
    for index, values in enumerate(handicaps):
        team = Participant.objects.create(competition=competition, name=f"Team {index + 1}", kind="team")
        for number, value in enumerate(values, start=1):
            RosterMember.objects.create(participant=team, name=f"T{index + 1} P{number}", number=number, handicap=value)
        teams.append(team)
    return teams


def _match(competition, official, teams):
    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    sides = [FixtureSide.objects.create(fixture=fixture, participant=team, position=index) for index, team in enumerate(teams)]
    FixtureReferee.objects.create(fixture=fixture, user=official)
    return fixture, sides


def _score(user, fixture, side, unit=0, **extra):
    goal = fixture.competition.scoring_categories.get(code="goal")
    return _client(user).post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(side.id), "scoring_category": str(goal.id), "unit_index": unit,
         "player": str(side.participant.roster.first().id), **extra},
        format="json",
    )


@pytest.mark.parametrize("key", HEAD_TO_HEAD)
def test_a_full_match_for_every_head_to_head_preset(people, key):
    owner, official = people["owner"], people["official"]
    competition = _create(owner, key)
    _assert_locked_and_governed(owner, competition, key)
    _appoint(owner, official, competition, "umpire")
    handicap = bool(PRESETS[key].get("head_start"))
    teams = _teams(competition, [[2, 2, 1, 1], [2, 2, 1, 1]] if handicap else [[None] * 4, [None] * 4])

    # A level match: in a league the points are shared (the tie).
    fixture, sides = _match(competition, official, teams)
    assert _score(official, fixture, sides[0]).status_code == 201
    assert _score(official, fixture, sides[1], unit=1).status_code == 201
    status_path = f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/set-status"
    assert _client(owner).post(status_path, {"status": "completed"}, format="json").status_code == 403, key
    assert _client(official).post(status_path, {"status": "completed"}, format="json").status_code == 200, key
    table = {row.name: row.points for row in compute_standings(competition)}
    assert table == {"Team 1": 1, "Team 2": 1}, key

    # After the result is final, a change needs an official and a reason, and is logged.
    assert _score(owner, fixture, sides[0], unit=1, amendment_reason="Late goal").status_code == 403, key
    assert _score(official, fixture, sides[0], unit=1).status_code == 400, key
    assert _score(official, fixture, sides[0], unit=1, amendment_reason="Goal-line review").status_code == 201, key
    assert ResultAmendment.objects.filter(fixture=fixture, action="amended", reason="Goal-line review").exists(), key
    table = {row.name: row.points for row in compute_standings(competition)}
    assert table == {"Team 1": 3, "Team 2": 0}, key


def test_no_engine_module_names_a_horse_sport():
    names = set(EQUESTRIAN_PRESETS)
    names |= {str(preset.get("sport") or "").lower() for preset in EQUESTRIAN_PRESETS.values()}
    # Sport-only words. "horse" is allowed: the shared registry credits horse, rider and trainer.
    names |= {"jockey", "chukka", "jump-off", "furlong"}
    for module in (
        "apps/competitions/engine.py",
        "apps/standings/services.py",
        "apps/results/calculators.py",
        "apps/results/services.py",
        "apps/results/views.py",
        "apps/fixtures/awards.py",
    ):
        text = Path(module).read_text().lower()
        for name in names:
            assert name.replace("_", " ") not in text.replace("_", " "), f"{module} names {name}"
