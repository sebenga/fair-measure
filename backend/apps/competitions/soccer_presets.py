"""Soccer codes and formats. Each one names how many start, the fewest who
may stay on, and the smallest squad that can take the field.
"""

from __future__ import annotations

from .catalog import OWN_GOAL, RED_CARD, YELLOW_CARD, _sport

FIFA = "FIFA"
IFAB = "IFAB Laws of the Game"
SAFA = "SAFA"


def _sheet(
    *,
    starters: int,
    min_on_field: int,
    min_squad: int,
    bench_max: int,
    max_substitutions: int,
    rolling: bool,
    keeper: str = "GK",
    lines: list[str] | None = None,
    formations: list[str] | None = None,
) -> dict:
    return {
        "starters": starters,
        "min_on_field": min_on_field,
        "min_squad": min_squad,
        "bench_max": bench_max,
        "max_substitutions": max_substitutions,
        "rolling_substitutions": rolling,
        "keeper": keeper,
        "lines": lines or ["DEF", "MID", "FWD"],
        "formations": formations or [],
    }


def _numbers_rule(sheet: dict) -> dict:
    on = sheet["starters"]
    fewest = sheet["min_on_field"]
    squad = sheet["min_squad"]
    bench = sheet["bench_max"]
    subs = sheet["max_substitutions"]
    rolling = (
        "Substitutions are rolling: a player taken off may come back on."
        if sheet["rolling_substitutions"]
        else "A player taken off cannot come back on."
    )
    return {
        "name": "Players",
        "description": (
            f"{on} start. A team may continue with {fewest}. "
            f"Name at least {squad} before kickoff, and up to {bench} substitutes. "
            f"Up to {subs} substitutions. {rolling}"
        ),
    }


GOAL_SCORES = [
    {"key": "goal", "label": "Goal", "value": 1, "affects_score": True},
    OWN_GOAL,
    YELLOW_CARD,
    RED_CARD,
]

FUTSAL_SCORES = [
    *GOAL_SCORES,
    {
        "key": "accumulated-foul",
        "label": "Accumulated foul",
        "value": 0,
        "affects_score": False,
        "description": (
            "A team's foul in the half. From the sixth onward the other side "
            "takes a direct free kick from 10 m, with no wall."
        ),
    },
]


def _football(**overrides) -> dict:
    sheet = overrides.get("team_sheet") or {}
    rules = list(overrides.pop("rules", None) or [])
    if sheet and not any(rule.get("name") == "Players" for rule in rules):
        rules.insert(0, _numbers_rule(sheet))
    overrides.setdefault("score_types", GOAL_SCORES)
    overrides.setdefault("formats_allowed", ["league", "knockout", "groups_knockout", "round_robin"])
    overrides.setdefault("family", "football")
    overrides.setdefault("family_label", "Football")
    locked = overrides.pop("locked", True)
    return _sport(
        icon="football-outline",
        locked=locked,
        rules=rules,
        **overrides,
    )


SOCCER_VARIANTS: dict[str, dict] = {
    "futsal": _football(
        label="Futsal",
        variant="futsal",
        variant_label="Futsal",
        sport="futsal",
        governing_body=FIFA,
        rulebook="FIFA Futsal Laws of the Game",
        description=(
            "Indoor 5-a-side under FIFA. Two halves of 20 minutes on a stopped clock. "
            "A goal is 1. An own goal scores 1 for the other side. Yellow and red cards "
            "are recorded without points. From a team's sixth foul in a half the other "
            "side takes a direct free kick from 10 m. A league draw shares the points. "
            "In a knockout, extra time and then penalties decide who advances."
        ),
        score_types=FUTSAL_SCORES,
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 20, "clock": "stopped"},
            {"unit": "extra_time", "count": 2, "minutes": 5, "clock": "stopped", "extra": True},
            {
                "unit": "penalties",
                "count": 1,
                "affects_total": False,
                "resolves_draw": True,
                "extra": True,
            },
        ],
        draw_resolution="penalties",
        team_sheet=_sheet(
            starters=5,
            min_on_field=3,
            min_squad=5,
            bench_max=9,
            max_substitutions=9,
            rolling=True,
            formations=["1-2-1", "1-1-2", "2-2"],
        ),
        rules=[
            {
                "name": "Accumulated fouls",
                "description": (
                    "Each team's fouls are counted per half. The sixth and later "
                    "concede a direct free kick from 10 m, with no wall."
                ),
            },
        ],
    ),
    "beach_soccer": _football(
        label="Beach soccer",
        sport="beach soccer",
        governing_body="FIFA / Beach Soccer Worldwide",
        rulebook="FIFA Beach Soccer Laws of the Game",
        variant="beach",
        variant_label="Beach",
        description=(
            "5-a-side on sand under FIFA and Beach Soccer Worldwide. Three periods "
            "of 12 minutes. A goal is 1. A game cannot end in a draw: extra time "
            "and then penalties decide it. League points: 3 for a win in normal "
            "time, 2 in extra time, 1 on penalties."
        ),
        draw_allowed=False,
        league_points={
            "win": 3,
            "draw": 0,
            "loss": 0,
            "extra_time_win": 2,
            "extra_time_loss": 0,
            "penalty_win": 1,
            "penalty_loss": 0,
        },
        match_structure=[
            {"unit": "period", "count": 3, "minutes": 12, "clock": "stopped"},
            {"unit": "extra_time", "count": 1, "minutes": 3, "clock": "stopped", "extra": True},
            {
                "unit": "penalties",
                "count": 1,
                "affects_total": False,
                "resolves_draw": True,
                "extra": True,
            },
        ],
        draw_resolution="penalties",
        team_sheet=_sheet(
            starters=5,
            min_on_field=3,
            min_squad=5,
            bench_max=7,
            max_substitutions=7,
            rolling=True,
            formations=["1-2-1", "1-3", "2-2"],
        ),
        rules=[
            {
                "name": "League points",
                "description": (
                    "A win in normal time is 3, a win in extra time is 2, a win on "
                    "penalties is 1. A loss is 0."
                ),
            },
            {
                "name": "No draws",
                "description": (
                    "If the score is level after three periods, one period of extra "
                    "time is played, then penalties."
                ),
            },
        ],
    ),
    "soccer_5": _football(
        label="5-a-side football",
        variant="five",
        variant_label="5-a-side",
        sport="small-sided football",
        governing_body=FIFA,
        local_body=SAFA,
        rulebook="Organiser playing rules (FIFA small-sided guidance)",
        description=(
            "Recreational and league 5-a-side. A goal is 1. Two halves of 20 minutes "
            "is the usual game. Rules vary by organiser: rolling substitutes are "
            "allowed, and there is no offside unless the organiser sets it. "
            "5 start; a team may continue with 3."
        ),
        match_structure=[{"unit": "half", "count": 2, "minutes": 20}],
        team_sheet=_sheet(
            starters=5,
            min_on_field=3,
            min_squad=5,
            bench_max=5,
            max_substitutions=5,
            rolling=True,
            formations=["1-2-1", "2-2", "1-3"],
        ),
    ),
    "soccer_6": _football(
        label="6-a-side football",
        variant="six",
        variant_label="6-a-side",
        sport="small-sided football",
        governing_body=FIFA,
        local_body=SAFA,
        rulebook="Organiser playing rules (FIFA small-sided guidance)",
        description=(
            "Recreational and league 6-a-side. A goal is 1. Two halves of 20 minutes "
            "is the usual game. Rules vary by organiser. 6 start; a team may continue "
            "with 4."
        ),
        match_structure=[{"unit": "half", "count": 2, "minutes": 20}],
        team_sheet=_sheet(
            starters=6,
            min_on_field=4,
            min_squad=6,
            bench_max=6,
            max_substitutions=6,
            rolling=True,
            formations=["2-2-1", "1-3-1", "2-3"],
        ),
    ),
    "soccer_7": _football(
        label="7-a-side football",
        variant="seven",
        variant_label="7-a-side",
        sport="small-sided football",
        governing_body=FIFA,
        local_body=SAFA,
        rulebook="Organiser playing rules (FIFA small-sided guidance)",
        description=(
            "Recreational and league 7-a-side. A goal is 1. Two halves of 25 minutes "
            "is the usual game. Rules vary by organiser. 7 start; a team may continue "
            "with 5."
        ),
        match_structure=[{"unit": "half", "count": 2, "minutes": 25}],
        team_sheet=_sheet(
            starters=7,
            min_on_field=5,
            min_squad=7,
            bench_max=7,
            max_substitutions=7,
            rolling=True,
            formations=["2-3-1", "3-2-1", "2-2-2"],
        ),
    ),
    "youth_4v4": _football(
        label="Youth football (4v4)",
        variant="youth_4v4",
        variant_label="Youth 4v4",
        sport="youth football",
        governing_body=FIFA,
        local_body=SAFA,
        rulebook="FIFA Grassroots / SAFA age-grade guidelines",
        description=(
            "The youngest age grades, typically U6–U8. 4v4 on a small pitch, two "
            "halves of 10 minutes. A goal is 1. No offside. 4 start; a team may "
            "continue with 3."
        ),
        match_structure=[{"unit": "half", "count": 2, "minutes": 10}],
        team_sheet=_sheet(
            starters=4,
            min_on_field=3,
            min_squad=4,
            bench_max=4,
            max_substitutions=4,
            rolling=True,
            keeper="",
            lines=["FWD"],
            formations=["2-2", "1-2-1"],
        ),
    ),
    "youth_7v7": _football(
        label="Youth football (7v7)",
        variant="youth_7v7",
        variant_label="Youth 7v7",
        sport="youth football",
        governing_body=FIFA,
        local_body=SAFA,
        rulebook="FIFA Grassroots / SAFA age-grade guidelines",
        description=(
            "Middle age grades, typically U9–U12. 7v7, two halves of 20 minutes. "
            "A goal is 1. 7 start; a team may continue with 5."
        ),
        match_structure=[{"unit": "half", "count": 2, "minutes": 20}],
        team_sheet=_sheet(
            starters=7,
            min_on_field=5,
            min_squad=7,
            bench_max=5,
            max_substitutions=5,
            rolling=True,
            formations=["2-3-1", "3-2-1"],
        ),
    ),
    "youth_9v9": _football(
        label="Youth football (9v9)",
        variant="youth_9v9",
        variant_label="Youth 9v9",
        sport="youth football",
        governing_body=FIFA,
        local_body=SAFA,
        rulebook="FIFA Grassroots / SAFA age-grade guidelines",
        description=(
            "Older youth grades, typically U13–U15, before 11-a-side. 9v9, two "
            "halves of 25 minutes. A goal is 1. 9 start; a team may continue with 6."
        ),
        match_structure=[{"unit": "half", "count": 2, "minutes": 25}],
        team_sheet=_sheet(
            starters=9,
            min_on_field=6,
            min_squad=9,
            bench_max=7,
            max_substitutions=7,
            rolling=True,
            formations=["3-3-2", "3-4-1", "4-3-1"],
        ),
    ),
    "blind_football": _football(
        label="Blind football (5-a-side)",
        variant="blind",
        variant_label="Blind",
        sport="blind football",
        governing_body="IBSA",
        rulebook="IBSA Blind Football Rules",
        description=(
            "Paralympic 5-a-side (four outfield players in eyeshades and a sighted "
            "goalkeeper) with a sound ball, under IBSA. Two halves of 20 minutes. "
            "A goal is 1. 5 start; a team may continue with 3."
        ),
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 20},
            {"unit": "penalties", "count": 1, "affects_total": False, "resolves_draw": True},
        ],
        draw_resolution="penalties",
        team_sheet=_sheet(
            starters=5,
            min_on_field=3,
            min_squad=5,
            bench_max=5,
            max_substitutions=5,
            rolling=True,
            formations=["1-2-1", "1-3"],
        ),
    ),
    "cp_football": _football(
        label="CP football (7-a-side)",
        variant="cp",
        variant_label="CP 7-a-side",
        sport="CP football",
        governing_body="IFCPF",
        rulebook="IFCPF CP Football Rules",
        description=(
            "Football for players with cerebral palsy, 7-a-side under IFCPF. Two "
            "halves of 30 minutes. A goal is 1. 7 start; a team may continue with 4."
        ),
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 30},
            {"unit": "extra_time", "count": 2, "minutes": 10},
            {"unit": "penalties", "count": 1, "affects_total": False, "resolves_draw": True},
        ],
        draw_resolution="penalties",
        team_sheet=_sheet(
            starters=7,
            min_on_field=4,
            min_squad=7,
            bench_max=5,
            max_substitutions=5,
            rolling=False,
            formations=["2-3-1", "3-2-1"],
        ),
    ),
    "amputee_football": _football(
        label="Amputee football (7-a-side)",
        variant="amputee",
        variant_label="Amputee",
        sport="amputee football",
        governing_body="WAFF",
        rulebook="WAFF Amputee Football Laws",
        description=(
            "7-a-side (six outfield players on crutches and a goalkeeper) under the "
            "World Amputee Football Federation. Two halves of 25 minutes. A goal is 1. "
            "7 start; a team may continue with 5."
        ),
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 25},
            {"unit": "penalties", "count": 1, "affects_total": False, "resolves_draw": True},
        ],
        draw_resolution="penalties",
        team_sheet=_sheet(
            starters=7,
            min_on_field=5,
            min_squad=7,
            bench_max=5,
            max_substitutions=5,
            rolling=True,
            formations=["2-3-1", "3-2-1"],
        ),
    ),
    "powerchair_football": _football(
        label="Powerchair football",
        variant="powerchair",
        variant_label="Powerchair",
        sport="powerchair football",
        governing_body="FIPFA",
        rulebook="FIPFA Powerchair Football Laws",
        description=(
            "4-a-side powered-wheelchair football under FIPFA. Two halves of 20 "
            "minutes. A goal is 1. 4 start; a team may continue with 2."
        ),
        match_structure=[{"unit": "half", "count": 2, "minutes": 20}],
        team_sheet=_sheet(
            starters=4,
            min_on_field=2,
            min_squad=4,
            bench_max=4,
            max_substitutions=4,
            rolling=True,
            keeper="",
            formations=["1-2", "2-1"],
        ),
    ),
    "walking_football": _football(
        label="Walking football",
        variant="walking",
        variant_label="Walking",
        locked=False,
        sport="walking football",
        governing_body=FIFA,
        local_body=SAFA,
        rulebook="FIFA Walking Football Laws of the Game",
        description=(
            "No running and no contact, aimed at older players. 6-a-side is the "
            "usual game. Two halves of 20 minutes. A goal is 1. 6 start; a team "
            "may continue with 5."
        ),
        match_structure=[{"unit": "half", "count": 2, "minutes": 20}],
        team_sheet=_sheet(
            starters=6,
            min_on_field=5,
            min_squad=6,
            bench_max=6,
            max_substitutions=6,
            rolling=True,
            formations=["2-2-1", "2-3"],
        ),
        rules=[
            {
                "name": "Walking only",
                "description": "A player who runs is penalised. There is no tackling.",
            },
        ],
    ),
    "arena_soccer": _football(
        label="Indoor / arena soccer",
        variant="arena",
        variant_label="Arena",
        locked=False,
        sport="arena soccer",
        governing_body="FIFA",
        rulebook="Arena / indoor soccer playing rules (MASL and similar)",
        description=(
            "A walled 6-a-side game with boards, played mainly in the US. Four "
            "quarters of 15 minutes. A goal is 1. The boards stay in play. 6 start; "
            "a team may continue with 4."
        ),
        match_structure=[{"unit": "quarter", "count": 4, "minutes": 15}],
        team_sheet=_sheet(
            starters=6,
            min_on_field=4,
            min_squad=6,
            bench_max=8,
            max_substitutions=8,
            rolling=True,
            formations=["1-2-2", "2-2-1"],
        ),
    ),
    "street_football": _football(
        label="Street football",
        variant="street",
        variant_label="Street",
        locked=False,
        sport="street football",
        governing_body=FIFA,
        rulebook="Organiser / street football playing rules",
        description=(
            "Informal 5-a-side, often on a yard or court. A goal is 1. Time is set "
            "by the organiser. Rolling substitutes. 5 start; a team may continue with 3."
        ),
        match_structure=[{"unit": "half", "count": 2, "minutes": 15}],
        team_sheet=_sheet(
            starters=5,
            min_on_field=3,
            min_squad=5,
            bench_max=5,
            max_substitutions=5,
            rolling=True,
            formations=["2-2", "1-2-1"],
        ),
    ),
    "freestyle_football": {
        **_sport(
            label="Freestyle football",
            icon="football-outline",
            sport="freestyle football",
            family="football",
            family_label="Football",
            variant="freestyle",
            variant_label="Freestyle",
            kind="sport",
            format="league",
            formats_allowed=["league"],
            contest_type="accumulation",
            participant_type="individual",
            locked=False,
            governing_body="World Freestyle Football Association",
            rulebook="WFFA judging criteria",
            description=(
                "Judged on tricks and skill rather than goals. Each routine is marked "
                "from 0 to 10 for difficulty, variety and control. The highest total "
                "wins. One person takes the field."
            ),
            score_types=[
                {
                    "key": "difficulty",
                    "label": "Difficulty",
                    "value": 1,
                    "affects_score": True,
                    "description": "How hard the tricks are, from 0 to 10.",
                },
                {
                    "key": "variety",
                    "label": "Variety",
                    "value": 1,
                    "affects_score": True,
                    "description": "How many different tricks are shown, from 0 to 10.",
                },
                {
                    "key": "execution",
                    "label": "Control",
                    "value": 1,
                    "affects_score": True,
                    "description": "How cleanly the routine is controlled, from 0 to 10.",
                },
            ],
            match_structure=[{"unit": "routine", "count": 2}],
            win_condition="highest_total",
            draw_allowed=True,
            draw_resolution="replay",
            league_points={"win": 0, "draw": 0, "loss": 0},
            tiebreakers=["points", "name"],
            accumulation_ranking="highest_first",
            table_mode="points",
            result_type="judged_score",
            result_config={
                "combine": "average",
                "count_best": 1,
                "max_score": 10,
                "decimals": 2,
            },
            rules=[
                {
                    "name": "Players",
                    "description": "One person performs. The minimum is 1.",
                },
                {
                    "name": "Judging",
                    "description": (
                        "Judges mark difficulty, variety and control. Goals are not recorded."
                    ),
                },
            ],
        ),
        "team_sheet": _sheet(
            starters=1,
            min_on_field=1,
            min_squad=1,
            bench_max=0,
            max_substitutions=0,
            rolling=False,
            keeper="",
            lines=[],
            formations=[],
        ),
    },
    "soccer_women": _football(
        label="Women's football",
        variant="women",
        variant_label="Women's",
        sport="soccer",
        category="women",
        governing_body=FIFA,
        local_body=SAFA,
        rulebook=IFAB,
        description=(
            "The same Laws as the men's 11-a-side game, run as a women's category. "
            "Each goal is worth 1. Two halves of 45 minutes. 11 start; a team may "
            "continue with 7. A squad needs 14 accepted players. A league draw "
            "shares the points. In a knockout, extra time and then a penalty "
            "shoot-out decide who advances."
        ),
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 45},
            {"unit": "extra_time", "count": 2, "minutes": 15},
            {"unit": "penalties", "count": 1, "affects_total": False, "resolves_draw": True},
        ],
        draw_resolution="penalties",
        team_sheet=_sheet(
            starters=11,
            min_on_field=7,
            min_squad=14,
            bench_max=12,
            max_substitutions=5,
            rolling=False,
            formations=[
                "4-4-2",
                "4-3-3",
                "4-2-3-1",
                "4-1-4-1",
                "3-5-2",
                "3-4-3",
                "5-3-2",
            ],
        ),
        rules=[
            {
                "name": "Category",
                "description": "Women's competitions use the IFAB Laws. The category is recorded separately from the men's game.",
            },
            {
                "name": "Knockout",
                "description": "If the match is level, extra time is played, then penalties decide who advances.",
            },
        ],
    ),
}
