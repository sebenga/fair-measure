"""Phase 1 of talent scouting: profiles, roles, age rules and consent."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import Competition, Participant, RosterMember
from apps.scouting import catalog
from apps.scouting.models import ConsentRecord, PlayerProfile, ScoutingRole
from apps.scouting.services import age_group, age_on, effective_visibility

pytestmark = pytest.mark.django_db
User = get_user_model()


def _client(email: str, **extra) -> tuple[APIClient, object]:
    person = User.objects.create_user(email=email, password="s3cret-password", **extra)
    client = APIClient()
    client.force_authenticate(person)
    return client, person


def _years_ago(years: int) -> str:
    today = date.today()
    return date(today.year - years, today.month, min(today.day, 28)).isoformat()


def _make_profile(client, **fields) -> dict:
    payload = {"first_name": "Thandi", "last_name": "Nkosi", "region": "gauteng", **fields}
    created = client.post("/api/v1/scouting/profile", payload, format="json")
    assert created.status_code == 201, created.data
    return created.data


def _scout() -> APIClient:
    client, _ = _client("scout@club.test", display_name="Scout")
    made = client.post(
        "/api/v1/scouting/organisations",
        {"name": "Lions Academy", "kind": "academy"},
        format="json",
    )
    assert made.status_code == 201
    return client


# --- Age ---------------------------------------------------------------------


def test_age_and_age_group_use_the_season_cut_off():
    born = date(2012, 7, 15)
    assert age_on(born, date(2026, 7, 14)) == 13
    assert age_on(born, date(2026, 7, 15)) == 14
    # On 1 January 2026 they were 13, so the whole 2026 season is U15.
    assert age_group(born, date(2026, 3, 1))["key"] == "u15"
    assert age_group(born, date(2026, 12, 31))["key"] == "u15"
    assert age_group(date(2000, 1, 1), date(2026, 6, 1))["key"] == "senior"
    assert age_group(date(1980, 1, 1), date(2026, 6, 1))["key"] == "masters"
    assert age_group(None) is None


def test_profile_reports_age_and_group():
    client, _ = _client("adult@player.test")
    data = _make_profile(client, date_of_birth=_years_ago(22))
    assert data["age"] == 22
    assert data["age_group"]["key"] in {"senior", "u21"}
    assert data["is_minor"] is False


# --- Minors and consent ------------------------------------------------------


def test_under_18_is_hidden_from_scouts_without_guardian_consent():
    player, _ = _client("teen@player.test")
    profile = _make_profile(player, date_of_birth=_years_ago(15), visibility="scouts")
    assert profile["is_minor"] is True
    assert profile["effective_visibility"] == "private"

    scout = _scout()
    assert scout.get(f"/api/v1/scouting/profiles/{profile['id']}").status_code == 404
    assert scout.get("/api/v1/scouting/profiles").data["count"] == 0

    guardian, guardian_user = _client("mum@family.test", display_name="Mum")
    invited = player.post(
        "/api/v1/scouting/profile/guardians",
        {"email": "mum@family.test", "relationship": "Mother"},
        format="json",
    )
    assert invited.status_code == 201
    link_id = guardian.get("/api/v1/scouting/guardian/links").data[0]["id"]
    assert guardian.post(f"/api/v1/scouting/guardian/links/{link_id}/accept").status_code == 200
    # Accepting the link is not consent yet.
    assert scout.get(f"/api/v1/scouting/profiles/{profile['id']}").status_code == 404

    granted = guardian.post(
        f"/api/v1/scouting/guardian/profiles/{profile['id']}/consent",
        {"visibility": "scouts", "sections": ["physical"], "note": "Happy for scouts to see"},
        format="json",
    )
    assert granted.status_code == 201, granted.data
    seen = scout.get(f"/api/v1/scouting/profiles/{profile['id']}")
    assert seen.status_code == 200
    assert seen.data["access"] == "scout"

    record = ConsentRecord.objects.get(given_as="guardian", action="granted")
    assert record.given_by == guardian_user
    assert set(record.sections) == {"identity", "sports", "physical"}
    assert record.visibility == "scouts"

    revoked = guardian.delete(f"/api/v1/scouting/guardian/profiles/{profile['id']}/consent")
    assert revoked.status_code == 200
    assert scout.get(f"/api/v1/scouting/profiles/{profile['id']}").status_code == 404
    assert ConsentRecord.objects.filter(action="revoked", given_as="guardian").count() == 1


def test_guardian_consent_caps_visibility_and_sections():
    player, _ = _client("teen2@player.test")
    profile = _make_profile(player, date_of_birth=_years_ago(16), visibility="public")
    player.post(
        "/api/v1/scouting/profile/measurements",
        {"kind": "height", "value": "180", "measured_on": date.today().isoformat()},
        format="json",
    )
    guardian, _ = _client("dad@family.test")
    player.post("/api/v1/scouting/profile/guardians", {"email": "dad@family.test"}, format="json")
    link_id = guardian.get("/api/v1/scouting/guardian/links").data[0]["id"]
    guardian.post(f"/api/v1/scouting/guardian/links/{link_id}/accept")
    guardian.post(
        f"/api/v1/scouting/guardian/profiles/{profile['id']}/consent",
        {"visibility": "scouts"},
        format="json",
    )
    assert effective_visibility(PlayerProfile.objects.get(pk=profile["id"])) == "scouts"

    stranger, _ = _client("stranger@nowhere.test")
    assert stranger.get(f"/api/v1/scouting/profiles/{profile['id']}").status_code == 404
    seen = _scout().get(f"/api/v1/scouting/profiles/{profile['id']}")
    # Physical data was not consented to, so it is not shared.
    assert seen.data["measurements"] == []


def test_a_removed_guardian_consent_stops_applying():
    player, _ = _client("teen3@player.test")
    profile = _make_profile(player, date_of_birth=_years_ago(14), visibility="scouts")
    guardian, _ = _client("aunt@family.test")
    player.post("/api/v1/scouting/profile/guardians", {"email": "aunt@family.test"}, format="json")
    link = guardian.get("/api/v1/scouting/guardian/links").data[0]
    guardian.post(f"/api/v1/scouting/guardian/links/{link['id']}/accept")
    guardian.post(
        f"/api/v1/scouting/guardian/profiles/{profile['id']}/consent",
        {"visibility": "scouts"},
        format="json",
    )
    scout = _scout()
    assert scout.get(f"/api/v1/scouting/profiles/{profile['id']}").status_code == 200
    player.delete(f"/api/v1/scouting/profile/guardians/{link['id']}")
    assert scout.get(f"/api/v1/scouting/profiles/{profile['id']}").status_code == 404


def test_a_profile_without_a_date_of_birth_stays_private():
    player, _ = _client("nodob@player.test")
    profile = _make_profile(player, visibility="public")
    assert profile["effective_visibility"] == "private"
    assert _scout().get(f"/api/v1/scouting/profiles/{profile['id']}").status_code == 404


def test_only_an_active_guardian_can_consent():
    player, _ = _client("teen4@player.test")
    profile = _make_profile(player, date_of_birth=_years_ago(15), visibility="scouts")
    other, _ = _client("random@nowhere.test")
    response = other.post(
        f"/api/v1/scouting/guardian/profiles/{profile['id']}/consent",
        {"visibility": "public"},
        format="json",
    )
    assert response.status_code == 403


# --- Contact details and private data ---------------------------------------


def test_scouts_never_see_contact_details_or_private_injuries():
    player, person = _client("adult2@player.test", phone="+27 82 000 0000", display_name="Sipho")
    profile = _make_profile(player, date_of_birth=_years_ago(20), visibility="scouts")
    player.post(
        "/api/v1/scouting/profile/injuries",
        {"description": "Hamstring strain", "injured_on": "2026-02-01"},
        format="json",
    )
    player.post(
        "/api/v1/scouting/profile/injuries",
        {"description": "Ankle sprain", "injured_on": "2025-05-01", "shared_with_scouts": True},
        format="json",
    )
    seen = _scout().get(f"/api/v1/scouting/profiles/{profile['id']}")
    assert seen.status_code == 200
    text = str(seen.data)
    assert person.email not in text
    assert "+27 82" not in text
    assert "phone" not in seen.data and "email" not in seen.data
    assert [item["description"] for item in seen.data["injuries"]] == ["Ankle sprain"]
    assert "date_of_birth" not in seen.data


def test_public_viewers_see_age_group_but_not_age_or_injuries():
    player, _ = _client("adult3@player.test")
    profile = _make_profile(player, date_of_birth=_years_ago(25), visibility="public")
    player.post(
        "/api/v1/scouting/profile/injuries",
        {"description": "Knee", "shared_with_scouts": True},
        format="json",
    )
    viewer, _ = _client("fan@nowhere.test")
    seen = viewer.get(f"/api/v1/scouting/profiles/{profile['id']}")
    assert seen.status_code == 200
    assert seen.data["access"] == "public"
    assert "age" not in seen.data
    assert seen.data["age_group"] is not None
    assert seen.data["injuries"] == []


# --- Players control visibility ---------------------------------------------


def test_players_can_revoke_visibility_and_it_is_audited():
    player, _ = _client("adult4@player.test")
    profile = _make_profile(player, date_of_birth=_years_ago(24), visibility="scouts")
    scout = _scout()
    assert scout.get(f"/api/v1/scouting/profiles/{profile['id']}").status_code == 200

    changed = player.patch("/api/v1/scouting/profile", {"visibility": "private"}, format="json")
    assert changed.status_code == 200
    assert changed.data["effective_visibility"] == "private"
    assert scout.get(f"/api/v1/scouting/profiles/{profile['id']}").status_code == 404

    audit = player.get("/api/v1/scouting/profile/consents").data
    assert [row["action"] for row in audit] == ["revoked", "granted"]
    assert all(row["given_as"] == "player" for row in audit)


def test_consent_records_cannot_be_edited():
    player, person = _client("adult5@player.test")
    _make_profile(player, date_of_birth=_years_ago(30), visibility="public")
    record = ConsentRecord.objects.get(given_by=person)
    record.note = "changed"
    with pytest.raises(ValueError):
        record.save()


# --- Sports, positions, measurements ----------------------------------------


def test_positions_must_come_from_the_sports_catalogue():
    player, _ = _client("adult6@player.test")
    _make_profile(player, date_of_birth=_years_ago(19))
    bad = player.post(
        "/api/v1/scouting/profile/sports",
        {"sport": "soccer", "primary_position": "fly-half"},
        format="json",
    )
    assert bad.status_code == 400
    good = player.post(
        "/api/v1/scouting/profile/sports",
        {
            "sport": "soccer",
            "primary_position": "striker",
            "secondary_positions": ["winger", "striker"],
        },
        format="json",
    )
    assert good.status_code == 201
    sport = good.data["sports"][0]
    assert sport["is_primary"] is True
    assert sport["secondary_positions"] == ["winger"]
    assert (
        player.post(
            "/api/v1/scouting/profile/sports", {"sport": "quidditch"}, format="json"
        ).status_code
        == 400
    )


def test_self_reported_measurements_are_labelled_and_coach_ones_verified():
    player, person = _client("adult7@player.test")
    profile = _make_profile(player, date_of_birth=_years_ago(21), visibility="scouts")
    mine = player.post(
        "/api/v1/scouting/profile/measurements",
        {"kind": "height", "value": "178", "measured_on": "2026-01-10"},
        format="json",
    )
    assert mine.data["measurements"][0]["source"] == "self"
    assert mine.data["measurements"][0]["verified"] is False

    coach, coach_user = _client("coach@team.test", display_name="Coach Dube")
    competition = Competition.objects.create(name="Schools league", owner=coach_user)
    team = Participant.objects.create(competition=competition, name="Hawks", kind="team")
    RosterMember.objects.create(participant=team, name="Player", user=person)
    assert (
        coach.post(
            "/api/v1/scouting/roles/coach", {"team": str(team.id)}, format="json"
        ).status_code
        == 201
    )

    verified = coach.post(
        f"/api/v1/scouting/profiles/{profile['id']}/measurements",
        {"kind": "height", "value": "180.5", "measured_on": "2026-03-01"},
        format="json",
    )
    assert verified.status_code == 201, verified.data
    assert verified.data["verified"] is True
    assert verified.data["verified_by_name"] == "Coach Dube"

    latest = player.get("/api/v1/scouting/profile").data["measurements"][0]
    assert latest["value"] == "180.50" and latest["source"] == "coach"
    # The player cannot delete the coach's verified record.
    assert player.delete(f"/api/v1/scouting/profile/measurements/{latest['id']}").status_code == 403


def test_a_coach_cannot_verify_someone_outside_their_team():
    player, _ = _client("adult8@player.test")
    profile = _make_profile(player, date_of_birth=_years_ago(21), visibility="scouts")
    coach, _ = _client("coach2@team.test")
    response = coach.post(
        f"/api/v1/scouting/profiles/{profile['id']}/measurements",
        {"kind": "weight", "value": "70", "measured_on": "2026-03-01"},
        format="json",
    )
    assert response.status_code == 403


# --- Roles and organisations -------------------------------------------------


def test_creating_an_organisation_makes_you_its_scout_admin():
    admin, _ = _client("head@club.test")
    made = admin.post(
        "/api/v1/scouting/organisations", {"name": "City FC", "kind": "club"}, format="json"
    )
    assert made.data["my_role"] == "scout_admin"
    _client("new.scout@club.test")
    added = admin.post(
        f"/api/v1/scouting/organisations/{made.data['id']}/members",
        {"email": "new.scout@club.test", "role": "scout"},
        format="json",
    )
    assert added.status_code == 201
    assert ScoutingRole.objects.filter(role="scout", user__email="new.scout@club.test").exists()

    outsider, _ = _client("outsider@club.test")
    refused = outsider.post(
        f"/api/v1/scouting/organisations/{made.data['id']}/members",
        {"email": "outsider@club.test"},
        format="json",
    )
    assert refused.status_code == 403
    me = admin.get("/api/v1/scouting/me").data
    assert me["role_keys"] == ["scout_admin"]


def test_creating_a_profile_makes_you_a_player():
    player, _ = _client("adult9@player.test")
    _make_profile(player, date_of_birth=_years_ago(19))
    assert player.get("/api/v1/scouting/me").data["role_keys"] == ["player"]


def test_catalogue_is_served_and_scouting_code_does_not_name_a_sport():
    response = APIClient().get("/api/v1/scouting/catalog")
    assert response.status_code == 200
    assert {item["key"] for item in response.data["sports"]} == set(catalog.SPORTS)
    for sport in catalog.SPORTS.values():
        assert sport["positions"], sport["label"]
    for name in (
        "views.py",
        "services.py",
        "serializers.py",
        "models.py",
        "selection.py",
        "reports.py",
    ):
        text = (Path("apps/scouting") / name).read_text().lower()
        for key in catalog.SPORTS:
            assert f'"{key}"' not in text, f"{name} names {key}"


def _team(owner, name: str, competition_name: str, *, private: bool = False) -> Participant:
    competition = Competition.objects.create(
        name=competition_name, owner=owner, sport="rugby", is_private=private
    )
    return Participant.objects.create(competition=competition, name=name, kind="team")


def test_profile_teams_come_from_the_platform_and_can_span_competitions():
    player, person = _client("sides@player.test")
    hawks = _team(person, "Harbour Hawks", "Coastal Cup")
    lions = _team(person, "Highveld Lions", "Winter League")
    listed = player.get("/api/v1/scouting/teams", {"q": "Hawks"})
    assert listed.status_code == 200
    assert any(row["id"] == str(hawks.id) for row in listed.data)

    profile = _make_profile(
        player, date_of_birth=_years_ago(20), team_ids=[str(hawks.id), str(lions.id)]
    )
    names = {row["name"] for row in profile["teams"]}
    competitions = {row["competition"] for row in profile["teams"]}
    assert names == {"Harbour Hawks", "Highveld Lions"}
    assert competitions == {"Coastal Cup", "Winter League"}
    assert "Harbour Hawks" in profile["school_or_club"]
    assert "Highveld Lions" in profile["school_or_club"]


def test_an_individual_entrant_cannot_be_listed_as_a_school_or_club():
    player, person = _client("solo@player.test")
    competition = Competition.objects.create(name="Singles", owner=person, sport="tennis")
    solo = Participant.objects.create(competition=competition, name="Solo Ace", kind="individual")
    created = player.post(
        "/api/v1/scouting/profile",
        {"first_name": "Solo", "team_ids": [str(solo.id)]},
        format="json",
    )
    assert created.status_code == 400


def test_rostered_teams_appear_on_the_profile_even_when_not_claimed():
    player, person = _client("roster@player.test")
    team = _team(person, "Owls", "City Shield")
    RosterMember.objects.create(participant=team, name="Roster", user=person)
    profile = _make_profile(player, date_of_birth=_years_ago(21), team_ids=[])
    assert [row["name"] for row in profile["teams"]] == ["Owls"]
    assert profile["teams"][0]["from_roster"] is True


def test_private_teams_are_hidden_from_people_outside_the_competition():
    _, owner = _client("owner.sides@test")
    _team(owner, "Secret FC", "Closed League", private=True)
    outsider, _ = _client("outsider.sides@test")
    hits = outsider.get("/api/v1/scouting/teams", {"q": "Secret"})
    assert hits.data == []


def test_seed_scouting_is_repeatable_and_respects_consent():
    from django.core.management import call_command

    call_command("seed_scouting", verbosity=0)
    first = PlayerProfile.objects.count()
    call_command("seed_scouting", verbosity=0)
    assert PlayerProfile.objects.count() == first

    scout = APIClient()
    scout.force_authenticate(User.objects.get(email="scout@example.com"))
    pending = PlayerProfile.objects.get(user__email="junior2@example.com")
    consented = PlayerProfile.objects.get(user__email="junior@example.com")
    assert scout.get(f"/api/v1/scouting/profiles/{pending.id}").status_code == 404
    assert scout.get(f"/api/v1/scouting/profiles/{consented.id}").status_code == 200
