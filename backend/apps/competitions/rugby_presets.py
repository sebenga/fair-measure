"""Rugby union and rugby league variants. Fifteens and thirteens live in catalog.py
so existing competitions keep their preset keys. These add the other locked codes.
"""

from __future__ import annotations

from .catalog import RED_CARD, YELLOW_CARD, _sport

UNION_SCORES = [
    {"key": "try", "label": "Try", "value": 5, "affects_score": True},
    {"key": "conversion", "label": "Conversion", "value": 2, "affects_score": True},
    {"key": "penalty-goal", "label": "Penalty goal", "value": 3, "affects_score": True},
    {"key": "drop-goal", "label": "Drop goal", "value": 3, "affects_score": True},
    {"key": "penalty-try", "label": "Penalty try", "value": 7, "affects_score": True},
    YELLOW_CARD,
    RED_CARD,
]

LEAGUE_SCORES = [
    {"key": "try", "label": "Try", "value": 4, "affects_score": True},
    {"key": "conversion", "label": "Conversion", "value": 2, "affects_score": True},
    {"key": "penalty-goal", "label": "Penalty goal", "value": 2, "affects_score": True},
    {"key": "field-goal", "label": "Field goal", "value": 1, "affects_score": True},
    YELLOW_CARD,
    RED_CARD,
]

SEVENS_POINTS = {"win": 3, "draw": 2, "loss": 1}
LEAGUE_POINTS = {"win": 2, "draw": 1, "loss": 0}


def _sheet(
    *,
    starters: int,
    bench_max: int,
    min_on_field: int | None = None,
    min_squad: int | None = None,
    rolling: bool = False,
    max_substitutions: int | None = None,
    extra: dict | None = None,
) -> dict:
    sheet = {
        "starters": starters,
        "min_on_field": min_on_field if min_on_field is not None else max(starters - 4, 1),
        "min_squad": min_squad if min_squad is not None else starters,
        "bench_max": bench_max,
        "max_substitutions": max_substitutions if max_substitutions is not None else bench_max,
        "rolling_substitutions": rolling,
    }
    if extra:
        sheet.update(extra)
    return sheet


def _union(**overrides) -> dict:
    return _sport(
        icon="american-football-outline",
        locked=True,
        family="rugby_union",
        family_label="Rugby union",
        governing_body=overrides.pop("governing_body", "World Rugby"),
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
        **overrides,
    )


def _league(**overrides) -> dict:
    return _sport(
        icon="american-football-outline",
        locked=True,
        family="rugby_league",
        family_label="Rugby league",
        governing_body=overrides.pop("governing_body", "International Rugby League"),
        league_points=overrides.pop("league_points", LEAGUE_POINTS),
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
        **overrides,
    )


RUGBY_VARIANTS: dict[str, dict] = {
    "rugby_tens": _union(
        label="Rugby tens",
        variant="tens",
        variant_label="Tens",
        sport="rugby tens",
        rulebook="World Rugby Laws of the Game (Tens variations)",
        description=(
            "Invitational 10-a-side. Scoring matches fifteens. Two halves of about "
            "10 minutes. Pool points follow sevens: a win is 3, a draw 2, a loss 1."
        ),
        score_types=UNION_SCORES,
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 10, "clock": "running"},
            {"unit": "sudden_death", "count": 1, "minutes": 5, "repeat": True, "extra": True},
        ],
        draw_resolution="sudden_death",
        league_points=SEVENS_POINTS,
        tiebreakers=["points", "score_difference", "category:try", "head_to_head"],
        team_sheet=_sheet(starters=10, bench_max=5, min_on_field=7, rolling=True),
        rules=[
            {"name": "League points", "description": "A win is 3, a draw is 2, a loss is 1."},
            {"name": "Players", "description": "10 start, with rolling substitutes."},
        ],
    ),
    "rugby_beach": _union(
        label="Beach rugby",
        variant="beach",
        variant_label="Beach",
        sport="beach rugby",
        rulebook="World Rugby Beach Rugby guidelines",
        description=(
            "5-a-side on sand. Only tries count, each worth 1. Two halves of 5 "
            "minutes. A level game goes to sudden-death extra time (golden try)."
        ),
        score_types=[
            {"key": "try", "label": "Try", "value": 1, "affects_score": True},
            YELLOW_CARD,
            RED_CARD,
        ],
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 5, "clock": "running"},
            {"unit": "sudden_death", "count": 1, "repeat": True, "golden": True, "extra": True},
        ],
        draw_resolution="sudden_death",
        league_points={"win": 3, "draw": 0, "loss": 0},
        draw_allowed=True,
        tiebreakers=["points", "score_difference", "score_for"],
        team_sheet=_sheet(starters=5, bench_max=5, min_on_field=3, rolling=True),
        rules=[
            {"name": "Scoring", "description": "Only tries count. Each try is 1 point."},
            {"name": "Players", "description": "5 start, with rolling substitutes."},
            {
                "name": "Ties",
                "description": "A level knockout is decided by a golden try in extra time.",
            },
        ],
    ),
    "wheelchair_rugby": _union(
        label="Wheelchair rugby",
        variant="wheelchair",
        variant_label="Wheelchair",
        sport="wheelchair rugby",
        governing_body="World Wheelchair Rugby",
        rulebook="World Wheelchair Rugby International Rules",
        description=(
            "A Paralympic indoor game. 4 on court, squad of 12, classification "
            "points on court may not exceed 8.0. A goal is 1 when a player "
            "crosses the line with the ball. Four periods of 8 minutes on a "
            "stopped clock. No draws: 3-minute overtimes until there is a winner."
        ),
        score_types=[{"key": "goal", "label": "Goal", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "period", "count": 4, "minutes": 8, "clock": "stopped"},
            {
                "unit": "overtime",
                "count": 1,
                "minutes": 3,
                "clock": "stopped",
                "repeat": True,
                "extra": True,
            },
        ],
        draw_allowed=False,
        draw_resolution="sudden_death",
        league_points={"win": 3, "draw": 0, "loss": 0},
        tiebreakers=["points", "score_difference", "score_for"],
        team_sheet=_sheet(
            starters=4,
            bench_max=8,
            min_on_field=3,
            min_squad=4,
            rolling=True,
            extra={"classification_max": 8.0, "squad_max": 12},
        ),
        rules=[
            {
                "name": "Classification",
                "description": "The four players on court may not total more than 8.0 classification points.",
            },
            {"name": "Players", "description": "4 on court from a squad of up to 12."},
            {
                "name": "Ties",
                "description": "A game cannot end in a draw. Overtime periods of 3 minutes are played until a winner.",
            },
        ],
    ),
    "touch_rugby": _union(
        label="Touch rugby",
        variant="touch",
        variant_label="Touch",
        sport="touch rugby",
        governing_body="Federation of International Touch",
        rulebook="FIT Playing Rules",
        description=(
            "Non-contact, played to 6 touches. 6 on the field with rolling "
            "substitutes. A touchdown is 1. Two halves of 20 minutes. Draws are "
            "allowed in pools. A knockout uses drop-off: players are removed "
            "progressively until a side leads."
        ),
        score_types=[{"key": "touchdown", "label": "Touchdown", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 20, "clock": "running"},
            {"unit": "drop_off", "count": 1, "repeat": True, "extra": True},
        ],
        draw_resolution="drop_off",
        league_points={"win": 3, "draw": 1, "loss": 0},
        tiebreakers=["points", "score_difference", "score_for"],
        team_sheet=_sheet(starters=6, bench_max=8, min_on_field=4, rolling=True),
        rules=[
            {"name": "Players", "description": "6 on the field, with rolling substitutes."},
            {"name": "Touch", "description": "A team has 6 touches before handing over the ball."},
            {
                "name": "Knockout",
                "description": "A level knockout is decided by drop-off: players are removed until a side leads.",
            },
        ],
    ),
    "tag_rugby": _union(
        label="Tag rugby",
        variant="tag",
        variant_label="Tag",
        sport="tag rugby",
        rulebook="Tag rugby playing rules (organiser / youth)",
        description=(
            "Non-contact, popular for youth and social play. 7 is the usual "
            "on-field number. A try is 1. Two halves of 20 minutes. Draws are allowed."
        ),
        score_types=[{"key": "try", "label": "Try", "value": 1, "affects_score": True}],
        match_structure=[{"unit": "half", "count": 2, "minutes": 20, "clock": "running"}],
        draw_allowed=True,
        draw_resolution="replay",
        league_points={"win": 3, "draw": 1, "loss": 0},
        tiebreakers=["points", "score_difference", "score_for"],
        team_sheet=_sheet(starters=7, bench_max=5, min_on_field=5, rolling=True),
        rules=[
            {"name": "Players", "description": "7 start, with rolling substitutes."},
            {"name": "Scoring", "description": "A try is 1 point. There are no conversions."},
        ],
    ),
    "rugby_nines": _league(
        label="Rugby league nines",
        variant="nines",
        variant_label="Nines",
        sport="rugby league nines",
        rulebook="International Rugby League Nines laws",
        description=(
            "Short-form rugby league. A try is 4, or 5 from the bonus try zone. "
            "A conversion is 2. Two halves of 9 minutes. A level knockout goes "
            "to golden point."
        ),
        score_types=[
            {"key": "try", "label": "Try", "value": 4, "affects_score": True},
            {
                "key": "bonus-try",
                "label": "Bonus-zone try",
                "value": 5,
                "affects_score": True,
                "description": "A try scored from the bonus try zone.",
            },
            {"key": "conversion", "label": "Conversion", "value": 2, "affects_score": True},
            YELLOW_CARD,
            RED_CARD,
        ],
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 9, "clock": "running"},
            {"unit": "extra_time", "count": 1, "extra": True, "golden": True},
        ],
        draw_resolution="sudden_death",
        tiebreakers=["points", "score_difference", "score_for"],
        team_sheet=_sheet(starters=9, bench_max=5, min_on_field=7, rolling=True),
        rules=[
            {"name": "League points", "description": "A win is 2 points, a draw is 1, a loss is 0."},
            {"name": "Players", "description": "9 start, with rolling substitutes."},
            {"name": "Knockout", "description": "If the match is level, golden point decides it."},
        ],
    ),
    "wheelchair_rugby_league": _league(
        label="Wheelchair rugby league",
        variant="wheelchair",
        variant_label="Wheelchair",
        sport="wheelchair rugby league",
        rulebook="International Rugby League Wheelchair Laws",
        description=(
            "5 on the field. Scoring matches thirteens: a try is 4, a conversion "
            "2, a penalty 2, a drop goal 1. Two halves of 40 minutes. Golden "
            "point in knockouts."
        ),
        score_types=LEAGUE_SCORES,
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 40, "clock": "running"},
            {"unit": "extra_time", "count": 1, "extra": True, "golden": True},
        ],
        draw_resolution="sudden_death",
        tiebreakers=["points", "score_difference", "score_for"],
        team_sheet=_sheet(starters=5, bench_max=5, min_on_field=4, rolling=True),
        rules=[
            {"name": "League points", "description": "A win is 2 points, a draw is 1, a loss is 0."},
            {"name": "Players", "description": "5 on the field, with rolling substitutes."},
            {"name": "Knockout", "description": "If the match is level, golden point decides it."},
        ],
    ),
}
