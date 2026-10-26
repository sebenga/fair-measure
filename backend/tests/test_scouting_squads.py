"""Scouting reports and league squads: a league's best players, picked like a national team."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import (
    Competition,
    Membership,
    Participant,
    RosterMember,
    ScoringCategory,
)
from apps.core.permissions import Role
from apps.fixtures.models import (
    Fixture,
    FixtureLineup,
    FixtureSide,
    LineupEntry,
    PlayerMatchRating,
    ScoreEvent,
)
from apps.scouting import catalog
from apps.scouting.models import (
    LeagueSquad,
    Organisation,
    PlayerProfile,
    PlayerSport,
    ReportExport,
)
from apps.scouting.services import grant_role

pytestmark = pytest.mark.django_db
User = get_user_model()

SPORT = next(iter(catalog.SQUADS))
TEMPLATE = catalog.SQUADS[SPORT]


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


def _born(age: int) -> date:
    today = date.today()
    return date(today.year - age, 1, 1)


@pytest.fixture
def league(db):
    owner = User.objects.create_user(email="selector@league.test", password="pw-123456789")
    competition = Competition.objects.create(
        name="Coastal League",
        owner=owner,
        sport=SPORT,
        status=Competition.Status.ACTIVE,
        open_to_scouts=True,
    )
    Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
    teams = [
        Participant.objects.create(competition=competition, name=name, kind="team")
        for name in ("Hawks", "Owls")
    ]
    goal = ScoringCategory.objects.create(
        competition=competition, name="Goal", code="goal", points=Decimal("1")
    )
    return {"owner": owner, "competition": competition, "teams": teams, "goal": goal}


def _player(league, team_index: int, name: str, group: dict, *, age=22, visibility="scouts"):
    user = User.objects.create_user(
        email=f"{name.lower().replace(' ', '.')}@league.test", password="pw-123456789"
    )
    first, last = name.split(" ")
    profile = PlayerProfile.objects.create(
        user=user,
        first_name=first,
        last_name=last,
        date_of_birth=_born(age),
        visibility=visibility,
    )
    PlayerSport.objects.create(
        profile=profile, sport=SPORT, primary_position=group["positions"][0], is_primary=True
    )
    member = RosterMember.objects.create(
        participant=league["teams"][team_index], name=name, user=user
    )
    return user, profile, member


def _fill_league(league, per_group_extra: int = 2) -> dict:
    players = {}
    for group in TEMPLATE["groups"]:
        for index in range(group["max"] + per_group_extra):
            name = f"{group['key'].title().replace('-', '')} P{index}"
            players[name] = _player(league, index % 2, name, group)
    return players


def _play(league, *, winner: int, ratings: dict | None = None, goals: dict | None = None):
    competition = league["competition"]
    fixture = Fixture.objects.create(competition=competition, status=Fixture.Status.COMPLETED)
    sides = []
    for index, team in enumerate(league["teams"]):
        sides.append(
            FixtureSide.objects.create(
                fixture=fixture,
                participant=team,
                position=index,
                outcome="win" if index == winner else "loss",
            )
        )
    for member, value in (ratings or {}).items():
        PlayerMatchRating.objects.create(fixture=fixture, player=member, rating=Decimal(value))
    for member, count in (goals or {}).items():
        side = next(side for side in sides if side.participant_id == member.participant_id)
        ScoreEvent.objects.create(
            fixture=fixture,
            side=side,
            scoring_category=league["goal"],
            quantity=Decimal(count),
            player=member,
        )
    return fixture


def test_squad_shapes_are_valid_data():
    for key, template in catalog.SQUADS.items():
        assert key in catalog.SPORTS
        mins = sum(group["min"] for group in template["groups"])
        maxes = sum(group["max"] for group in template["groups"])
        assert mins <= template["size"] <= maxes, key
        positions = catalog.position_keys(key)
        for group in template["groups"]:
            assert set(group["positions"]) <= positions, (key, group["key"])


def test_competition_sports_map_onto_the_catalogue():
    for key, aliases in catalog.COMPETITION_SPORT_ALIASES.items():
        assert key in catalog.SPORTS
        for alias in aliases:
            assert catalog.sport_for_competition(alias.upper()) == key
    assert catalog.sport_for_competition("chess") is None
    assert catalog.squad_template(None)["size"] == catalog.DEFAULT_SQUAD_SIZE


def test_generate_fills_the_squad_with_group_minimums(league):
    _fill_league(league)
    _play(league, winner=0)

    response = _client(league["owner"]).post(
        f"/api/v1/scouting/leagues/{league['competition'].id}/squad/generate"
    )
    assert response.status_code == 200, response.data
    squad = response.data["squad"]
    assert squad["size"] == TEMPLATE["size"]
    assert squad["filled"] == TEMPLATE["size"]
    counts = {group["key"]: len(group["picks"]) for group in squad["groups"]}
    for group in TEMPLATE["groups"]:
        assert group["min"] <= counts[group["key"]] <= group["max"], group["key"]


def test_better_evidence_wins_the_place(league):
    group = TEMPLATE["groups"][0]
    players = _fill_league(league)
    names = [name for name in players if name.startswith(group["key"].title().replace("-", ""))]
    star, bench = names[-1], names[0]
    _play(
        league,
        winner=0 if players[star][2].participant_id == league["teams"][0].id else 1,
        ratings={players[star][2]: "9.0", players[bench][2]: "3.0"},
        goals={players[star][2]: 2},
    )

    client = _client(league["owner"])
    client.post(f"/api/v1/scouting/leagues/{league['competition'].id}/squad/generate")
    ranked = client.get(f"/api/v1/scouting/leagues/{league['competition'].id}/candidates").data
    order = [row["name"] for row in ranked["results"]]
    assert order.index(star) < order.index(bench)
    star_row = next(row for row in ranked["results"] if row["name"] == star)
    assert star_row["avg_rating"] == "9.0"
    assert "form" in star_row["basis"] and "output" in star_row["basis"]
    assert any("Average match rating 9.0" in line for line in star_row["summary"])


def test_the_roster_position_decides_the_group(league):
    first, second = TEMPLATE["groups"][0], TEMPLATE["groups"][1]
    user, _, member = _player(league, 0, "Two Roles", first)
    # The team rosters them in a different group from the one their profile claims.
    member.position = second["label"]
    member.save()

    ranked = _client(league["owner"]).get(
        f"/api/v1/scouting/leagues/{league['competition'].id}/candidates"
    )
    row = next(item for item in ranked.data["results"] if item["user_id"] == str(user.id))
    assert row["group_key"] == second["key"]
    assert row["position"] == second["label"]


def test_match_shirts_put_a_player_in_every_line_they_played(league):
    first, second = TEMPLATE["groups"][0], TEMPLATE["groups"][1]
    user, _, member = _player(league, 0, "Two Lines", first)
    member.position = first["positions"][0]
    member.save()

    for shirt in (first["positions"][0], second["positions"][0]):
        fixture = _play(league, winner=0)
        side = fixture.sides.get(participant=member.participant)
        lineup = FixtureLineup.objects.create(fixture=fixture, side=side)
        LineupEntry.objects.create(
            lineup=lineup,
            player=member,
            role=LineupEntry.Role.STARTER,
            slot=0,
            position=shirt,
            order=0,
        )

    ranked = _client(league["owner"]).get(
        f"/api/v1/scouting/leagues/{league['competition'].id}/candidates"
    )
    row = next(item for item in ranked.data["results"] if item["user_id"] == str(user.id))
    assert first["key"] in row["group_keys"]
    assert second["key"] in row["group_keys"]
    assert row["user_id"] == str(user.id)


def test_private_profiles_and_minors_without_consent_are_never_picked(league):
    _fill_league(league)
    group = TEMPLATE["groups"][1]
    hidden_user, *_ = _player(league, 0, "Hidden Adult", group, visibility="private")
    minor_user, *_ = _player(league, 1, "Young Talent", group, age=15)

    client = _client(league["owner"])
    squad = client.post(f"/api/v1/scouting/leagues/{league['competition'].id}/squad/generate").data[
        "squad"
    ]
    picked = {pick["user_id"] for group in squad["groups"] for pick in group["picks"]}
    assert str(hidden_user.id) not in picked
    assert str(minor_user.id) not in picked

    ranked = client.get(f"/api/v1/scouting/leagues/{league['competition'].id}/candidates").data
    listed = {row["user_id"] for row in ranked["results"]}
    assert str(minor_user.id) not in listed
    assert ranked["counts"]["private"] == 2


def test_injured_players_are_left_out_of_an_automatic_pick(league):
    players = _fill_league(league, per_group_extra=0)
    injured_name = next(iter(players))
    profile = players[injured_name][1]
    profile.availability = "injured"
    profile.save()

    squad = (
        _client(league["owner"])
        .post(f"/api/v1/scouting/leagues/{league['competition'].id}/squad/generate")
        .data["squad"]
    )
    picked = {pick["name"] for group in squad["groups"] for pick in group["picks"]}
    assert injured_name not in picked


def test_drafts_are_private_to_selectors_and_publishing_tells_players(league):
    players = _fill_league(league)
    competition = league["competition"]
    owner = _client(league["owner"])
    owner.post(f"/api/v1/scouting/leagues/{competition.id}/squad/generate")

    fan = User.objects.create_user(email="fan@league.test", password="pw-123456789")
    fan_view = _client(fan).get(f"/api/v1/scouting/leagues/{competition.id}/squad")
    assert fan_view.status_code == 200
    assert fan_view.data["squad"] is None
    assert (
        _client(fan).post(f"/api/v1/scouting/leagues/{competition.id}/squad/generate").status_code
        == 403
    )
    assert (
        _client(fan).get(f"/api/v1/scouting/leagues/{competition.id}/candidates").status_code == 403
    )

    published = owner.post(f"/api/v1/scouting/leagues/{competition.id}/squad/publish")
    assert published.status_code == 200
    seen = _client(fan).get(f"/api/v1/scouting/leagues/{competition.id}/squad").data["squad"]
    assert seen["status"] == "published"
    assert seen["warnings"] == []
    assert seen["can_edit"] is False
    # A fan is not a scout, so "scouts only" profiles are not linked.
    assert all(pick["profile_id"] is None for group in seen["groups"] for pick in group["picks"])

    from apps.notifications.models import Notification

    picked_user = next(
        user for user, *_ in players.values() if LeagueSquad.objects.get().picks.filter(user=user)
    )
    assert Notification.objects.filter(user=picked_user, kind="squad.selected").count() == 1

    # Back to draft and out again: nobody is told twice.
    owner.delete(f"/api/v1/scouting/leagues/{competition.id}/squad/publish")
    owner.post(f"/api/v1/scouting/leagues/{competition.id}/squad/publish")
    assert Notification.objects.filter(user=picked_user, kind="squad.selected").count() == 1


def test_dropped_players_stay_out_and_locked_picks_stay_in(league):
    _fill_league(league)
    competition = league["competition"]
    client = _client(league["owner"])
    squad = client.post(f"/api/v1/scouting/leagues/{competition.id}/squad/generate").data["squad"]
    first_group = squad["groups"][0]
    dropped, kept = first_group["picks"][0], first_group["picks"][1]

    client.delete(f"/api/v1/scouting/leagues/{competition.id}/squad/picks/{dropped['id']}")
    client.patch(
        f"/api/v1/scouting/leagues/{competition.id}/squad/picks/{kept['id']}",
        {"locked": True},
        format="json",
    )
    again = client.post(f"/api/v1/scouting/leagues/{competition.id}/squad/generate").data["squad"]
    picked = {pick["user_id"]: pick for group in again["groups"] for pick in group["picks"]}
    assert dropped["user_id"] not in picked
    assert picked[kept["user_id"]]["locked"] is True
    assert dropped["user_id"] in again["excluded"]

    restored = client.delete(
        f"/api/v1/scouting/leagues/{competition.id}/squad/excluded/{dropped['user_id']}"
    )
    assert dropped["user_id"] not in restored.data["squad"]["excluded"]


def test_hand_picking_respects_size_and_eligibility(league):
    players = _fill_league(league)
    competition = league["competition"]
    client = _client(league["owner"])
    client.post(f"/api/v1/scouting/leagues/{competition.id}/squad/generate")
    squad = LeagueSquad.objects.get()

    outsider = User.objects.create_user(email="nobody@league.test", password="pw-123456789")
    refused = client.post(
        f"/api/v1/scouting/leagues/{competition.id}/squad/picks",
        {"user": str(outsider.id)},
        format="json",
    )
    assert refused.status_code == 400

    benched = next(
        user for user, *_ in players.values() if not squad.picks.filter(user=user).exists()
    )
    full = client.post(
        f"/api/v1/scouting/leagues/{competition.id}/squad/picks",
        {"user": str(benched.id)},
        format="json",
    )
    assert full.status_code == 400  # the squad is already at its size

    client.patch(f"/api/v1/scouting/leagues/{competition.id}/squad", {"size": 24}, format="json")
    added = client.post(
        f"/api/v1/scouting/leagues/{competition.id}/squad/picks",
        {"user": str(benched.id)},
        format="json",
    )
    assert added.status_code == 201
    pick = squad.picks.get(user=benched)
    assert pick.locked is True


def test_leagues_list_shows_squad_state(league):
    _fill_league(league, per_group_extra=0)
    client = _client(league["owner"])
    client.post(f"/api/v1/scouting/leagues/{league['competition'].id}/squad/generate")
    rows = client.get("/api/v1/scouting/leagues").data
    row = next(item for item in rows if item["id"] == str(league["competition"].id))
    assert row["can_select"] is True
    assert row["squad_status"] == "draft"
    assert row["teams"] == 2


def test_scouting_report_uses_stored_data_and_respects_privacy(league):
    group = TEMPLATE["groups"][0]
    user, profile, member = _player(league, 0, "Report Subject", group)
    _play(league, winner=0, ratings={member: "7.5"}, goals={member: 1})

    scout = User.objects.create_user(email="scout@league.test", password="pw-123456789")
    organisation = Organisation.objects.create(name="Lions Academy")
    grant_role(scout, "scout_admin", organisation=organisation)

    response = _client(scout).get(f"/api/v1/scouting/profiles/{profile.id}/report?export=1")
    assert response.status_code == 200
    data = response.data
    assert data["access"] == "scout"
    assert user.email not in str(data)
    league_row = data["leagues"][0]
    assert league_row["competition"] == "Coastal League"
    assert league_row["avg_rating"] == "7.5"
    assert league_row["ratings"][0]["rating"] == "7.5"
    assert league_row["stats"][0]["count"] == "1"
    assert league_row["record"] == {"won": 1, "drawn": 0, "lost": 0}
    coverage = {item["key"]: item for item in data["coverage"]}
    assert coverage["ratings"]["available"] is True
    assert coverage["scout_ratings"]["available"] is False
    assert ReportExport.objects.filter(viewer=scout, profile=profile).exists()

    stranger = User.objects.create_user(email="stranger@league.test", password="pw-123456789")
    assert (
        _client(stranger).get(f"/api/v1/scouting/profiles/{profile.id}/report").status_code == 404
    )

    owner_view = _client(user).get(f"/api/v1/scouting/profiles/{profile.id}/report")
    assert owner_view.data["access"] == "owner"
    assert owner_view.data["shaped_as"] == "scout"


def test_report_leaves_out_leagues_not_open_to_scouts(league):
    group = TEMPLATE["groups"][0]
    _, profile, _member = _player(league, 0, "Closed League", group)
    league["competition"].open_to_scouts = False
    league["competition"].save()

    scout = User.objects.create_user(email="scout2@league.test", password="pw-123456789")
    grant_role(scout, "scout_admin", organisation=Organisation.objects.create(name="Other"))
    data = _client(scout).get(f"/api/v1/scouting/profiles/{profile.id}/report").data
    assert data["leagues"] == []


def test_an_admin_can_amend_the_published_squad(league):
    _fill_league(league)
    competition = league["competition"]
    admin = User.objects.create_user(email="admin@league.test", password="pw-123456789")
    Membership.objects.create(competition=competition, user=admin, role=Role.ADMIN)
    owner = _client(league["owner"])
    owner.post(f"/api/v1/scouting/leagues/{competition.id}/squad/generate")
    owner.post(f"/api/v1/scouting/leagues/{competition.id}/squad/publish")

    client = _client(admin)
    squad = client.get(f"/api/v1/scouting/leagues/{competition.id}/squad").data["squad"]
    assert squad["can_edit"] is True
    pick = next(row for group in squad["groups"] for row in group["picks"])
    dropped = client.delete(f"/api/v1/scouting/leagues/{competition.id}/squad/picks/{pick['id']}")
    assert dropped.status_code == 200, dropped.data
    left = {row["id"] for group in dropped.data["squad"]["groups"] for row in group["picks"]}
    assert pick["id"] not in left

    competition.open_to_scouts = False
    competition.save(update_fields=["open_to_scouts"])
    assert client.get(f"/api/v1/scouting/leagues/{competition.id}/squad").status_code == 200
    assert client.get(f"/api/v1/scouting/leagues/{competition.id}/candidates").status_code == 200
