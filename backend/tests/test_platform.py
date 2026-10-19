"""Locks, the public board, knockout byes, and draws. One engine, two paths."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant
from apps.competitions.presets import PRESETS
from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent
from apps.standings.services import compute_standings

pytestmark = pytest.mark.django_db


def _icon_import(name: str) -> str:
    parts = name.split("-")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def test_every_preset_icon_is_registered_for_the_app():
    source = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "app.component.ts"
    ).read_text()
    block = source.split("addIcons({", 1)[1].split("});", 1)[0]
    registered = set(re.findall(r"\b([A-Za-z][A-Za-z0-9]*)\b", block))
    missing = [
        (key, preset.get("icon"))
        for key, preset in PRESETS.items()
        if _icon_import(preset.get("icon") or "trophy-outline") not in registered
    ]
    assert missing == []
    # Older Scrabble data used this name. Keep it registered so the icon is not blank.
    assert "textOutline" in registered


def test_discover_hides_drafts_and_private_competitions(api, user, other_user):
    Competition.objects.create(name="Draft Cup", owner=user, status="draft", is_private=False)
    Competition.objects.create(name="Live Cup", owner=user, status="active", is_private=False)
    Competition.objects.create(name="Secret Cup", owner=user, status="active", is_private=True)
    Competition.objects.create(name="Finished Cup", owner=user, status="completed", is_private=False)
    Competition.objects.create(name="Archived Cup", owner=user, status="archived", is_private=False)

    stranger = APIClient()
    stranger.force_authenticate(user=other_user)
    found = stranger.get("/api/v1/competitions", {"discover": "1"})
    assert found.status_code == 200
    assert {row["name"] for row in found.data["results"]} == {"Live Cup", "Finished Cup"}

    # The owner still sees a draft on My leagues, and not on Discover.
    mine = api.get("/api/v1/competitions", {"mine": "1"})
    assert "Draft Cup" in {row["name"] for row in mine.data["results"]}
    board = api.get("/api/v1/competitions", {"discover": "1"})
    assert "Draft Cup" not in {row["name"] for row in board.data["results"]}
    assert "Secret Cup" not in {row["name"] for row in board.data["results"]}


def test_search_hides_private_and_draft_competitions(api, user, anon_api):
    Competition.objects.create(
        name="Hidden Quidditch League", owner=user, is_private=True, status="active"
    )
    Competition.objects.create(
        name="Draft Quidditch League", owner=user, is_private=False, status="draft"
    )
    public = Competition.objects.create(
        name="Public Quidditch League", owner=user, is_private=False, status="active"
    )
    Participant.objects.create(competition=public, name="Public Quidditch", kind="team")
    private = Competition.objects.get(name="Hidden Quidditch League")
    Participant.objects.create(competition=private, name="Secret Quidditch", kind="team")

    found = anon_api.get("/api/v1/search", {"q": "Quidditch"})
    assert found.status_code == 200
    names = {hit["name"] for hit in found.data["results"]["competitions"]}
    assert names == {"Public Quidditch League"}
    sides = {hit["name"] for hit in found.data["results"]["participants"]}
    assert sides == {"Public Quidditch"}


def test_locked_preset_refuses_engine_edits_and_custom_stays_open(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Sunday League", "preset": "soccer"},
        format="json",
    )
    assert created.status_code == 201
    competition_id = created.data["id"]
    detail = api.get(f"/api/v1/competitions/{competition_id}").data
    settings = detail["settings_json"]

    for patch in (
        {"settings_json": {**settings, "score_types": []}},
        {"settings_json": {**settings, "time_limit_minutes": 40}},
        {"settings_json": {**settings, "tiebreakers": ["name"]}},
        {"format": "ladder"},
    ):
        blocked = api.patch(f"/api/v1/competitions/{competition_id}", patch, format="json")
        assert blocked.status_code == 403, patch

    rule = api.post(
        f"/api/v1/competitions/{competition_id}/rules",
        {"name": "House rule", "description": "Goals are worth 2."},
        format="json",
    )
    assert rule.status_code == 403

    renamed = api.patch(
        f"/api/v1/competitions/{competition_id}",
        {"name": "Sunday League Cup"},
        format="json",
    )
    assert renamed.status_code == 200
    assert renamed.data["name"] == "Sunday League Cup"
    assert renamed.data["settings_json"]["score_types"][0]["key"] == "goal"

    custom = api.post(
        "/api/v1/competitions",
        {
            "name": "Chores",
            "preset": "custom",
            "scoring_categories": [
                {"name": "Dishes", "points": "2", "description": "Washed and put away."}
            ],
        },
        format="json",
    )
    assert custom.status_code == 201, custom.data
    custom_detail = api.get(f"/api/v1/competitions/{custom.data['id']}").data
    category = custom_detail["scoring_categories"][0]
    edited = api.patch(
        f"/api/v1/competitions/{custom.data['id']}/scoring-categories/{category['id']}",
        {"points": "4"},
        format="json",
    )
    assert edited.status_code == 200
    assert edited.data["points"] == "4.00"
    added = api.post(
        f"/api/v1/competitions/{custom.data['id']}/rules",
        {"name": "On time", "description": "A bonus when the chore is done the same day."},
        format="json",
    )
    assert added.status_code == 201


def test_member_emails_are_hidden_from_other_members(api, user, other_user):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Public league", "preset": "soccer"},
        format="json",
    )
    competition_id = created.data["id"]
    api.patch(f"/api/v1/competitions/{competition_id}", {"status": "active"}, format="json")
    api.post(
        f"/api/v1/competitions/{competition_id}/members",
        {"user_id": str(other_user.id), "role": "member"},
        format="json",
    )
    member = APIClient()
    member.force_authenticate(user=other_user)
    listing = member.get(f"/api/v1/competitions/{competition_id}/members")
    assert listing.status_code == 200
    by_id = {row["user"]["id"]: row["member_email"] for row in listing.data["results"]}
    assert by_id[str(other_user.id)] == other_user.email
    assert by_id[str(user.id)] == ""

    owner_view = api.get(f"/api/v1/competitions/{competition_id}/members")
    owner_emails = {row["member_email"] for row in owner_view.data["results"]}
    assert user.email in owner_emails
    assert other_user.email in owner_emails


def test_knockout_bye_advances_with_the_match_winner(
    api, bus_redis, django_capture_on_commit_callbacks
):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Cup", "preset": "soccer", "format": "knockout"},
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    for name in ("Alpha", "Beta", "Gamma"):
        Participant.objects.create(competition=competition, name=name, kind="team")

    generated = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/generate",
        {
            "method": "knockout",
            "starts_on": str(date(2026, 6, 1)),
            "weekdays": [5],
            "kickoff": "15:00:00",
        },
        format="json",
    )
    assert generated.status_code == 201, generated.data
    assert len(generated.data) == 2
    bye = next(item for item in generated.data if item["label"] == "Bye")
    assert bye["status"] == "completed"

    rows = {row.name: row for row in compute_standings(competition)}
    assert all(row.played == 0 for row in rows.values())

    played = Fixture.objects.get(
        competition=competition, round_number=1, status=Fixture.Status.SCHEDULED
    )
    goal = competition.scoring_categories.get(code="goal")
    sides = {side.participant.name: side for side in played.sides.all()}
    ScoreEvent.objects.create(fixture=played, side=sides["Beta"], scoring_category=goal, quantity=1)
    played.status = Fixture.Status.COMPLETED
    played.save(update_fields=["status", "updated_at"])
    played.recalculate_scores()

    with django_capture_on_commit_callbacks(execute=True):
        advanced = api.post(f"/api/v1/competitions/{competition.id}/advance", {}, format="json")
    assert advanced.status_code == 201, advanced.data
    assert advanced.data["advanced"] is True
    final = Fixture.objects.get(competition=competition, round_number=2)
    assert set(final.sides.values_list("participant__name", flat=True)) == {"Alpha", "Beta"}

    events = [json.loads(message)["event"] for _, message in bus_redis.published]
    assert "competition.updated" in events
    assert "fixture.created" in events


def test_draws_follow_the_preset_and_the_custom_checkbox(api):
    tennis = api.post(
        "/api/v1/competitions",
        {"name": "Club", "preset": "tennis"},
        format="json",
    )
    assert tennis.status_code == 201
    competition = Competition.objects.get(pk=tennis.data["id"])
    assert competition.points_policy.allow_draws is False
    ada = Participant.objects.create(competition=competition, name="Ada", kind="individual")
    bo = Participant.objects.create(competition=competition, name="Bo", kind="individual")
    refused = api.post(
        f"/api/v1/competitions/{competition.id}/score-assist",
        {"kind": "result", "home": str(ada.id), "away": str(bo.id), "outcome": "draw"},
        format="json",
    )
    assert refused.status_code == 400

    custom = api.post(
        "/api/v1/competitions",
        {
            "name": "Office league",
            "preset": "custom",
            "scoring_basis": "results",
            "scoring_categories": [{"name": "Goal", "points": "1"}],
        },
        format="json",
    )
    assert custom.status_code == 201, custom.data
    policy = api.patch(
        f"/api/v1/competitions/{custom.data['id']}/points-policy",
        {"allow_draws": False},
        format="json",
    )
    assert policy.status_code == 200
    office = Competition.objects.get(pk=custom.data["id"])
    home = Participant.objects.create(competition=office, name="Home", kind="team")
    away = Participant.objects.create(competition=office, name="Away", kind="team")
    blocked = api.post(
        f"/api/v1/competitions/{office.id}/score-assist",
        {"kind": "result", "home": str(home.id), "away": str(away.id), "outcome": "draw"},
        format="json",
    )
    assert blocked.status_code == 400
    recorded = api.post(
        f"/api/v1/competitions/{office.id}/score-assist",
        {"kind": "result", "home": str(home.id), "away": str(away.id), "outcome": "home"},
        format="json",
    )
    assert recorded.status_code == 201, recorded.data

    soccer = api.post(
        "/api/v1/competitions", {"name": "Goals", "preset": "soccer"}, format="json"
    )
    league = Competition.objects.get(pk=soccer.data["id"])
    red = Participant.objects.create(competition=league, name="Red", kind="team")
    blue = Participant.objects.create(competition=league, name="Blue", kind="team")
    fixture = Fixture.objects.create(competition=league, status=Fixture.Status.COMPLETED)
    red_side = FixtureSide.objects.create(fixture=fixture, participant=red, position=0, is_home=True)
    blue_side = FixtureSide.objects.create(fixture=fixture, participant=blue, position=1)
    goal = league.scoring_categories.get(code="goal")
    ScoreEvent.objects.create(fixture=fixture, side=red_side, scoring_category=goal, quantity=Decimal(1))
    ScoreEvent.objects.create(fixture=fixture, side=blue_side, scoring_category=goal, quantity=Decimal(1))
    fixture.recalculate_scores()
    fixture.refresh_from_db()
    outcomes = set(fixture.sides.values_list("outcome", flat=True))
    assert outcomes == {"draw"}


def test_a_locked_preset_cannot_be_opened_by_a_start_lock_or_a_draft(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Sunday League", "preset": "soccer"},
        format="json",
    )
    competition_id = created.data["id"]
    settings = api.get(f"/api/v1/competitions/{competition_id}").data["settings_json"]
    opened = api.patch(
        f"/api/v1/competitions/{competition_id}",
        {"settings_json": {**settings, "lock_when_started": True, "score_types": []}},
        format="json",
    )
    assert opened.status_code == 403
    still = api.get(f"/api/v1/competitions/{competition_id}").data
    assert still["settings_json"]["score_types"][0]["key"] == "goal"
    assert still["settings_json"]["lock_when_started"] is False

    kpi = api.post(
        "/api/v1/competitions",
        {
            "name": "Floor",
            "preset": "kpi",
            "scoring_categories": [
                {"name": "Sale", "points": "10", "description": "A signed deal."}
            ],
        },
        format="json",
    )
    assert kpi.status_code == 201, kpi.data
    kpi_detail = api.get(f"/api/v1/competitions/{kpi.data['id']}").data
    started = api.patch(
        f"/api/v1/competitions/{kpi.data['id']}",
        {"status": "active"},
        format="json",
    )
    assert started.status_code == 200
    assert started.data["settings_json"]["scoring_sealed"] is True
    reopened = api.patch(
        f"/api/v1/competitions/{kpi.data['id']}",
        {"status": "draft"},
        format="json",
    )
    assert reopened.status_code == 200
    category = kpi_detail["scoring_categories"][0]
    blocked = api.patch(
        f"/api/v1/competitions/{kpi.data['id']}/scoring-categories/{category['id']}",
        {"points": "1"},
        format="json",
    )
    assert blocked.status_code == 403


def test_seeded_byes_meet_the_opposite_half(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Seeded cup", "preset": "soccer", "format": "knockout"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    for seed in range(1, 7):
        Participant.objects.create(
            competition=competition, name=f"Seed {seed}", kind="team", seed=seed
        )
    generated = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/generate",
        {
            "method": "knockout",
            "starts_on": str(date(2026, 6, 1)),
            "weekdays": [5],
            "kickoff": "15:00:00",
        },
        format="json",
    )
    assert generated.status_code == 201, generated.data
    assert len(generated.data) == 4
    goal = competition.scoring_categories.get(code="goal")
    for fixture in Fixture.objects.filter(competition=competition, status=Fixture.Status.SCHEDULED):
        names = sorted(fixture.sides.values_list("participant__name", flat=True))
        winner_name = names[0]
        winner = fixture.sides.get(participant__name=winner_name)
        ScoreEvent.objects.create(fixture=fixture, side=winner, scoring_category=goal, quantity=1)
        fixture.status = Fixture.Status.COMPLETED
        fixture.save(update_fields=["status", "updated_at"])
        fixture.recalculate_scores()

    advanced = api.post(f"/api/v1/competitions/{competition.id}/advance", {}, format="json")
    assert advanced.status_code == 201, advanced.data
    pairings = {
        frozenset(item.sides.values_list("participant__name", flat=True))
        for item in Fixture.objects.filter(competition=competition, round_number=2)
    }
    assert pairings == {frozenset({"Seed 1", "Seed 4"}), frozenset({"Seed 2", "Seed 3"})}


def test_quick_result_decides_a_set_match(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Club", "preset": "tennis"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    ada = Participant.objects.create(competition=competition, name="Ada", kind="individual")
    bo = Participant.objects.create(competition=competition, name="Bo", kind="individual")
    recorded = api.post(
        f"/api/v1/competitions/{competition.id}/score-assist",
        {"kind": "result", "home": str(ada.id), "away": str(bo.id), "outcome": "home"},
        format="json",
    )
    assert recorded.status_code == 201, recorded.data
    fixture = Fixture.objects.get(pk=recorded.data["id"])
    assert set(fixture.sides.values_list("outcome", flat=True)) == {"win", "loss"}
    rows = {row.name: row for row in compute_standings(competition)}
    assert rows["Ada"].points == Decimal("3")


def test_unimplemented_formats_are_refused(api):
    groups = api.post(
        "/api/v1/competitions",
        {"name": "Groups", "preset": "soccer", "format": "group_knockout"},
        format="json",
    )
    assert groups.status_code == 400
    golf = api.post(
        "/api/v1/competitions",
        {"name": "Medal", "preset": "golf_stroke"},
        format="json",
    )
    assert golf.status_code == 201
    generated = api.post(
        f"/api/v1/competitions/{golf.data['id']}/fixtures/generate",
        {
            "method": "knockout",
            "starts_on": str(date(2026, 6, 1)),
            "weekdays": [6],
            "kickoff": "09:00:00",
        },
        format="json",
    )
    assert generated.status_code == 400
