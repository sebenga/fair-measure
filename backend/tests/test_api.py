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


def test_creating_a_competition_with_a_preset_seeds_scoring(api):
    response = api.post(
        "/api/v1/competitions",
        {"name": "Sunday Soccer", "preset": "soccer"},
        format="json",
    )
    assert response.status_code == 201

    detail = api.get(f"/api/v1/competitions/{response.data['id']}")
    codes = {item["code"] for item in detail.data["scoring_categories"]}

    assert codes == {"goal"}
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


def test_a_team_is_created_from_multiple_profiles(api, user, other_user):
    from apps.accounts.models import User

    second = User.objects.create_user(
        email="second@example.com", password="s3cret-password", display_name="Second"
    )
    created = api.post("/api/v1/competitions", {"name": "Sunday league"}, format="json")
    assert created.status_code == 201
    competition_id = created.data["id"]
    participants_url = f"/api/v1/competitions/{competition_id}/participants"

    too_small = api.post(
        participants_url,
        {"name": "Short", "kind": "team", "member_ids": [str(other_user.id)]},
        format="json",
    )
    assert too_small.status_code == 400

    team = api.post(
        participants_url,
        {
            "name": "Northside",
            "kind": "team",
            "member_ids": [str(other_user.id), str(second.id)],
        },
        format="json",
    )
    assert team.status_code == 201
    assert team.data["kind"] == "team"
    assert sorted(member["name"] for member in team.data["roster"]) == ["Member", "Second"]

    player = api.post(participants_url, {"name": "Solo", "kind": "individual"}, format="json")
    assert player.status_code == 400

    with_owner = api.post(
        participants_url,
        {
            "name": "Owners",
            "kind": "team",
            "member_ids": [str(user.id), str(other_user.id)],
        },
        format="json",
    )
    assert with_owner.status_code == 201
    assert "Owner" in [member["name"] for member in with_owner.data["roster"]]

    second_team = api.post(
        participants_url,
        {
            "name": "Owners again",
            "kind": "team",
            "member_ids": [str(user.id), str(second.id)],
        },
        format="json",
    )
    assert second_team.status_code == 400

    admin = User.objects.create_user(
        email="coach@example.com", password="s3cret-password", display_name="Coach"
    )
    Membership.objects.create(competition_id=competition_id, user=admin, role=Role.ADMIN)
    placed_by_owner = api.post(
        f"/api/v1/competitions/{competition_id}/participants/{team.data['id']}/roster",
        {"user": str(admin.id), "name": "Coach"},
        format="json",
    )
    assert placed_by_owner.status_code == 400

    from rest_framework.test import APIClient

    coach = APIClient()
    coach.force_authenticate(user=admin)
    joined = coach.post(
        participants_url,
        {
            "name": "Coaches",
            "kind": "team",
            "member_ids": [str(admin.id), str(second.id)],
        },
        format="json",
    )
    assert joined.status_code == 201
    assert "Coach" in [member["name"] for member in joined.data["roster"]]


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
            "scoring_basis": "results",
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

    fixture = Fixture.objects.create(competition=competition)
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


def test_score_event_updates_the_fixture_score(api, competition, rugby_scoring, participants):
    from apps.fixtures.models import FixtureSide

    fixture = Fixture.objects.create(competition=competition)
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


def test_an_event_cannot_reference_another_competitions_category(
    api, competition, participants, user
):
    from apps.competitions.models import ScoringCategory
    from apps.fixtures.models import FixtureSide

    other = Competition.objects.create(name="Other", owner=user)
    foreign = ScoringCategory.objects.create(
        competition=other, name="Goal", code="goal", points=1
    )

    fixture = Fixture.objects.create(competition=competition)
    side = FixtureSide.objects.create(fixture=fixture, participant=participants[0], position=0)

    response = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {"side": str(side.id), "scoring_category": str(foreign.id), "quantity": "1"},
        format="json",
    )
    assert response.status_code == 400


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
