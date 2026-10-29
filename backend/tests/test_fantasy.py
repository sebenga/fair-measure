"""Fantasy league: pick a squad from the competition roster and score it like FPL."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.competitions.models import Participant, RosterMember
from apps.fantasy.models import FantasyTeam
from apps.fantasy.scoring import classify_slot, player_match_points
from apps.fantasy.models import FantasySlot
from apps.fixtures.models import (
    Fixture,
    FixtureLineup,
    FixtureSide,
    LineupEntry,
    PlayerAppearance,
    ScoreEvent,
)

pytestmark = pytest.mark.django_db

# Spread shirts across clubs so a legal 15 can be built without four from one side.
SQUAD_SHIRTS = (
    ("Club 1", "GK"),
    ("Club 2", "GK"),
    ("Club 1", "CB"),
    ("Club 2", "CB"),
    ("Club 3", "CB"),
    ("Club 4", "CB"),
    ("Club 5", "CB"),
    ("Club 1", "CM"),
    ("Club 2", "CM"),
    ("Club 3", "CM"),
    ("Club 4", "CM"),
    ("Club 5", "CM"),
    ("Club 3", "ST"),
    ("Club 4", "ST"),
    ("Club 5", "ST"),
    ("Club 6", "ST"),
)


def _roster(competition) -> list[RosterMember]:
    clubs: dict[str, Participant] = {}
    members: list[RosterMember] = []
    for index, (club_name, position) in enumerate(SQUAD_SHIRTS, start=1):
        club = clubs.get(club_name)
        if club is None:
            club = Participant.objects.create(
                competition=competition, name=club_name, kind=Participant.Kind.TEAM
            )
            clubs[club_name] = club
        members.append(
            RosterMember.objects.create(
                participant=club,
                name=f"{club_name} {position} {index}",
                number=index,
                position=position,
            )
        )
    return members


def _picks(members: list[RosterMember]) -> list[dict]:
    slots = ["GKP"] * 2 + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    # 4-4-2: first GK, first 4 DEF, first 4 MID, first 2 FWD start.
    starters = set()
    by_slot: dict[str, list[int]] = {"GKP": [], "DEF": [], "MID": [], "FWD": []}
    for index, slot in enumerate(slots):
        by_slot[slot].append(index)
    starters.update(by_slot["GKP"][:1])
    starters.update(by_slot["DEF"][:4])
    starters.update(by_slot["MID"][:4])
    starters.update(by_slot["FWD"][:2])
    captain = by_slot["FWD"][0]
    vice = by_slot["MID"][0]
    return [
        {
            "player": str(members[index].id),
            "slot": slot,
            "is_starter": index in starters,
            "is_captain": index == captain,
            "is_vice": index == vice,
            "bench_order": 0 if index in starters else 1,
        }
        for index, slot in enumerate(slots)
    ]


def test_position_words_map_onto_fpl_slots():
    assert classify_slot("Goalkeeper") == FantasySlot.GKP
    assert classify_slot("Centre-back") == FantasySlot.DEF
    assert classify_slot("Attacking midfield") == FantasySlot.MID
    assert classify_slot("Striker") == FantasySlot.FWD
    assert classify_slot("") == FantasySlot.MID


def test_a_forward_goal_and_a_clean_sheet_score_like_fpl():
    events = []

    class _Cat:
        def __init__(self, code):
            self.code = code

    class _Event:
        def __init__(self, code, quantity=1):
            self.scoring_category = _Cat(code)
            self.quantity = Decimal(quantity)

    events = [_Event("goal"), _Event("assist")]
    assert player_match_points(
        slot=FantasySlot.FWD, minutes=90, events=events, conceded=Decimal("1")
    ) == Decimal("9")
    assert player_match_points(
        slot=FantasySlot.DEF, minutes=90, events=[], conceded=Decimal("0")
    ) == Decimal("6")


def test_save_a_complete_squad_and_read_it_back(api, competition):
    members = _roster(competition)
    created = api.put(
        f"/api/v1/competitions/{competition.id}/fantasy",
        {"name": "Sunday XI", "picks": _picks(members)},
        format="json",
    )
    assert created.status_code == 200, created.data
    team = created.data["team"]
    assert team["name"] == "Sunday XI"
    assert team["complete"] is True
    assert team["formation"] == "4-4-2"
    assert len(team["picks"]) == 15
    assert Decimal(team["budget_used"]) <= Decimal("100.0")

    board = api.get(f"/api/v1/competitions/{competition.id}/fantasy")
    assert board.status_code == 200
    assert board.data["team"]["name"] == "Sunday XI"
    assert board.data["rules"]["squad_size"] == 15

    players = api.get(f"/api/v1/competitions/{competition.id}/fantasy/players")
    assert players.status_code == 200
    assert players.data["count"] == 16
    assert {row["slot"] for row in players.data["players"]} <= {"GKP", "DEF", "MID", "FWD"}


def test_four_from_one_club_is_rejected(api, competition):
    members = _roster(competition)
    extra = RosterMember.objects.create(
        participant=members[0].participant,
        name="Fourth from Club 1",
        number=99,
        position="CM",
    )
    same_club = [
        member
        for member in [*members, extra]
        if member.participant_id == members[0].participant_id
    ]
    response = api.put(
        f"/api/v1/competitions/{competition.id}/fantasy",
        {
            "name": "Illegal",
            "picks": [
                {
                    "player": str(player.id),
                    "slot": classify_slot(player.position),
                    "is_starter": False,
                    "is_captain": False,
                    "is_vice": False,
                    "bench_order": 1,
                }
                for player in same_club
            ],
        },
        format="json",
    )
    assert response.status_code == 400
    assert "at most 3" in str(response.data)


def test_captain_doubles_points_from_recorded_goals(api, competition, rugby_scoring):
    members = _roster(competition)
    scorer = members[12]  # first forward — the captain in _picks
    home = scorer.participant
    away = members[0].participant
    fixture = Fixture.objects.create(
        competition=competition, status=Fixture.Status.COMPLETED, duration_minutes=90
    )
    home_side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0, score=1)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1, score=0)
    ScoreEvent.objects.create(
        fixture=fixture,
        side=home_side,
        scoring_category=rugby_scoring["try"],
        player=scorer,
        quantity=1,
    )
    PlayerAppearance.objects.create(fixture=fixture, player=scorer, minutes=90)

    saved = api.put(
        f"/api/v1/competitions/{competition.id}/fantasy",
        {"name": "Captain Club", "picks": _picks(members)},
        format="json",
    )
    assert saved.status_code == 200, saved.data
    # A 90-minute forward try (goal code) is 2 (appearance) + 4 (FWD goal) = 6, doubled to 12.
    assert Decimal(saved.data["team"]["points"]) == Decimal("12")
    # The player's own performance points stay undoubled; captaincy is a squad rule.
    performance = api.get(
        f"/api/v1/competitions/{competition.id}/fantasy/players/{scorer.id}/performance"
    )
    assert performance.data["total_performance_points"] == "6"

    table = api.get(f"/api/v1/competitions/{competition.id}/fantasy/standings")
    assert table.status_code == 200
    assert table.data["rows"][0]["name"] == "Captain Club"
    assert table.data["rows"][0]["rank"] == 1


def test_auto_pick_returns_a_legal_complete_squad(api, competition):
    _roster(competition)
    suggestion = api.post(f"/api/v1/competitions/{competition.id}/fantasy/auto-pick", {}, format="json")
    assert suggestion.status_code == 200, suggestion.data
    assert len(suggestion.data["picks"]) == 15
    saved = api.put(
        f"/api/v1/competitions/{competition.id}/fantasy",
        {"name": "Auto XI", "picks": suggestion.data["picks"]},
        format="json",
    )
    assert saved.status_code == 200, saved.data
    assert saved.data["team"]["complete"] is True
    assert FantasyTeam.objects.filter(competition=competition).count() == 1


def test_incomplete_squad_can_be_saved_while_building(api, competition):
    members = _roster(competition)
    response = api.put(
        f"/api/v1/competitions/{competition.id}/fantasy",
        {
            "name": "Work in progress",
            "picks": [
                {
                    "player": str(members[0].id),
                    "slot": "GKP",
                    "is_starter": True,
                    "is_captain": False,
                    "is_vice": False,
                    "bench_order": 0,
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["team"]["complete"] is False
    assert len(response.data["team"]["picks"]) == 1


def test_a_player_who_played_two_lines_is_listed_in_both_slots(api, competition):
    club = Participant.objects.create(competition=competition, name="Wanderers", kind=Participant.Kind.TEAM)
    member = RosterMember.objects.create(participant=club, name="Hybrid Wide", number=8, position="CB")
    opponent = Participant.objects.create(competition=competition, name="Visitors", kind=Participant.Kind.TEAM)
    for index, shirt in enumerate(("DEF", "MID")):
        fixture = Fixture.objects.create(
            competition=competition, status=Fixture.Status.COMPLETED, label=f"Round {index}"
        )
        side = FixtureSide.objects.create(fixture=fixture, participant=club, position=0)
        FixtureSide.objects.create(fixture=fixture, participant=opponent, position=1)
        lineup = FixtureLineup.objects.create(fixture=fixture, side=side)
        LineupEntry.objects.create(
            lineup=lineup,
            player=member,
            role=LineupEntry.Role.STARTER,
            slot=1,
            position=shirt,
            order=0,
        )

    market = api.get(f"/api/v1/competitions/{competition.id}/fantasy/players")
    row = next(item for item in market.data["players"] if item["id"] == str(member.id))
    assert set(row["slots"]) == {"DEF", "MID"}
    assert row["id"] == str(member.id)

    defenders = api.get(f"/api/v1/competitions/{competition.id}/fantasy/players?slot=DEF")
    mids = api.get(f"/api/v1/competitions/{competition.id}/fantasy/players?slot=MID")
    assert str(member.id) in {item["id"] for item in defenders.data["players"]}
    assert str(member.id) in {item["id"] for item in mids.data["players"]}
    def_row = next(item for item in defenders.data["players"] if item["id"] == str(member.id))
    mid_row = next(item for item in mids.data["players"] if item["id"] == str(member.id))
    assert def_row["id"] == mid_row["id"]


def test_fantasy_is_only_for_team_sport_leagues(api, user):
    from apps.competitions.models import Competition, Membership
    from apps.core.permissions import Role

    singles = Competition.objects.create(
        name="City Open",
        owner=user,
        sport="tennis",
        settings_json={"participant_type": "individual", "scoring_basis": "results"},
    )
    Membership.objects.create(competition=singles, user=user, role=Role.OWNER)
    blocked = api.get(f"/api/v1/competitions/{singles.id}/fantasy")
    assert blocked.status_code == 400

    table = Competition.objects.create(
        name="Sales ladder",
        owner=user,
        sport="custom",
        settings_json={"participant_type": "team", "scoring_basis": "criteria"},
    )
    Membership.objects.create(competition=table, user=user, role=Role.OWNER)
    assert api.get(f"/api/v1/competitions/{table.id}/fantasy").status_code == 400
