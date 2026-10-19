"""The Games experience: opening screen, NOC/athlete/event pages, records, follows and
alerts, reports (JSON and CSV agree), the live medal table and local games points."""

from __future__ import annotations

import csv
import io
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.fixtures.models import Fixture
from apps.games import services
from apps.games.experience import send_start_alerts
from apps.games.models import NOC, Athlete, Games, GamesAlert, GamesOfficial
from apps.notifications.models import Notification
from apps.results import services as results

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(user=None) -> APIClient:
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


@pytest.fixture
def games(db):
    owner = User.objects.create_user(email="owner@exp.test", password="pw-123456789")
    games = Games.objects.create(
        name="Experience Games",
        owner=owner,
        starts_on=timezone.localdate() + timedelta(days=10),
        ends_on=timezone.localdate() + timedelta(days=24),
    )
    games.delegate = User.objects.create_user(email="td@exp.test", password="pw-123456789")
    GamesOfficial.objects.create(games=games, user=games.delegate)
    for code in ("RSA", "KEN", "BRA", "JPN"):
        NOC.objects.create(games=games, code=code, name=code)
    return games


def _swim_event(games, name="Men's 100 m freestyle"):
    key = f"aquatics|Swimming|{name}"
    return services.add_catalog_events(games, [key])["created"][0]


def _run_final(games, event, times: dict, *, label="Final", finalise=True):
    """``times`` maps NOC code to the swim time; returns the fixture."""

    entries = {}
    for code in times:
        noc = games.nocs.get(code=code)
        athlete, _ = Athlete.objects.get_or_create(games=games, noc=noc, name=f"Swimmer {code}")
        entries[code] = services.add_entry(event, noc, athlete)
    fixture = results.create_event(
        event.competition,
        label=label,
        participant_ids=[entry.participant_id for entry in entries.values()],
        actor=games.owner,
    )
    sides = {side.participant_id: side for side in fixture.sides.all()}
    results.save_results(
        fixture,
        [
            {"side": str(sides[entries[code].participant_id].id), "data": {"time": value}}
            for code, value in times.items()
        ],
        games.owner,
    )
    if finalise:
        results.finalise(fixture, games.delegate)
    return fixture


TIMES = {"RSA": "47.80", "KEN": "47.51", "BRA": "48.90", "JPN": "48.02"}


# --- Live medal table ---------------------------------------------------------------------


def test_the_medal_table_is_pushed_live_when_medals_are_confirmed(games):
    event = _swim_event(games)
    with mock.patch("apps.core.bus.publish_event") as publish:
        _run_final(games, event, TIMES)
    calls = [call for call in publish.call_args_list if call.args[0] == "games.medals"]
    assert len(calls) == 1
    _, payload, rooms = calls[0].args
    assert rooms == [f"games:{games.id}"]
    table = {row["code"]: row for row in payload["table"]}
    assert (table["KEN"]["gold"], table["RSA"]["silver"], table["JPN"]["bronze"]) == (1, 1, 1)
    assert table["KEN"]["rank"] == 1


def test_only_viewers_of_the_games_may_join_its_room(games, settings):
    settings.INTERNAL_API_TOKEN = "internal-test-token"
    games.is_private = True
    games.save()
    stranger = User.objects.create_user(email="stranger@exp.test", password="pw-123456789")
    room = f"games:{games.id}"
    for user, expected in ((stranger, []), (games.delegate, [room]), (games.owner, [room])):
        response = APIClient().post(
            "/internal/rooms/authorize",
            {"user_id": str(user.id), "rooms": [room]},
            format="json",
            HTTP_AUTHORIZATION="Bearer internal-test-token",
        )
        assert response.status_code == 200, response.content
        assert response.json()["allowed"] == expected


# --- Opening screen, NOC, athlete and event pages ------------------------------------------


def test_opening_screen_counts_down_and_lists_today_and_live(games):
    event = _swim_event(games)
    soon = timezone.now() + timedelta(minutes=5)
    _run_final(games, event, TIMES, finalise=False)
    heat = Fixture.objects.create(competition=event.competition, label="Heat 2", scheduled_at=soon)
    live = Fixture.objects.create(
        competition=event.competition, label="Heat 3", status=Fixture.Status.LIVE
    )
    data = _client(games.owner).get(f"/api/v1/games/{games.id}/overview").json()
    assert data["countdown"] == {"state": "upcoming", "days_to_go": 10, "day": None}
    if timezone.localdate(soon) == timezone.localdate():
        assert [row["fixture_id"] for row in data["today"]] == [str(heat.id)]
    assert [row["fixture_id"] for row in data["live"]] == [str(live.id)]
    assert data["medal_table"] and data["latest_medals"] == []


def test_noc_athlete_and_event_pages(games):
    event = _swim_event(games)
    event.qualification_rule = "Fastest 8 from the heats"
    event.save()
    _run_final(games, event, TIMES)
    client = _client(games.owner)

    ken = games.nocs.get(code="KEN")
    noc = client.get(f"/api/v1/games/{games.id}/nocs/{ken.id}").json()
    assert noc["medals_by_sport"] == [{"sport": "Aquatics", "gold": 1, "silver": 0, "bronze": 0}]
    assert noc["results"][0]["rank"] == 1 and noc["results"][0]["mark"] == "47.51"

    athlete = Athlete.objects.get(games=games, noc=ken)
    response = client.patch(
        f"/api/v1/games/{games.id}/athletes/{athlete.id}",
        {"personal_bests": [{"event": "100 m freestyle", "mark": "47.40", "date": "2026-05-01"}]},
        format="json",
    )
    assert response.status_code == 200, response.json()
    page = response.json()
    assert page["personal_bests"][0]["mark"] == "47.40"
    assert page["best_at_games"] == [
        {"event_id": str(event.id), "event": "Aquatics: Men's 100 m freestyle", "mark": "47.51"}
    ]
    assert page["medals"][0]["medal"] == "gold"

    detail = client.get(f"/api/v1/games/{games.id}/events/{event.id}").json()
    assert detail["qualification_rule"] == "Fastest 8 from the heats"
    final = detail["rounds"][0]
    assert [row["noc"] for row in final["results"]] == ["KEN", "RSA", "JPN", "BRA"]
    assert len(final["start_list"]) == 4


def test_officials_record_records_and_others_cannot(games):
    event = _swim_event(games)
    _run_final(games, event, TIMES)
    ken_swimmer = Athlete.objects.get(games=games, noc__code="KEN")
    url = f"/api/v1/games/{games.id}/events/{event.id}/records"
    body = {
        "scope": "games",
        "mark": "47.51",
        "previous_mark": "47.58",
        "athlete": str(ken_swimmer.id),
    }
    stranger = User.objects.create_user(email="fan@exp.test", password="pw-123456789")
    assert _client(stranger).post(url, body, format="json").status_code == 403
    response = _client(games.delegate).post(url, body, format="json")
    assert response.status_code == 201, response.json()
    assert response.json()["holder"] == "Swimmer KEN" and response.json()["noc"] == "KEN"
    athlete = _client(games.owner).get(f"/api/v1/games/{games.id}/athletes/{ken_swimmer.id}")
    assert athlete.json()["records"][0]["scope_label"] == "Games record"


# --- Follows and alerts -----------------------------------------------------------------------


def test_followers_get_one_result_alert_and_one_start_alert(games):
    event = _swim_event(games)
    fan = User.objects.create_user(email="fan@exp.test", password="pw-123456789")
    sport_fan = User.objects.create_user(email="sport@exp.test", password="pw-123456789")
    client = _client(fan)
    ken = games.nocs.get(code="KEN")
    assert (
        client.post(
            f"/api/v1/games/{games.id}/follows",
            {"target": "noc", "noc": str(ken.id)},
            format="json",
        ).status_code
        == 201
    )
    assert (
        _client(sport_fan)
        .post(
            f"/api/v1/games/{games.id}/follows",
            {"target": "sport", "sport_key": "aquatics"},
            format="json",
        )
        .status_code
        == 201
    )

    _run_final(games, event, TIMES)
    for person in (fan, sport_fan):
        alerts = Notification.objects.filter(user=person, kind="games.result")
        assert alerts.count() == 1
        assert "Gold KEN Swimmer KEN" in alerts.first().body
    services.sync_medals(event)  # nothing changed: no second alert
    assert Notification.objects.filter(kind="games.result").count() == 2

    other = _swim_event(games, "Women's 100 m freestyle")
    Athlete.objects.create(games=games, noc=ken, name="Swimmer KEN 2")
    entry = services.add_entry(other, ken, Athlete.objects.get(name="Swimmer KEN 2"))
    heat = results.create_event(
        other.competition, label="Heat 1", participant_ids=[entry.participant_id], actor=games.owner
    )
    heat.scheduled_at = timezone.now() + timedelta(minutes=10)
    heat.save()
    assert send_start_alerts(games, minutes=30) == 2
    assert send_start_alerts(games, minutes=30) == 0
    start = Notification.objects.get(user=fan, kind="games.start")
    assert start.title == "Starting soon: Aquatics: Women's 100 m freestyle"
    assert GamesAlert.objects.filter(kind="start").count() == 2


def test_a_follow_must_point_at_something_in_this_games(games):
    fan = User.objects.create_user(email="fan@exp.test", password="pw-123456789")
    response = _client(fan).post(
        f"/api/v1/games/{games.id}/follows",
        {"target": "sport", "sport_key": "curling"},
        format="json",
    )
    assert response.status_code == 400


# --- Reports ----------------------------------------------------------------------------------


def _csv_sections(text: str) -> tuple[list[str], list[list[list[str]]]]:
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    sections, current = [], None
    for row in rows[1:]:
        if not row:
            current = None
            continue
        if current is None:
            current = []
            sections.append(current)
        current.append(row)
    return header, sections


@pytest.mark.parametrize("kind", ["medal-table", "results-book", "noc-summary", "daily"])
def test_every_report_csv_matches_its_json(games, kind):
    event = _swim_event(games)
    _run_final(games, event, TIMES)
    client = _client(games.owner)
    params = {"noc": str(games.nocs.get(code="KEN").id)} if kind == "noc-summary" else {}
    url = f"/api/v1/games/{games.id}/reports/{kind}"
    report = client.get(url, params).json()
    response = client.get(url, {**params, "export": "csv"})
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    header, sections = _csv_sections(response.content.decode())
    assert header == [report["title"]]
    # The subtitle sits alone before the first blank line; then one block per section.
    assert sections[0] == [[report["subtitle"]]]
    for block, section in zip(sections[1:], report["sections"], strict=True):
        assert block[0] == [section["heading"]]
        assert block[1] == section["columns"]
        assert block[2:] == section["rows"]


def test_reports_agree_with_the_medal_api(games):
    event = _swim_event(games)
    _run_final(games, event, TIMES)
    client = _client(games.owner)
    api = client.get(f"/api/v1/games/{games.id}/medals").json()["table"]
    report = client.get(f"/api/v1/games/{games.id}/reports/medal-table").json()
    rows = report["sections"][0]["rows"]
    assert [row[1] for row in rows] == [row["code"] for row in api]
    assert [row[3:] for row in rows] == [
        [str(row["gold"]), str(row["silver"]), str(row["bronze"]), str(row["total"])] for row in api
    ]
    book = client.get(
        f"/api/v1/games/{games.id}/reports/results-book", {"sport": "aquatics"}
    ).json()
    final = next(section for section in book["sections"] if section["heading"].endswith("Final"))
    assert [row[2] for row in final["rows"]] == ["KEN", "RSA", "JPN", "BRA"]
    daily = client.get(f"/api/v1/games/{games.id}/reports/daily").json()
    assert daily["sections"][0]["rows"] == [
        [
            "Aquatics: Men's 100 m freestyle",
            "Swimmer KEN (KEN)",
            "Swimmer RSA (RSA)",
            "Swimmer JPN (JPN)",
        ]
    ]
    assert client.get(f"/api/v1/games/{games.id}/reports/nonsense").status_code == 404


# --- Local games --------------------------------------------------------------------------------


def test_local_games_points_per_placing_with_a_shared_place(db):
    owner = User.objects.create_user(email="teacher@school.test", password="pw-123456789")
    response = _client(owner).post(
        "/api/v1/games",
        {
            "name": "Sports day",
            "kind": "custom",
            "team_label": "House",
            "placing_points": [5, 3, 1],
        },
        format="json",
    )
    assert response.status_code == 201, response.json()
    games = Games.objects.get(pk=response.json()["id"])
    for code, name in (("RED", "Red house"), ("BLU", "Blue house"), ("GRN", "Green house")):
        NOC.objects.create(games=games, code=code, name=name)
    games.delegate = User.objects.create_user(email="judge@school.test", password="pw-123456789")
    GamesOfficial.objects.create(games=games, user=games.delegate)

    def race(name, places: dict):
        event = services.add_custom_event(
            games, sport_label="Athletics", name=name, preset_key="athletics_road"
        )
        entries = {}
        for code in places:
            noc = games.nocs.get(code=code)
            athlete = Athlete.objects.create(games=games, noc=noc, name=f"{name} {code}")
            entries[code] = services.add_entry(event, noc, athlete)
        fixture = results.create_event(event.competition, label="Final", actor=owner)
        sides = {side.participant_id: side for side in fixture.sides.all()}
        results.save_results(
            fixture,
            [
                {"side": str(sides[entries[code].participant_id].id), "data": {"position": place}}
                for code, place in places.items()
            ],
            owner,
        )
        results.finalise(fixture, games.delegate)

    race("Egg and spoon", {"RED": 1, "BLU": 2, "GRN": 3})  # RED 5, BLU 3, GRN 1
    race("Sack race", {"BLU": 1, "GRN": 1, "RED": 3})  # dead heat: BLU 5, GRN 5; RED is 3rd: 1
    table = _client(owner).get(f"/api/v1/games/{games.id}/overview").json()["points_table"]
    assert [(row["code"], row["points"], row["rank"]) for row in table] == [
        ("BLU", "8", 1),
        ("GRN", "6", 2),  # level with RED on points and medals: shared place, by code
        ("RED", "6", 2),
    ]
    medals = _client(owner).get(f"/api/v1/games/{games.id}/medals").json()
    assert medals["points_table"] == table
    report = _client(owner).get(f"/api/v1/games/{games.id}/reports/medal-table").json()
    assert report["sections"][1]["rows"][0][:4] == ["1", "BLU", "Blue house", "8"]


def test_placing_points_must_be_numbers(db):
    owner = User.objects.create_user(email="teacher@school.test", password="pw-123456789")
    response = _client(owner).post(
        "/api/v1/games",
        {"name": "Bad", "kind": "custom", "placing_points": ["five"]},
        format="json",
    )
    assert response.status_code == 400
