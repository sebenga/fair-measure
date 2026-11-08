"""A custom competition takes teams, individuals, pairs or horse and rider combinations."""

from __future__ import annotations

import pytest

from apps.competitions.models import Competition, Participant

pytestmark = pytest.mark.django_db

CRITERIA = [{"name": "Points", "points": "1", "affects_score": True}]


def _create(api, basis: str, entrants: str) -> Competition:
    created = api.post(
        "/api/v1/competitions",
        {
            "name": f"Custom {basis} {entrants}",
            "preset": "custom",
            "format": "league" if basis == "results" else "freeform",
            "scoring_basis": basis,
            "scoring_categories": CRITERIA,
            "participant_type": entrants,
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    return Competition.objects.get(pk=created.data["id"])


@pytest.mark.parametrize("basis", ["criteria", "results"])
@pytest.mark.parametrize("entrants", ["team", "individual", "pair", "combination"])
def test_custom_competitions_keep_who_takes_part(api, basis, entrants):
    competition = _create(api, basis, entrants)
    settings = competition.settings_json

    assert settings["participant_type"] == entrants
    assert settings["participant_types"] == [entrants]
    assert settings.get("profile_entrants", False) is (entrants == "individual")
    assert settings["table_mode"] == ("points" if basis == "criteria" else "head_to_head")


@pytest.mark.parametrize("basis", ["criteria", "results"])
def test_entrants_are_added_the_way_the_type_needs(api, user, other_user, basis):
    url = lambda competition: f"/api/v1/competitions/{competition.id}/participants"  # noqa: E731

    individuals = _create(api, basis, "individual")
    named = api.post(url(individuals), {"name": "Somebody"}, format="json")
    assert named.status_code == 400
    profile = api.post(url(individuals), {"user": str(other_user.id)}, format="json")
    assert profile.status_code == 201, profile.data
    assert Participant.objects.get(pk=profile.data["id"]).kind == Participant.Kind.INDIVIDUAL

    named_entrants = (
        ("team", "Harbour Hawks"),
        ("pair", "Ada / Ben"),
        ("combination", "Star / Ada"),
    )
    for entrants, name in named_entrants:
        competition = _create(api, basis, entrants)
        added = api.post(url(competition), {"name": name}, format="json")
        assert added.status_code == 201, (entrants, added.data)
        assert Participant.objects.get(pk=added.data["id"]).kind == Participant.Kind.TEAM


@pytest.mark.parametrize(
    ("basis", "entrants"),
    [("criteria", "team"), ("criteria", "pair"), ("criteria", "combination"), ("results", "pair")],
)
def test_a_demo_fills_whichever_entrants_were_chosen(api, basis, entrants):
    competition = _create(api, basis, entrants)
    demo = api.post(f"/api/v1/competitions/{competition.id}/demo-league", {}, format="json")
    assert demo.status_code == 201, demo.data
    assert demo.data["entrants"] == 16
    kinds = set(competition.participants.values_list("kind", flat=True))
    assert kinds == {Participant.Kind.TEAM}


@pytest.mark.parametrize(("basis", "expected"), [("results", "team"), ("criteria", "individual")])
def test_older_custom_requests_without_a_choice_keep_their_old_entrants(api, basis, expected):
    created = api.post(
        "/api/v1/competitions",
        {
            "name": f"Older custom {basis}",
            "preset": "custom",
            "format": "league" if basis == "results" else "freeform",
            "scoring_basis": basis,
            "scoring_categories": CRITERIA,
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    settings = Competition.objects.get(pk=created.data["id"]).settings_json
    assert settings["participant_type"] == expected
