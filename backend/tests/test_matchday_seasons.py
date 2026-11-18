"""Soccer league and rugby union pool + knockout seasons through the API."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.competitions.models import Competition, Participant, RosterMember
from apps.competitions.season import season_is_finished
from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide, ScoreEvent
from apps.standings.services import refresh_standings

User = get_user_model()

pytestmark = pytest.mark.django_db


def _codes(api, competition_id: str) -> dict[str, str]:
    detail = api.get(f"/api/v1/competitions/{competition_id}").data
    return {item["code"]: item["id"] for item in detail["scoring_categories"]}


def _add_teams(api, competition_id: str, names: list[str]) -> list[Participant]:
    teams = []
    for name in names:
        created = api.post(
            f"/api/v1/competitions/{competition_id}/participants",
            {"name": name, "kind": "team"},
            format="json",
        )
        assert created.status_code == 201, created.data
        teams.append(Participant.objects.get(pk=created.data["id"]))
    return teams


def _roster(team: Participant, count: int, start: int = 1) -> list[RosterMember]:
    return [
        RosterMember.objects.create(participant=team, name=f"{team.name} {n}", number=n)
        for n in range(start, start + count)
    ]


def _appoint_ref(api, competition, fixture, user) -> None:
    FixtureReferee.objects.get_or_create(fixture=fixture, user=user)
    # Kickoff needs a duration; presets set it on create.
    if not fixture.duration_minutes:
        fixture.duration_minutes = 90
        fixture.save(update_fields=["duration_minutes", "updated_at"])


def _submit_sheets(
    api, competition, fixture, *, starters: int, named: int | None = None, formation: str = "4-4-2"
) -> dict:
    """Name a full team sheet for each side so kickoff is allowed."""

    needed = named or starters
    captains = {}
    for side in fixture.sides.select_related("participant"):
        existing = list(side.participant.roster.filter(is_active=True).order_by("number"))
        while len(existing) < needed:
            n = len(existing) + 1
            existing.append(
                RosterMember.objects.create(
                    participant=side.participant,
                    name=f"{side.participant.name} {n}",
                    number=n,
                )
            )
        for index, member in enumerate(existing[:needed]):
            want = index + 1
            if member.number != want:
                member.number = want
                member.save(update_fields=["number", "updated_at"])
        by_number = {member.number: member for member in existing[:needed]}

        if formation == "numbers":
            from apps.fixtures.matchday import number_layout_slots, team_sheet_config

            slots = number_layout_slots(team_sheet_config(competition) or {})
            starters_payload = [
                {
                    "player": str(by_number[slot["number"]].id),
                    "slot": slot["index"],
                    "number": slot["number"],
                }
                for slot in slots
            ]
            bench_numbers = list(range(starters + 1, needed + 1))
            bench_payload = [
                {"player": str(by_number[number].id), "number": number} for number in bench_numbers
            ]
            captain = by_number[1]
        else:
            start_members = [by_number[n] for n in range(1, starters + 1)]
            bench_members = [by_number[n] for n in range(starters + 1, needed + 1)]
            starters_payload = [
                {"player": str(member.id), "slot": index, "number": member.number}
                for index, member in enumerate(start_members)
            ]
            bench_payload = [
                {"player": str(member.id), "number": member.number} for member in bench_members
            ]
            captain = start_members[0]

        body = {
            "formation": formation,
            "captain": str(captain.id),
            "starters": starters_payload,
            "bench": bench_payload,
        }
        response = api.put(
            f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/team-sheets/{side.id}",
            body,
            format="json",
        )
        assert response.status_code == 200, response.data
        captains[side.participant_id] = captain
    return captains


def _event(api, fixture, side, category, player, *, minute=10, quantity="1", source="referee"):
    return api.post(
        f"/api/v1/fixtures/{fixture.id}/events",
        {
            "side": str(side.id),
            "scoring_category": category,
            "quantity": quantity,
            "player": str(player.id),
            "minute": minute,
            "second": 0,
            "source": source,
        },
        format="json",
    )


def _complete(api, competition, fixture):
    response = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/{fixture.id}/set-status",
        {"status": "completed"},
        format="json",
    )
    assert response.status_code == 200, response.data
    fixture.refresh_from_db()
    assert fixture.status == Fixture.Status.COMPLETED
    assert fixture.confirmed_at is not None
    return response


def test_soccer_label_and_search_aliases(api):
    presets = api.get("/api/v1/competitions/presets").data
    soccer = next(item for item in presets if item["key"] == "soccer")
    assert soccer["label"] == "Football (Soccer)"
    assert soccer["family_label"] == "Football (Soccer)"
    assert "soccer" in [alias.lower() for alias in soccer.get("search_aliases", [])]
    assert "football" in [alias.lower() for alias in soccer.get("search_aliases", [])]


def test_results_sport_cannot_invent_a_fixture_via_score_assist(api):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Guard league", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition_id = created.data["id"]
    teams = _add_teams(api, competition_id, ["A", "B"])
    blocked = api.post(
        f"/api/v1/competitions/{competition_id}/score-assist",
        {
            "kind": "result",
            "home": str(teams[0].id),
            "away": str(teams[1].id),
            "outcome": "home",
            "note": "Invented",
        },
        format="json",
    )
    assert blocked.status_code == 400
    assert Competition.objects.get(pk=competition_id).fixtures.count() == 0


def test_synthetic_result_alone_does_not_finish_a_season(api, user):
    created = api.post(
        "/api/v1/competitions",
        {"name": "One result trap", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    home = Participant.objects.create(competition=competition, name="Home", kind="team")
    away = Participant.objects.create(competition=competition, name="Away", kind="team")
    fixture = Fixture.objects.create(
        competition=competition,
        status=Fixture.Status.CONFIRMED,
        completed_at=timezone.now(),
        confirmed_at=timezone.now(),
        label="Synthetic",
    )
    FixtureSide.objects.create(fixture=fixture, participant=home, position=0, is_home=True, outcome="win")
    FixtureSide.objects.create(fixture=fixture, participant=away, position=1, outcome="loss")
    assert season_is_finished(competition) is False


def test_soccer_double_round_robin_standings_from_events(api, user):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Soccer four", "preset": "soccer", "format": "league"},
        format="json",
    )
    competition = Competition.objects.get(pk=created.data["id"])
    activated = api.patch(
        f"/api/v1/competitions/{competition.id}", {"status": "active"}, format="json"
    )
    assert activated.status_code == 200, activated.data
    teams = _add_teams(api, str(competition.id), ["Alpha", "Bravo", "Charlie", "Delta"])
    for team in teams:
        _roster(team, 14)
    codes = _codes(api, str(competition.id))

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
    fixtures = list(competition.fixtures.order_by("round_number", "created_at"))
    assert len(fixtures) == 12  # 4 teams, double RR

    # Deterministic results: Alpha beats everyone home and away (6 wins).
    # Bravo beats Charlie and Delta; Charlie beats Delta.
    winners = {
        frozenset({"Alpha", "Bravo"}): "Alpha",
        frozenset({"Alpha", "Charlie"}): "Alpha",
        frozenset({"Alpha", "Delta"}): "Alpha",
        frozenset({"Bravo", "Charlie"}): "Bravo",
        frozenset({"Bravo", "Delta"}): "Bravo",
        frozenset({"Charlie", "Delta"}): "Charlie",
    }

    for fixture in fixtures:
        _appoint_ref(api, competition, fixture, user)
        scorers = _submit_sheets(api, competition, fixture, starters=11, named=14)
        sides = list(fixture.sides.select_related("participant").order_by("position"))
        home, away = sides[0], sides[1]
        pair = frozenset({home.participant.name, away.participant.name})
        winner_name = winners[pair]
        winner = home if home.participant.name == winner_name else away
        loser = away if winner is home else home
        goal = _event(
            api,
            fixture,
            winner,
            codes["goal"],
            scorers[winner.participant_id],
            minute=12,
        )
        assert goal.status_code == 201, goal.data
        _complete(api, competition, fixture)
        # Loser has zero goals — score derived from events only.
        assert ScoreEvent.objects.filter(fixture=fixture, side=loser).count() == 0

    table = api.get(f"/api/v1/competitions/{competition.id}/standings?refresh=true").data["rows"]
    by_name = {row["participant"]["name"]: row for row in table}
    assert by_name["Alpha"]["played"] == 6
    assert by_name["Alpha"]["wins"] == 6
    assert by_name["Alpha"]["points"] == "18.00"
    assert by_name["Bravo"]["points"] == "12.00"
    assert by_name["Charlie"]["points"] == "6.00"
    assert by_name["Delta"]["points"] == "0.00"
    assert by_name["Alpha"]["score_for"] == "6.00"
    assert by_name["Alpha"]["score_against"] == "0.00"

    competition.refresh_from_db()
    assert competition.status == Competition.Status.COMPLETED
    assert season_is_finished(competition) is True


def test_rugby_union_bonus_points_and_sin_bin(api, user):
    created = api.post(
        "/api/v1/competitions",
        {"name": "Rugby pool", "preset": "rugby_union", "format": "league"},
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    activated = api.patch(
        f"/api/v1/competitions/{competition.id}", {"status": "active"}, format="json"
    )
    assert activated.status_code == 200, activated.data
    teams = _add_teams(api, str(competition.id), ["Sharks", "Bulls", "Lions", "Stormers"])
    codes = _codes(api, str(competition.id))
    assert "try" in codes and "tackle" in codes and "hia" in codes

    generated = api.post(
        f"/api/v1/competitions/{competition.id}/fixtures/generate",
        {
            "method": "round_robin",
            "starts_on": "2026-08-01",
            "weekdays": [5],
            "kickoff": "16:00:00",
        },
        format="json",
    )
    assert generated.status_code == 201, generated.data

    for team in teams:
        _roster(team, 17)

    # Play one match with 4 tries (bonus) and a narrow losing bonus for the other side.
    fixture = competition.fixtures.order_by("created_at").first()
    _appoint_ref(api, competition, fixture, user)
    _submit_sheets(api, competition, fixture, starters=15, named=17, formation="numbers")
    home = fixture.sides.filter(is_home=True).first() or fixture.sides.order_by("position").first()
    away = fixture.sides.exclude(pk=home.pk).get()
    home_players = list(home.participant.roster.order_by("number"))
    away_players = list(away.participant.roster.order_by("number"))

    for index in range(4):
        scored = _event(
            api,
            fixture,
            home,
            codes["try"],
            home_players[index],
            minute=10 + index * 5,
        )
        assert scored.status_code == 201, scored.data
        if index < 3:
            conversion = _event(
                api,
                fixture,
                home,
                codes["conversion"],
                home_players[14],
                minute=11 + index * 5,
            )
            assert conversion.status_code == 201, conversion.data

    # Away score enough to lose by 7 or fewer (home ~23–26, away needs within 7).
    # 3 tries + 2 conversions = 19 → margin depends on home total (5+2)*3 + 5 = 26 → margin 7.
    for index in range(3):
        scored = _event(
            api,
            fixture,
            away,
            codes["try"],
            away_players[index],
            minute=50 + index * 5,
        )
        assert scored.status_code == 201, scored.data
        if index < 2:
            conversion = _event(
                api,
                fixture,
                away,
                codes["conversion"],
                away_players[14],
                minute=51 + index * 5,
            )
            assert conversion.status_code == 201, conversion.data

    yellow = _event(
        api,
        fixture,
        away,
        codes["yellow-card"],
        away_players[5],
        minute=60,
    )
    assert yellow.status_code == 201, yellow.data

    from apps.fixtures.cards import sin_bins

    bins = sin_bins(fixture, as_of_minute=65)
    assert away_players[5].id in bins
    assert bins[away_players[5].id]["minutes"] == 10

    _complete(api, competition, fixture)
    refresh_standings(competition)
    table = api.get(f"/api/v1/competitions/{competition.id}/standings?refresh=true").data["rows"]
    home_row = next(row for row in table if row["participant"]["id"] == str(home.participant_id))
    away_row = next(row for row in table if row["participant"]["id"] == str(away.participant_id))
    # Win 4 + try bonus 1 = 5; loss 0 + losing bonus 1 = 1
    assert home_row["points"] == "5.00"
    assert away_row["points"] == "1.00"
    assert float(home_row["bonus_points"]) >= 1.0
    assert float(away_row["bonus_points"]) >= 1.0

    # Finish the rest of the pool so a knockout can be scheduled.
    for other in competition.fixtures.exclude(pk=fixture.pk):
        _appoint_ref(api, competition, other, user)
        scorers = _submit_sheets(api, competition, other, starters=15, named=17, formation="numbers")
        side = other.sides.order_by("position").first()
        scored = _event(api, other, side, codes["try"], scorers[side.participant_id], minute=20)
        assert scored.status_code == 201, scored.data
        _complete(api, competition, other)

    competition.refresh_from_db()
    assert season_is_finished(competition) is True

    playoff = api.post(
        f"/api/v1/competitions/{competition.id}/next-season",
        {
            "kind": "knockout",
            "starts_on": "2026-10-01",
            "weekdays": [5],
            "kickoff": "16:00:00",
            "advance": 4,
        },
        format="json",
    )
    assert playoff.status_code == 201, playoff.data
    assert playoff.data["stage"]["kind"] == "knockout"
