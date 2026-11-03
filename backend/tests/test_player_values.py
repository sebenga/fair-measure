"""Fantasy values in rands that start at R0, and player availability."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.competitions.models import Competition, Participant, RosterMember
from apps.fantasy.models import FantasyPick
from apps.fantasy.scoring import value_after
from apps.fixtures.models import Fixture, FixtureSide

from .test_fantasy import _picks, _roster

pytestmark = pytest.mark.django_db


def _row(points: str, minutes: int = 90, rating: str | None = None) -> dict:
    return {
        "breakdown": {"points": Decimal(points), "minutes": minutes},
        "rating": Decimal(rating) if rating is not None else None,
    }


def test_value_grows_with_points_and_ratings_and_never_drops_below_zero():
    assert value_after([]) == (Decimal("0"), Decimal("0"))
    # 9 points and an 8.0 rating: R0.9m + R0.2m.
    assert value_after([_row("9", rating="8.0")]) == (Decimal("1.1"), Decimal("1.1"))
    # A poor game after that takes value off again.
    value, change = value_after([_row("9", rating="8.0"), _row("-2", rating="4.0")])
    assert (value, change) == (Decimal("0.7"), Decimal("-0.4"))
    # A bad first game cannot push value below R0, and a missed game changes nothing.
    rows = [_row("-3", rating="3.0"), _row("0", minutes=0)]
    assert value_after(rows) == (Decimal("0"), Decimal("0"))


def test_every_player_starts_the_season_at_zero_rand(api, competition):
    _roster(competition)
    market = api.get(f"/api/v1/competitions/{competition.id}/fantasy/players")
    assert market.status_code == 200
    assert {player["price"] for player in market.data["players"]} == {"0.0"}
    board = api.get(f"/api/v1/competitions/{competition.id}/fantasy")
    assert board.data["rules"]["currency"] == "ZAR"
    assert board.data["rules"]["budget"] == "100.0"


def test_players_keep_the_value_they_were_bought_at(api, competition, user):
    members = _roster(competition)
    url = f"/api/v1/competitions/{competition.id}/fantasy"
    assert api.put(url, {"picks": _picks(members)}, format="json").status_code == 200
    FantasyPick.objects.filter(team__user=user).update(price=Decimal("2.5"))

    again = api.put(url, {"picks": _picks(members)}, format="json")
    assert again.status_code == 200, again.data
    assert set(FantasyPick.objects.filter(team__user=user).values_list("price", flat=True)) == {
        Decimal("2.5")
    }
    assert again.data["team"]["budget_used"] == "37.5"
    assert again.data["team"]["squad_value"] == "0.0"


def test_organisers_mark_players_injured_or_suspended(api, competition):
    club = Participant.objects.create(competition=competition, name="Lions", kind="team")
    player = RosterMember.objects.create(participant=club, name="Sipho Dube", number=9)
    url = f"/api/v1/competitions/{competition.id}/participants/{club.id}/roster/{player.id}"

    injured = api.patch(
        url,
        {
            "availability": "injured",
            "availability_note": "Hamstring",
            "available_from": "2026-12-01",
        },
        format="json",
    )
    assert injured.status_code == 200, injured.data
    assert injured.data["availability"] == "injured"
    assert injured.data["availability_note"] == "Hamstring"

    fit = api.patch(url, {"availability": "available"}, format="json")
    assert fit.status_code == 200
    assert fit.data["availability_note"] == ""
    assert fit.data["available_from"] is None

    assert api.patch(url, {"availability": "on holiday"}, format="json").status_code == 400


def test_injured_and_suspended_players_cannot_be_named_on_a_team_sheet(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Availability league", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    team = Participant.objects.create(competition=competition, name="Home XI", kind="team")
    squad = [
        RosterMember.objects.create(participant=team, name=f"Player {index}", number=index)
        for index in range(1, 15)
    ]
    away = Participant.objects.create(competition=competition, name="Away XI", kind="team")
    fixture = Fixture.objects.create(competition=competition, label="Round 1", duration_minutes=90)
    side = FixtureSide.objects.create(fixture=fixture, participant=team, position=0)
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
    url = f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/team-sheets/{side.id}"
    sheet = {
        "formation": "4-4-2",
        "captain": str(squad[0].id),
        "starters": [
            {"player": str(member.id), "slot": index, "number": member.number}
            for index, member in enumerate(squad[:11])
        ],
        "bench": [{"player": str(member.id), "number": member.number} for member in squad[11:]],
    }

    squad[12].availability = RosterMember.Availability.SUSPENDED
    squad[12].save()
    refused = api.put(url, sheet, format="json")
    assert refused.status_code == 400
    assert "suspended" in str(refused.data)

    day = api.get(f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/team-sheets")
    listed = {row["player_id"]: row["availability"] for row in day.data["sides"][0]["squad"]}
    assert listed[str(squad[12].id)] == "suspended"

    sheet["bench"] = [row for row in sheet["bench"] if row["player"] != str(squad[12].id)]
    assert api.put(url, sheet, format="json").status_code == 200
