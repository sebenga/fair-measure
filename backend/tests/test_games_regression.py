"""Full Games regression (the Olympics final check).

1. Select all Summer: every sport, discipline and event appears; remove some; add a
   custom event.
2. Each result type from the first round to the final, medals into the medal table;
   a shared medal, a two-bronze event, a bronze bout and a post-event DQ.
3. Gold-first versus total-first ordering.
4. Every Olympic preset is locked and shows its federation and rulebook; no engine
   code names a sport.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.olympic_presets import GOVERNANCE, OLYMPIC_PRESETS
from apps.competitions.presets import PRESETS
from apps.games import olympic_catalog as catalog
from apps.games import services
from apps.games.models import NOC, Athlete, Games, GamesOfficial, Medal, MedalChange
from apps.results import services as results

pytestmark = pytest.mark.django_db
User = get_user_model()
CODES = ["RSA", "KEN", "BRA", "JPN", "NZL"]
EQUESTRIAN = {"show_jumping", "dressage", "eventing"}


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def games(db):
    owner = User.objects.create_user(email="owner@regression.test", password="pw-123456789")
    games = Games.objects.create(name="Regression Games", owner=owner)
    games.delegate = User.objects.create_user(email="td@regression.test", password="pw-123456789")
    GamesOfficial.objects.create(games=games, user=games.delegate)
    for code in CODES:
        NOC.objects.create(games=games, code=code, name=code)
    return games


def _event(games, key: str):
    return services.add_catalog_events(games, [key])["created"][0]


def _enter(games, event, codes):
    entries = {}
    for code in codes:
        noc = games.nocs.get(code=code)
        if event.kind == "team":
            entries[code] = services.add_entry(event, noc)
        else:
            athlete, _ = Athlete.objects.get_or_create(
                games=games, noc=noc, name=f"{event.name} {code}"
            )
            entries[code] = services.add_entry(event, noc, athlete)
    return entries


def _round(games, event, entries, label: str, data: dict, *, finalise=True):
    """``data`` maps NOC code to that entrant's result data for this round."""

    fixture = results.create_event(
        event.competition,
        label=label,
        participant_ids=[entries[code].participant_id for code in data],
        actor=games.owner,
    )
    sides = {side.participant_id: side for side in fixture.sides.all()}
    results.save_results(
        fixture,
        [
            {"side": str(sides[entries[code].participant_id].id), "data": row}
            for code, row in data.items()
        ],
        games.owner,
    )
    if finalise:
        results.finalise(fixture, games.delegate)
    return fixture, {code: sides[entries[code].participant_id] for code in data}


def _medals(event):
    return sorted((row.medal, row.noc.code) for row in Medal.objects.filter(event=event))


def _table(games):
    return {
        row["code"]: (row["gold"], row["silver"], row["bronze"])
        for row in services.medal_table(games)
    }


# --- 1. Select all Summer ---------------------------------------------------------------------


def test_select_all_summer_then_edit_the_programme(games):
    client = _client(games.owner)
    response = client.post(f"/api/v1/games/{games.id}/sports", {"season": "summer"}, format="json")
    assert response.status_code == 201, response.data
    every = services.keys_for(season="summer")
    unavailable = set(response.data["unavailable"])
    expected_missing = {
        catalog.event_key(sport["key"], discipline["name"], event["name"])
        for sport in catalog.SUMMER
        for discipline in sport["disciplines"]
        for event in discipline["events"]
        if catalog.preset_for(sport, discipline, event) in EQUESTRIAN
    }
    assert unavailable == expected_missing and len(expected_missing) == 6
    assert len(response.data["created"]) == len(every) - len(expected_missing)

    events = client.get(f"/api/v1/games/{games.id}/events").json()
    seen = {(row["sport_key"], row["discipline"], row["name"]) for row in events}
    for sport in catalog.SUMMER:
        for discipline in sport["disciplines"]:
            for event in discipline["events"]:
                if catalog.preset_for(sport, discipline, event) in EQUESTRIAN:
                    continue
                assert (sport["key"], discipline["name"], event["name"]) in seen

    for row in events[:3]:
        assert client.delete(f"/api/v1/games/{games.id}/events/{row['id']}").status_code == 204
    custom = client.post(
        f"/api/v1/games/{games.id}/events",
        {"sport": "Netball", "name": "Women's netball", "preset": "netball", "kind": "team"},
        format="json",
    )
    assert custom.status_code == 201, custom.data
    after = client.get(f"/api/v1/games/{games.id}/events").json()
    assert len(after) == len(events) - 3 + 1
    assert any(row["custom"] and row["name"] == "Women's netball" for row in after)

    again = client.post(f"/api/v1/games/{games.id}/sports", {"season": "summer"}, format="json")
    assert len(again.data["created"]) == 3  # only the removed events come back


def test_select_all_winter_has_nothing_unavailable(games):
    response = _client(games.owner).post(
        f"/api/v1/games/{games.id}/sports", {"season": "winter"}, format="json"
    )
    assert response.data["unavailable"] == []
    assert len(response.data["created"]) == len(services.keys_for(season="winter"))


# --- 2. Every result type, first round to final ------------------------------------------------


def _strength(result_type: str, config: dict, strength: int, place: int) -> dict:
    if result_type == "timed_lowest":
        return {"time": f"{50 - strength * 0.5:.2f}"}
    if result_type == "measured_highest" and config.get("mode") == "heights":
        heights = {f"2.{height:02d}": "o" for height in range(1, strength + 1)}
        return {"heights": {**heights, f"2.{strength + 1:02d}": "xxx"}}
    if result_type == "measured_highest" and config.get("mode") == "total_of_best":
        return {"lifts": {"snatch": [str(100 + strength)], "clean_jerk": [str(130 + strength)]}}
    if result_type == "measured_highest":
        return {"attempts": [f"{60 + strength:.2f}"]}
    if result_type == "judged_score":
        return {"attempts": [{"scores": [str(5 + strength * 0.5)] * 7, "difficulty": "3.0"}]}
    if result_type == "points_highest":
        return {"rounds": [str(100 + strength)]}
    if result_type == "points_lowest":
        return {"rounds": [10 - strength] * 3}
    if result_type == "multi_run_aggregate":
        return {"runs": [{"time": f"{100 - strength}"}]}
    if result_type == "finishing_order":
        return {"position": place}
    if result_type == "combined_events":
        marks = {
            "100m_hurdles": "13.50",
            "high_jump": "1.80",
            "shot_put": "14.00",
            "200m": "24.00",
            "long_jump": "6.40",
            "javelin": "45.00",
            "800m": f"{150 - strength * 2}",
        }
        return {"marks": marks}
    raise AssertionError(result_type)


def _data(event, strengths: dict) -> dict:
    settings = event.competition.settings_json
    order = sorted(strengths, key=lambda code: -strengths[code])
    return {
        code: _strength(
            settings["result_type"],
            settings["result_config"],
            strengths[code],
            order.index(code) + 1,
        )
        for code in strengths
    }


ROUND_TO_FINAL = [
    ("timed_lowest", "aquatics|Swimming|Men's 100 m freestyle"),
    ("measured_highest", "athletics|Throws|Women's Javelin throw"),
    ("measured_highest (heights)", "athletics|Vertical jumps|Men's High jump"),
    ("measured_highest (total)", "weightlifting|Weightlifting|Men's -89 kg / -71 kg"),
    ("judged_score", "aquatics|Diving|Women's 10 m platform"),
    ("points_highest", "shooting|Shooting|Men's 10 m air rifle"),
    ("points_lowest", "sailing|Sailing|Women's ILCA dinghy"),
    ("multi_run_aggregate", "canoe|Canoe slalom|Men's K1"),
    ("finishing_order", "triathlon|Triathlon|Women's Individual"),
    ("combined_events", "athletics|Combined events|Women's heptathlon"),
    ("timed_lowest (winter)", "speed_skating|Speed skating|Women's 500 m"),
    ("multi_run_aggregate (winter)", "alpine_skiing|Technical|Men's Giant slalom"),
]


@pytest.mark.parametrize(
    "key", [row[1] for row in ROUND_TO_FINAL], ids=[row[0] for row in ROUND_TO_FINAL]
)
def test_first_round_to_final_reaches_the_medal_table(games, key):
    event = _event(games, key)
    entries = _enter(games, event, CODES)
    heat = _data(event, {"RSA": 5, "KEN": 4, "BRA": 3, "JPN": 2, "NZL": 1})
    if event.competition.settings_json["result_type"] == "multi_run_aggregate":
        runs = event.competition.settings_json["result_config"].get("runs")
        if runs:
            for row in heat.values():
                row["runs"] = row["runs"] * int(runs)
    for code in ("RSA", "KEN", "BRA", "JPN"):
        heat[code]["qualified"] = "Q"
    _round(games, event, entries, "Heat 1", heat)
    assert _medals(event) == [], "a heat never awards medals"

    final = _data(event, {"KEN": 8, "BRA": 7, "RSA": 6, "JPN": 5})
    if event.competition.settings_json["result_type"] == "multi_run_aggregate":
        runs = event.competition.settings_json["result_config"].get("runs")
        if runs:
            for row in final.values():
                row["runs"] = row["runs"] * int(runs)
    _round(games, event, entries, "Final", final)
    assert _medals(event) == [("bronze", "RSA"), ("gold", "KEN"), ("silver", "BRA")]
    table = _table(games)
    assert table["KEN"] == (1, 0, 0) and table["BRA"] == (0, 1, 0) and table["RSA"] == (0, 0, 1)
    rounds = (
        _client(games.owner).get(f"/api/v1/games/{games.id}/events/{event.id}").json()["rounds"]
    )
    assert [row["label"] for row in rounds] == ["Heat 1", "Final"]
    assert [row["qualified"] for row in rounds[0]["results"]][:4] == ["Q"] * 4


def test_a_shared_silver_and_no_bronze(games):
    event = _event(games, "aquatics|Swimming|Women's 100 m freestyle")
    entries = _enter(games, event, CODES[:4])
    _round(
        games,
        event,
        entries,
        "Final",
        {
            "KEN": {"time": "52.10"},
            "BRA": {"time": "52.40"},
            "RSA": {"time": "52.40"},
            "JPN": {"time": "53.00"},
        },
    )
    assert _medals(event) == [("gold", "KEN"), ("silver", "BRA"), ("silver", "RSA")]
    assert _table(games)["JPN"] == (0, 0, 0)


def test_a_post_event_disqualification_reallocates_the_medals(games):
    event = _event(games, "aquatics|Swimming|Men's 200 m freestyle")
    entries = _enter(games, event, CODES[:4])
    fixture, sides = _round(
        games,
        event,
        entries,
        "Final",
        {
            "KEN": {"time": "104.10"},
            "BRA": {"time": "104.40"},
            "RSA": {"time": "104.90"},
            "JPN": {"time": "105.20"},
        },
    )
    assert _medals(event) == [("bronze", "RSA"), ("gold", "KEN"), ("silver", "BRA")]
    results.set_status(
        fixture, sides["KEN"].id, "DQ", games.delegate, reason="Illegal turn found on video review"
    )
    services.sync_medals(event)
    assert _medals(event) == [("bronze", "JPN"), ("gold", "BRA"), ("silver", "RSA")]
    assert _table(games)["KEN"] == (0, 0, 0)
    change = MedalChange.objects.filter(event=event).order_by("-created_at").first()
    assert "Illegal turn found on video review" in change.reason


def _bout(games, event, entries, label, winner, loser, *, finalise=True):
    return _round(
        games,
        event,
        entries,
        label,
        {winner: {"cards": [30, 30, 29, 30, 29]}, loser: {"cards": [27, 28, 28, 27, 28]}},
        finalise=finalise,
    )


def test_two_bronzes_go_to_the_losing_semi_finalists(games):
    event = _event(games, "boxing|Boxing|Men's Flyweight")
    assert event.medal_type == "two_bronze"
    entries = _enter(games, event, CODES[:4])
    _bout(games, event, entries, "Semi-final 1", "KEN", "JPN")
    _bout(games, event, entries, "Semi-final 2", "BRA", "RSA")
    assert _medals(event) == [], "semi-finals never award medals"
    _bout(games, event, entries, "Final", "BRA", "KEN")
    assert _medals(event) == [
        ("bronze", "JPN"),
        ("bronze", "RSA"),
        ("gold", "BRA"),
        ("silver", "KEN"),
    ]
    assert _table(games)["JPN"] == (0, 0, 1) and _table(games)["RSA"] == (0, 0, 1)


def test_a_bronze_bout_decides_bronze(games):
    event = _event(games, "breaking|Breaking|B-Girls")
    assert event.medal_type == "bronze_match"
    entries = _enter(games, event, CODES[:4])
    _bout(games, event, entries, "Semi-final 1", "KEN", "JPN")
    _bout(games, event, entries, "Semi-final 2", "BRA", "RSA")
    _bout(games, event, entries, "Bronze medal battle", "RSA", "JPN")
    assert _medals(event) == []
    _bout(games, event, entries, "Final", "KEN", "BRA")
    assert _medals(event) == [("bronze", "RSA"), ("gold", "KEN"), ("silver", "BRA")]


def test_the_organiser_can_choose_the_medal_round(games):
    event = _event(games, "rowing|Rowing|Men's Single sculls")
    entries = _enter(games, event, CODES[:4])
    _round(
        games,
        event,
        entries,
        "Heat 1",
        {code: {"time": f"{400 + index}"} for index, code in enumerate(CODES[:4])},
    )
    medal_race, _ = _round(
        games,
        event,
        entries,
        "A race",
        {
            "JPN": {"time": "398"},
            "BRA": {"time": "399"},
            "KEN": {"time": "401"},
            "RSA": {"time": "402"},
        },
    )
    assert _medals(event) == [], '"A race" is not labelled as a final'
    response = _client(games.owner).patch(
        f"/api/v1/games/{games.id}/events/{event.id}",
        {"final_fixture": str(medal_race.id)},
        format="json",
    )
    assert response.status_code == 200
    assert _medals(event) == [("bronze", "KEN"), ("gold", "JPN"), ("silver", "BRA")]


# --- 3. Gold-first versus total-first -------------------------------------------------------------


def test_gold_first_and_total_first_order(games):
    finals = [
        ("aquatics|Swimming|Men's 100 m freestyle", ["RSA", "KEN", "BRA"]),
        ("aquatics|Swimming|Women's 100 m freestyle", ["JPN", "KEN", "BRA"]),
        ("aquatics|Swimming|Men's 200 m freestyle", ["JPN", "KEN", "RSA"]),
    ]
    for key, podium in finals:
        event = _event(games, key)
        entries = _enter(games, event, podium)
        _round(
            games,
            event,
            entries,
            "Final",
            {code: {"time": f"{50 + index}"} for index, code in enumerate(podium)},
        )
    # RSA 1G 1B, KEN 3S, BRA 2B, JPN 2G.
    order = [row["code"] for row in services.medal_table(games) if row["total"]]
    assert order == ["JPN", "RSA", "KEN", "BRA"]
    response = _client(games.owner).patch(
        f"/api/v1/games/{games.id}", {"medal_table_ranking": "total_first"}, format="json"
    )
    assert response.status_code == 400, "the ranking is locked once the Games exists"

    games.medal_table_ranking = Games.Ranking.TOTAL_FIRST
    games.save()
    order = [row["code"] for row in services.medal_table(games) if row["total"]]
    assert order == ["KEN", "JPN", "RSA", "BRA"]


# --- 4. Locked presets with their federation; no sport names in engine code -----------------


def test_every_olympic_event_page_shows_its_locked_preset_federation_and_rulebook(games):
    client = _client(games.owner)
    client.post(f"/api/v1/games/{games.id}/sports", {"season": "all"}, format="json")
    one_per_preset = {}
    for event in games.events.select_related("competition"):
        settings = event.competition.settings_json
        assert settings["locked"] and settings["scoring_locked"], event
        assert settings["official_results"], event
        assert settings["governing_body"] and settings["rulebook"], event
        one_per_preset.setdefault(event.preset_key, event)
    # Every Olympic preset is used, plus the reused presets linked into the catalogue.
    reused = set(GOVERNANCE) - {"athletics"}
    assert set(one_per_preset) == set(OLYMPIC_PRESETS) | reused
    for key, event in one_per_preset.items():
        page = client.get(f"/api/v1/games/{games.id}/events/{event.id}").json()
        assert page["locked"] is True, key
        assert page["governing_body"] == PRESETS[key]["governing_body"], key
        assert page["rulebook"] == PRESETS[key]["rulebook"], key


def test_no_engine_code_names_a_sport():
    names = set(PRESETS) | {str(preset.get("sport") or "").lower() for preset in PRESETS.values()}
    names = {name for name in names if name and name != "custom"}
    for module in (
        "apps/results/calculators.py",
        "apps/results/services.py",
        "apps/results/views.py",
        "apps/competitions/engine.py",
        "apps/standings/services.py",
        "apps/games/services.py",
        "apps/games/experience.py",
        "apps/games/reports.py",
        "apps/games/views.py",
    ):
        text = Path(module).read_text().lower()
        for name in names:
            assert f'"{name}"' not in text and f"'{name}'" not in text, f"{module} names {name}"
