"""Red-card bans and yellow-card accumulations for team sheets."""

from __future__ import annotations

import pytest

from apps.competitions.models import Competition, Participant, RosterMember
from apps.fixtures.discipline import AUTO_PREFIX, effective_availability, sync_roster_discipline
from apps.fixtures.models import Fixture, FixtureSide


@pytest.fixture
def league(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Discipline league", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    home = Participant.objects.create(competition=competition, name="Home", kind="team")
    away = Participant.objects.create(competition=competition, name="Away", kind="team")
    player = RosterMember.objects.create(participant=home, name="Booked", number=4)
    squad = [player] + [
        RosterMember.objects.create(participant=home, name=f"Mate {index}", number=index)
        for index in range(5, 16)
    ]
    away_squad = [
        RosterMember.objects.create(participant=away, name=f"Away {index}", number=index)
        for index in range(1, 15)
    ]
    first = Fixture.objects.create(
        competition=competition, label="Round 1", status=Fixture.Status.LIVE, duration_minutes=90
    )
    first_home = FixtureSide.objects.create(fixture=first, participant=home, position=0)
    FixtureSide.objects.create(fixture=first, participant=away, position=1)
    second = Fixture.objects.create(
        competition=competition, label="Round 2", status=Fixture.Status.SCHEDULED, duration_minutes=90
    )
    second_home = FixtureSide.objects.create(fixture=second, participant=home, position=0)
    FixtureSide.objects.create(fixture=second, participant=away, position=1)
    return {
        "competition": competition,
        "home": home,
        "away": away,
        "player": player,
        "squad": squad,
        "away_squad": away_squad,
        "first": first,
        "first_home": first_home,
        "second": second,
        "second_home": second_home,
    }


def _codes(api, competition):
    detail = api.get(f"/api/v1/competitions/{competition.id}").data
    return {item["code"]: item["id"] for item in detail["scoring_categories"]}


def _card(api, fixture, side, player, category, minute):
    return api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": category,
            "quantity": "1",
            "player": str(player.id),
            "minute": minute,
        },
        format="json",
    )


def _complete(fixture):
    fixture.status = Fixture.Status.COMPLETED
    fixture.save(update_fields=["status", "updated_at"])
    sync_roster_discipline(fixture)
    return fixture


def _sheet_body(squad, exclude=None):
    out = {str(member.id) for member in (exclude or [])}
    starters = [member for member in squad if str(member.id) not in out][:11]
    bench = [member for member in squad if str(member.id) not in out][11:14]
    return {
        "formation": "4-4-2",
        "captain": str(starters[0].id),
        "starters": [
            {"player": str(member.id), "slot": index, "number": member.number}
            for index, member in enumerate(starters)
        ],
        "bench": [{"player": str(member.id), "number": member.number} for member in bench],
    }


def test_red_card_suspends_player_for_next_team_sheet(api, league):
    competition = league["competition"]
    player = league["player"]
    first = league["first"]
    first_home = league["first_home"]
    second = league["second"]
    second_home = league["second_home"]
    codes = _codes(api, competition)

    assert _card(api, first, first_home, player, codes["red-card"], 40).status_code == 201
    _complete(first)

    player.refresh_from_db()
    assert player.availability == RosterMember.Availability.SUSPENDED
    assert player.availability_note.startswith(AUTO_PREFIX)
    assert "Red card" in player.availability_note

    day = api.get(f"/api/v1/competitions/{competition.id}/fixtures/{second.id}/team-sheets")
    assert day.status_code == 200
    listed = {row["player_id"]: row for row in day.data["sides"][0]["squad"]}
    assert listed[str(player.id)]["availability"] == "suspended"
    assert "Red card" in listed[str(player.id)]["availability_note"]

    url = f"/api/v1/competitions/{competition.id}/fixtures/{second.id}/team-sheets/{second_home.id}"
    refused = api.put(url, _sheet_body(league["squad"]), format="json")
    assert refused.status_code == 400
    assert "suspended" in str(refused.data).lower()

    allowed = api.put(url, _sheet_body(league["squad"], exclude=[player]), format="json")
    assert allowed.status_code == 200, allowed.data


def test_five_yellow_cards_suspend_for_next_match(api, league):
    competition = league["competition"]
    player = league["player"]
    home = league["home"]
    away = league["away"]
    codes = _codes(api, competition)
    # Keep the pre-built Round 2 for other tests; build a clean run after it.
    league["second"].status = Fixture.Status.CANCELLED
    league["second"].save(update_fields=["status", "updated_at"])

    for round_number in range(1, 6):
        if round_number == 1:
            fixture = league["first"]
            side = league["first_home"]
        else:
            fixture = Fixture.objects.create(
                competition=competition,
                label=f"Caution round {round_number}",
                status=Fixture.Status.LIVE,
                duration_minutes=90,
            )
            side = FixtureSide.objects.create(fixture=fixture, participant=home, position=0)
            FixtureSide.objects.create(fixture=fixture, participant=away, position=1)
        assert _card(api, fixture, side, player, codes["yellow-card"], 20).status_code == 201
        _complete(fixture)

    next_match = Fixture.objects.create(
        competition=competition,
        label="After five yellows",
        status=Fixture.Status.SCHEDULED,
        duration_minutes=90,
    )
    FixtureSide.objects.create(fixture=next_match, participant=home, position=0)
    FixtureSide.objects.create(fixture=next_match, participant=away, position=1)
    last = Fixture.objects.filter(competition=competition, status=Fixture.Status.COMPLETED).latest("created_at")
    sync_roster_discipline(last)

    player.refresh_from_db()
    assert player.availability == RosterMember.Availability.SUSPENDED
    assert "5 yellow cards" in player.availability_note

    status, note, _ = effective_availability(player, next_match)
    assert status == RosterMember.Availability.SUSPENDED
    assert "5 yellow cards" in note


def test_injured_player_is_marked_on_team_sheet_and_blocked(api, league):
    competition = league["competition"]
    player = league["player"]
    second = league["second"]
    second_home = league["second_home"]

    player.availability = RosterMember.Availability.INJURED
    player.availability_note = "Hamstring"
    player.save(update_fields=["availability", "availability_note", "updated_at"])

    day = api.get(f"/api/v1/competitions/{competition.id}/fixtures/{second.id}/team-sheets")
    listed = {row["player_id"]: row for row in day.data["sides"][0]["squad"]}
    assert listed[str(player.id)]["availability"] == "injured"
    assert listed[str(player.id)]["availability_note"] == "Hamstring"

    url = f"/api/v1/competitions/{competition.id}/fixtures/{second.id}/team-sheets/{second_home.id}"
    refused = api.put(url, _sheet_body(league["squad"]), format="json")
    assert refused.status_code == 400
    assert "injured" in str(refused.data).lower()


def test_serving_suspension_clears_automatic_ban(api, league):
    competition = league["competition"]
    player = league["player"]
    first = league["first"]
    first_home = league["first_home"]
    second = league["second"]
    codes = _codes(api, competition)

    assert _card(api, first, first_home, player, codes["red-card"], 12).status_code == 201
    _complete(first)
    player.refresh_from_db()
    assert player.availability == RosterMember.Availability.SUSPENDED

    _complete(second)

    player.refresh_from_db()
    assert player.availability == RosterMember.Availability.AVAILABLE
    assert player.availability_note == ""
