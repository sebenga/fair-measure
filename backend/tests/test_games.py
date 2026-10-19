"""Multi-sport Games: catalogue, events, entries, medals, the medal table and officials."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from apps.competitions.presets import PRESETS
from apps.fixtures.models import Fixture, FixtureSide
from apps.games import olympic_catalog as catalog
from apps.games import services
from apps.games.models import NOC, Athlete, Games, GamesEvent, Medal, MedalChange
from apps.results.models import CompetitionOfficial

pytestmark = pytest.mark.django_db
User = get_user_model()

AVAILABLE = next(key for key in ("soccer", "basketball", "tennis") if key in PRESETS)


def _client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def games(db):
    owner = User.objects.create_user(email="organiser@games.test", password="pw-123456789")
    games = Games.objects.create(name="Test Games", owner=owner, kind=Games.Kind.SUMMER)
    for code, name in (
        ("RSA", "South Africa"),
        ("KEN", "Kenya"),
        ("BRA", "Brazil"),
        ("JPN", "Japan"),
        ("NZL", "New Zealand"),
    ):
        NOC.objects.create(games=games, code=code, name=name)
    return games


def _nocs(games) -> dict:
    return {noc.code: noc for noc in games.nocs.all()}


def _performance_event(games, medal_type="standard") -> GamesEvent:
    """An event ranked by a result sheet. No such locked preset exists yet, so the
    competition's settings are given the result type directly."""

    event = services.add_custom_event(
        games, sport_label="Demo sport", name="Final", preset_key=AVAILABLE, medal_type=medal_type
    )
    competition = event.competition
    competition.settings_json = {
        **competition.settings_json,
        "result_type": "finishing_order",
        "result_config": {},
        "official_results": True,
    }
    competition.save()
    return event


def _athletes(games, event, codes):
    nocs = _nocs(games)
    entries = []
    for index, code in enumerate(codes):
        athlete = Athlete.objects.create(
            games=games, noc=nocs[code], name=f"Athlete {index} {code}"
        )
        entries.append(services.add_entry(event, nocs[code], athlete))
    return entries


def _race(event, entries, places, official):
    from apps.results import services as results

    fixture = results.create_event(event.competition, label="Final", actor=event.games.owner)
    sides = {side.participant_id: side for side in fixture.sides.all()}
    rows = [
        {"side": str(sides[entry.participant_id].id), "data": data}
        for entry, data in zip(entries, places, strict=True)
    ]
    results.save_results(fixture, rows, event.games.owner)
    results.finalise(fixture, official)
    return fixture, sides


@pytest.fixture
def official(games):
    person = User.objects.create_user(email="td@games.test", password="pw-123456789")
    return person


def _appoint(event, person):
    CompetitionOfficial.objects.get_or_create(
        competition=event.competition, user=person, title="technical_delegate"
    )


# --- Catalogue ---------------------------------------------------------------


def test_catalogue_is_complete_data():
    keys = set()
    for sport in catalog.all_sports():
        assert sport["federation"] and sport["federation_name"], sport["key"]
        assert sport["season"] in {"summer", "winter"}
        for discipline in sport["disciplines"]:
            assert discipline["events"], (sport["key"], discipline["name"])
            for event in discipline["events"]:
                key = catalog.event_key(sport["key"], discipline["name"], event["name"])
                assert key not in keys, key
                keys.add(key)
                assert event["gender"] in {"men", "women", "mixed", "open"}
    seasons = {sport["season"] for sport in catalog.all_sports()}
    assert seasons == {"summer", "winter"}
    assert len(catalog.SUMMER) >= 35 and len(catalog.WINTER) >= 14


def test_select_all_summer_creates_only_events_with_locked_presets(games):
    client = _client(games.owner)
    response = client.post(f"/api/v1/games/{games.id}/sports", {"season": "summer"}, format="json")
    assert response.status_code == 201, response.data
    created = response.data["created"]
    assert created, "some Summer sports already have presets"
    assert response.data["unavailable"], "sports without presets are reported, not created"
    for row in created:
        assert row["preset_key"] in PRESETS
    event = GamesEvent.objects.filter(games=games).first()
    settings = event.competition.settings_json
    assert settings["official_results"] is True
    assert settings["scoring_locked"] is True
    assert event.competition.name.startswith("Test Games")

    again = client.post(f"/api/v1/games/{games.id}/sports", {"season": "summer"}, format="json")
    assert again.data["created"] == []
    assert len(again.data["skipped"]) == len(created)

    catalog_view = client.get(
        "/api/v1/games/catalog", {"season": "summer", "games": str(games.id)}
    ).data
    added = [
        event
        for sport in catalog_view
        for disc in sport["disciplines"]
        for event in disc["events"]
        if event["added"]
    ]
    assert len(added) == len(created)


def test_events_can_be_removed_and_custom_events_added(games):
    client = _client(games.owner)
    created = client.post(
        f"/api/v1/games/{games.id}/sports", {"season": "summer"}, format="json"
    ).data["created"]
    first = created[0]
    assert client.delete(f"/api/v1/games/{games.id}/events/{first['id']}").status_code == 204
    custom = client.post(
        f"/api/v1/games/{games.id}/events",
        {"sport": "School relay", "name": "Under-13 relay", "preset": AVAILABLE},
        format="json",
    )
    assert custom.status_code == 201
    assert custom.data["custom"] is True
    bad = client.post(
        f"/api/v1/games/{games.id}/events",
        {"sport": "X", "name": "Y", "preset": "not-a-preset"},
        format="json",
    )
    assert bad.status_code == 400
    stranger = _client(User.objects.create_user(email="x@games.test", password="pw-123456789"))
    assert (
        stranger.post(
            f"/api/v1/games/{games.id}/sports", {"season": "summer"}, format="json"
        ).status_code
        == 403
    )


# --- Entries -------------------------------------------------------------------


def test_entries_follow_the_noc_rules(games):
    nocs = _nocs(games)
    event = services.add_custom_event(
        games, sport_label="Demo", name="Sprint", preset_key=AVAILABLE
    )
    athlete = Athlete.objects.create(games=games, noc=nocs["KEN"], name="Runner")
    with pytest.raises(ValidationError):
        services.add_entry(event, nocs["RSA"], athlete)
    services.add_entry(event, nocs["KEN"], athlete)
    with pytest.raises(ValidationError):
        services.add_entry(event, nocs["KEN"], athlete)

    team = services.add_custom_event(
        games, sport_label="Demo", name="Relay", preset_key=AVAILABLE, kind="team"
    )
    services.add_entry(team, nocs["RSA"])
    with pytest.raises(ValidationError):
        services.add_entry(team, nocs["RSA"])

    client = _client(games.owner)
    clash = client.post(
        f"/api/v1/games/{games.id}/nocs", {"name": "Again", "code": "rsa"}, format="json"
    )
    assert clash.status_code == 400
    bad = client.post(
        f"/api/v1/games/{games.id}/nocs", {"name": "Bad", "code": "R1"}, format="json"
    )
    assert bad.status_code == 400


# --- Medals ------------------------------------------------------------------------


def test_medals_are_awarded_when_an_official_confirms_the_final(games, official):
    event = _performance_event(games)
    _appoint(event, official)
    entries = _athletes(games, event, ["RSA", "KEN", "BRA", "JPN"])
    _race(
        event,
        entries,
        [{"position": 1}, {"position": 2}, {"position": 3}, {"position": 4}],
        official,
    )

    medals = {row.entry.noc.code: row.medal for row in Medal.objects.filter(event=event)}
    assert medals == {"RSA": "gold", "KEN": "silver", "BRA": "bronze"}
    event.refresh_from_db()
    assert event.status == GamesEvent.Status.MEDALS_AWARDED
    assert MedalChange.objects.filter(event=event).count() == 1


def test_a_dead_heat_shares_gold_and_skips_silver(games, official):
    event = _performance_event(games)
    _appoint(event, official)
    entries = _athletes(games, event, ["RSA", "KEN", "BRA", "JPN"])
    _race(
        event,
        entries,
        [{"position": 1}, {"position": 1}, {"position": 3}, {"position": 4}],
        official,
    )
    medals = sorted((row.entry.noc.code, row.medal) for row in Medal.objects.filter(event=event))
    assert medals == [("BRA", "bronze"), ("KEN", "gold"), ("RSA", "gold")]


def test_a_disqualification_reallocates_medals_and_is_logged(games, official):
    from apps.results import services as results

    event = _performance_event(games)
    _appoint(event, official)
    entries = _athletes(games, event, ["RSA", "KEN", "BRA", "JPN"])
    fixture, sides = _race(
        event,
        entries,
        [{"position": 1}, {"position": 2}, {"position": 3}, {"position": 4}],
        official,
    )
    results.set_status(
        fixture,
        sides[entries[0].participant_id].id,
        "DQ",
        official,
        reason="Anti-doping rule violation",
    )
    medals = {row.entry.noc.code: row.medal for row in Medal.objects.filter(event=event)}
    assert medals == {"KEN": "gold", "BRA": "silver", "JPN": "bronze"}
    change = MedalChange.objects.filter(event=event).order_by("-created_at").first()
    assert "Anti-doping" in change.reason
    assert {row["noc"] for row in change.before} == {"RSA", "KEN", "BRA"}


def _knockout_event(games, medal_type):
    event = services.add_custom_event(
        games,
        sport_label="Demo",
        name=f"Bracket {medal_type}",
        preset_key=AVAILABLE,
        kind="team",
        medal_type=medal_type,
    )
    event.competition.format = "knockout"
    event.competition.save(update_fields=["format"])
    nocs = _nocs(games)
    entries = {code: services.add_entry(event, nocs[code]) for code in ("RSA", "KEN", "BRA", "JPN")}
    return event, entries


def _match(event, round_number, winner, loser, label=""):
    fixture = Fixture.objects.create(
        competition=event.competition,
        round_number=round_number,
        label=label,
        status=Fixture.Status.COMPLETED,
    )
    FixtureSide.objects.create(
        fixture=fixture, participant=winner.participant, position=0, outcome="win", score=2
    )
    FixtureSide.objects.create(
        fixture=fixture, participant=loser.participant, position=1, outcome="loss", score=1
    )
    return fixture


def test_two_bronze_events_give_both_losing_semi_finalists_bronze(games):
    event, e = _knockout_event(games, GamesEvent.MedalType.TWO_BRONZE)
    _match(event, 1, e["RSA"], e["JPN"])
    _match(event, 1, e["KEN"], e["BRA"])
    _match(event, 2, e["RSA"], e["KEN"])
    services.sync_medals(event)
    medals = sorted((row.entry.noc.code, row.medal) for row in Medal.objects.filter(event=event))
    assert medals == [("BRA", "bronze"), ("JPN", "bronze"), ("KEN", "silver"), ("RSA", "gold")]


def test_a_bronze_medal_match_decides_third(games):
    event, e = _knockout_event(games, GamesEvent.MedalType.BRONZE_MATCH)
    _match(event, 1, e["RSA"], e["JPN"])
    _match(event, 1, e["KEN"], e["BRA"])
    client = _client(games.owner)
    made = client.post(f"/api/v1/games/{games.id}/events/{event.id}/bronze-match")
    assert made.status_code == 201, made.data
    _match(event, 2, e["RSA"], e["KEN"])
    event.refresh_from_db()
    services.sync_medals(event)
    assert sorted(row.medal for row in Medal.objects.filter(event=event)) == ["gold", "silver"]

    bronze = Fixture.objects.get(pk=made.data["fixture_id"])
    for side in bronze.sides.all():
        side.outcome = "win" if side.participant_id == e["JPN"].participant_id else "loss"
        side.save()
    bronze.status = Fixture.Status.COMPLETED
    bronze.save()
    services.sync_medals(event)
    medals = {row.entry.noc.code: row.medal for row in Medal.objects.filter(event=event)}
    assert medals == {"RSA": "gold", "KEN": "silver", "JPN": "bronze"}


# --- Medal table -------------------------------------------------------------------------


def _award(games, code, kind):
    event = services.add_custom_event(
        games,
        sport_label="Demo",
        name=f"{code}-{kind}-{Medal.objects.count()}",
        preset_key=AVAILABLE,
    )
    noc = games.nocs.get(code=code)
    athlete = Athlete.objects.create(
        games=games, noc=noc, name=f"{code} athlete {Medal.objects.count()}"
    )
    entry = services.add_entry(event, noc, athlete)
    Medal.objects.create(
        event=event,
        noc=noc,
        entry=entry,
        medal=kind,
        rank={"gold": 1, "silver": 2, "bronze": 3}[kind],
    )


def test_gold_first_and_total_first_rank_differently(games):
    _award(games, "KEN", "gold")
    for _ in range(3):
        _award(games, "BRA", "bronze")
    _award(games, "RSA", "silver")
    _award(games, "RSA", "silver")

    gold_first = [row["code"] for row in services.medal_table(games)][:3]
    assert gold_first == ["KEN", "RSA", "BRA"]

    games.medal_table_ranking = Games.Ranking.TOTAL_FIRST
    games.save()
    total_first = [row["code"] for row in services.medal_table(games)][:3]
    assert total_first == ["BRA", "RSA", "KEN"]

    table = services.medal_table(games)
    no_medals = [row for row in table if row["total"] == 0]
    assert len({row["rank"] for row in no_medals}) == 1  # level NOCs share a rank


def test_the_ranking_is_locked_after_creation(games):
    client = _client(games.owner)
    response = client.patch(
        f"/api/v1/games/{games.id}", {"medal_table_ranking": "total_first"}, format="json"
    )
    assert response.status_code == 400
    created = client.post(
        "/api/v1/games", {"name": "New", "medal_table_ranking": "total_first"}, format="json"
    )
    assert created.status_code == 201
    assert created.data["medal_table_ranking"] == "total_first"


def test_medal_endpoint_and_noc_page(games, official):
    event = _performance_event(games)
    _appoint(event, official)
    entries = _athletes(games, event, ["RSA", "KEN", "BRA"])
    _race(event, entries, [{"position": 1}, {"position": 2}, {"position": 3}], official)
    client = _client(games.owner)
    medals = client.get(f"/api/v1/games/{games.id}/medals").data
    assert medals["table"][0]["code"] == "RSA"
    assert medals["feed"]
    rsa = games.nocs.get(code="RSA")
    page = client.get(f"/api/v1/games/{games.id}/nocs/{rsa.id}").data
    assert page["medals_by_sport"][0]["gold"] == 1


# --- Officials -------------------------------------------------------------------------------


def test_technical_delegates_join_every_event_and_only_they_confirm(games, official):
    client = _client(games.owner)
    client.post(f"/api/v1/games/{games.id}/sports", {"sports": ["football"]}, format="json")
    appointed = client.post(
        f"/api/v1/games/{games.id}/officials", {"user": str(official.id)}, format="json"
    )
    assert appointed.status_code == 200
    for event in games.events.all():
        assert CompetitionOfficial.objects.filter(
            competition=event.competition, user=official
        ).exists()

    event = _performance_event(games)
    entries = _athletes(games, event, ["RSA", "KEN"])
    from apps.results import services as results

    fixture = results.create_event(event.competition, label="Final", actor=games.owner)
    sides = list(fixture.sides.all())
    results.save_results(
        fixture,
        [
            {"side": str(side.id), "data": {"position": index + 1}}
            for index, side in enumerate(sides)
        ],
        games.owner,
    )
    with pytest.raises(PermissionDenied):
        results.finalise(fixture, games.owner)
    assert not Medal.objects.filter(event=event).exists()
    assert entries


def test_games_code_never_names_a_sport():
    names = set(PRESETS) | {str(preset.get("sport") or "").lower() for preset in PRESETS.values()}
    names = {name for name in names if name and name != "custom"}
    for module in ("services.py", "views.py", "signals.py", "models.py"):
        text = (Path("apps/games") / module).read_text().lower()
        for name in names:
            assert f'"{name}"' not in text and f"'{name}'" not in text, f"{module} names {name}"
