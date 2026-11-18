"""Score every entrant on one accumulation criterion in a single round."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.competitions.models import Competition, Participant

pytestmark = pytest.mark.django_db


def _board(api, *, score_all: bool = True):
    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Weekly board",
            "preset": "custom",
            "scoring_basis": "criteria",
            "scoring_categories": [
                {
                    "name": "Sales closed",
                    "description": "Deals closed in the period.",
                    "points": "2",
                }
            ],
            "settings_json": {"score_all_on_criterion": score_all},
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    competition = Competition.objects.get(pk=created.data["id"])
    if score_all:
        settings = dict(competition.settings_json or {})
        settings["score_all_on_criterion"] = True
        competition.settings_json = settings
        competition.save(update_fields=["settings_json", "updated_at"])
    category = competition.scoring_categories.get()
    ada = Participant.objects.create(competition=competition, name="Ada")
    ben = Participant.objects.create(competition=competition, name="Ben")
    return competition, category, ada, ben


def test_criterion_round_scores_every_entrant_on_one_kpi(api):
    competition, category, ada, ben = _board(api)

    awarded = api.post(
        f"/api/v1/competitions/{competition.id}/score-assist",
        {
            "kind": "criterion_round",
            "scoring_category": str(category.id),
            "note": "Week 4 board.",
            "entries": [
                {"participant": str(ada.id), "quantity": "3"},
                {"participant": str(ben.id), "quantity": "1"},
            ],
        },
        format="json",
    )
    assert awarded.status_code == 201, awarded.data
    assert awarded.data["count"] == 2
    assert Decimal(awarded.data["awarded"]) == Decimal("8")

    table = api.get(f"/api/v1/competitions/{competition.id}/standings")
    by_name = {row["participant"]["name"]: row for row in table.data["rows"]}
    assert Decimal(by_name["Ada"]["points"]) == Decimal("6")
    assert Decimal(by_name["Ben"]["points"]) == Decimal("2")


def test_criterion_round_requires_the_setting(api):
    competition, category, ada, ben = _board(api, score_all=False)
    settings = dict(competition.settings_json or {})
    settings.pop("score_all_on_criterion", None)
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])

    refused = api.post(
        f"/api/v1/competitions/{competition.id}/score-assist",
        {
            "kind": "criterion_round",
            "scoring_category": str(category.id),
            "note": "Week 4 board.",
            "entries": [
                {"participant": str(ada.id), "quantity": "1"},
                {"participant": str(ben.id), "quantity": "1"},
            ],
        },
        format="json",
    )
    assert refused.status_code == 400
