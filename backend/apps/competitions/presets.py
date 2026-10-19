"""Starting-point presets.

A preset is data: how entrants score, how a match is split into units, and how
a table is ordered. The engine reads those fields and does not branch on the
preset key.
"""

from __future__ import annotations

from typing import TypedDict

from .catalog import OWN_GOAL, RED_CARD, YELLOW_CARD


class Preset(TypedDict, total=False):
    label: str
    icon: str
    description: str
    sport: str
    kind: str
    format: str
    contest_type: str
    participant_type: str
    formats_allowed: list[str]
    score_types: list[dict]
    match_structure: list[dict]
    win_condition: str
    draw_allowed: bool
    draw_resolution: str
    league_points: dict
    tiebreakers: list[str]
    accumulation_ranking: str
    locked: bool
    table_mode: str
    rules: list[dict]


POINTS_TABLE = "points"
HEAD_TO_HEAD = "head_to_head"

SCORING_LOCKED_MESSAGE = "This preset locks scoring. Duplicate the competition to change it."

# The model uses group_knockout; presets say groups_knockout.
FORMAT_TO_MODEL = {
    "league": "league",
    "knockout": "knockout",
    "groups_knockout": "group_knockout",
    "round_robin": "league",
    "ladder": "ladder",
}


def allowed_model_formats(settings: dict | None) -> set[str] | None:
    """Model formats a competition may use, or None when anything goes."""

    allowed = (settings or {}).get("formats_allowed")
    if not allowed:
        return None
    return {FORMAT_TO_MODEL.get(item, item) for item in allowed}


def format_allowed(settings: dict | None, model_format: str | None) -> bool:
    allowed = allowed_model_formats(settings)
    if allowed is None or not model_format or model_format == "freeform":
        return True
    return model_format in allowed


def _categories(score_types: list[dict]) -> list[dict]:
    rows = []
    for item in score_types:
        rows.append(
            {
                "name": item["label"],
                "code": item["key"],
                "points": item["value"],
                "affects_score": item.get("affects_score", True),
                "description": item.get("description", ""),
            }
        )
    return rows


def _policy(preset: Preset) -> dict:
    league = preset.get("league_points") or {"win": 0, "draw": 0, "loss": 0}
    return {
        "win_points": league.get("win", 0),
        "draw_points": league.get("draw", 0),
        "loss_points": league.get("loss", 0),
        "bonus_win_points": 0,
        "bonus_loss_points": 0,
        "tiebreakers": list(preset.get("tiebreakers") or ["points", "score_difference", "score_for"]),
    }


SOCCER: Preset = {
    "label": "Soccer",
    "icon": "football-outline",
    "description": (
        "Each goal is worth 1. An own goal scores 1 for the other side. "
        "Yellow and red cards are recorded without points. "
        "A league match is two halves of 45 minutes. "
        "A draw shares the points. In a knockout, a draw is played out with "
        "extra time and then a penalty shoot-out. The table ranks by points, "
        "then goal difference, then goals scored, then the head-to-head result."
    ),
    "sport": "soccer",
    "kind": "sport",
    "format": "league",
    "contest_type": "head_to_head",
    "participant_type": "team",
    "formats_allowed": ["league", "knockout", "groups_knockout", "round_robin"],
    "score_types": [
        {"key": "goal", "label": "Goal", "value": 1, "affects_score": True},
        OWN_GOAL,
        YELLOW_CARD,
        RED_CARD,
    ],
    "match_structure": [
        {"unit": "half", "count": 2, "minutes": 45, "affects_total": True},
        {"unit": "extra_time", "count": 2, "minutes": 15, "affects_total": True},
        {"unit": "penalties", "count": 1, "affects_total": False, "resolves_draw": True},
    ],
    "win_condition": "highest_total",
    "draw_allowed": True,
    "draw_resolution": "penalties",
    "league_points": {"win": 3, "draw": 1, "loss": 0},
    "tiebreakers": ["points", "score_difference", "score_for", "head_to_head"],
    "locked": True,
    "rules": [
        {
            "name": "League points",
            "description": "A win is 3 points, a draw is 1, a loss is 0.",
        },
        {
            "name": "Knockout",
            "description": "If the match is level, extra time is played, then penalties decide who advances.",
        },
    ],
}

GOLF_STROKE: Preset = {
    "label": "Golf (stroke play)",
    "icon": "golf-outline",
    "description": (
        "Each hole is scored in strokes. After 18 holes the lowest total wins. "
        "If two players finish on the same total, the last hole is compared, "
        "then the one before it, back to the first."
    ),
    "sport": "golf",
    "kind": "sport",
    "format": "league",
    "contest_type": "accumulation",
    "participant_type": "individual",
    "formats_allowed": ["league"],
    "score_types": [
        {
            "key": "stroke",
            "label": "Stroke",
            "value": 1,
            "affects_score": True,
            "description": "One stroke on a hole. The lowest total wins.",
        },
    ],
    "match_structure": [
        {"unit": "hole", "count": 18, "affects_total": True},
    ],
    "win_condition": "lowest_total",
    "draw_allowed": True,
    "draw_resolution": "sudden_death",
    "league_points": {"win": 0, "draw": 0, "loss": 0},
    "tiebreakers": ["countback"],
    "accumulation_ranking": "lowest_first",
    "locked": True,
    "rules": [
        {
            "name": "Stroke play",
            "description": "Add a stroke every time the ball is played. The lowest 18-hole total ranks first.",
        },
    ],
}

CUSTOM: Preset = {
    "label": "Custom",
    "icon": "construct-outline",
    "description": "You define how points are earned. Scoring stays editable.",
    "sport": "",
    "kind": "custom",
    "format": "freeform",
    "contest_type": "accumulation",
    "participant_type": "team",
    "formats_allowed": ["league", "knockout", "ladder"],
    "score_types": [],
    "match_structure": [],
    "win_condition": "highest_total",
    "draw_allowed": True,
    "draw_resolution": "replay",
    "league_points": {"win": 0, "draw": 0, "loss": 0},
    "tiebreakers": ["points", "score_difference", "score_for"],
    "accumulation_ranking": "highest_first",
    "locked": False,
    "table_mode": POINTS_TABLE,
    "rules": [],
}

from .catalog import CATALOG

PRESETS: dict[str, Preset] = {
    "soccer": SOCCER,
    "golf_stroke": GOLF_STROKE,
    **CATALOG,
    "custom": CUSTOM,
}

PRESET_CHOICES = [(key, value["label"]) for key, value in PRESETS.items()]


def scoring_is_locked(competition) -> bool:
    settings = competition.settings_json or {}
    if settings.get("lock_when_started"):
        status = getattr(competition, "status", None)
        return status not in {None, "", "draft"}
    if "scoring_locked" in settings:
        return bool(settings["scoring_locked"])
    if "locked" in settings:
        return bool(settings["locked"])
    preset = PRESETS.get(settings.get("preset") or "")
    if preset is None:
        return False
    return bool(preset.get("locked", preset.get("key") != "custom"))


def public_preset(key: str, preset: Preset) -> dict:
    categories = _categories(preset.get("score_types") or [])
    contest = preset.get("contest_type", HEAD_TO_HEAD)
    table_mode = preset.get("table_mode") or (
        POINTS_TABLE if contest == "accumulation" else HEAD_TO_HEAD
    )
    return {
        "key": key,
        "label": preset["label"],
        "icon": preset.get("icon", "trophy-outline"),
        "description": preset.get("description", ""),
        "sport": preset.get("sport", ""),
        "kind": preset.get("kind", "sport"),
        "format": preset.get("format", "league"),
        "formats_allowed": list(preset.get("formats_allowed") or []),
        "contest_type": contest,
        "participant_type": preset.get("participant_type", "team"),
        "score_types": list(preset.get("score_types") or []),
        "match_structure": list(preset.get("match_structure") or []),
        "win_condition": preset.get("win_condition", "highest_total"),
        "draw_allowed": bool(preset.get("draw_allowed", True)),
        "draw_resolution": preset.get("draw_resolution", "replay"),
        "league_points": dict(preset.get("league_points") or {}),
        "tiebreakers": list(preset.get("tiebreakers") or []),
        "accumulation_ranking": preset.get("accumulation_ranking"),
        "locked": bool(preset.get("locked", key != "custom")),
        "lock_when_started": bool(preset.get("lock_when_started")),
        "table_mode": table_mode,
        "scoring_locked": bool(preset.get("locked", key != "custom")),
        "scoring_categories": [
            {
                "name": item["name"],
                "code": item["code"],
                "points": str(item["points"]),
                "affects_score": item.get("affects_score", True),
                "description": item.get("description", ""),
            }
            for item in categories
        ],
        "rules": list(preset.get("rules") or []),
    }


def game_time_from_structure(structure: list[dict] | None) -> tuple[int | None, int]:
    """Regulation minutes from the first timed block, overtime from the timed blocks after it."""

    timed = [block for block in structure or [] if block.get("minutes")]
    if not timed:
        return None, 0
    first, *rest = timed
    regulation = int(first.get("count") or 1) * int(first["minutes"])
    overtime = sum(int(block.get("count") or 1) * int(block["minutes"]) for block in rest)
    return regulation, overtime


def default_game_time(settings: dict | None) -> tuple[int | None, int]:
    """The competition's time limit and overtime, falling back to its match structure."""

    settings = settings or {}
    derived_limit, derived_overtime = game_time_from_structure(settings.get("match_structure"))
    try:
        limit = int(settings.get("time_limit_minutes") or 0) or None
    except (TypeError, ValueError):
        limit = None
    raw_overtime = settings.get("overtime_minutes")
    try:
        overtime = derived_overtime if raw_overtime is None else max(int(raw_overtime), 0)
    except (TypeError, ValueError):
        overtime = derived_overtime
    return limit or derived_limit, overtime


def apply_preset(competition, preset_key: str) -> None:
    """Copy a preset's scoring, structure, and ranking onto a competition."""

    from .models import MatchUnit, PointsPolicy, Rule, ScoringCategory

    preset = PRESETS.get(preset_key)
    if preset is None:
        raise ValueError(f"Unknown preset '{preset_key}'.")

    # Re-applying a preset updates categories it already added instead of
    # stacking a second copy of every score type.
    for index, item in enumerate(_categories(preset.get("score_types") or [])):
        values = {
            "name": item["name"],
            "description": item.get("description", ""),
            "points": item["points"],
            "affects_score": item.get("affects_score", True),
            "display_order": index,
        }
        current = competition.scoring_categories.filter(code=item["code"]).first()
        if current is None:
            ScoringCategory.objects.create(competition=competition, code=item["code"], **values)
        else:
            for field, value in values.items():
                setattr(current, field, value)
            current.save()

    PointsPolicy.objects.update_or_create(
        competition=competition, defaults=_policy(preset)
    )

    competition.match_units.all().delete()
    MatchUnit.objects.bulk_create(
        [
            MatchUnit(
                competition=competition,
                display_order=index,
                unit=block.get("unit") or "unit",
                count=int(block.get("count") or block.get("best_of") or 1),
                minutes=block.get("minutes"),
                best_of=block.get("best_of"),
                first_to=block.get("first_to"),
                win_by=block.get("win_by"),
                tiebreak_at=block.get("tiebreak_at"),
                affects_total=bool(block.get("affects_total", True)),
                resolves_draw=bool(block.get("resolves_draw", False)),
            )
            for index, block in enumerate(preset.get("match_structure") or [])
        ]
    )

    contest = preset.get("contest_type", HEAD_TO_HEAD)
    table_mode = preset.get("table_mode") or (
        POINTS_TABLE if contest == "accumulation" else HEAD_TO_HEAD
    )
    locked = bool(preset.get("locked", preset_key != "custom"))
    settings = dict(competition.settings_json or {})
    settings.update(
        {
            "preset": preset_key,
            "table_mode": table_mode,
            "scoring_basis": "criteria" if table_mode == POINTS_TABLE else "results",
            "scoring_locked": locked,
            "locked": locked,
            "icon": preset.get("icon", ""),
            "description": preset.get("description", ""),
            "contest_type": contest,
            "participant_type": preset.get("participant_type", "team"),
            "formats_allowed": list(preset.get("formats_allowed") or []),
            "match_structure": list(preset.get("match_structure") or []),
            "win_condition": preset.get("win_condition", "highest_total"),
            "draw_allowed": bool(preset.get("draw_allowed", True)),
            "draw_resolution": preset.get("draw_resolution", "replay"),
            "league_points": dict(preset.get("league_points") or {}),
            "tiebreakers": list(preset.get("tiebreakers") or []),
            "accumulation_ranking": preset.get("accumulation_ranking"),
            "score_types": list(preset.get("score_types") or []),
            "participant_types": list(preset.get("participant_types") or []),
            "bonuses": list(preset.get("bonuses") or []),
            "rate_basis": preset.get("rate_basis") or {},
            "countback_windows": list(preset.get("countback_windows") or []),
            "placing_points": list(preset.get("placing_points") or []),
            "handicap": bool(preset.get("handicap")),
            "performance": preset.get("performance"),
            "lock_when_started": bool(preset.get("lock_when_started")),
            "target": preset.get("target"),
            "category_better": {
                item["key"]: item["better"]
                for item in (preset.get("score_types") or [])
                if item.get("better")
            },
        }
    )
    regulation, overtime = game_time_from_structure(preset.get("match_structure"))
    if regulation and not settings.get("time_limit_minutes"):
        settings["time_limit_minutes"] = regulation
        settings.setdefault("overtime_minutes", overtime)
    competition.settings_json = settings
    competition.save(update_fields=["settings_json", "updated_at"])

    existing_rules = set(competition.rules.values_list("name", flat=True))
    Rule.objects.bulk_create(
        [
            Rule(
                competition=competition,
                name=item["name"],
                description=item["description"],
                display_order=index,
            )
            for index, item in enumerate(preset.get("rules") or [])
            if item["name"] not in existing_rules
        ]
    )
