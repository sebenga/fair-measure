"""Scouting Phase 2: the attribute catalogue, as data, per sport."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant
from apps.competitions.presets import PRESETS, apply_preset
from apps.competitions.stat_types import STAT_SCORE_TYPES
from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent
from apps.scouting import attributes, catalog
from apps.scouting.formulas import FormulaError, evaluate, names

User = get_user_model()
AREAS = {"physical", "technical", "tactical", "mental", "context"}


@pytest.mark.parametrize("sport", list(catalog.SPORTS))
def test_every_sport_has_all_five_areas_and_described_attributes(sport):
    entry = catalog.sport_catalogue(sport)
    assert {area["key"] for area in entry["areas"]} == AREAS
    positions = {item["key"] for item in entry["positions"]}
    for area in entry["areas"]:
        assert area["attributes"], f"{sport} has no {area['key']} attributes"
        assert set(area["anchors"]) == {"2", "5", "8", "10"}
        assert all(area["anchors"].values())
        for row in area["attributes"]:
            assert row["area"] == area["key"]
            assert len(row["description"]) > 10, (sport, row["key"])
            assert row["scale"] == {"min": 1, "max": 10}
            assert set(row.get("applies_to_positions") or []) <= positions, (sport, row["key"])
    keys = [row["key"] for area in entry["areas"] for row in area["attributes"]]
    assert len(keys) == len(set(keys)), f"{sport} repeats an attribute key"


@pytest.mark.parametrize("sport", list(catalog.SPORTS))
def test_every_match_stat_comes_from_the_engine_or_a_valid_formula(sport):
    assert catalog.stat_problems(sport) == []
    entry = catalog.sport_catalogue(sport)
    assert entry["match_stats"], sport
    engine = catalog.engine_score_types(sport) | set(attributes.ENGINE_SOURCES)
    for row in entry["match_stats"]:
        assert row["per"] in {"match", "90min", "game"}
        assert bool(row.get("formula")) != bool(row.get("source")), row["key"]
        if row.get("source"):
            assert row["source"] in engine, (sport, row["source"])


@pytest.mark.parametrize("sport", list(catalog.SPORTS))
def test_every_sport_has_physical_tests_with_a_direction(sport):
    tests = catalog.sport_catalogue(sport)["physical_tests"]
    assert tests, sport
    for row in tests:
        assert row["unit"] and row["better"] in {"lower", "higher"} and row["description"]


def test_universal_attributes_reach_every_sport_unless_skipped():
    universal = {row["key"] for row in attributes.UNIVERSAL_ATTRIBUTES}
    assert {"speed", "decision_making", "composure", "level_of_competition"} <= universal
    for sport in catalog.SPORTS:
        skipped = set((attributes.SPORT_ATTRIBUTES.get(sport) or {}).get("skip_universal") or [])
        assert skipped <= universal
        have = {row["key"] for row in catalog.attributes_for(sport) if row["universal"]}
        assert have == universal - skipped


def test_a_bad_stat_is_caught():
    original = attributes.SPORT_ATTRIBUTES["netball"]["match_stats"]
    try:
        attributes.SPORT_ATTRIBUTES["netball"]["match_stats"] = [
            *original,
            {"key": "ghost", "label": "Ghost", "per": "match", "source": "not-recorded"},
            {"key": "bad", "label": "Bad", "per": "match", "formula": "goals / unknown_thing"},
            {"key": "evil", "label": "Evil", "per": "match", "formula": "__import__('os')"},
        ]
        problems = " ".join(catalog.stat_problems("netball"))
        assert "ghost" in problems and "unknown_thing" in problems and "evil" in problems
    finally:
        attributes.SPORT_ATTRIBUTES["netball"]["match_stats"] = original


def test_formulas_are_plain_arithmetic():
    assert names("goals * 90 / minutes") == {"goals", "minutes"}
    assert evaluate("goals * 90 / minutes", {"goals": 3, "minutes": 270}) == Decimal("1")
    assert evaluate("goals / shots * 100", {"goals": 1, "shots": 0}) is None
    assert evaluate("goals / shots", {"goals": 1}) is None
    for bad in ("os.system('x')", "goals ** 2", "[goals]", "goals if shots else 0", "'a'"):
        with pytest.raises(FormulaError):
            names(bad)


def test_catalogue_api():
    client = APIClient()
    overview = client.get("/api/v1/scouting/catalog").json()
    assert [area["key"] for area in overview["areas"]] == [
        "physical",
        "technical",
        "tactical",
        "mental",
        "context",
    ]
    soccer_row = next(row for row in overview["sports"] if row["key"] == "soccer")
    assert soccer_row["attribute_count"] > 20 and soccer_row["match_stat_count"] >= 8
    soccer = client.get("/api/v1/scouting/catalog/soccer")
    assert soccer.status_code == 200
    technical = next(area for area in soccer.json()["areas"] if area["key"] == "technical")
    handling = next(row for row in technical["attributes"] if row["key"] == "gk_handling")
    assert handling["applies_to_positions"] == ["goalkeeper"]
    assert "soccer" in soccer.json()["presets"]
    assert client.get("/api/v1/scouting/catalog/quidditch").status_code == 404


# --- Stat score types in the engine ----------------------------------------------------------


def test_stat_types_are_recorded_but_never_change_the_score(db):
    for key, rows in STAT_SCORE_TYPES.items():
        types = {item["key"]: item for item in PRESETS[key]["score_types"]}
        for row in rows:
            assert types[row["key"]]["affects_score"] is False and types[row["key"]]["stat"]
    owner = User.objects.create_user(email="stats@catalog.test", password="pw-123456789")
    competition = Competition.objects.create(name="Stats league", owner=owner, sport="soccer")
    apply_preset(competition, "soccer")
    home = Participant.objects.create(competition=competition, name="Home", kind="team")
    away = Participant.objects.create(competition=competition, name="Away", kind="team")
    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0, is_home=True)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    for code in ("goal", "assist", "shot", "shot-on-target"):
        ScoreEvent.objects.create(
            fixture=fixture,
            side=side,
            scoring_category=competition.scoring_categories.get(code=code),
        )
    fixture.status = Fixture.Status.COMPLETED
    fixture.completed_at = timezone.now()
    fixture.save()
    fixture.recalculate_scores()
    side.refresh_from_db()
    assert side.score == Decimal("1")


def test_existing_competitions_get_the_stat_types(db):
    owner = User.objects.create_user(email="old@catalog.test", password="pw-123456789")
    competition = Competition.objects.create(name="Old league", owner=owner, sport="basketball")
    apply_preset(competition, "basketball")
    competition.scoring_categories.filter(code__in=["rebound", "assist"]).delete()
    settings = competition.settings_json
    settings["score_types"] = [row for row in settings["score_types"] if not row.get("stat")]
    competition.settings_json = settings
    competition.save()

    call_command("add_player_stat_types")
    codes = set(competition.scoring_categories.values_list("code", flat=True))
    assert {"rebound", "assist", "steal"} <= codes
    competition.refresh_from_db()
    assert any(
        row["key"] == "rebound" and row["stat"] for row in competition.settings_json["score_types"]
    )
    before = competition.scoring_categories.count()
    call_command("add_player_stat_types")
    assert competition.scoring_categories.count() == before


def test_scouting_code_still_names_no_sport():
    for name in ("views.py", "services.py", "catalog.py", "formulas.py"):
        text = (Path("apps/scouting") / name).read_text().lower()
        if name == "catalog.py":
            # The SPORTS data sits at the top of catalog.py; check the functions below it.
            text = text[text.index("def sport(") :]
        for key in catalog.SPORTS:
            assert f'"{key}"' not in text, f"{name} names {key}"
