"""Starting points for a competition.

Presets are ordinary data written through the same models as a hand-built
competition, so applying one is a convenience rather than a special case. Sports,
KPIs, and a cleaning rota all use the same scoring rows. Every value stays
editable afterwards.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypedDict


class Preset(TypedDict):
    label: str
    sport: str
    format: str
    kind: str  # sport | work | home | custom
    # head_to_head = VS fixtures; points = accumulate scores into one table.
    table_mode: str
    scoring_categories: list[dict[str, Any]]
    points_policy: dict[str, Any]
    rules: list[dict[str, str]]


T = "score_difference"
POINTS_TABLE = "points"
HEAD_TO_HEAD = "head_to_head"

# Shared policy for boards that rank by accumulated score, not match results.
POINTS_ACCUMULATION_POLICY: dict[str, Any] = {
    "win_points": Decimal("0"),
    "draw_points": Decimal("0"),
    "loss_points": Decimal("0"),
    "allow_draws": True,
    "tiebreakers": ["score_for", "name"],
}

PRESETS: dict[str, Preset] = {
    "soccer": {
        "label": "Soccer",
        "sport": "soccer",
        "kind": "sport",
        "format": "league",
        "table_mode": HEAD_TO_HEAD,
        "scoring_categories": [
            {"name": "Goal", "code": "goal", "points": Decimal("1"), "description": "Ball over the line."},
            {"name": "Own goal", "code": "own-goal", "points": Decimal("1"), "description": "Credited to the opposing side."},
            {"name": "Yellow card", "code": "yellow-card", "points": Decimal("0"), "affects_score": False},
            {"name": "Red card", "code": "red-card", "points": Decimal("0"), "affects_score": False},
        ],
        "points_policy": {
            "win_points": Decimal("3"),
            "draw_points": Decimal("1"),
            "loss_points": Decimal("0"),
            "tiebreakers": ["points", T, "score_for", "name"],
        },
        "rules": [
            {"name": "Match length", "description": "Two halves of 45 minutes plus stoppage time."},
            {"name": "Squad size", "description": "Eleven players per side, up to five substitutions."},
        ],
    },
    "rugby": {
        "label": "Rugby union",
        "sport": "rugby",
        "kind": "sport",
        "format": "league",
        "table_mode": HEAD_TO_HEAD,
        "scoring_categories": [
            {"name": "Try", "code": "try", "points": Decimal("5"), "description": "Grounding the ball over the line."},
            {"name": "Conversion", "code": "conversion", "points": Decimal("2"), "description": "Kick after a try."},
            {"name": "Penalty kick", "code": "penalty", "points": Decimal("3")},
            {"name": "Drop goal", "code": "drop-goal", "points": Decimal("3")},
        ],
        "points_policy": {
            "win_points": Decimal("4"),
            "draw_points": Decimal("2"),
            "loss_points": Decimal("0"),
            "bonus_win_margin": None,
            "bonus_win_points": Decimal("1"),
            "bonus_loss_margin": 7,
            "bonus_loss_points": Decimal("1"),
            "tiebreakers": ["points", T, "score_for", "name"],
        },
        "rules": [
            {"name": "Match length", "description": "Two halves of 40 minutes."},
            {"name": "Losing bonus", "description": "One point for losing by seven or fewer."},
        ],
    },
    "basketball": {
        "label": "Basketball",
        "sport": "basketball",
        "kind": "sport",
        "format": "league",
        "table_mode": HEAD_TO_HEAD,
        "scoring_categories": [
            {"name": "Free throw", "code": "free-throw", "points": Decimal("1")},
            {"name": "Field goal", "code": "field-goal", "points": Decimal("2")},
            {"name": "Three pointer", "code": "three-pointer", "points": Decimal("3")},
        ],
        "points_policy": {
            "win_points": Decimal("2"),
            "draw_points": Decimal("0"),
            "loss_points": Decimal("0"),
            "allow_draws": False,
            "tiebreakers": ["points", "wins", T, "name"],
        },
        "rules": [{"name": "Match length", "description": "Four quarters of 12 minutes."}],
    },
    "tennis": {
        "label": "Tennis",
        "sport": "tennis",
        "kind": "sport",
        "format": "knockout",
        "table_mode": HEAD_TO_HEAD,
        "scoring_categories": [
            {"name": "Set won", "code": "set", "points": Decimal("1")},
            {"name": "Game won", "code": "game", "points": Decimal("0"), "affects_score": False},
            {"name": "Ace", "code": "ace", "points": Decimal("0"), "affects_score": False},
        ],
        "points_policy": {
            "win_points": Decimal("1"),
            "draw_points": Decimal("0"),
            "loss_points": Decimal("0"),
            "allow_draws": False,
            "tiebreakers": ["wins", T, "name"],
        },
        "rules": [{"name": "Match format", "description": "Best of three tie-break sets."}],
    },
    "squash": {
        "label": "Squash",
        "sport": "squash",
        "kind": "sport",
        "format": "ladder",
        "table_mode": HEAD_TO_HEAD,
        "scoring_categories": [
            {"name": "Game won", "code": "game", "points": Decimal("1")},
            {"name": "Rally won", "code": "rally", "points": Decimal("0"), "affects_score": False},
        ],
        "points_policy": {
            "win_points": Decimal("3"),
            "draw_points": Decimal("0"),
            "loss_points": Decimal("1"),
            "allow_draws": False,
            "tiebreakers": ["points", T, "name"],
        },
        "rules": [{"name": "Match format", "description": "Best of five games to eleven points."}],
    },
    "golf": {
        "label": "Golf (stroke play)",
        "sport": "golf",
        "kind": "sport",
        "format": "league",
        "table_mode": HEAD_TO_HEAD,
        "scoring_categories": [
            # Negative points make a lower total the better one, and the
            # standings engine needs no special case for it.
            {"name": "Stroke", "code": "stroke", "points": Decimal("-1")},
            {"name": "Penalty stroke", "code": "penalty-stroke", "points": Decimal("-1")},
        ],
        "points_policy": {
            "win_points": Decimal("1"),
            "draw_points": Decimal("0.5"),
            "loss_points": Decimal("0"),
            "tiebreakers": ["points", "score_for", "name"],
        },
        "rules": [{"name": "Format", "description": "Eighteen holes, lowest total strokes wins."}],
    },
    "kpi": {
        "label": "KPIs",
        "sport": "KPIs",
        "kind": "work",
        "format": "league",
        "table_mode": POINTS_TABLE,
        "scoring_categories": [
            {
                "name": "Target met",
                "code": "target-met",
                "points": Decimal("3"),
                "description": "The agreed number for the period was hit.",
            },
            {
                "name": "Stretch",
                "code": "stretch",
                "points": Decimal("5"),
                "description": "The result beat the target, not just met it.",
            },
            {
                "name": "Miss",
                "code": "miss",
                "points": Decimal("0"),
                "affects_score": False,
                "description": "Recorded for the timeline, but did not change the score.",
            },
            {
                "name": "Penalty",
                "code": "penalty",
                "points": Decimal("-1"),
                "description": "Late, incomplete, or unverifiable data.",
            },
        ],
        "points_policy": dict(POINTS_ACCUMULATION_POLICY),
        "rules": [
            {
                "name": "What is being measured",
                "description": "Replace this with the KPI, the target, and the review period.",
            },
        ],
    },
    "cleaning": {
        "label": "Cleaning",
        "sport": "cleaning",
        "kind": "home",
        "format": "league",
        "table_mode": POINTS_TABLE,
        "scoring_categories": [
            {
                "name": "Task done",
                "code": "task-done",
                "points": Decimal("1"),
                "description": "A listed chore was finished to the agreed standard.",
            },
            {
                "name": "Deep clean",
                "code": "deep-clean",
                "points": Decimal("3"),
                "description": "A room or area was fully cleaned, not just tidied.",
            },
            {
                "name": "Extra task",
                "code": "extra-task",
                "points": Decimal("1"),
                "description": "Something done that was not on the rota.",
            },
            {
                "name": "Missed",
                "code": "missed",
                "points": Decimal("-1"),
                "description": "A listed job was skipped or left unfinished.",
            },
        ],
        "points_policy": dict(POINTS_ACCUMULATION_POLICY),
        "rules": [
            {
                "name": "The standard",
                "description": "Write what 'done' looks like for each area, so scoring stays fair.",
            },
        ],
    },
    "custom": {
        "label": "Custom",
        "sport": "",
        "kind": "custom",
        "format": "league",
        "table_mode": POINTS_TABLE,
        "scoring_categories": [],
        "points_policy": dict(POINTS_ACCUMULATION_POLICY),
        "rules": [],
    },
}

PRESET_CHOICES = [(key, value["label"]) for key, value in PRESETS.items()]


def apply_preset(competition, preset_key: str) -> None:
    """Populate a competition's scoring, points policy and rules from a preset."""

    from .models import PointsPolicy, Rule, ScoringCategory

    preset = PRESETS.get(preset_key)
    if preset is None:
        raise ValueError(f"Unknown preset '{preset_key}'.")

    ScoringCategory.objects.bulk_create(
        [
            ScoringCategory(
                competition=competition,
                name=item["name"],
                code=item["code"],
                description=item.get("description", ""),
                points=item["points"],
                affects_score=item.get("affects_score", True),
                display_order=index,
            )
            for index, item in enumerate(preset["scoring_categories"])
        ]
    )

    PointsPolicy.objects.update_or_create(
        competition=competition, defaults=preset["points_policy"]
    )

    settings = dict(competition.settings_json or {})
    settings["table_mode"] = preset.get("table_mode", HEAD_TO_HEAD)
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])

    Rule.objects.bulk_create(
        [
            Rule(
                competition=competition,
                name=item["name"],
                description=item["description"],
                display_order=index,
            )
            for index, item in enumerate(preset["rules"])
        ]
    )
