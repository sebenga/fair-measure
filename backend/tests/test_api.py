"""End-to-end checks over the HTTP API, including access control."""

from __future__ import annotations

from datetime import date

import pytest

from apps.competitions.models import Competition, Membership
from apps.core.permissions import Role
from apps.fixtures.models import Fixture

pytestmark = pytest.mark.django_db


def test_register_returns_tokens_and_user(anon_api):
    response = anon_api.post(
        "/api/v1/auth/register",
        {"email": "New@Example.com", "password": "a-strong-passphrase", "display_name": "New"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["access"]
    assert response.data["refresh"]
    assert response.data["user"]["email"] == "new@example.com"


def test_register_rejects_a_duplicate_email(anon_api, user):
    response = anon_api.post(
        "/api/v1/auth/register",
        {"email": "OWNER@example.com", "password": "a-strong-passphrase"},
        format="json",
    )
    assert response.status_code == 400


def test_login_then_read_me(anon_api, user):
    login = anon_api.post(
        "/api/v1/auth/login",
        {"email": "owner@example.com", "password": "s3cret-password"},
        format="json",
    )
    assert login.status_code == 200

    anon_api.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    me = anon_api.get("/api/v1/auth/me")

    assert me.status_code == 200
    assert me.data["email"] == "owner@example.com"
    assert me.data["given_name"] == ""
    assert me.data["family_name"] == ""
    assert me.data["date_of_birth"] is None
    assert me.data["id_number"] == ""


def test_personal_details_are_optional_and_can_be_saved(api):
    empty = api.patch("/api/v1/auth/me", {}, format="json")
    assert empty.status_code == 200
    assert empty.data["date_of_birth"] is None

    saved = api.patch(
        "/api/v1/auth/me",
        {
            "given_name": "Alex",
            "family_name": "Nkosi",
            "date_of_birth": "1994-03-12",
            "id_number": "9403125800084",
            "phone": "",
            "city": "Johannesburg",
            "headline": "Midfielder",
            "experience": "Club captain, 2020–2024",
            "education": "",
            "skills": "Passing",
            "website": "",
        },
        format="json",
    )
    assert saved.status_code == 200
    assert saved.data["given_name"] == "Alex"
    assert saved.data["family_name"] == "Nkosi"
    assert saved.data["date_of_birth"] == "1994-03-12"
    assert saved.data["id_number"] == "9403125800084"
    assert saved.data["phone"] == ""
    assert saved.data["education"] == ""

    cleared = api.patch(
        "/api/v1/auth/me",
        {"given_name": "", "family_name": "", "date_of_birth": "", "id_number": ""},
        format="json",
    )
    assert cleared.status_code == 200
    assert cleared.data["given_name"] == ""
    assert cleared.data["date_of_birth"] is None
    assert cleared.data["id_number"] == ""

    future = api.patch("/api/v1/auth/me", {"date_of_birth": "2999-01-01"}, format="json")
    assert future.status_code == 400


def test_creating_a_competition_with_a_preset_seeds_scoring(api):
    response = api.post(
        "/api/v1/competitions",
        {"name": "Sunday Soccer", "preset": "soccer"},
        format="json",
    )
    assert response.status_code == 201

    detail = api.get(f"/api/v1/competitions/{response.data['id']}")
    codes = {item["code"] for item in detail.data["scoring_categories"]}
    stats = {"assist", "shot", "shot-on-target", "tackle", "interception", "save"}

    assert codes == {"goal", "own-goal", "yellow-card", "red-card"} | stats
    assert not any(
        item["affects_score"] for item in detail.data["scoring_categories"] if item["code"] in stats
    )
    by_code = {item["code"]: item for item in detail.data["scoring_categories"]}
    assert by_code["goal"]["points"] == "1.00"
    assert detail.data["points_policy"]["win_points"] == "3.00"
    assert detail.data["points_policy"]["draw_points"] == "1.00"
    assert detail.data["points_policy"]["loss_points"] == "0.00"
    assert detail.data["points_policy"]["bonus_loss_points"] == "0.00"
    assert detail.data["settings_json"]["scoring_locked"] is True
    assert detail.data["my_role"] == Role.OWNER


def test_locked_preset_scoring_cannot_be_changed(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Sunday League", "preset": "soccer"},
        format="json",
    )
    assert created.status_code == 201
    competition_id = created.data["id"]

    detail = api.get(f"/api/v1/competitions/{competition_id}")
    policy = detail.data["points_policy"]
    assert policy["win_points"] == "3.00"
    assert policy["draw_points"] == "1.00"
    assert policy["loss_points"] == "0.00"
    goal = next(item for item in detail.data["scoring_categories"] if item["code"] == "goal")

    edited = api.patch(
        f"/api/v1/competitions/{competition_id}/scoring-categories/{goal['id']}",
        {"points": "9"},
        format="json",
    )
    assert edited.status_code == 403

    added = api.post(
        f"/api/v1/competitions/{competition_id}/scoring-categories",
        {"name": "Bonus", "code": "bonus", "points": "1"},
        format="json",
    )
    assert added.status_code == 403

    removed = api.delete(
        f"/api/v1/competitions/{competition_id}/scoring-categories/{goal['id']}"
    )
    assert removed.status_code == 403

    policy_edit = api.patch(
        f"/api/v1/competitions/{competition_id}/points-policy",
        {"win_points": "10"},
        format="json",
    )
    assert policy_edit.status_code == 403

    unlocked = api.patch(
        f"/api/v1/competitions/{competition_id}",
        {"settings_json": {"scoring_locked": False, "preset": "custom"}},
        format="json",
    )
    assert unlocked.status_code == 200
    assert unlocked.data["settings_json"]["scoring_locked"] is True

    still_locked = api.patch(
        f"/api/v1/competitions/{competition_id}/points-policy",
        {"win_points": "10"},
        format="json",
    )
    assert still_locked.status_code == 403

    overridden = api.post(
        "/api/v1/competitions",
        {
            "name": "Rewritten soccer",
            "preset": "soccer",
            "scoring_categories": [{"name": "Goal", "points": "5"}],
        },
        format="json",
    )
    assert overridden.status_code == 403

    reapplied = api.post(
        f"/api/v1/competitions/{competition_id}/apply-preset",
        {"preset": "soccer", "replace_existing": True},
        format="json",
    )
    assert reapplied.status_code == 403


def test_golf_stroke_play_accumulates_without_results(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Monthly medal", "preset": "golf_stroke"},
        format="json",
    )
    assert created.status_code == 201
    detail = api.get(f"/api/v1/competitions/{created.data['id']}")
    assert detail.data["settings_json"]["table_mode"] == "points"
    assert detail.data["settings_json"]["scoring_basis"] == "criteria"
    assert detail.data["points_policy"]["win_points"] == "0.00"
    stroke = next(item for item in detail.data["scoring_categories"] if item["code"] == "stroke")
    assert stroke["points"] == "1.00"
    assert detail.data["settings_json"]["accumulation_ranking"] == "lowest_first"
    assert "lowest total" in stroke["description"]


def test_create_accepts_custom_scoring_with_descriptions(api):
    response = api.post(
        "/api/v1/competitions",
        {
            "name": "Flat rota",
            "preset": "custom",
            "scoring_categories": [
                {
                    "name": "Bathroom",
                    "description": "Sink, toilet, floor.",
                    "points": "2",
                    "affects_score": True,
                },
                {
                    "name": "Skipped",
                    "description": "Did not do the listed job.",
                    "points": "-1",
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 201

    detail = api.get(f"/api/v1/competitions/{response.data['id']}")
    rows = detail.data["scoring_categories"]
    names = [item["name"] for item in rows]
    codes = {item["code"] for item in rows}

    assert names == ["Bathroom", "Skipped"]
    assert rows[0]["description"] == "Sink, toilet, floor."
    assert rows[1]["points"] == "-1.00"
    assert "task-done" not in codes


def test_owner_can_delete_a_competition(api):
    created = api.post("/api/v1/competitions", {"name": "Temp league"}, format="json")
    competition_id = created.data["id"]

    deleted = api.delete(f"/api/v1/competitions/{competition_id}")
    assert deleted.status_code == 204
    assert api.get(f"/api/v1/competitions/{competition_id}").status_code == 404


def test_owner_can_delete_a_league_that_already_has_points(api):
    from apps.competitions.models import Participant

    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Points to remove",
            "preset": "custom",
            "scoring_categories": [
                {"name": "Task", "description": "A finished task.", "points": "1"}
            ],
        },
        format="json",
    )
    assert created.status_code == 201
    competition_id = created.data["id"]
    detail = api.get(f"/api/v1/competitions/{competition_id}")
    category_id = detail.data["scoring_categories"][0]["id"]
    participant = Participant.objects.create(competition_id=competition_id, name="Ada")
    awarded = api.post(
        f"/api/v1/competitions/{competition_id}/score-assist",
        {
            "kind": "criterion",
            "participant": str(participant.id),
            "scoring_category": category_id,
            "quantity": "1",
            "note": "Finished the task.",
        },
        format="json",
    )
    assert awarded.status_code == 201

    deleted = api.delete(f"/api/v1/competitions/{competition_id}")
    assert deleted.status_code == 204
    assert api.get(f"/api/v1/competitions/{competition_id}").status_code == 404


def test_a_team_is_named_then_a_player_accepts_the_pick(api, user, other_user):
    from apps.accounts.models import User
    from rest_framework.test import APIClient

    second = User.objects.create_user(
        email="second@example.com", password="s3cret-password", display_name="Second"
    )
    created = api.post("/api/v1/competitions", {"name": "Sunday league"}, format="json")
    assert created.status_code == 201
    competition_id = created.data["id"]
    participants_url = f"/api/v1/competitions/{competition_id}/participants"

    named = api.post(
        participants_url,
        {"name": "Short", "kind": "team"},
        format="json",
    )
    assert named.status_code == 201
    assert named.data["roster"] == []

    player = api.post(participants_url, {"name": "Solo", "kind": "individual"}, format="json")
    assert player.status_code == 400

    team = api.post(participants_url, {"name": "Northside", "kind": "team"}, format="json")
    assert team.status_code == 201
    picks_url = f"{participants_url}/{team.data['id']}/picks"

    offered = api.post(picks_url, {"user": str(other_user.id)}, format="json")
    assert offered.status_code == 201
    assert offered.data["status"] == "accepted"
    assert offered.data["competition"] == competition_id
    assert "Member" in team_roster(api, competition_id, team.data["id"])

    member = APIClient()
    member.force_authenticate(user=other_user)
    assert member.get("/api/v1/me/team-picks").data == []

    waiting = api.post(picks_url, {"user": str(second.id)}, format="json")
    assert waiting.status_code == 201
    assert waiting.data["status"] == "accepted"
    assert "Second" in team_roster(api, competition_id, team.data["id"])

    rival = api.post(participants_url, {"name": "Owners", "kind": "team"}, format="json")
    assert rival.status_code == 201
    taken = api.post(
        f"{participants_url}/{rival.data['id']}/picks",
        {"user": str(other_user.id)},
        format="json",
    )
    assert taken.status_code == 400

    reserved = api.post(
        f"{participants_url}/{rival.data['id']}/picks",
        {"user": str(second.id)},
        format="json",
    )
    assert reserved.status_code == 400

    admin = User.objects.create_user(
        email="coach@example.com", password="s3cret-password", display_name="Coach"
    )
    Membership.objects.create(competition_id=competition_id, user=admin, role=Role.ADMIN)
    placed_by_owner = api.post(picks_url, {"user": str(admin.id)}, format="json")
    assert placed_by_owner.status_code == 400

    coach = APIClient()
    coach.force_authenticate(user=admin)
    self_pick = coach.post(
        f"{participants_url}/{rival.data['id']}/picks",
        {"user": str(admin.id)},
        format="json",
    )
    assert self_pick.status_code == 201
    assert self_pick.data["status"] == "accepted"
    assert "Coach" in team_roster(api, competition_id, rival.data["id"])

    mine = member.get(f"/api/v1/competitions/{competition_id}/picks")
    assert mine.status_code == 200
    assert mine.data == []
    assert member.get("/api/v1/me/team-picks").data == []


def team_roster(api, competition_id, participant_id) -> list[str]:
    detail = api.get(f"/api/v1/competitions/{competition_id}/participants/{participant_id}")
    assert detail.status_code == 200
    return [member["name"] for member in detail.data["roster"]]


def test_teams_are_picked_or_drafted_with_fourteen_players(api, other_user):
    from apps.accounts.models import User

    created = api.post("/api/v1/competitions", {"name": "Squad league"}, format="json")
    assert created.status_code == 201
    competition_id = created.data["id"]
    settings = {"participant_type": "team", "team_entry": "pick"}
    chosen = api.patch(
        f"/api/v1/competitions/{competition_id}",
        {"settings_json": settings},
        format="json",
    )
    assert chosen.status_code == 200

    players = [other_user]
    for index in range(13):
        players.append(
            User.objects.create_user(
                email=f"squad{index}@example.com",
                password="s3cret-password",
                display_name=f"Squad {index}",
            )
        )
    participants_url = f"/api/v1/competitions/{competition_id}/participants"
    short = api.post(
        participants_url,
        {"name": "Short", "kind": "team", "member_ids": [str(player.id) for player in players[:13]]},
        format="json",
    )
    assert short.status_code == 400

    full = api.post(
        participants_url,
        {"name": "Full", "kind": "team", "member_ids": [str(player.id) for player in players]},
        format="json",
    )
    assert full.status_code == 201
    assert len(full.data["roster"]) == 14
    assert full.data["pending_count"] == 0

    removed = api.delete(f"{participants_url}/{full.data['id']}")
    assert removed.status_code == 204

    settings["team_entry"] = "draft"
    drafted = api.patch(
        f"/api/v1/competitions/{competition_id}",
        {"settings_json": settings},
        format="json",
    )
    assert drafted.status_code == 200
    alpha = api.post(participants_url, {"name": "Alpha", "kind": "team"}, format="json")
    bravo = api.post(participants_url, {"name": "Bravo", "kind": "team"}, format="json")
    assert alpha.status_code == 201
    assert bravo.status_code == 201

    order = []
    for index in range(4):
        player = User.objects.create_user(
            email=f"draft{index}@example.com",
            password="s3cret-password",
            display_name=f"Draft {index}",
        )
        response = api.post(
            f"/api/v1/competitions/{competition_id}/draft",
            {"user": str(player.id)},
            format="json",
        )
        assert response.status_code == 201
        order.append(response.data["pick"]["team_name"])
    assert order == ["Alpha", "Bravo", "Bravo", "Alpha"]

    blocked = api.post(
        f"/api/v1/competitions/{competition_id}/fixtures/generate",
        {
            "method": "round_robin",
            "starts_on": "2026-11-01",
            "kickoff": "15:00",
            "minutes_between_fixtures": 0,
            "double_round": False,
            "replace_existing": False,
        },
        format="json",
    )
    assert blocked.status_code == 400


def test_non_owner_cannot_delete_a_competition(competition, other_user):
    from rest_framework.test import APIClient

    Membership.objects.create(competition=competition, user=other_user, role=Role.ADMIN)
    client = APIClient()
    client.force_authenticate(user=other_user)

    response = client.delete(f"/api/v1/competitions/{competition.id}")
    assert response.status_code == 403
    assert Competition.objects.filter(pk=competition.id).exists()


def test_presets_include_kind_and_category_descriptions(anon_api):
    response = anon_api.get("/api/v1/competitions/presets")
    assert response.status_code == 200

    by_key = {item["key"]: item for item in response.data}
    assert by_key["kpi"]["lock_when_started"] is True
    assert by_key["cleaning"]["score_types"]
    assert by_key["scrabble"]["locked"] is True
    assert by_key["darts_501"]["locked"] is True
    assert by_key["custom"]["kind"] == "custom"
    assert by_key["custom"]["scoring_categories"] == []
    assert by_key["custom"]["table_mode"] == "points"
    assert by_key["soccer"]["table_mode"] == "head_to_head"
    assert by_key["soccer"]["scoring_locked"] is True
    assert by_key["custom"]["scoring_locked"] is False
    assert "rugby" not in by_key
    assert "golf" not in by_key
    assert by_key["golf_stroke"]["table_mode"] == "points"
    assert by_key["golf_stroke"]["contest_type"] == "accumulation"
    assert by_key["golf_stroke"]["locked"] is True
    assert by_key["soccer"]["draw_resolution"] == "penalties"
    assert "rugby_union" in by_key
    assert "golf_stableford" in by_key
    assert by_key["padel"]["match_structure"] == by_key["tennis"]["match_structure"]
    assert by_key["soccer"]["group"] == "ball"
    assert by_key["soccer"]["group_label"] == "Ball sports"
    assert by_key["futsal"]["group"] == "ball"
    assert by_key["futsal"]["family"] == "football"
    assert by_key["futsal"]["variant"] == "futsal"
    assert by_key["futsal"]["team_sheet"]["starters"] == 5
    assert by_key["futsal"]["team_sheet"]["min_squad"] == 5
    assert by_key["soccer"]["family"] == "football"
    assert by_key["soccer"]["variant"] == "association"
    assert by_key["soccer_women"]["category"] == "women"
    assert by_key["rugby_union"]["family"] == "rugby_union"
    assert by_key["rugby_union"]["variant"] == "fifteens"
    assert by_key["rugby_union"]["league_points"]["win"] == 4
    assert by_key["rugby_league"]["league_points"]["win"] == 2
    assert by_key["rugby_sevens"]["family"] == "rugby_union"
    assert by_key["beach_soccer"]["league_points"]["penalty_win"] == 1
    assert by_key["walking_football"]["locked"] is False
    assert by_key["arena_soccer"]["locked"] is False
    assert by_key["freestyle_football"]["locked"] is False
    assert by_key["freestyle_football"]["participant_type"] == "individual"
    assert by_key["swimming"]["group"] == "olympic"
    assert by_key["ice_hockey"]["group"] == "winter"
    assert by_key["tennis"]["group"] == "racket"
    assert by_key["chess"]["group"] == "board"
    assert by_key["golf_stroke"]["group"] == "golf"
    assert by_key["darts_501"]["group"] == "target"
    assert by_key["custom"]["group"] == ""
    assert by_key["kpi"]["group"] == ""
    assert by_key["cleaning"]["group"] == ""


def test_every_sport_preset_has_a_create_page_group():
    from apps.competitions.preset_groups import GROUP_ORDER, group_for
    from apps.competitions.presets import PRESETS

    known = {key for key, _label in GROUP_ORDER}
    for key, preset in PRESETS.items():
        if preset.get("kind", "sport") == "sport":
            assert group_for(key) in known, key
        else:
            assert group_for(key) == "", key


def test_custom_preset_uses_points_accumulation_table(api):
    response = api.post(
        "/api/v1/competitions",
        {
            "name": "Office board",
            "preset": "custom",
            "scoring_categories": [
                {
                    "name": "Task done",
                    "description": "A listed job was finished.",
                    "points": "1",
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 201

    detail = api.get(f"/api/v1/competitions/{response.data['id']}")
    assert detail.data["settings_json"]["table_mode"] == "points"
    assert detail.data["settings_json"]["scoring_basis"] == "criteria"
    assert detail.data["points_policy"]["win_points"] == "0.00"
    assert detail.data["scoring_categories"][0]["name"] == "Task done"


def test_custom_competition_requires_scoring_criteria(api):
    response = api.post(
        "/api/v1/competitions",
        {"name": "Office board", "preset": "custom"},
        format="json",
    )
    assert response.status_code == 400
    assert "scoring criterion" in str(response.data).lower()


def test_custom_has_no_fixture_schedule(api):
    response = api.post(
        "/api/v1/competitions",
        {
            "name": "Office derby",
            "preset": "custom",
            "format": "league",
            "match_weekdays": [0, 2],
            "scoring_categories": [
                {"name": "Goal", "description": "A goal in a match.", "points": "1"}
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    detail = api.get(f"/api/v1/competitions/{response.data['id']}")
    assert detail.data["settings_json"]["scoring_basis"] == "criteria"
    assert detail.data["settings_json"]["table_mode"] == "points"
    assert detail.data["format"] == "freeform"
    assert detail.data["match_weekdays"] == []


def test_score_assist_accumulates_criteria_with_a_note(api, user):
    from decimal import Decimal

    from apps.competitions.models import Participant

    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Office board",
            "preset": "custom",
            "scoring_basis": "criteria",
            "scoring_categories": [
                {
                    "name": "Sales closed",
                    "description": "Deals closed in the period.",
                    "points": "2",
                }
            ],
        },
        format="json",
    )
    assert created.status_code == 201
    competition_id = created.data["id"]
    detail = api.get(f"/api/v1/competitions/{competition_id}")
    category_id = detail.data["scoring_categories"][0]["id"]
    participant = Participant.objects.create(
        competition_id=competition_id, name="Ada"
    )

    awarded = api.post(
        f"/api/v1/competitions/{competition_id}/score-assist",
        {
            "kind": "criterion",
            "participant": str(participant.id),
            "scoring_category": category_id,
            "quantity": "3",
            "note": "Three enterprise deals.",
        },
        format="json",
    )
    assert awarded.status_code == 201
    assert Decimal(awarded.data["awarded"]) == Decimal("6")

    table = api.get(f"/api/v1/competitions/{competition_id}/standings")
    assert table.data["scoring_basis"] == "criteria"
    row = next(item for item in table.data["rows"] if item["participant"]["name"] == "Ada")
    assert Decimal(row["points"]) == Decimal("6")
    breakdown = table.data["breakdown"][str(participant.id)]
    assert breakdown[0]["name"] == "Sales closed"
    assert breakdown[0]["description"] == "Deals closed in the period."
    assert breakdown[0]["entries"][0]["note"] == "Three enterprise deals."


def test_points_reach_the_table_when_a_custom_league_has_no_win_rule(api):
    from decimal import Decimal

    from apps.competitions.models import Participant

    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Older board",
            "preset": "custom",
            "scoring_basis": "criteria",
            "scoring_categories": [{"name": "Early arrival", "points": "2"}],
        },
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    competition.settings_json = {
        key: value
        for key, value in competition.settings_json.items()
        if key not in {"win_condition", "match_structure", "contest_type"}
    }
    competition.save(update_fields=["settings_json"])
    category = competition.scoring_categories.get()
    participant = Participant.objects.create(competition=competition, name="Ada")

    awarded = api.post(
        f"/api/v1/competitions/{competition.id}/score-assist",
        {
            "kind": "criterion",
            "participant": str(participant.id),
            "scoring_category": str(category.id),
            "quantity": "4",
            "note": "In before nine.",
        },
        format="json",
    )
    assert awarded.status_code == 201

    table = api.get(f"/api/v1/competitions/{competition.id}/standings")
    row = next(item for item in table.data["rows"] if item["participant"]["name"] == "Ada")
    assert Decimal(row["points"]) == Decimal("8")


def test_a_custom_vs_competition_uses_the_win_draw_loss_points_it_sets(api):
    from decimal import Decimal

    from apps.competitions.models import Participant
    from apps.fixtures.models import FixtureSide, ScoreEvent

    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Office darts night",
            "preset": "custom",
            "scoring_basis": "results",
            "format": "league",
            "league_points": {"win": 2, "draw": 1, "loss": 0},
            "scoring_categories": [{"name": "Leg", "points": "1"}],
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    assert competition.format == "league"
    assert competition.settings_json["table_mode"] == "head_to_head"
    assert competition.settings_json["scoring_basis"] == "results"
    assert competition.settings_json["participant_type"] == "team"
    detail = api.get(f"/api/v1/competitions/{competition.id}").data
    assert detail["points_policy"]["win_points"] == "2.00"
    assert detail["points_policy"]["draw_points"] == "1.00"
    assert detail["points_policy"]["loss_points"] == "0.00"

    leg = competition.scoring_categories.get(code="leg")
    home = Participant.objects.create(competition=competition, name="Ada")
    away = Participant.objects.create(competition=competition, name="Bo")
    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.COMPLETED)
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    away_side = FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    ScoreEvent.objects.create(fixture=fixture, side=home_side, scoring_category=leg, quantity=3)
    ScoreEvent.objects.create(fixture=fixture, side=away_side, scoring_category=leg, quantity=1)
    fixture.recalculate_scores()

    table = api.get(f"/api/v1/competitions/{competition.id}/standings?refresh=true")
    points = {row["participant"]["name"]: Decimal(row["points"]) for row in table.data["rows"]}
    assert points == {"Ada": Decimal("2"), "Bo": Decimal("0")}

    with_bonus = api.post(
        "/api/v1/competitions",
        {
            "name": "Office rugby night",
            "preset": "custom",
            "scoring_basis": "results",
            "format": "league",
            "league_points": {"win": 4, "draw": 2, "loss": 0},
            "table_bonus": {
                "enabled": True,
                "scoring_threshold": 4,
                "scoring_points": 1,
                "scoring_code": "Try",
                "loss_margin": 7,
                "loss_points": 1,
            },
            "scoring_categories": [{"name": "Try", "points": "5"}],
        },
        format="json",
    )
    assert with_bonus.status_code == 201, with_bonus.data
    bonus_comp = Competition.objects.get(pk=with_bonus.data["id"])
    assert bonus_comp.settings_json["table_bonus"]["enabled"] is True
    assert bonus_comp.settings_json["table_bonus"]["scoring_code"] == "try"
    assert bonus_comp.points_policy.bonus_loss_margin == 7
    assert Decimal(str(bonus_comp.points_policy.bonus_loss_points)) == Decimal("1")

    try_cat = bonus_comp.scoring_categories.get(code="try")
    home = Participant.objects.create(competition=bonus_comp, name="Reds")
    away = Participant.objects.create(competition=bonus_comp, name="Blues")
    fixture = Fixture.objects.create(competition=bonus_comp, status=Fixture.Status.COMPLETED)
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    away_side = FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    ScoreEvent.objects.create(fixture=fixture, side=home_side, scoring_category=try_cat, quantity=4)
    ScoreEvent.objects.create(fixture=fixture, side=away_side, scoring_category=try_cat, quantity=3)
    fixture.recalculate_scores()

    bonus_table = api.get(f"/api/v1/competitions/{bonus_comp.id}/standings?refresh=true")
    bonus_points = {
        row["participant"]["name"]: (
            Decimal(row["points"]),
            Decimal(row["bonus_points"]),
        )
        for row in bonus_table.data["rows"]
    }
    # Reds: 4 for the win + 1 scoring bonus (4 tries). Blues: 1 losing bonus (lost by 5).
    assert bonus_points["Reds"] == (Decimal("5"), Decimal("1"))
    assert bonus_points["Blues"] == (Decimal("1"), Decimal("1"))

    switched_off = api.post(
        "/api/v1/competitions",
        {
            "name": "Office rugby, no bonus",
            "preset": "custom",
            "scoring_basis": "results",
            "table_bonus": {"enabled": False, "scoring_threshold": 4, "scoring_points": 1},
            "scoring_categories": [{"name": "Try", "points": "5"}],
        },
        format="json",
    )
    assert switched_off.status_code == 201, switched_off.data
    off = Competition.objects.get(pk=switched_off.data["id"])
    assert off.settings_json["table_bonus"]["enabled"] is False
    assert off.points_policy.bonus_loss_margin is None

    singles = api.post(
        "/api/v1/competitions",
        {
            "name": "Office singles",
            "preset": "custom",
            "scoring_basis": "results",
            "participant_type": "individual",
            "scoring_categories": [{"name": "Point", "points": "1"}],
        },
        format="json",
    )
    assert singles.status_code == 201, singles.data
    singles_id = singles.data["id"]
    assert Competition.objects.get(pk=singles_id).settings_json["participant_type"] == "individual"
    named_only = api.post(
        f"/api/v1/competitions/{singles_id}/participants", {"name": "Cy"}, format="json"
    )
    assert named_only.status_code == 400

    from apps.accounts.models import User

    cy = User.objects.create_user(
        email="cy@example.com", password="s3cret-password", display_name="Cy Player"
    )
    player = api.post(
        f"/api/v1/competitions/{singles_id}/participants", {"user": str(cy.id)}, format="json"
    )
    assert player.status_code == 201, player.data
    assert player.data["kind"] == "individual"
    assert player.data["name"] == cy.get_full_name()
    assert str(player.data["roster"][0]["user"]) == str(cy.id)
    again = api.post(
        f"/api/v1/competitions/{singles_id}/participants", {"user": str(cy.id)}, format="json"
    )
    assert again.status_code == 400

    accumulation = api.post(
        "/api/v1/competitions",
        {
            "name": "Still points",
            "preset": "custom",
            "scoring_basis": "criteria",
            "scoring_categories": [{"name": "Task", "points": "1"}],
        },
        format="json",
    )
    still = Competition.objects.get(pk=accumulation.data["id"])
    assert still.format == "freeform"
    assert still.settings_json["table_mode"] == "points"


def test_custom_league_records_match_events_with_time_and_player(api):
    from apps.competitions.models import Participant, RosterMember
    from apps.fixtures.models import FixtureSide, PlayerMatchRating

    created = api.post(
        "/api/v1/competitions",
        {
            "name": "League night",
            "preset": "custom",
            "scoring_basis": "results",
            "format": "league",
            "scoring_categories": [{"name": "Test1", "points": "1"}],
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    competition_id = created.data["id"]
    detail = api.get(f"/api/v1/competitions/{competition_id}").data
    codes = {item["code"]: item for item in detail["scoring_categories"]}
    assert "test1" in codes
    assert "yellow-card" in codes
    assert "red-card" in codes
    assert detail["settings_json"]["time_limit_minutes"] == 90

    home = Participant.objects.create(
        competition_id=competition_id, name="Lions", kind="team"
    )
    away = Participant.objects.create(
        competition_id=competition_id, name="Sharks", kind="team"
    )
    scorer = RosterMember.objects.create(participant=home, name="Lebo Maseko", number=9)
    booked = RosterMember.objects.create(participant=away, name="Sipho Dlamini", number=11)
    fixture = Fixture.objects.create(
        competition_id=competition_id, status=Fixture.Status.LIVE, label="Round 1"
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    away_side = FixtureSide.objects.create(fixture=fixture, participant=away, position=1)

    goal = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(home_side.id),
            "scoring_category": codes["test1"]["id"],
            "quantity": "1",
            "player": str(scorer.id),
            "minute": 12,
        },
        format="json",
    )
    assert goal.status_code == 201, goal.data
    card = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(away_side.id),
            "scoring_category": codes["yellow-card"]["id"],
            "quantity": "1",
            "player": str(booked.id),
            "minute": 29,
        },
        format="json",
    )
    assert card.status_code == 201, card.data
    PlayerMatchRating.objects.create(fixture=fixture, player=scorer, rating="8.1")

    listed = api.get(f"/api/v1/competitions/{competition_id}/fixtures")
    row = listed.data["results"][0]
    kinds = {item["kind"] for item in row["highlights"]}
    assert kinds == {"score", "yellow"}
    by_minute = {item["minute"]: item for item in row["highlights"]}
    assert by_minute[12]["player_name"] == "Lebo Maseko"
    assert by_minute[29]["player_name"] == "Sipho Dlamini"
    assert row["ratings"][0]["rating"] == "8.1"


def test_custom_knockout_records_match_events_with_time_and_player(api):
    from apps.competitions.models import Participant, RosterMember
    from apps.fixtures.models import FixtureSide, PlayerMatchRating

    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Cup night",
            "preset": "custom",
            "scoring_basis": "results",
            "format": "knockout",
            "scoring_categories": [{"name": "Test1", "points": "1"}],
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    competition_id = created.data["id"]
    detail = api.get(f"/api/v1/competitions/{competition_id}").data
    codes = {item["code"]: item for item in detail["scoring_categories"]}
    assert "test1" in codes
    assert "yellow-card" in codes
    assert "red-card" in codes
    assert detail["settings_json"]["time_limit_minutes"] == 90

    home = Participant.objects.create(
        competition_id=competition_id, name="Lions", kind="team"
    )
    away = Participant.objects.create(
        competition_id=competition_id, name="Sharks", kind="team"
    )
    scorer = RosterMember.objects.create(participant=home, name="Sipho Dlamini", number=9)
    booked = RosterMember.objects.create(participant=away, name="Thabo Nkosi", number=4)
    fixture = Fixture.objects.create(
        competition_id=competition_id, status=Fixture.Status.LIVE, label="Final"
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    away_side = FixtureSide.objects.create(fixture=fixture, participant=away, position=1)

    goal = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(home_side.id),
            "scoring_category": codes["test1"]["id"],
            "quantity": "1",
            "player": str(scorer.id),
            "minute": 23,
        },
        format="json",
    )
    assert goal.status_code == 201, goal.data
    assert goal.data["player_name"] == "Sipho Dlamini"
    assert goal.data["minute"] == 23

    card = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(away_side.id),
            "scoring_category": codes["yellow-card"]["id"],
            "quantity": "1",
            "player": str(booked.id),
            "minute": 41,
        },
        format="json",
    )
    assert card.status_code == 201, card.data

    PlayerMatchRating.objects.create(fixture=fixture, player=scorer, rating="8.4")

    listed = api.get(f"/api/v1/competitions/{competition_id}/fixtures")
    row = listed.data["results"][0]
    kinds = {item["kind"] for item in row["highlights"]}
    assert kinds == {"score", "yellow"}
    by_minute = {item["minute"]: item for item in row["highlights"]}
    assert by_minute[23]["player_name"] == "Sipho Dlamini"
    assert by_minute[23]["label"] == "Test1"
    assert by_minute[41]["player_name"] == "Thabo Nkosi"
    assert row["ratings"][0]["player_name"] == "Sipho Dlamini"
    assert row["ratings"][0]["rating"] == "8.4"


def test_individual_entrants_are_picked_from_profiles(api):
    from apps.accounts.models import User

    ada = User.objects.create_user(
        email="ada.player@example.com", password="s3cret-password", display_name="Ada Player"
    )
    for preset in ("chess", "tennis"):
        created = api.post(
            "/api/v1/competitions", {"name": f"{preset} club", "preset": preset}, format="json"
        )
        assert created.status_code == 201, created.data
        url = f"/api/v1/competitions/{created.data['id']}/participants"
        typed = api.post(url, {"name": "Typed name"}, format="json")
        assert typed.status_code == 400
        picked = api.post(url, {"user": str(ada.id)}, format="json")
        assert picked.status_code == 201, picked.data
        assert picked.data["kind"] == "individual"
        assert picked.data["name"] == ada.get_full_name()


def test_a_fully_custom_competition_needs_no_preset(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Office Table Tennis Ladder", "format": "ladder", "sport": "table tennis"},
        format="json",
    )
    competition_id = created.data["id"]

    rally = api.post(
        f"/api/v1/competitions/{competition_id}/scoring-categories",
        {"name": "Rally", "code": "rally", "points": "1"},
        format="json",
    )
    assert rally.status_code == 201

    rule = api.post(
        f"/api/v1/competitions/{competition_id}/rules",
        {"name": "Serving", "description": "Two serves each, alternating."},
        format="json",
    )
    assert rule.status_code == 201

    policy = api.patch(
        f"/api/v1/competitions/{competition_id}/points-policy",
        {"win_points": "2", "draw_points": "0", "allow_draws": False},
        format="json",
    )
    assert policy.status_code == 200
    assert policy.data["win_points"] == "2.00"


def test_private_competitions_are_hidden_from_non_members(api, anon_api, user, other_user):
    private = Competition.objects.create(name="Invite Only", owner=user, is_private=True)
    Membership.objects.create(competition=private, user=user, role=Role.OWNER)

    assert anon_api.get("/api/v1/competitions").data["count"] == 0
    assert anon_api.get(f"/api/v1/competitions/{private.id}").status_code == 404

    # The owner can still see it.
    assert api.get(f"/api/v1/competitions/{private.id}").status_code == 200


def test_members_cannot_edit_scoring(competition, other_user, rugby_scoring):
    from rest_framework.test import APIClient

    Membership.objects.create(competition=competition, user=other_user, role=Role.MEMBER)
    client = APIClient()
    client.force_authenticate(user=other_user)

    response = client.post(
        f"/api/v1/competitions/{competition.id}/scoring-categories",
        {"name": "Bonus", "code": "bonus", "points": "1"},
        format="json",
    )
    assert response.status_code == 403


def test_scorers_can_record_but_not_restructure(
    competition, other_user, rugby_scoring, participants
):
    from rest_framework.test import APIClient

    Membership.objects.create(competition=competition, user=other_user, role=Role.SCORER)
    client = APIClient()
    client.force_authenticate(user=other_user)

    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    from apps.fixtures.models import FixtureSide

    side = FixtureSide.objects.create(
        fixture=fixture, participant=participants[0], position=0
    )
    FixtureSide.objects.create(fixture=fixture, participant=participants[1], position=1)

    recorded = client.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(side.id), "scoring_category": str(rugby_scoring["try"].id), "quantity": "1"},
        format="json",
    )
    assert recorded.status_code == 201

    # Creating fixtures is an admin action.
    blocked = client.post(
        f"/api/v1/competitions/{competition.id}/fixtures",
        {"label": "Extra match"},
        format="json",
    )
    assert blocked.status_code == 403


def test_an_admin_can_appoint_another_admin_and_a_referee_scores_one_game(
    api, competition, other_user, rugby_scoring, participants
):
    from apps.accounts.models import User
    from apps.fixtures.models import FixtureSide
    from rest_framework.test import APIClient

    appointed = api.post(
        f"/api/v1/competitions/{competition.id}/members",
        {"user_id": str(other_user.id), "role": "admin"},
        format="json",
    )
    assert appointed.status_code == 201
    assert appointed.data["role"] == "admin"

    changed = api.patch(
        f"/api/v1/competitions/{competition.id}/members/{appointed.data['id']}",
        {"role": "member"},
        format="json",
    )
    assert changed.status_code == 200
    assert changed.data["role"] == "member"

    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    side = FixtureSide.objects.create(fixture=fixture, participant=participants[0], position=0)
    FixtureSide.objects.create(fixture=fixture, participant=participants[1], position=1)
    referee = User.objects.create_user(
        email="referee@example.com", password="s3cret-password", display_name="Referee"
    )
    assigned = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/referees",
        {"user": str(referee.id)},
        format="json",
    )
    assert assigned.status_code == 201
    assert assigned.data["referees"][0]["email"] == "referee@example.com"

    scorer = APIClient()
    scorer.force_authenticate(user=other_user)
    Membership.objects.filter(competition=competition, user=other_user).update(role=Role.SCORER)
    denied = scorer.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(side.id), "scoring_category": str(rugby_scoring["try"].id), "quantity": "1"},
        format="json",
    )
    assert denied.status_code == 403

    official = APIClient()
    official.force_authenticate(user=referee)
    recorded = official.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(side.id), "scoring_category": str(rugby_scoring["try"].id), "quantity": "1"},
        format="json",
    )
    assert recorded.status_code == 201


def test_score_event_updates_the_fixture_score(api, competition, rugby_scoring, participants):
    from apps.fixtures.models import FixtureSide

    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    side = FixtureSide.objects.create(fixture=fixture, participant=participants[0], position=0)
    FixtureSide.objects.create(fixture=fixture, participant=participants[1], position=1)

    api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": str(rugby_scoring["try"].id),
            "quantity": "1",
            "minute": 12,
        },
        format="json",
    )

    detail = api.get(f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}")
    scores = {item["participant"]["name"]: item["score"] for item in detail.data["sides"]}

    assert scores[participants[0].name] == "5.00"
    assert len(detail.data["events"]) == 1


def test_scoring_names_the_player_and_rates_the_game(
    api, competition, rugby_scoring, other_user
):
    from rest_framework.test import APIClient

    from apps.accounts.models import User
    from apps.competitions.models import Participant, RosterMember
    from apps.fixtures.models import FixtureSide
    from rest_framework.test import APIClient

    mate = User.objects.create_user(
        email="mate@example.com", password="s3cret-password", display_name="Mate"
    )
    mate.bio = "Plays on the wing."
    mate.save(update_fields=["bio"])
    created = api.post(
        f"/api/v1/competitions/{competition.id}/participants",
        {"name": "Wings", "kind": "team"},
        format="json",
    )
    assert created.status_code == 201
    mate_row = RosterMember.objects.create(
        participant_id=created.data["id"], user=mate, name="Mate"
    )
    RosterMember.objects.create(
        participant_id=created.data["id"], user=other_user, name="Member"
    )
    roster_id = str(mate_row.id)
    opponent = Participant.objects.create(competition=competition, name="The Rest")
    fixture = Fixture.objects.create(
        competition=competition, label="Week 1", status=Fixture.Status.LIVE
    )
    side = FixtureSide.objects.create(
        fixture=fixture, participant_id=created.data["id"], position=0
    )
    FixtureSide.objects.create(fixture=fixture, participant=opponent, position=1)

    missing = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": str(rugby_scoring["try"].id),
            "quantity": "1",
        },
        format="json",
    )
    assert missing.status_code == 400

    recorded = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": str(rugby_scoring["try"].id),
            "quantity": "1",
            "minute": 23,
            "player": roster_id,
        },
        format="json",
    )
    assert recorded.status_code == 201
    assert recorded.data["player_name"] == "Mate"
    assert recorded.data["minute"] == 23

    first = User.objects.create_user(email="rater-one@example.com", password="s3cret-password")
    second = User.objects.create_user(email="rater-two@example.com", password="s3cret-password")
    raters = f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/raters"
    assert api.post(raters, {"user": str(first.id)}, format="json").status_code == 201
    assert api.post(raters, {"user": str(second.id)}, format="json").status_code == 201
    for person in (first, second):
        client = APIClient()
        client.force_authenticate(person)
        marked = client.put(
            f"{raters}/ratings",
            {"ratings": [{"player": roster_id, "rating": "7.5"}]},
            format="json",
        )
        assert marked.status_code == 200, marked.data

    detail = api.get(f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}")
    assert detail.data["ratings"][0]["player_name"] == "Mate"
    assert detail.data["ratings"][0]["rating"] == "7.5"
    assert detail.data["events"][0]["player_name"] == "Mate"

    card = api.get(f"/api/v1/competitions/{competition.id}/players/{mate.id}")
    assert card.status_code == 200
    assert card.data["profile"]["bio"] == "Plays on the wing."
    assert card.data["team"]["name"] == "Wings"
    assert card.data["timeline"][0]["minute"] == 23
    assert card.data["timeline"][0]["category"] == "Try"
    assert card.data["ratings"][0]["rating"] == "7.5"
    assert card.data["totals"][0]["category"] == "Try"


def test_goals_and_cards_belong_to_a_profile_on_the_match_and_the_player(api):
    from apps.accounts.models import User
    from apps.competitions.models import Participant, RosterMember
    from apps.fixtures.models import Fixture, FixtureSide

    created = api.post(
        "/api/v1/competitions",
        {"name": "Profile events", "preset": "soccer"},
        format="json",
    )
    assert created.status_code == 201
    competition_id = created.data["id"]
    categories = {
        item["code"]: item["id"]
        for item in api.get(f"/api/v1/competitions/{competition_id}").data["scoring_categories"]
    }
    player = User.objects.create_user(
        email="striker@example.com", password="s3cret-password", display_name="Striker"
    )
    home = Participant.objects.create(
        competition_id=competition_id, name="Home", kind="team"
    )
    away = Participant.objects.create(
        competition_id=competition_id, name="Away", kind="team"
    )
    roster = RosterMember.objects.create(participant=home, user=player, name="Striker")
    fixture = Fixture.objects.create(
        competition_id=competition_id, label="Match stats", status=Fixture.Status.LIVE
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)

    missing = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(home_side.id), "scoring_category": categories["yellow-card"], "quantity": "1"},
        format="json",
    )
    assert missing.status_code == 400

    for code in ("goal", "own-goal", "yellow-card", "red-card"):
        recorded = api.post(
            f"/api/v1/fixtures/{fixture.id}/events",
            {
                "side": str(home_side.id),
                "scoring_category": categories[code],
                "quantity": "1",
                "player": str(roster.id),
            },
            format="json",
        )
        assert recorded.status_code == 201, recorded.data
        assert str(recorded.data["player_user_id"]) == str(player.id)

    detail = api.get(f"/api/v1/competitions/{competition_id}/fixtures/{fixture.id}")
    names = {event["scoring_category_name"] for event in detail.data["events"]}
    assert names == {"Goal", "Own goal", "Yellow card", "Red card"}
    assert all(event["player_name"] == "Striker" for event in detail.data["events"])
    scores = {item["participant"]["name"]: item["score"] for item in detail.data["sides"]}
    assert scores["Home"] == "1.00"
    assert scores["Away"] == "1.00"

    card = api.get(f"/api/v1/competitions/{competition_id}/players/{player.id}")
    totals = {item["code"]: item for item in card.data["totals"]}
    assert set(totals) == {"goal", "own-goal", "yellow-card", "red-card"}
    assert totals["goal"]["count"] == "1.00"
    assert totals["yellow-card"]["affects_score"] is False
    assert card.data["timeline"][0]["category"] in names


def test_an_event_cannot_reference_another_competitions_category(
    api, competition, participants, user
):
    from apps.competitions.models import ScoringCategory
    from apps.fixtures.models import FixtureSide

    other = Competition.objects.create(name="Other", owner=user)
    foreign = ScoringCategory.objects.create(
        competition=other, name="Goal", code="goal", points=1
    )

    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.LIVE)
    side = FixtureSide.objects.create(fixture=fixture, participant=participants[0], position=0)

    response = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(side.id), "scoring_category": str(foreign.id), "quantity": "1"},
        format="json",
    )
    assert response.status_code == 400


def test_a_game_needs_a_time_limit_and_a_referee_before_kickoff(api, other_user):
    from apps.competitions.models import Participant, RosterMember
    from apps.fixtures.models import FixtureSide
    from rest_framework.test import APIClient

    created = api.post(
        "/api/v1/competitions",
        {"name": "Timed league", "preset": "soccer"},
        format="json",
    )
    assert created.status_code == 201
    competition_id = created.data["id"]
    settings = api.get(f"/api/v1/competitions/{competition_id}").data["settings_json"]
    assert settings["time_limit_minutes"] == 90
    assert settings["overtime_minutes"] == 30

    home = Participant.objects.create(competition_id=competition_id, name="Home", kind="team")
    away = Participant.objects.create(competition_id=competition_id, name="Away", kind="team")
    fixture = Fixture.objects.create(competition_id=competition_id, label="Kickoff")
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
    away_side = FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    assert fixture.duration_minutes == 90
    assert fixture.overtime_minutes == 30

    detail_url = f"/api/v1/competitions/{competition_id}/fixtures/{fixture.id}"
    assert api.get(detail_url).data["kickoff_problems"] == [
        "Pick the match officials before kickoff.",
        "Submit Home's team sheet before kickoff.",
        "Submit Away's team sheet before kickoff.",
    ]
    blocked = api.post(f"{detail_url}/set-status", {"status": "live"}, format="json")
    assert blocked.status_code == 400

    cleared = api.patch(detail_url, {"duration_minutes": None}, format="json")
    assert cleared.status_code == 400
    no_overtime = api.patch(detail_url, {"overtime_minutes": 0}, format="json")
    assert no_overtime.status_code == 200
    assert no_overtime.data["overtime_minutes"] == 0

    api.post(
        f"/api/v1/competitions/{competition_id}/members",
        {"user_id": str(other_user.id), "role": "scorer"},
        format="json",
    )
    scorer = APIClient()
    scorer.force_authenticate(user=other_user)
    denied = scorer.patch(detail_url, {"overtime_minutes": 10}, format="json")
    assert denied.status_code == 403

    assigned = api.post(f"{detail_url}/referees", {"user": str(other_user.id)}, format="json")
    assert assigned.data["kickoff_problems"] == [
        "Submit Home's team sheet before kickoff.",
        "Submit Away's team sheet before kickoff.",
    ]

    def sheet(team):
        members = [
            RosterMember.objects.create(participant=team, name=f"{team.name} {index}", number=index)
            for index in range(1, 12)
        ]
        return {
            "formation": "4-4-2",
            "captain": str(members[0].id),
            "starters": [{"player": str(member.id), "slot": index} for index, member in enumerate(members)],
        }

    assert api.put(f"{detail_url}/team-sheets/{home_side.id}", sheet(home), format="json").status_code == 200
    still_away = api.get(detail_url).data["kickoff_problems"]
    assert still_away == ["Submit Away's team sheet before kickoff."]
    assert api.put(f"{detail_url}/team-sheets/{away_side.id}", sheet(away), format="json").status_code == 200
    assert api.get(detail_url).data["kickoff_problems"] == []
    started = scorer.post(f"{detail_url}/set-status", {"status": "live"}, format="json")
    assert started.status_code == 200
    assert started.data["status"] == "live"

    must_keep = api.patch(
        f"/api/v1/competitions/{competition_id}",
        {"settings_json": {**settings, "time_limit_minutes": 0}},
        format="json",
    )
    assert must_keep.status_code == 400


def test_generating_a_round_robin_schedules_every_pairing(api, competition, participants):
    response = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/generate",
        {
            "method": "round_robin",
            "starts_on": str(date(2026, 9, 5)),
            "weekdays": [5],  # Saturdays
            "kickoff": "15:00:00",
        },
        format="json",
    )

    assert response.status_code == 201
    # Four participants play three rounds of two matches each.
    assert len(response.data) == 6
    assert {fixture["round_number"] for fixture in response.data} == {1, 2, 3}

    dates = {fixture["scheduled_at"][:10] for fixture in response.data}
    assert dates == {"2026-09-05", "2026-09-12", "2026-09-19"}


def _finish_all(competition):
    for fixture in competition.fixtures.exclude(status=Fixture.Status.COMPLETED):
        fixture.status = Fixture.Status.COMPLETED
        fixture.save(update_fields=["status", "updated_at"])
        for side in fixture.sides.all():
            if side.outcome == "pending":
                side.outcome = "win" if side.is_home else "loss"
                side.save(update_fields=["outcome", "updated_at"])


def test_a_finished_season_can_schedule_the_next_one(api, competition, participants):
    generated = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/generate",
        {"method": "round_robin", "starts_on": "2026-09-05", "weekdays": [5], "kickoff": "15:00:00"},
        format="json",
    )
    assert generated.status_code == 201
    too_soon = api.post(
        f"/api/v1/competitions/{competition.id}/next-season",
        {"kind": "season", "starts_on": "2027-01-09", "weekdays": [5], "kickoff": "15:00:00"},
        format="json",
    )
    assert too_soon.status_code == 400

    _finish_all(competition)
    detail = api.get(f"/api/v1/competitions/{competition.id}")
    assert detail.data["season_finished"] is True

    nxt = api.post(
        f"/api/v1/competitions/{competition.id}/next-season",
        {"kind": "season", "starts_on": "2027-01-09", "weekdays": [5], "kickoff": "15:00:00"},
        format="json",
    )
    assert nxt.status_code == 201, nxt.data
    assert nxt.data["stage"]["name"] == "Season 2"
    assert nxt.data["stage"]["kind"] == "league"
    assert len(nxt.data["fixtures"]) == 6
    competition.refresh_from_db()
    assert competition.status == Competition.Status.ACTIVE
    assert competition.fixtures.filter(stage_id=nxt.data["stage"]["id"]).count() == 6


def test_a_finished_league_can_schedule_a_knockout(api, competition, participants):
    generated = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/generate",
        {"method": "round_robin", "starts_on": "2026-09-05", "weekdays": [5], "kickoff": "15:00:00"},
        format="json",
    )
    assert generated.status_code == 201
    _finish_all(competition)

    playoff = api.post(
        f"/api/v1/competitions/{competition.id}/next-season",
        {
            "kind": "knockout",
            "starts_on": "2026-12-05",
            "weekdays": [5],
            "kickoff": "15:00:00",
            "advance": 4,
        },
        format="json",
    )
    assert playoff.status_code == 201, playoff.data
    assert playoff.data["stage"]["name"] == "Play-offs"
    assert playoff.data["stage"]["kind"] == "knockout"
    competition.refresh_from_db()
    assert competition.format == Competition.Format.GROUP_KNOCKOUT
    assert competition.status == Competition.Status.ACTIVE
    assert playoff.data["competition"]["season_finished"] is False


def test_completing_the_last_fixture_marks_the_season_finished(
    api, competition, participants
):
    generated = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/generate",
        {"method": "round_robin", "starts_on": "2026-09-05", "weekdays": [5], "kickoff": "15:00:00"},
        format="json",
    )
    assert generated.status_code == 201
    fixtures = list(competition.fixtures.order_by("round_number", "created_at"))
    for fixture in fixtures[:-1]:
        api.post(
            f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/set-status",
            {"status": "completed"},
            format="json",
        )
    competition.refresh_from_db()
    assert competition.status == Competition.Status.ACTIVE

    last = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixtures[-1].id}/set-status",
        {"status": "completed"},
        format="json",
    )
    assert last.status_code == 200
    competition.refresh_from_db()
    assert competition.status == Competition.Status.COMPLETED
    detail = api.get(f"/api/v1/competitions/{competition.id}")
    assert detail.data["season_finished"] is True


def test_standings_endpoint_returns_an_ordered_table(
    api, competition, rugby_scoring, points_policy, participants
):
    from apps.fixtures.models import FixtureSide, ScoreEvent

    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.COMPLETED)
    home = FixtureSide.objects.create(fixture=fixture, participant=participants[0], position=0)
    FixtureSide.objects.create(fixture=fixture, participant=participants[1], position=1)
    ScoreEvent.objects.create(
        fixture=fixture, side=home, scoring_category=rugby_scoring["try"], quantity=3
    )
    fixture.recalculate_scores()

    response = api.get(f"/api/v1/competitions/{competition.id}/standings?refresh=true")

    assert response.status_code == 200
    rows = response.data["rows"]
    assert rows[0]["participant"]["name"] == "Tank United"
    assert rows[0]["points"] == "4.00"
    assert rows[0]["position"] == 1


def test_posting_requires_membership(competition, other_user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=other_user)

    response = client.post(
        f"/api/v1/competitions/{competition.id}/posts",
        {"body": "Great match!"},
        format="json",
    )
    assert response.status_code == 403


def test_post_comment_and_reaction_flow(api, competition, user):
    post = api.post(
        f"/api/v1/competitions/{competition.id}/posts",
        {"body": "What a finish."},
        format="json",
    )
    assert post.status_code == 201
    post_id = post.data["id"]

    comment = api.post(
        f"/api/v1/posts/{post_id}/comments", {"body": "Agreed!"}, format="json"
    )
    assert comment.status_code == 201

    liked = api.post(
        f"/api/v1/competitions/{competition.id}/posts/{post_id}/react",
        {"kind": "clap"},
        format="json",
    )
    assert liked.status_code == 201
    assert liked.data["my_reaction"] == "clap"
    assert liked.data["reaction_count"] == 1

    # Sending the same reaction again removes it.
    unliked = api.post(
        f"/api/v1/competitions/{competition.id}/posts/{post_id}/react",
        {"kind": "clap"},
        format="json",
    )
    assert unliked.data["my_reaction"] is None
    assert unliked.data["reaction_count"] == 0

    feed = api.get(f"/api/v1/competitions/{competition.id}/posts")
    assert feed.data["results"][0]["comment_count"] == 1


def test_an_empty_post_is_rejected(api, competition):
    response = api.post(
        f"/api/v1/competitions/{competition.id}/posts", {"body": "   "}, format="json"
    )
    assert response.status_code == 400


def test_a_post_cannot_attach_someone_elses_media(api, competition, other_user):
    from apps.media_assets.models import MediaAsset

    foreign = MediaAsset.objects.create(owner=other_user, kind=MediaAsset.Kind.IMAGE)

    response = api.post(
        f"/api/v1/competitions/{competition.id}/posts",
        {"body": "Look at this", "media_asset_ids": [str(foreign.id)]},
        format="json",
    )
    assert response.status_code == 400


def test_internal_endpoints_reject_a_missing_token(anon_api, competition, settings):
    settings.INTERNAL_API_TOKEN = "the-shared-secret"

    unauthenticated = anon_api.post(
        "/internal/standings/recompute",
        {"competition_id": str(competition.id)},
        format="json",
    )
    assert unauthenticated.status_code in {401, 403}

    anon_api.credentials(HTTP_AUTHORIZATION="Bearer the-shared-secret")
    authorised = anon_api.post(
        "/internal/standings/recompute",
        {"competition_id": str(competition.id)},
        format="json",
    )
    assert authorised.status_code == 200


def test_swagger_schema_is_served(anon_api):
    response = anon_api.get("/api/schema/?format=json")
    assert response.status_code == 200
    assert response.data["info"]["title"] == "Fair Measure API"
