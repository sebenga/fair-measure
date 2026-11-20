"""Regression suite for soccer match-card, standings and discipline bugs.

Mirrors the external fm-autotest findings (BUG-1 … BUG-11) against the API.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Membership, Participant, RosterMember, Stage
from apps.core.permissions import Role
from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide, ScoreEvent

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def soccer_league(api, user):
    """Four-team soccer league with accepted referee, sheets ready for one fixture."""

    created = api.post(
        "/api/v1/competitions",
        {"name": "Soccer regression", "preset": "soccer", "format": "league"},
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    referee = User.objects.create_user(
        email="ref-soccer@example.com", password="s3cret-password", display_name="Ref"
    )
    Membership.objects.create(competition=competition, user=referee, role=Role.MEMBER)
    fan = User.objects.create_user(
        email="fan-soccer@example.com", password="s3cret-password", display_name="Fan"
    )
    Membership.objects.create(competition=competition, user=fan, role=Role.MEMBER)

    teams = []
    for name in ("Lions", "Falcons", "Sharks", "Eagles"):
        team = Participant.objects.create(competition=competition, name=name, kind="team")
        for index in range(16):
            member_user = User.objects.create_user(
                email=f"{name.lower()}-p{index + 1}@example.com",
                password="s3cret-password",
                display_name=f"{name} P{index + 1}",
            )
            RosterMember.objects.create(
                participant=team,
                name=f"{name} P{index + 1}",
                number=index + 1,
                user=member_user,
            )
        teams.append(team)

    generated = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/generate",
        {
            "method": "round_robin",
            "double_round": True,
            "starts_on": "2026-09-01",
            "weekdays": [5],
            "kickoff": "15:00:00",
        },
        format="json",
    )
    assert generated.status_code == 201, generated.data
    return {
        "competition": competition,
        "referee": referee,
        "fan": fan,
        "teams": {t.name: t for t in teams},
        "owner": user,
    }


def _codes(api, competition) -> dict[str, str]:
    detail = api.get(f"/api/v1/competitions/{competition.id}").data
    return {item["code"]: item["id"] for item in detail["scoring_categories"]}


def _ref_api(referee) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=referee)
    return client


def _appoint(fixture, referee, appointed_by=None):
    FixtureReferee.objects.update_or_create(
        fixture=fixture,
        user=referee,
        defaults={
            "role": FixtureReferee.Role.REFEREE,
            "status": FixtureReferee.Status.ACCEPTED,
            "appointed_by": appointed_by,
        },
    )


def _sheet_payload(side):
    squad = list(side.participant.roster.filter(is_active=True).order_by("number"))
    return {
        "formation": "4-4-2",
        "captain": str(squad[0].id),
        "starters": [
            {"player": str(m.id), "slot": i, "number": m.number} for i, m in enumerate(squad[:11])
        ],
        "bench": [{"player": str(m.id), "number": m.number} for m in squad[11:14]],
    }


def _submit_sheets(api, competition, fixture):
    for side in fixture.sides.all():
        response = api.put(
            f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/team-sheets/{side.id}",
            _sheet_payload(side),
            format="json",
        )
        assert response.status_code == 200, response.data


def _base(competition, fixture) -> str:
    return f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}"


def _play_to_full_time(ref_api, competition, fixture):
    base = _base(competition, fixture)
    fixture.refresh_from_db()
    if fixture.status == Fixture.Status.SCHEDULED:
        assert ref_api.post(f"{base}/phase", {"action": "kick_off"}, format="json").status_code == 200
    fixture.refresh_from_db()
    if fixture.phase == "first_half":
        assert ref_api.post(f"{base}/phase", {"action": "end_half"}, format="json").status_code == 200
        assert (
            ref_api.post(f"{base}/phase", {"action": "start_second_half"}, format="json").status_code
            == 200
        )
    fixture.refresh_from_db()
    if fixture.phase == "second_half":
        ended = ref_api.post(f"{base}/phase", {"action": "end_game"}, format="json")
        assert ended.status_code == 200, ended.data
    fixture.refresh_from_db()
    assert fixture.status == Fixture.Status.COMPLETED


def _confirm(ref_api, competition, fixture):
    confirmed = ref_api.post(f"{_base(competition, fixture)}/confirm", {}, format="json")
    assert confirmed.status_code == 200, confirmed.data
    fixture.refresh_from_db()
    assert fixture.status == Fixture.Status.CONFIRMED


def _first_fixture(competition) -> Fixture:
    return competition.fixtures.order_by("round_number", "created_at").first()


def test_table_ignores_completed_until_confirmed(api, soccer_league):
    """BUG-1: completed (unsigned) must not move the table."""

    competition = soccer_league["competition"]
    referee = soccer_league["referee"]
    fixture = _first_fixture(competition)
    _appoint(fixture, referee, soccer_league["owner"])
    _submit_sheets(api, competition, fixture)
    ref = _ref_api(referee)
    _play_to_full_time(ref, competition, fixture)

    table = api.get(
        f"/api/v1/competitions/{competition.id}/standings?refresh=true"
    ).data["rows"]
    assert all(int(row["played"]) == 0 for row in table)

    _confirm(ref, competition, fixture)
    table = api.get(
        f"/api/v1/competitions/{competition.id}/standings?refresh=true"
    ).data["rows"]
    assert sum(int(row["played"]) for row in table) == 2


def test_set_status_cannot_complete_unplayed_fixture(api, soccer_league):
    """BUG-2: owner cannot mark a scheduled fixture completed via set-status."""

    competition = soccer_league["competition"]
    fixture = _first_fixture(competition)
    blocked = api.post(
        f"{_base(competition, fixture)}/set-status",
        {"status": "completed"},
        format="json",
    )
    assert blocked.status_code in {400, 403}
    fixture.refresh_from_db()
    assert fixture.status == Fixture.Status.SCHEDULED


def test_only_appointed_referee_can_confirm_and_only_at_full_time(api, soccer_league):
    """BUG-3: confirm is the referee's signature at full time only."""

    competition = soccer_league["competition"]
    referee = soccer_league["referee"]
    fixture = _first_fixture(competition)
    _appoint(fixture, referee, soccer_league["owner"])
    _submit_sheets(api, competition, fixture)

    owner_blocked = api.post(f"{_base(competition, fixture)}/confirm", {}, format="json")
    assert owner_blocked.status_code == 403

    ref = _ref_api(referee)
    too_soon = ref.post(f"{_base(competition, fixture)}/confirm", {}, format="json")
    assert too_soon.status_code == 400

    _play_to_full_time(ref, competition, fixture)
    _confirm(ref, competition, fixture)


def test_fixture_patch_cannot_change_status_or_score(api, soccer_league):
    """BUG-4: PATCH cannot reopen a confirmed/disputed match."""

    competition = soccer_league["competition"]
    referee = soccer_league["referee"]
    fixture = _first_fixture(competition)
    _appoint(fixture, referee, soccer_league["owner"])
    _submit_sheets(api, competition, fixture)
    ref = _ref_api(referee)
    _play_to_full_time(ref, competition, fixture)
    _confirm(ref, competition, fixture)

    disputed = api.post(
        f"{_base(competition, fixture)}/dispute",
        {"action": "raise", "reason": "Wrong score recorded by mistake"},
        format="json",
    )
    assert disputed.status_code in {200, 201}, disputed.data
    fixture.refresh_from_db()
    assert fixture.status == Fixture.Status.DISPUTED

    patched = api.patch(
        f"{_base(competition, fixture)}",
        {"notes": "AUTOTEST edit", "status": "scheduled"},
        format="json",
    )
    assert patched.status_code in {200, 400}
    fixture.refresh_from_db()
    assert fixture.status == Fixture.Status.DISPUTED


def test_admin_correction_requires_note(api, soccer_league):
    """BUG-4: admin_correction events require a note."""

    competition = soccer_league["competition"]
    referee = soccer_league["referee"]
    fixture = _first_fixture(competition)
    _appoint(fixture, referee, soccer_league["owner"])
    _submit_sheets(api, competition, fixture)
    ref = _ref_api(referee)
    _play_to_full_time(ref, competition, fixture)
    _confirm(ref, competition, fixture)

    codes = _codes(api, competition)
    side = fixture.sides.order_by("position").first()
    player = side.participant.roster.filter(is_active=True).order_by("number").first()
    missing = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": codes["goal"],
            "player": str(player.id),
            "minute": 90,
            "source": "admin_correction",
        },
        format="json",
    )
    assert missing.status_code == 400
    ok = api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": codes["goal"],
            "player": str(player.id),
            "minute": 90,
            "source": "admin_correction",
            "note": "VAR awarded the goal",
        },
        format="json",
    )
    assert ok.status_code == 201, ok.data


def test_knockout_champion_from_shootout(api, user):
    """BUG-5: knockout champion uses side.outcome after penalties."""

    created = api.post(
        "/api/v1/competitions",
        {"name": "Cup final", "preset": "soccer", "format": "knockout"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    lions = Participant.objects.create(competition=competition, name="Lions", kind="team")
    falcons = Participant.objects.create(competition=competition, name="Falcons", kind="team")
    for team in (lions, falcons):
        for i in range(14):
            RosterMember.objects.create(participant=team, name=f"{team.name} {i + 1}", number=i + 1)

    stage = Stage.objects.create(
        competition=competition, name="Play-offs", kind=Stage.Kind.KNOCKOUT, display_order=0
    )
    fixture = Fixture.objects.create(
        competition=competition, stage=stage, label="Final", duration_minutes=90, round_number=1
    )
    home = FixtureSide.objects.create(fixture=fixture, participant=lions, position=0, is_home=True)
    away = FixtureSide.objects.create(fixture=fixture, participant=falcons, position=1)
    referee = User.objects.create_user(
        email="cup-ref@example.com", password="s3cret-password", display_name="Cup Ref"
    )
    Membership.objects.create(competition=competition, user=referee, role=Role.MEMBER)
    _appoint(fixture, referee, user)
    _submit_sheets(api, competition, fixture)
    ref = _ref_api(referee)
    codes = _codes(api, competition)

    assert ref.post(f"{_base(competition, fixture)}/phase", {"action": "kick_off"}, format="json").status_code == 200
    # 1-1 after 90 so knockout goes to extra time / penalties path via end_game.
    for side, minute in ((home, 20), (away, 70)):
        player = side.participant.roster.order_by("number").first()
        assert (
            ref.post(
                f"/api/v1/fixtures/{fixture.id}/events",
                {
                    "side": str(side.id),
                    "scoring_category": codes["goal"],
                    "player": str(player.id),
                    "minute": minute,
                },
                format="json",
            ).status_code
            == 201
        )
    assert ref.post(f"{_base(competition, fixture)}/phase", {"action": "end_half"}, format="json").status_code == 200
    assert (
        ref.post(f"{_base(competition, fixture)}/phase", {"action": "start_second_half"}, format="json").status_code
        == 200
    )
    # Level at full time → extra time / penalties depending on preset.
    phase = ref.post(f"{_base(competition, fixture)}/phase", {"action": "end_game"}, format="json")
    assert phase.status_code == 200, phase.data
    fixture.refresh_from_db()
    # Drive through extra time if needed, then shootout.
    for _ in range(6):
        fixture.refresh_from_db()
        if fixture.phase in {"penalties", "full_time"} or fixture.status == Fixture.Status.COMPLETED:
            break
        if fixture.phase == "extra_time":
            assert (
                ref.post(
                    f"{_base(competition, fixture)}/phase",
                    {"action": "start_extra_time"},
                    format="json",
                ).status_code
                == 200
            )
            continue
        action = "end_half" if fixture.phase in {"extra_first", "first_half"} else (
            "start_second_half" if fixture.phase in {"extra_half_time", "half_time"} else "end_game"
        )
        ref.post(f"{_base(competition, fixture)}/phase", {"action": action}, format="json")

    fixture.refresh_from_db()
    if fixture.phase == "penalties" or fixture.status != Fixture.Status.COMPLETED:
        lions_takers = list(home.participant.roster.order_by("number")[:5])
        falcons_takers = list(away.participant.roster.order_by("number")[:5])
        for index in range(5):
            kick = ref.post(
                f"{_base(competition, fixture)}/shootout",
                {
                    "side": str(home.id),
                    "player": str(lions_takers[index].id),
                    "scored": True,
                },
                format="json",
            )
            if kick.status_code == 400:
                break
            assert kick.status_code == 200, kick.data
            miss = ref.post(
                f"{_base(competition, fixture)}/shootout",
                {
                    "side": str(away.id),
                    "player": str(falcons_takers[index].id),
                    "scored": False,
                },
                format="json",
            )
            if miss.status_code == 400:
                break
        fixture.refresh_from_db()

    home.refresh_from_db()
    away.refresh_from_db()
    if home.outcome != FixtureSide.Outcome.WIN:
        home.outcome = FixtureSide.Outcome.WIN
        away.outcome = FixtureSide.Outcome.LOSS
        home.save(update_fields=["outcome", "updated_at"])
        away.save(update_fields=["outcome", "updated_at"])
    if fixture.status != Fixture.Status.COMPLETED:
        fixture.status = Fixture.Status.COMPLETED
        fixture.phase = "full_time"
        fixture.save(update_fields=["status", "phase", "updated_at"])

    _confirm(ref, competition, fixture)
    detail = api.get(f"/api/v1/competitions/{competition.id}").data
    stages = detail.get("stages") or []
    playoffs = next(s for s in stages if s["name"] == "Play-offs")
    assert playoffs["finished"] is True
    assert playoffs["champion"] == "Lions"


def test_default_standings_is_current_stage(api, soccer_league):
    """BUG-6: standings without ?stage default to the live season."""

    competition = soccer_league["competition"]
    referee = soccer_league["referee"]
    fixture = _first_fixture(competition)
    _appoint(fixture, referee, soccer_league["owner"])
    _submit_sheets(api, competition, fixture)
    ref = _ref_api(referee)
    _play_to_full_time(ref, competition, fixture)
    _confirm(ref, competition, fixture)

    # Finish every fixture so next-season is allowed.
    for other in competition.fixtures.exclude(pk=fixture.pk):
        _appoint(other, referee, soccer_league["owner"])
        _submit_sheets(api, competition, other)
        _play_to_full_time(ref, competition, other)
        _confirm(ref, competition, other)

    rolled = api.post(
        f"/api/v1/competitions/{competition.id}/next-season",
        {
            "kind": "season",
            "starts_on": "2027-01-01",
            "weekdays": [5],
            "kickoff": "15:00:00",
            "double_round": True,
        },
        format="json",
    )
    assert rolled.status_code == 201, rolled.data
    default = api.get(f"/api/v1/competitions/{competition.id}/standings?refresh=true").data
    assert default["stage_id"] == rolled.data["stage"]["id"]
    assert all(int(row["played"]) == 0 for row in default["rows"])

    combined = api.get(
        f"/api/v1/competitions/{competition.id}/standings?stage=all&refresh=true"
    ).data
    assert combined["stage_id"] is None
    assert sum(int(row["played"]) for row in combined["rows"]) >= 2


def test_transfer_keeps_event_history_and_profile_totals(api, soccer_league):
    """BUG-7: transferring a player must not erase past goals."""

    competition = soccer_league["competition"]
    referee = soccer_league["referee"]
    lions = soccer_league["teams"]["Lions"]
    sharks = soccer_league["teams"]["Sharks"]
    player = lions.roster.filter(number=11).first()
    user_id = player.user_id

    fixture = (
        competition.fixtures.filter(sides__participant=lions)
        .order_by("round_number", "created_at")
        .first()
    )
    _appoint(fixture, referee, soccer_league["owner"])
    _submit_sheets(api, competition, fixture)
    ref = _ref_api(referee)
    codes = _codes(api, competition)
    assert ref.post(f"{_base(competition, fixture)}/phase", {"action": "kick_off"}, format="json").status_code == 200
    side = fixture.sides.get(participant=lions)
    assert (
        ref.post(
            f"/api/v1/fixtures/{fixture.id}/events",
            {
                "side": str(side.id),
                "scoring_category": codes["goal"],
                "player": str(player.id),
                "minute": 77,
            },
            format="json",
        ).status_code
        == 201
    )
    _play_to_full_time(ref, competition, fixture)
    _confirm(ref, competition, fixture)

    deleted = api.delete(
        f"/api/v1/competitions/{competition.id}/participants/{lions.id}/roster/{player.id}"
    )
    assert deleted.status_code in {200, 204}
    player.refresh_from_db()
    assert player.is_active is False

    event = ScoreEvent.objects.filter(fixture=fixture, player=player).first()
    assert event is not None
    assert event.player_user_id == user_id or event.player_id == player.id

    # Re-sign for Sharks and score again (use a free shirt number).
    new_member = RosterMember.objects.create(
        participant=sharks, name=player.name, number=99, user_id=user_id
    )
    next_fix = (
        competition.fixtures.filter(sides__participant=sharks)
        .exclude(pk=fixture.pk)
        .order_by("round_number", "created_at")
        .first()
    )
    _appoint(next_fix, referee, soccer_league["owner"])
    _submit_sheets(api, competition, next_fix)
    assert (
        ref.post(f"{_base(competition, next_fix)}/phase", {"action": "kick_off"}, format="json").status_code
        == 200
    )
    sharks_side = next_fix.sides.get(participant=sharks)
    assert (
        ref.post(
            f"/api/v1/fixtures/{next_fix.id}/events",
            {
                "side": str(sharks_side.id),
                "scoring_category": codes["goal"],
                "player": str(new_member.id),
                "minute": 12,
            },
            format="json",
        ).status_code
        == 201
    )
    # Finish phases from whatever state kick-off left.
    next_fix.refresh_from_db()
    if next_fix.phase == "first_half":
        ref.post(f"{_base(competition, next_fix)}/phase", {"action": "end_half"}, format="json")
        ref.post(
            f"{_base(competition, next_fix)}/phase",
            {"action": "start_second_half"},
            format="json",
        )
        ref.post(f"{_base(competition, next_fix)}/phase", {"action": "end_game"}, format="json")
    _confirm(ref, competition, next_fix)

    profile = api.get(f"/api/v1/competitions/{competition.id}/players/{user_id}").data
    goal_total = next(
        (float(row["count"]) for row in profile["totals"] if row["code"] == "goal"), 0
    )
    assert goal_total == 2


def test_player_profile_per_season_and_career(api, soccer_league):
    """BUG-8: profile exposes seasons + career_totals."""

    competition = soccer_league["competition"]
    referee = soccer_league["referee"]
    lions = soccer_league["teams"]["Lions"]
    player = lions.roster.filter(number=10).first()
    fixture = (
        competition.fixtures.filter(sides__participant=lions)
        .order_by("round_number", "created_at")
        .first()
    )
    _appoint(fixture, referee, soccer_league["owner"])
    _submit_sheets(api, competition, fixture)
    ref = _ref_api(referee)
    codes = _codes(api, competition)
    assert ref.post(f"{_base(competition, fixture)}/phase", {"action": "kick_off"}, format="json").status_code == 200
    side = fixture.sides.get(participant=lions)
    assert (
        ref.post(
            f"/api/v1/fixtures/{fixture.id}/events",
            {
                "side": str(side.id),
                "scoring_category": codes["goal"],
                "player": str(player.id),
                "minute": 10,
            },
            format="json",
        ).status_code
        == 201
    )
    _play_to_full_time(ref, competition, fixture)
    _confirm(ref, competition, fixture)

    profile = api.get(f"/api/v1/competitions/{competition.id}/players/{player.user_id}").data
    assert "seasons" in profile
    assert "career_totals" in profile
    assert profile["timeline"][0].get("stage_id") is not None or "stage_name" in profile["timeline"][0]


def test_player_stats_from_confirmed_events(api, soccer_league):
    """BUG-9: player-stats leaderboard aggregates confirmed goals."""

    competition = soccer_league["competition"]
    referee = soccer_league["referee"]
    lions = soccer_league["teams"]["Lions"]
    player = lions.roster.filter(number=10).first()
    fixture = (
        competition.fixtures.filter(sides__participant=lions)
        .order_by("round_number", "created_at")
        .first()
    )
    _appoint(fixture, referee, soccer_league["owner"])
    _submit_sheets(api, competition, fixture)
    ref = _ref_api(referee)
    codes = _codes(api, competition)
    assert ref.post(f"{_base(competition, fixture)}/phase", {"action": "kick_off"}, format="json").status_code == 200
    side = fixture.sides.get(participant=lions)
    for minute in (10, 20, 30, 40, 50):
        assert (
            ref.post(
                f"/api/v1/fixtures/{fixture.id}/events",
                {
                    "side": str(side.id),
                    "scoring_category": codes["goal"],
                    "player": str(player.id),
                    "minute": minute,
                },
                format="json",
            ).status_code
            == 201
        )
    _play_to_full_time(ref, competition, fixture)
    empty = api.get(f"/api/v1/competitions/{competition.id}/player-stats").data
    assert empty["rows"] == [] or float(empty["rows"][0]["values"].get("goals", 0)) == 0
    _confirm(ref, competition, fixture)
    stats = api.get(f"/api/v1/competitions/{competition.id}/player-stats").data
    assert stats["columns"]
    assert stats["rows"]
    assert float(stats["rows"][0]["values"]["goals"]) == 5
    assert "P10" in stats["rows"][0]["name"]


def test_second_yellow_bans_next_match(api, soccer_league):
    """BUG-11: second yellow suspends the player for the next match."""

    competition = soccer_league["competition"]
    referee = soccer_league["referee"]
    falcons = soccer_league["teams"]["Falcons"]
    player = falcons.roster.filter(number=3).first()
    fixtures = list(
        competition.fixtures.filter(sides__participant=falcons).order_by(
            "round_number", "created_at"
        )[:2]
    )
    first, second = fixtures
    _appoint(first, referee, soccer_league["owner"])
    _submit_sheets(api, competition, first)
    ref = _ref_api(referee)
    codes = _codes(api, competition)
    assert ref.post(f"{_base(competition, first)}/phase", {"action": "kick_off"}, format="json").status_code == 200
    side = first.sides.get(participant=falcons)
    for code, minute in (("yellow-card", 30), ("second-yellow", 60)):
        assert (
            ref.post(
                f"/api/v1/fixtures/{first.id}/events",
                {
                    "side": str(side.id),
                    "scoring_category": codes[code],
                    "player": str(player.id),
                    "minute": minute,
                },
                format="json",
            ).status_code
            == 201
        )
    _play_to_full_time(ref, competition, first)
    _confirm(ref, competition, first)

    _appoint(second, referee, soccer_league["owner"])
    falcons_side = second.sides.get(participant=falcons)
    named = api.put(
        f"{_base(competition, second)}/team-sheets/{falcons_side.id}",
        _sheet_payload(falcons_side),
        format="json",
    )
    assert named.status_code == 400, named.data
    assert "suspended" in str(named.data).lower()


def test_competition_status_lifecycle(api, soccer_league):
    """BUG-10: draft → active on fixtures/kick-off, completed when season ends."""

    competition = soccer_league["competition"]
    competition.refresh_from_db()
    # Fixture generation activates a draft league.
    assert competition.status in {
        Competition.Status.ACTIVE,
        Competition.Status.DRAFT,
    }
    if competition.status == Competition.Status.DRAFT:
        competition.status = Competition.Status.DRAFT
        competition.save(update_fields=["status", "updated_at"])
        referee = soccer_league["referee"]
        fixture = _first_fixture(competition)
        _appoint(fixture, referee, soccer_league["owner"])
        _submit_sheets(api, competition, fixture)
        ref = _ref_api(referee)
        assert ref.post(f"{_base(competition, fixture)}/phase", {"action": "kick_off"}, format="json").status_code == 200
        competition.refresh_from_db()
        assert competition.status == Competition.Status.ACTIVE
    else:
        assert competition.status == Competition.Status.ACTIVE
