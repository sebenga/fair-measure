"""Named, recurring points milestones for custom criteria competitions."""

from decimal import Decimal

from apps.competitions.milestones import (
    crossed_milestone_values,
    list_milestones,
    normalize_milestone_settings,
)


def test_crossed_milestone_values_cycles_every_interval():
    assert crossed_milestone_values(Decimal("0"), Decimal("49"), 50) == []
    assert crossed_milestone_values(Decimal("0"), Decimal("50"), 50) == [50]
    assert crossed_milestone_values(Decimal("49"), Decimal("51"), 50) == [50]
    assert crossed_milestone_values(Decimal("50"), Decimal("50"), 50) == []
    assert crossed_milestone_values(Decimal("50"), Decimal("150"), 50) == [100, 150]
    assert crossed_milestone_values(Decimal("0"), Decimal("150"), 50) == [50, 100, 150]


def test_normalize_named_milestones_and_legacy_migration():
    settings = {
        "points_milestones": [
            {"name": " Star sticker ", "interval": "50"},
            {"id": "treat", "name": "Treat", "interval": 100},
        ]
    }
    normalize_milestone_settings(settings)
    assert "points_milestone_interval" not in settings
    assert len(settings["points_milestones"]) == 2
    assert settings["points_milestones"][0]["name"] == "Star sticker"
    assert settings["points_milestones"][0]["interval"] == 50
    assert settings["points_milestones"][1] == {
        "id": "treat",
        "name": "Treat",
        "interval": 100,
    }

    legacy = {"points_milestone_interval": "75"}
    normalize_milestone_settings(legacy)
    assert "points_milestone_interval" not in legacy
    assert legacy["points_milestones"][0]["name"] == "Milestone"
    assert legacy["points_milestones"][0]["interval"] == 75

    cleared = {"points_milestones": []}
    normalize_milestone_settings(cleared)
    assert "points_milestones" not in cleared


def test_score_assist_reports_named_milestones(api):
    from apps.competitions.models import Competition, Participant

    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Chore board",
            "preset": "custom",
            "scoring_basis": "criteria",
            "scoring_categories": [{"name": "Helped", "points": "10"}],
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    competition_id = created.data["id"]
    detail = api.get(f"/api/v1/competitions/{competition_id}")
    settings = dict(detail.data["settings_json"] or {})
    enabled = api.patch(
        f"/api/v1/competitions/{competition_id}",
        {
            "settings_json": {
                **settings,
                "points_milestones": [
                    {"id": "star", "name": "Star sticker", "interval": 50},
                    {"id": "treat", "name": "Treat", "interval": 100},
                ],
            }
        },
        format="json",
    )
    assert enabled.status_code == 200, enabled.data
    competition = Competition.objects.get(pk=competition_id)
    names = [item["name"] for item in list_milestones(competition)]
    assert names == ["Star sticker", "Treat"]

    category_id = detail.data["scoring_categories"][0]["id"]
    child = Participant.objects.create(competition_id=competition_id, name="Sam")

    first = api.post(
        f"/api/v1/competitions/{competition_id}/score-assist",
        {
            "kind": "criterion",
            "participant": str(child.id),
            "scoring_category": category_id,
            "quantity": "4",
            "note": "Tidy room.",
        },
        format="json",
    )
    assert first.status_code == 201
    assert first.data["milestones"] == []

    second = api.post(
        f"/api/v1/competitions/{competition_id}/score-assist",
        {
            "kind": "criterion",
            "participant": str(child.id),
            "scoring_category": category_id,
            "quantity": "2",
            "note": "Homework done.",
        },
        format="json",
    )
    assert second.status_code == 201
    # 60 pts → Star sticker at 50 only
    assert len(second.data["milestones"]) == 1
    hit = second.data["milestones"][0]
    assert hit["milestone_name"] == "Star sticker"
    assert hit["milestone"] == 50

    third = api.post(
        f"/api/v1/competitions/{competition_id}/score-assist",
        {
            "kind": "criterion",
            "participant": str(child.id),
            "scoring_category": category_id,
            "quantity": "5",
            "note": "Big week.",
        },
        format="json",
    )
    assert third.status_code == 201
    # 110 → Star at 100 and Treat at 100
    names_hit = [m["milestone_name"] for m in third.data["milestones"]]
    marks = [m["milestone"] for m in third.data["milestones"]]
    assert names_hit == ["Star sticker", "Treat"]
    assert marks == [100, 100]


def test_admin_can_clear_named_milestones(api):
    created = api.post(
        "/api/v1/competitions",
        {
            "name": "Goals",
            "preset": "custom",
            "scoring_basis": "criteria",
            "scoring_categories": [{"name": "Star", "points": "1"}],
        },
        format="json",
    )
    assert created.status_code == 201
    competition_id = created.data["id"]
    detail = api.get(f"/api/v1/competitions/{competition_id}")
    settings = dict(detail.data["settings_json"] or {})

    updated = api.patch(
        f"/api/v1/competitions/{competition_id}",
        {
            "settings_json": {
                **settings,
                "points_milestones": [{"name": "Good job", "interval": 25}],
            }
        },
        format="json",
    )
    assert updated.status_code == 200, updated.data
    assert updated.data["settings_json"]["points_milestones"][0]["name"] == "Good job"
    assert updated.data["settings_json"]["points_milestones"][0]["interval"] == 25

    cleared = api.patch(
        f"/api/v1/competitions/{competition_id}",
        {"settings_json": {**updated.data["settings_json"], "points_milestones": []}},
        format="json",
    )
    assert cleared.status_code == 200
    assert "points_milestones" not in (cleared.data["settings_json"] or {})
