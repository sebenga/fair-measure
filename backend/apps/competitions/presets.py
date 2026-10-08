"""Official starting points for a competition.

Each preset is either head-to-head (entrants play each other) or accumulation
(entrants build a total from a fixed scoring structure). Official presets write
their scoring through the same models as a hand-built competition, then lock
those rows. Only the Custom preset stays editable afterwards.
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
    # Official presets refuse later edits to categories and the points policy.
    scoring_locked: bool
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
    "bonus_win_margin": None,
    "bonus_win_points": Decimal("0"),
    "bonus_loss_margin": None,
    "bonus_loss_points": Decimal("0"),
    "tiebreakers": ["score_for", "name"],
}

# League tables use the same result points for every head-to-head sport.
# Match scoring (a try, a goal, a leg) stays on the scoring categories.
LEAGUE_POLICY: dict[str, Any] = {
    "win_points": Decimal("3"),
    "draw_points": Decimal("1"),
    "loss_points": Decimal("0"),
    "allow_draws": True,
    "bonus_win_margin": None,
    "bonus_win_points": Decimal("0"),
    "bonus_loss_margin": None,
    "bonus_loss_points": Decimal("0"),
    "tiebreakers": ["points", T, "score_for", "name"],
}

# Knockout fixtures only need a winner. They do not feed a league table.
KNOCKOUT_POLICY: dict[str, Any] = {
    "win_points": Decimal("1"),
    "draw_points": Decimal("0"),
    "loss_points": Decimal("0"),
    "allow_draws": False,
    "bonus_win_margin": None,
    "bonus_win_points": Decimal("0"),
    "bonus_loss_margin": None,
    "bonus_loss_points": Decimal("0"),
    "tiebreakers": ["wins", "name"],
}


def league_policy(*, allow_draws: bool = True) -> dict[str, Any]:
    policy = dict(LEAGUE_POLICY)
    policy["allow_draws"] = allow_draws
    return policy

PRESETS: dict[str, Preset] = {
    "soccer": {
        "label": "Soccer",
        "sport": "soccer",
        "kind": "sport",
        "format": "league",
        "table_mode": HEAD_TO_HEAD,
        "scoring_locked": True,
        "scoring_categories": [
            {"name": "Goal", "code": "goal", "points": Decimal("1"), "description": "Ball over the line."},
            {"name": "Own goal", "code": "own-goal", "points": Decimal("1"), "description": "Credited to the opposing side."},
            {"name": "Yellow card", "code": "yellow-card", "points": Decimal("0"), "affects_score": False},
            {"name": "Red card", "code": "red-card", "points": Decimal("0"), "affects_score": False},
        ],
        "points_policy": league_policy(),
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
        "scoring_locked": True,
        "scoring_categories": [
            {"name": "Try", "code": "try", "points": Decimal("5"), "description": "Grounding the ball over the line."},
            {"name": "Conversion", "code": "conversion", "points": Decimal("2"), "description": "Kick after a try."},
            {"name": "Penalty kick", "code": "penalty", "points": Decimal("3")},
            {"name": "Drop goal", "code": "drop-goal", "points": Decimal("3")},
        ],
        "points_policy": league_policy(),
        "rules": [
            {"name": "Match length", "description": "Two halves of 40 minutes."},
            {
                "name": "League points",
                "description": "3 points for a win, 1 for a draw, 0 for a loss.",
            },
        ],
    },
    "basketball": {
        "label": "Basketball",
        "sport": "basketball",
        "kind": "sport",
        "format": "league",
        "table_mode": HEAD_TO_HEAD,
        "scoring_locked": True,
        "scoring_categories": [
            {"name": "Free throw", "code": "free-throw", "points": Decimal("1"), "description": "A shot worth one point, taken from the free-throw line."},
            {"name": "Field goal", "code": "field-goal", "points": Decimal("2"), "description": "A shot worth two points, inside the three-point line."},
            {"name": "Three pointer", "code": "three-pointer", "points": Decimal("3"), "description": "A shot worth three points, from outside the three-point line."},
        ],
        "points_policy": league_policy(allow_draws=False),
        "rules": [{"name": "Match length", "description": "Four quarters of 12 minutes."}],
    },
    "tennis": {
        "label": "Tennis",
        "sport": "tennis",
        "kind": "sport",
        "format": "knockout",
        "table_mode": HEAD_TO_HEAD,
        "scoring_locked": True,
        "scoring_categories": [
            {"name": "Set won", "code": "set", "points": Decimal("1"), "description": "A set won. The match winner is the first to win the agreed number of sets."},
            {"name": "Game won", "code": "game", "points": Decimal("0"), "affects_score": False},
            {"name": "Ace", "code": "ace", "points": Decimal("0"), "affects_score": False},
        ],
        "points_policy": dict(KNOCKOUT_POLICY),
        "rules": [
            {"name": "Match format", "description": "Best of three tie-break sets."},
            {
                "name": "How the competition is decided",
                "description": "The winner of each match advances. There is no league table.",
            },
        ],
    },
    "squash": {
        "label": "Squash",
        "sport": "squash",
        "kind": "sport",
        "format": "league",
        "table_mode": HEAD_TO_HEAD,
        "scoring_locked": True,
        "scoring_categories": [
            {"name": "Game won", "code": "game", "points": Decimal("1"), "description": "A game won. Games are played to 11 points, and must be won by two."},
            {"name": "Rally won", "code": "rally", "points": Decimal("0"), "affects_score": False},
        ],
        "points_policy": league_policy(allow_draws=False),
        "rules": [{"name": "Match format", "description": "Best of five games to eleven points."}],
    },
    "golf": {
        "label": "Golf (stroke play)",
        "sport": "golf",
        "kind": "sport",
        "format": "league",
        "table_mode": POINTS_TABLE,
        "scoring_locked": True,
        "scoring_categories": [
            # Each stroke lowers the total, so the highest total is the fewest strokes.
            {
                "name": "Stroke",
                "code": "stroke",
                "points": Decimal("-1"),
                "description": "One stroke played. Each stroke is −1, so the highest total is the fewest strokes.",
            },
            {
                "name": "Penalty stroke",
                "code": "penalty-stroke",
                "points": Decimal("-1"),
                "description": "A penalty stroke under the Rules of Golf. It also counts as −1.",
            },
        ],
        "points_policy": dict(POINTS_ACCUMULATION_POLICY),
        "rules": [
            {
                "name": "Format",
                "description": "Stroke play over eighteen holes. Entrants do not play each other. The table ranks by total, highest first, which is the fewest strokes.",
            },
        ],
    },
    "custom": {
        "label": "Custom",
        "sport": "",
        "kind": "custom",
        "format": "league",
        "table_mode": POINTS_TABLE,
        "scoring_locked": False,
        "scoring_categories": [],
        "points_policy": dict(POINTS_ACCUMULATION_POLICY),
        "rules": [],
    },
}

PRESET_CHOICES = [(key, value["label"]) for key, value in PRESETS.items()]

SCORING_LOCKED_MESSAGE = (
    "This competition uses an official preset. Scoring categories and the "
    "points policy cannot be changed."
)


def scoring_is_locked(competition) -> bool:
    """True when the competition was created from an official preset."""

    settings = getattr(competition, "settings_json", None) or {}
    return bool(settings.get("scoring_locked"))


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
    table_mode = preset.get("table_mode", HEAD_TO_HEAD)
    settings["preset"] = preset_key
    settings["table_mode"] = table_mode
    settings["scoring_basis"] = "criteria" if table_mode == POINTS_TABLE else "results"
    settings["scoring_locked"] = bool(preset.get("scoring_locked", preset_key != "custom"))
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
