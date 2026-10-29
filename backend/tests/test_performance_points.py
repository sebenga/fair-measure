"""Soccer performance points: FPL-style match points, per-match lines, season sum."""

from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.competitions.models import Participant, RosterMember, ScoringCategory
from apps.fantasy.models import FantasySlot
from apps.fantasy.scoring import match_breakdown, player_match_points, season_totals
from apps.fixtures.models import Fixture, FixtureSide, PlayerAppearance, ScoreEvent

pytestmark = pytest.mark.django_db


class _Cat:
    def __init__(self, code: str) -> None:
        self.code = code


class _Event:
    def __init__(self, code: str, quantity: int = 1) -> None:
        self.scoring_category = _Cat(code)
        self.quantity = Decimal(quantity)


def points(slot, minutes, codes, conceded=0):
    return player_match_points(
        slot=slot,
        minutes=minutes,
        events=[_Event(code) for code in codes],
        conceded=Decimal(conceded),
    )


def test_midfielder_goal_assist_and_yellow():
    assert points(FantasySlot.MID, 90, ["goal", "assist", "yellow-card"], conceded=1) == Decimal(
        "9"
    )


def test_defender_clean_sheet():
    assert points(FantasySlot.DEF, 90, [], conceded=0) == Decimal("6")


def test_goalkeeper_seven_saves_and_clean_sheet():
    assert points(FantasySlot.GKP, 90, ["save"] * 7, conceded=0) == Decimal("8")


def test_forward_45_minutes_two_goals_gets_no_60_bonus_or_clean_sheet():
    assert points(FantasySlot.FWD, 45, ["goal", "goal"], conceded=0) == Decimal("9")


def test_red_card_and_own_goal_are_taken_off():
    assert points(FantasySlot.MID, 90, ["red-card", "own-goal"], conceded=2) == Decimal("-3")
    assert points(FantasySlot.MID, 90, ["red", "own_goal"], conceded=2) == Decimal("-3")


def test_every_engine_code_is_mapped():
    assert points(FantasySlot.MID, 90, ["try"], conceded=1) == Decimal("7")
    assert points(FantasySlot.MID, 90, ["yellow"], conceded=1) == Decimal("1")
    assert points(FantasySlot.GKP, 90, ["penalty-save", "pen-save"], conceded=1) == Decimal("12")


def test_stat_only_types_earn_nothing():
    stats = ["shot", "shot-on-target", "tackle", "interception"]
    assert points(FantasySlot.MID, 90, stats, conceded=1) == Decimal("2")


def test_no_minutes_scores_nothing_even_with_events():
    assert points(FantasySlot.FWD, 0, ["goal", "assist"], conceded=0) == Decimal("0")


def test_breakdown_lines_add_up_and_read_like_the_rules():
    breakdown = match_breakdown(
        slot=FantasySlot.MID,
        minutes=90,
        events=[_Event("goal", 2), _Event("assist"), _Event("yellow-card"), _Event("shot", 4)],
        conceded=Decimal("0"),
    )
    lines = {line["label"]: line for line in breakdown["lines"]}

    assert list(lines) == [
        "Appearance",
        "60+ minutes",
        "Goal (MID)",
        "Assist",
        "Clean sheet (MID)",
        "Yellow card",
    ]
    assert lines["Goal (MID)"]["each"] == Decimal("5")
    assert lines["Goal (MID)"]["points"] == Decimal("10")
    assert lines["Goal (MID)"]["detail"] == "× 2"  # noqa: RUF001
    assert breakdown["points"] == sum(line["points"] for line in lines.values()) == Decimal("15")
    assert breakdown["minutes"] == 90 and breakdown["slot"] == FantasySlot.MID


def test_captaincy_is_not_part_of_match_points():
    import inspect

    assert "captain" not in inspect.signature(player_match_points).parameters
    assert "captain" not in inspect.signature(match_breakdown).parameters


# --- Season totals and the API ------------------------------------------------


@pytest.fixture
def soccer(competition):
    categories = {
        code: ScoringCategory.objects.create(
            competition=competition,
            name=name,
            code=code,
            points=Decimal(value),
            affects_score=affects,
        )
        for code, name, value, affects in (
            ("goal", "Goal", "1", True),
            ("assist", "Assist", "0", False),
            ("yellow-card", "Yellow card", "0", False),
            ("save", "Save", "0", False),
            ("shot", "Shot", "0", False),
        )
    }
    home = Participant.objects.create(competition=competition, name="Harbour Hawks")
    away = Participant.objects.create(competition=competition, name="Seaview Sharks")
    mid = RosterMember.objects.create(participant=home, name="Mia Mid", number=8, position="CM")
    keeper = RosterMember.objects.create(
        participant=away, name="Gus Keeper", number=1, position="GK"
    )
    return {"categories": categories, "home": home, "away": away, "mid": mid, "keeper": keeper}


def _fixture(competition, soccer, home_score, away_score, status=Fixture.Status.COMPLETED):
    fixture = Fixture.objects.create(competition=competition, status=status, duration_minutes=90)
    home = FixtureSide.objects.create(
        fixture=fixture, participant=soccer["home"], position=0, score=home_score
    )
    away = FixtureSide.objects.create(
        fixture=fixture, participant=soccer["away"], position=1, score=away_score
    )
    return fixture, home, away


def _event(fixture, side, soccer, code, player, quantity=1):
    return ScoreEvent.objects.create(
        fixture=fixture,
        side=side,
        scoring_category=soccer["categories"][code],
        player=player,
        player_name=player.name,
        quantity=quantity,
    )


def test_season_total_is_the_sum_of_match_points(api, competition, soccer):
    mid = soccer["mid"]
    # Match 1: 90 minutes, goal + assist + yellow, conceded 1 -> 9.
    first, home, _ = _fixture(competition, soccer, 1, 1)
    PlayerAppearance.objects.create(fixture=first, player=mid, minutes=90)
    for code in ("goal", "assist", "yellow-card"):
        _event(first, home, soccer, code, mid)
    # Match 2: no appearance row but a tagged shot, so the full 90; clean sheet -> 1+1+1 = 3.
    second, home2, _ = _fixture(competition, soccer, 2, 0)
    _event(second, home2, soccer, "shot", mid, quantity=3)
    # Live and scheduled fixtures never count.
    live, home3, _ = _fixture(competition, soccer, 5, 0, status=Fixture.Status.LIVE)
    _event(live, home3, soccer, "goal", mid, quantity=5)

    totals = season_totals(competition)
    assert totals[mid.id]["points"] == Decimal("12")
    assert totals[mid.id]["minutes"] == 180

    response = api.get(
        f"/api/v1/competitions/{competition.id}/fantasy/players/{mid.id}/performance"
    )
    assert response.status_code == 200, response.data
    body = response.data
    assert body["total_performance_points"] == "12"
    assert body["matches_played"] == 2
    assert [match["points"] for match in body["matches"]] == ["9", "3"]
    assert sum(Decimal(match["points"]) for match in body["matches"]) == Decimal(
        body["total_performance_points"]
    )
    first_lines = {line["label"]: line["points"] for line in body["matches"][0]["lines"]}
    assert first_lines == {
        "Appearance": "1",
        "60+ minutes": "1",
        "Goal (MID)": "5",
        "Assist": "3",
        "Yellow card": "-1",
    }
    assert all("Shot" not in line["label"] for match in body["matches"] for line in match["lines"])
    assert body["matches"][1]["opponents"] == ["Seaview Sharks"]


def test_keeper_saves_and_clean_sheet_through_the_api(api, competition, soccer):
    keeper = soccer["keeper"]
    fixture, _, away = _fixture(competition, soccer, 0, 1)
    PlayerAppearance.objects.create(fixture=fixture, player=keeper, minutes=90)
    _event(fixture, away, soccer, "save", keeper, quantity=7)

    body = api.get(
        f"/api/v1/competitions/{competition.id}/fantasy/players/{keeper.id}/performance"
    ).data
    assert body["total_performance_points"] == "8"
    lines = {line["label"]: line for line in body["matches"][0]["lines"]}
    assert lines["3 saves"]["points"] == "2"
    assert lines["3 saves"]["detail"] == "7 saves"
    assert lines["Clean sheet (GK/DEF)"]["points"] == "4"


def test_zero_minutes_scores_zero(api, competition, soccer):
    mid = soccer["mid"]
    fixture, home, _ = _fixture(competition, soccer, 1, 0)
    PlayerAppearance.objects.create(fixture=fixture, player=mid, minutes=0)
    _event(fixture, home, soccer, "goal", mid)

    body = api.get(
        f"/api/v1/competitions/{competition.id}/fantasy/players/{mid.id}/performance"
    ).data
    assert body["total_performance_points"] == "0"
    assert body["matches"] == []


def test_untagged_goals_change_the_score_but_earn_no_player_points(competition, soccer):
    fixture, home, _ = _fixture(competition, soccer, 0, 0)
    ScoreEvent.objects.create(
        fixture=fixture, side=home, scoring_category=soccer["categories"]["goal"], quantity=1
    )
    fixture.recalculate_scores()
    home.refresh_from_db()

    assert home.score == Decimal("1")
    assert season_totals(competition)[soccer["mid"].id]["points"] == Decimal("0")


def test_performance_needs_a_signed_in_viewer_and_a_player_from_this_competition(
    api, competition, soccer, user
):
    url = f"/api/v1/competitions/{competition.id}/fantasy/players/{soccer['mid'].id}/performance"
    assert APIClient().get(url).status_code == 401

    from apps.competitions.models import Competition

    elsewhere = Competition.objects.create(name="Other League", owner=user)
    stranger = RosterMember.objects.create(
        participant=Participant.objects.create(competition=elsewhere, name="Elsewhere FC"),
        name="Not Here",
    )
    response = api.get(
        f"/api/v1/competitions/{competition.id}/fantasy/players/{stranger.id}/performance"
    )
    assert response.status_code == 404


def test_public_rules_list_matches_the_scoring_table():
    from apps.fantasy.rules import RULES_PUBLIC

    table = {row["label"]: row["points"] for row in RULES_PUBLIC["scoring"]}
    assert table["Appearance"] == "1"
    assert table["60+ minutes"] == "1"
    assert table["Goal (GK/DEF)"] == "6"
    assert table["Goal (MID)"] == "5"
    assert table["Goal (FWD)"] == "4"
    assert table["Assist"] == "3"
    assert table["Clean sheet (GK/DEF)"] == "4"
    assert table["Clean sheet (MID)"] == "1"
    assert table["3 saves"] == "1"
    assert table["Penalty save"] == "5"
    assert table["Yellow card"] == "-1"
    assert table["Red card"] == "-3"
    assert table["Own goal"] == "-2"
