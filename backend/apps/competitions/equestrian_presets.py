"""Locked equestrian presets. The engine reads this data and does not branch on it.

Rulebooks are revised often. Lines marked VERIFY should be checked against the
current edition before a competition is treated as official.
"""

from __future__ import annotations

WELFARE_RULES = [
    {
        "name": "Horse welfare",
        "description": (
            "Officials or vets can eliminate a horse at any time for lameness, injury or abuse. "
            "That elimination cannot be overridden in the app."
        ),
    },
    {
        "name": "Clean sport",
        "description": (
            "A disqualification after a positive test removes the result and the standings "
            "are calculated again. Racing follows IFHA Article 6."
        ),
    },
    {
        "name": "Combination",
        "description": (
            "An entrant is the horse together with its rider or jockey and trainer. "
            "The result belongs to that combination. Horse, rider and trainer each keep their own record."
        ),
    },
    {
        "name": "Officials",
        "description": (
            "Stewards' decisions are final. Only a steward can confirm or change a result, "
            "and every change is logged with a reason."
        ),
    },
]

RACE_STATUSES = [
    {"code": "PU", "label": "Pulled up"},
    {"code": "F", "label": "Fell"},
    {"code": "UR", "label": "Unseated rider"},
    {"code": "BD", "label": "Brought down"},
    {"code": "R", "label": "Refused"},
    {"code": "DNF", "label": "Did not finish"},
    {"code": "RT", "label": "Retired"},
    {"code": "WD", "label": "Withdrawn"},
    {"code": "EL", "label": "Eliminated"},
    {"code": "DQ", "label": "Disqualified"},
]

CARD_FIELDS = [
    {"key": "grade", "label": "Class or grade"},
    {"key": "distance_m", "label": "Distance (m)", "number": True},
    {"key": "going", "label": "Going"},
    {"key": "conditions", "label": "Age and sex conditions"},
]

RUNNER_FIELDS = [
    {"key": "weight", "label": "Weight carried"},
    {"key": "rating", "label": "Official rating"},
    {"key": "prize", "label": "Prize money", "number": True},
]


def _racing(*, label: str, surface_options: list[str], runner_fields: list[dict], description: str) -> dict:
    return {
        "label": label,
        "icon": "flag-outline",
        "description": description,
        "sport": "horse racing",
        "kind": "sport",
        "format": "league",
        "formats_allowed": ["league"],
        "contest_type": "accumulation",
        "participant_type": "combination",
        "score_types": [],
        "match_structure": [],
        "win_condition": "highest_total",
        "draw_allowed": True,
        "draw_resolution": "replay",
        "league_points": {"win": 0, "draw": 0, "loss": 0},
        "tiebreakers": ["wins", "seconds", "thirds", "points", "name"],
        "accumulation_ranking": "highest_first",
        "locked": True,
        "official_results": True,
        "result_type": "finishing_order",
        "statuses": RACE_STATUSES,
        "governing_body": "IFHA",
        "rulebook": "International Agreement on Breeding, Racing and Wagering",
        "local_body": "National Horseracing Authority of Southern Africa (NHA)",
        "result_config": {
            "record_fields": ["margin", "time"],
            "money_field": "prize",
            "roles": {"horse": "Horses", "rider": "Jockeys", "trainer": "Trainers"},
            "card_fields": [
                *CARD_FIELDS[:2],
                {"key": "surface", "label": "Surface", "options": surface_options},
                *CARD_FIELDS[2:],
            ],
            "runner_fields": runner_fields,
        },
        "rules": [
            *WELFARE_RULES,
            {
                "name": "Finishing order",
                "description": (
                    "Runners are placed 1st, 2nd, 3rd. A dead heat shares the place. "
                    "Margins are recorded in lengths (nose, short head, head, neck, ½, ¾, 1, 1¼). "
                    "Pulled up, fell, unseated, brought down, refused and did-not-finish "
                    "rank below every horse that finished, and they do not score."
                ),
            },
            {
                "name": "Stewards' inquiry",
                "description": (
                    "A steward can demote or disqualify a runner after an inquiry or objection. "
                    "Placings are worked out again, and the horse, jockey and trainer championships follow."
                ),
            },
            {
                "name": "Handicaps",
                "description": (
                    "The official rating and the weight allotted are stored for each runner. "
                    "The app does not calculate handicaps."
                ),
            },
            {
                "name": "Championships",
                "description": (
                    "Horse, jockey and trainer tables rank by number of wins, then seconds, then thirds. "
                    "Prize money is shown when it is entered. VERIFY local championship tie-breakers."
                ),
            },
            {
                "name": "No wagering",
                "description": "Odds and betting are not part of this competition.",
            },
        ],
    }


HORSE_RACING_FLAT = _racing(
    label="Horse racing (flat)",
    surface_options=["Turf", "Sand", "All-weather"],
    runner_fields=[
        *RUNNER_FIELDS[:2],
        {"key": "draw", "label": "Draw"},
        RUNNER_FIELDS[2],
    ],
    description=(
        "Flat racing under the IFHA International Agreement, with NHA conditions locally (VERIFY). "
        "Each race places the finishers. A dead heat shares the place. Stewards can demote or "
        "disqualify after an inquiry, and the horse, jockey and trainer championships then "
        "rank by wins, then seconds, then thirds."
    ),
)

HORSE_RACING_JUMPS = _racing(
    label="Horse racing (jumps)",
    surface_options=["Hurdle", "Steeplechase"],
    runner_fields=list(RUNNER_FIELDS),
    description=(
        "Jump racing under the IFHA International Agreement, with NHA conditions locally (VERIFY). "
        "Hurdle and steeplechase races place the finishers. A dead heat shares the place. "
        "Fell, unseated, brought down and refused rank below the finishers. Championships "
        "rank by wins, then seconds, then thirds."
    ),
)

POLO_SCORES = [
    {
        "key": "goal",
        "label": "Goal",
        "value": 1,
        "affects_score": True,
        "description": "The ball crosses the line between the posts. Teams change ends after every goal.",
    },
    {
        "key": "penalty-goal",
        "label": "Penalty goal (converted)",
        "value": 1,
        "affects_score": True,
        "description": "A goal scored from a Penalty 2 to 6 hit. Counts as a goal and a conversion.",
    },
    {
        "key": "penalty-1",
        "label": "Penalty 1 (awarded goal)",
        "value": 1,
        "affects_score": True,
        "no_player": True,
        "description": "A goal awarded by the umpires without a shot being taken.",
    },
    *(
        {
            "key": f"penalty-{number}",
            "label": f"Penalty {number} awarded",
            "value": 0,
            "affects_score": False,
            "no_player": True,
            "description": "Recorded for the match report. Only a converted shot scores.",
        }
        for number in range(2, 7)
    ),
]

POLO_RULES = [
    *WELFARE_RULES[:2],
    {
        "name": "Officials",
        "description": (
            "The umpires and the referee decide the match. Only they confirm or change a result, "
            "and every change is logged with a reason."
        ),
    },
    {
        "name": "Teams",
        "description": (
            "Four players a side, numbered 1 to 4. Each player carries a handicap from -2 to +10 goals."
        ),
    },
    {
        "name": "Chukkas",
        "description": (
            "Chukkas of 7 minutes, plus up to 30 seconds when the ball is in play when the bell goes "
            "(HPA; VERIFY FIP timing). The number of chukkas is chosen when the competition is created "
            "and then locked."
        ),
    },
    {
        "name": "Scoring",
        "description": (
            "A goal is 1. A Penalty 1 awards a goal without a shot. Penalties 2 to 6 are recorded, "
            "and only a converted hit scores. Teams change ends after every goal."
        ),
    },
    {
        "name": "Level at the end",
        "description": (
            "Where a winner is needed, an extra chukka is played and the first goal wins (golden goal). "
            "The goals may be widened under the tournament rules (VERIFY)."
        ),
    },
    {
        "name": "Awards",
        "description": "Each match names a Most Valuable Player and a Best Playing Pony.",
    },
]

POLO_AWARDS = [
    {"key": "mvp", "label": "Most valuable player", "kind": "player"},
    {
        "key": "best_playing_pony",
        "label": "Best Playing Pony",
        "kind": "horse",
        "description": "The pony's name, and the player who rode it.",
    },
]

POLO_PLAYER_STATS = [
    {"key": "goals", "label": "Goals", "codes": ["goal", "penalty-goal"]},
    {"key": "conversions", "label": "Penalty conversions", "codes": ["penalty-goal"]},
    {"key": "mvp", "label": "MVP awards", "award": "mvp"},
]


def _polo(*, label: str, handicap: bool, description: str, rules: list[dict]) -> dict:
    preset = {
        "label": label,
        "icon": "ribbon-outline",
        "description": description,
        "sport": "polo",
        "kind": "sport",
        "format": "league",
        "formats_allowed": ["league", "knockout", "groups_knockout", "round_robin"],
        "contest_type": "head_to_head",
        "participant_type": "team",
        "score_types": POLO_SCORES,
        "match_structure": [
            {"unit": "chukka", "count": 6, "minutes": 7},
            {"unit": "extra_chukka", "count": 1, "minutes": 7, "repeat": True, "golden": True, "extra": True},
        ],
        "unit_count_options": {"unit": "chukka", "options": [4, 5, 6, 8], "default": 6},
        "roster_numbers": [1, 2, 3, 4],
        "win_condition": "highest_total",
        "draw_allowed": True,
        "draw_resolution": "sudden_death",
        "league_points": {"win": 3, "draw": 1, "loss": 0},
        "tiebreakers": ["points", "net_score_difference", "score_for", "head_to_head"],
        "locked": True,
        "official_results": True,
        "match_awards": POLO_AWARDS,
        "player_stats": POLO_PLAYER_STATS,
        "governing_body": "FIP",
        "rulebook": "FIP Rules of Polo, with HPA rules where noted (VERIFY the edition)",
        "local_body": "South African Polo Association (SAPA)",
        "rules": [*POLO_RULES, *rules],
    }
    if handicap:
        preset["head_start"] = {
            "source": "roster_handicap",
            "min": -2,
            "max": 10,
            "unit": "chukka",
            "prorate_units": 6,
            "round_to": "0.5",
        }
    return preset


POLO_HANDICAP = _polo(
    label="Polo (handicap)",
    handicap=True,
    description=(
        "Handicap polo under FIP rules (HPA where noted). Each team adds up its four players' "
        "handicaps, and the lower team starts with the difference as goals on the board, scaled "
        "for matches shorter than six chukkas (VERIFY). A goal and a Penalty 1 are each worth 1. "
        "A league win is 3 points and a draw 1. A level knockout goes to an extra chukka and the "
        "first goal wins. The table uses points, then goal difference without the handicap goals, "
        "then goals scored, then the head-to-head result."
    ),
    rules=[
        {
            "name": "Handicap start",
            "description": (
                "The lower-rated team starts with the difference in team handicaps as goals. For fewer "
                "than six chukkas the difference is scaled down and rounded to the nearest half goal "
                "(VERIFY against the tournament's handicap table)."
            ),
        },
        {
            "name": "Table",
            "description": (
                "3 points for a win, 1 for a draw, 0 for a loss. Ties use goal difference without "
                "handicap goals (both figures are kept), then goals scored, then head-to-head. "
                "VERIFY tournament tie-breakers."
            ),
        },
    ],
)

POLO_OPEN = _polo(
    label="Polo (open)",
    handicap=False,
    description=(
        "Open (level) polo under FIP rules (HPA where noted). Both teams start on 0. A goal and a "
        "Penalty 1 are each worth 1. A league win is 3 points and a draw 1. A level knockout goes "
        "to an extra chukka and the first goal wins. The table uses points, then goal difference, "
        "then goals scored, then the head-to-head result."
    ),
    rules=[
        {
            "name": "Table",
            "description": (
                "3 points for a win, 1 for a draw, 0 for a loss. Ties use goal difference, then goals "
                "scored, then head-to-head. VERIFY tournament tie-breakers."
            ),
        },
    ],
)

JUMPING_STATUSES = [
    {"code": "EL", "label": "Eliminated"},
    {"code": "RT", "label": "Retired"},
    {"code": "WD", "label": "Withdrawn"},
    {"code": "DQ", "label": "Disqualified"},
]

JUMPING_FAULTS = [
    {"key": "knockdown", "label": "Knock-down", "faults": 4},
    {"key": "water", "label": "Foot in the water or on the tape", "faults": 4},
    {"key": "refusal", "label": "Refusal or run-out", "faults": 4, "eliminate_at": 2},
    {"key": "fall", "label": "Fall of horse or athlete", "eliminate_at": 1},
    {"key": "wrong_course", "label": "Error of course not corrected", "eliminate_at": 1},
]

# Table A: 1 time fault per commenced 4 seconds over the time allowed; over twice
# the time allowed eliminates.
TABLE_A_TIME = {"penalty": 1, "per_seconds": 4, "commenced": True, "limit_factor": 2}

JUMPING_RULES = [
    *WELFARE_RULES,
    {
        "name": "Faults",
        "description": (
            "A knock-down is 4 faults, and so is a foot in the water. The first refusal or run-out "
            "is 4 faults; the second eliminates (VERIFY the current edition). A fall of horse or "
            "athlete, or an error of course that is not corrected, eliminates."
        ),
    },
    {
        "name": "Time",
        "description": (
            "The time allowed is set for each round. Each commenced 4 seconds over it is 1 time "
            "fault. Over the time limit, twice the time allowed, eliminates."
        ),
    },
]

SERIES_POINTS = [10, 8, 6, 5, 4, 3, 2, 1]


def _jumping(*, label: str, description: str, config: dict, rules: list[dict]) -> dict:
    return {
        "label": label,
        "icon": "flag-outline",
        "description": description,
        "sport": "show jumping",
        "kind": "sport",
        "format": "league",
        "formats_allowed": ["league"],
        "contest_type": "accumulation",
        "participant_type": "combination",
        "score_types": [],
        "match_structure": [],
        "win_condition": "highest_total",
        "draw_allowed": True,
        "draw_resolution": "replay",
        "league_points": {"win": 0, "draw": 0, "loss": 0},
        "tiebreakers": ["points", "placings", "name"],
        "accumulation_ranking": "highest_first",
        "placing_points": SERIES_POINTS,
        "dead_heat_points": "shared",
        "locked": True,
        "official_results": True,
        "result_type": "faults_then_time",
        "statuses": JUMPING_STATUSES,
        "result_config": {"penalties": JUMPING_FAULTS, **config},
        "governing_body": "FEI",
        "rulebook": "FEI Jumping Rules (VERIFY current article numbers)",
        "local_body": "SA Equestrian Federation (SAEF) / SA Show Jumping",
        "rules": [
            *JUMPING_RULES,
            *rules,
            {
                "name": "Series table",
                "description": (
                    "Each show awards placing points: 10, 8, 6, 5, 4, 3, 2 and 1. Shared places "
                    "share the points. Eliminations and retirements score nothing. VERIFY against "
                    "the series rules."
                ),
            },
        ],
    }


SHOW_JUMPING = _jumping(
    label="Show jumping (jump-off)",
    description=(
        "FEI Table A with one jump-off. Fewest faults wins. Combinations level on faults for first "
        "place jump off over a shortened course: fewest faults, then fastest time. Every other tie "
        "goes to the fastest time in the first round."
    ),
    config={
        "rounds": [
            {"key": "round", "label": "First round"},
            {"key": "jump_off", "label": "Jump-off", "decides": "first"},
        ],
        "time": TABLE_A_TIME,
    },
    rules=[
        {
            "name": "Jump-off",
            "description": (
                "Only those level on faults for first place jump off. The jump-off decides first "
                "place and the order among those who jumped off."
            ),
        }
    ],
)

SHOW_JUMPING_TABLE_A = _jumping(
    label="Show jumping (against the clock)",
    description=(
        "FEI Table A against the clock. Fewest faults wins, and the fastest time separates "
        "combinations on the same faults. There is no jump-off."
    ),
    config={"rounds": [{"key": "round", "label": "Round"}], "time": TABLE_A_TIME},
    rules=[],
)

SHOW_JUMPING_TWO_PHASE = _jumping(
    label="Show jumping (two-phase)",
    description=(
        "A two-phase class. Combinations clear in the first phase go straight on to the second. "
        "They rank by total faults over both phases, then time in the second phase. Everyone "
        "else ranks on faults and time in the first phase, behind them (VERIFY)."
    ),
    config={
        "rounds": [
            {"key": "phase_1", "label": "Phase 1"},
            {"key": "phase_2", "label": "Phase 2", "qualify": "clear"},
        ],
        "time": TABLE_A_TIME,
    },
    rules=[
        {
            "name": "Two phases",
            "description": (
                "Only combinations without faults in phase 1 ride phase 2. Elimination in phase 2 "
                "places a combination after the phase 2 finishers (VERIFY)."
            ),
        }
    ],
)

SHOW_JUMPING_TABLE_C = _jumping(
    label="Show jumping (Table C)",
    description=(
        "FEI Table C: faults are converted to seconds and the lowest time wins. Each knock-down "
        "or foot in the water adds 4 seconds (VERIFY the conversion for the class). A refusal "
        "costs only the time it takes; the second eliminates."
    ),
    config={
        "rounds": [{"key": "round", "label": "Round"}],
        "ranking": "time_plus_penalties",
        "time": {"limit_factor": 2},
        "penalties": [
            {"key": "knockdown", "label": "Knock-down", "penalty_seconds": 4},
            {"key": "water", "label": "Foot in the water or on the tape", "penalty_seconds": 4},
            {"key": "refusal", "label": "Refusal or run-out", "eliminate_at": 2},
            {"key": "fall", "label": "Fall of horse or athlete", "eliminate_at": 1},
            {"key": "wrong_course", "label": "Error of course not corrected", "eliminate_at": 1},
        ],
    },
    rules=[
        {
            "name": "Table C",
            "description": (
                "Penalty seconds are added to the time taken. The lowest total wins. There are no "
                "time faults; going past the time limit eliminates."
            ),
        }
    ],
)

def _movements(*rows: tuple[str, str, int]) -> list[dict]:
    return [{"key": key, "label": label, "coefficient": coefficient} for key, label, coefficient in rows]


# Outlines of the FEI tests: the shape (movements, coefficients, collective mark) is
# right for scoring, but VERIFY every line against the official FEI test sheet in use.
HARMONY = {
    "key": "harmony",
    "label": "Harmony between athlete and horse",
    "coefficient": 2,
    "collective": True,
}

PRIX_ST_GEORGES = [
    *_movements(
        ("entry", "Entry, halt, salute; proceed in collected trot", 1),
        ("half_pass_r", "Half-pass right in trot", 1),
        ("half_pass_l", "Half-pass left in trot", 1),
        ("extended_trot", "Extended trot", 1),
        ("collected_walk", "Collected walk", 2),
        ("extended_walk", "Extended walk", 2),
        ("walk_pirouette_r", "Half pirouette right in walk", 1),
        ("walk_pirouette_l", "Half pirouette left in walk", 1),
        ("canter_half_pass", "Half-pass in canter", 1),
        ("changes_4", "Four flying changes every 4th stride", 1),
        ("changes_3", "Five flying changes every 3rd stride", 1),
        ("canter_pirouette_r", "Half pirouette right in canter", 2),
        ("canter_pirouette_l", "Half pirouette left in canter", 2),
        ("extended_canter", "Extended canter", 1),
        ("final", "Final halt, salute", 1),
    ),
    HARMONY,
]

GRAND_PRIX = [
    *_movements(
        ("entry", "Entry, halt, salute; proceed in collected trot", 1),
        ("extended_trot", "Extended trot", 1),
        ("half_pass_r", "Half-pass right in trot", 1),
        ("half_pass_l", "Half-pass left in trot", 1),
        ("collected_walk", "Collected walk", 2),
        ("extended_walk", "Extended walk", 2),
        ("piaffe_1", "Piaffe", 2),
        ("passage_1", "Passage", 2),
        ("transitions", "Transitions between passage and piaffe", 1),
        ("canter_zigzag", "Canter zig-zag half-passes", 1),
        ("changes_2", "Nine flying changes every 2nd stride", 1),
        ("changes_1", "Fifteen flying changes every stride", 1),
        ("canter_pirouette_r", "Pirouette right in canter", 2),
        ("canter_pirouette_l", "Pirouette left in canter", 2),
        ("extended_canter", "Extended canter", 1),
        ("final", "Final piaffe, halt, salute", 1),
    ),
    HARMONY,
]

DRESSAGE_JUDGING = {
    "max_mark": 10,
    "mark_step": "0.5",
    "decimals": 3,
    "judges": ["E", "H", "C", "M", "B"],
    "judge_positions": ["C", "E", "B", "H", "M", "K", "F"],
    "judge_count": [3, 7],
}

DRESSAGE_RULES = [
    *WELFARE_RULES,
    {
        "name": "Judging",
        "description": (
            "Three to seven judges, at C, E, B, H, M and the other letters, mark every movement "
            "from 0 to 10 in half marks. Each mark is multiplied by its coefficient. A judge's "
            "percentage is their total over the maximum, and the final score is the average of the "
            "judges' percentages, to three decimals. Each judge's score is published."
        ),
    },
    {
        "name": "Elimination",
        "description": (
            "Lameness, a fall of horse or athlete, or leaving the arena eliminates. The ground "
            "jury records it with a reason."
        ),
    },
]

DRESSAGE = {
    "label": "Dressage",
    "icon": "ribbon-outline",
    "description": (
        "FEI dressage tests. Judges mark each movement from 0 to 10, multiplied by its "
        "coefficient, and the final score is the average of the judges' percentages to three "
        "decimals. The first error of course costs 2 points from each judge's total (VERIFY); "
        "the second eliminates. The highest percentage wins, and a tie goes to the higher "
        "collective marks (VERIFY)."
    ),
    "sport": "dressage",
    "kind": "sport",
    "format": "league",
    "formats_allowed": ["league"],
    "contest_type": "accumulation",
    "participant_type": "combination",
    "score_types": [],
    "match_structure": [],
    "win_condition": "highest_total",
    "draw_allowed": True,
    "draw_resolution": "replay",
    "league_points": {"win": 0, "draw": 0, "loss": 0},
    "tiebreakers": ["points", "placings", "name"],
    "accumulation_ranking": "highest_first",
    "placing_points": SERIES_POINTS,
    "dead_heat_points": "shared",
    "locked": True,
    "official_results": True,
    "result_type": "judged_percentage",
    "statuses": JUMPING_STATUSES,
    "result_config": {
        **DRESSAGE_JUDGING,
        "test": "prix_st_georges",
        "tests": {
            "prix_st_georges": {"label": "FEI Prix St-Georges (outline, VERIFY)", "sheet": PRIX_ST_GEORGES},
            "grand_prix": {"label": "FEI Grand Prix (outline, VERIFY)", "sheet": GRAND_PRIX},
        },
        "errors": {"deduct_points": [2], "eliminate_at": 2},
    },
    "governing_body": "FEI",
    "rulebook": "FEI Dressage Rules (VERIFY the current edition and test sheets)",
    "local_body": "SA Equestrian Federation (SAEF) / Dressage SA",
    "rules": [
        *DRESSAGE_RULES,
        {
            "name": "Errors of course",
            "description": (
                "The first error of course costs 2 points from each judge's total (VERIFY for the "
                "test); the second eliminates."
            ),
        },
        {
            "name": "Test sheets",
            "description": (
                "Each event names its test. The test is data: its movements, coefficients and "
                "collective mark."
            ),
        },
        {
            "name": "Ties",
            "description": "Level percentages go to the higher collective marks (VERIFY).",
        },
    ],
}

FREESTYLE_TECHNICAL = [
    {**row, "section": "technical"}
    for row in _movements(
        ("collected_walk", "Collected walk", 1),
        ("extended_walk", "Extended walk", 1),
        ("collected_trot", "Collected trot, including half-pass", 1),
        ("extended_trot", "Extended trot", 1),
        ("collected_canter", "Collected canter, including half-pass", 1),
        ("extended_canter", "Extended canter", 1),
        ("changes_2", "Flying changes every 2nd stride", 1),
        ("changes_1", "Flying changes every stride", 1),
        ("canter_pirouettes", "Canter pirouettes", 2),
        ("passage", "Passage", 2),
        ("piaffe", "Piaffe", 2),
        ("transitions", "Transitions between passage and piaffe", 1),
        ("entry_final", "Entry and final halt", 1),
    )
]

FREESTYLE_ARTISTIC = [
    {**row, "section": "artistic", "collective": True}
    for row in _movements(
        ("rhythm", "Rhythm, energy and elasticity", 4),
        ("harmony", "Harmony between athlete and horse", 4),
        ("choreography", "Choreography and use of the arena", 4),
        ("difficulty", "Degree of difficulty", 4),
        ("music", "Music and interpretation", 4),
    )
]

DRESSAGE_FREESTYLE = {
    **DRESSAGE,
    "label": "Dressage (freestyle to music)",
    "description": (
        "FEI freestyle to music. The judges give a technical score and an artistic score, each as "
        "a percentage, and the two count half each (VERIFY the current FEI formula). The final "
        "score is the average of the judges, to three decimals. The highest wins; a tie goes to "
        "the higher artistic score."
    ),
    "result_config": {
        **DRESSAGE_JUDGING,
        "sheet": [*FREESTYLE_TECHNICAL, *FREESTYLE_ARTISTIC],
        "section_weights": {"technical": "0.5", "artistic": "0.5"},
    },
    "rules": [
        *DRESSAGE_RULES,
        {
            "name": "Technical and artistic",
            "description": (
                "Technical marks rate each required movement. Artistic marks, coefficient 4 each, "
                "rate rhythm, harmony, choreography, difficulty and music. Each is a percentage and "
                "they count half each (VERIFY)."
            ),
        },
        {"name": "Ties", "description": "Level scores go to the higher artistic score."},
    ],
}

EVENTING = {
    "label": "Eventing",
    "icon": "flag-outline",
    "description": (
        "FEI eventing over three phases, lowest total penalties wins. Dressage penalties are 100 "
        "minus the percentage. Cross-country: 20 for a first refusal at an obstacle, 40 for a "
        "second, and a third eliminates; 0.4 per second over the optimum time. Jumping: 4 per "
        "knock-down or refusal; 0.4 per second over the time allowed (VERIFY). A failed horse "
        "inspection eliminates. Ties go to the cross-country score, then the cross-country time, "
        "then the jumping, then the dressage (VERIFY the order)."
    ),
    "sport": "eventing",
    "kind": "sport",
    "format": "league",
    "formats_allowed": ["league"],
    "contest_type": "accumulation",
    "participant_type": "combination",
    "score_types": [],
    "match_structure": [],
    "win_condition": "highest_total",
    "draw_allowed": True,
    "draw_resolution": "replay",
    "league_points": {"win": 0, "draw": 0, "loss": 0},
    "tiebreakers": ["points", "placings", "name"],
    "accumulation_ranking": "highest_first",
    "placing_points": SERIES_POINTS,
    "dead_heat_points": "shared",
    "locked": True,
    "official_results": True,
    "result_type": "penalty_total_lowest",
    "statuses": JUMPING_STATUSES,
    "result_config": {
        "inspections": [
            {"key": "before_cross_country", "label": "horse inspection before cross-country"},
            {"key": "before_jumping", "label": "horse inspection before jumping"},
        ],
        "phases": [
            {
                "key": "dressage",
                "label": "Dressage",
                "input": "percentage",
                "from_percentage": 100,
                "decimals": 1,
            },
            {
                "key": "cross_country",
                "label": "Cross-country",
                "time_label": "Optimum time",
                "penalties": [
                    {
                        "key": "refusals",
                        "label": "Refusals, run-outs or circles",
                        "per_obstacle": True,
                        "scale": [20, 40],
                        "eliminate_at": 3,
                        "eliminate_total_at": 4,
                    },
                    {"key": "frangible", "label": "Frangible device activated", "faults": 11},
                    {"key": "missed_flag", "label": "Flag missed", "faults": 15},
                    {"key": "dangerous_riding", "label": "Dangerous riding", "faults": 25},
                    {"key": "rider_fall", "label": "Fall of athlete", "eliminate_at": 1},
                    {"key": "horse_fall", "label": "Fall of horse", "eliminate_at": 1},
                    {"key": "wrong_course", "label": "Error of course not corrected", "eliminate_at": 1},
                ],
                "time": {"penalty": "0.4", "per_seconds": 1, "commenced": True, "limit_factor": 2},
            },
            {
                "key": "jumping",
                "label": "Jumping",
                "penalties": [
                    {"key": "knockdown", "label": "Knock-down", "faults": 4},
                    {"key": "refusal", "label": "Refusal or run-out", "faults": 4, "eliminate_at": 3},
                    {"key": "rider_fall", "label": "Fall of athlete", "eliminate_at": 1},
                    {"key": "wrong_course", "label": "Error of course not corrected", "eliminate_at": 1},
                ],
                "time": {"penalty": "0.4", "per_seconds": 1, "commenced": True, "limit_factor": 2},
            },
        ],
        "tiebreakers": [
            "phase:cross_country",
            "phase_time:cross_country",
            "phase:jumping",
            "phase:dressage",
        ],
    },
    "governing_body": "FEI",
    "rulebook": "FEI Eventing Rules (VERIFY the current edition; they change often)",
    "local_body": "SA Equestrian Federation (SAEF) / Eventing SA",
    "rules": [
        *WELFARE_RULES,
        {
            "name": "Dressage",
            "description": "Penalties are 100 minus the dressage percentage, to one decimal.",
        },
        {
            "name": "Cross-country",
            "description": (
                "A first refusal, run-out or circle at an obstacle is 20; a second at the same "
                "obstacle is 40; a third there eliminates, and so does a fourth on the course "
                "(VERIFY). A frangible device is 11, a missed flag 15 and dangerous riding 25 "
                "(VERIFY). Each commenced second over the optimum time is 0.4. Over twice the "
                "optimum time, or a fall of horse or athlete, eliminates."
            ),
        },
        {
            "name": "Jumping",
            "description": (
                "A knock-down or a refusal is 4; the third refusal eliminates (VERIFY). Each "
                "commenced second over the time allowed is 0.4 (VERIFY). A fall of the athlete "
                "eliminates."
            ),
        },
        {
            "name": "Horse inspections",
            "description": (
                "Horses are inspected before the cross-country and before the jumping. A horse "
                "not accepted is eliminated, and that decision cannot be overridden in the app."
            ),
        },
        {
            "name": "Ties",
            "description": (
                "The best cross-country score (jumping and time penalties), then the fastest "
                "cross-country time, then the best jumping round, then the best dressage (VERIFY)."
            ),
        },
        {
            "name": "Series table",
            "description": (
                "Each event awards placing points: 10, 8, 6, 5, 4, 3, 2 and 1. Eliminations and "
                "retirements score nothing."
            ),
        },
    ],
}

def _loops(*distances: int) -> list[dict]:
    rows = []
    for index, distance in enumerate(distances, start=1):
        last = index == len(distances)
        rows.append(
            {
                "key": f"loop_{index}",
                "label": "Finish" if last else f"Vet gate {index}",
                "distance_km": distance,
            }
        )
    return rows


ENDURANCE_STATUSES = [
    {"code": "FTQ", "label": "Failed to qualify"},
    {"code": "RET", "label": "Retired"},
    {"code": "FTC", "label": "Failed to complete"},
    {"code": "EL", "label": "Eliminated"},
    {"code": "WD", "label": "Withdrawn"},
    {"code": "DQ", "label": "Disqualified"},
]

ENDURANCE = {
    "label": "Endurance",
    "icon": "stopwatch-outline",
    "description": (
        "FEI endurance. The ride is split into loops, each ending at a vet gate. The horse must be "
        "presented in time, its heart rate must be at or below the limit, and it must be sound. Any "
        "failure is Failed to Qualify (FTQ) with a reason. Hold times do not count. The fastest "
        "total riding time among horses that pass every gate and the final inspection wins. "
        "Average speed is shown. Best Condition is a separate award (VERIFY the FEI formula)."
    ),
    "sport": "endurance",
    "kind": "sport",
    "format": "league",
    "formats_allowed": ["league"],
    "contest_type": "accumulation",
    "participant_type": "combination",
    "score_types": [],
    "match_structure": [],
    "win_condition": "highest_total",
    "draw_allowed": True,
    "draw_resolution": "replay",
    "league_points": {"win": 0, "draw": 0, "loss": 0},
    "tiebreakers": ["points", "placings", "name"],
    "accumulation_ranking": "highest_first",
    "placing_points": SERIES_POINTS,
    "dead_heat_points": "shared",
    "locked": True,
    "official_results": True,
    "result_type": "timed_with_vet_gates",
    "statuses": ENDURANCE_STATUSES,
    "result_config": {
        "failed_status": "FTQ",
        "heart_rate_max": 64,
        "presentation_limit_seconds": 900,
        "final_inspection": True,
        "ftq_codes": [
            {"code": "GA", "label": "Irregular gait (lameness)"},
            {"code": "ME", "label": "Metabolic"},
            {"code": "GA ME", "label": "Irregular gait and metabolic"},
            {"code": "SI", "label": "Serious injury"},
            {"code": "OT", "label": "Over time to present"},
        ],
        "test_label": "Ride class",
        "test": "cei1_80",
        "tests": {
            "intro_40": {
                "label": "40 km (national, VERIFY speed limit)",
                "loops": _loops(20, 20),
                "speed_max_kmh": 16,
            },
            "cei1_80": {"label": "80 km (CEI 1*)", "loops": _loops(30, 30, 20)},
            "cei2_120": {"label": "120 km (CEI 2*)", "loops": _loops(35, 30, 30, 25)},
            "cei3_160": {"label": "160 km (CEI 3*)", "loops": _loops(40, 35, 30, 30, 25)},
        },
        "best_condition": {
            "eligible": 10,
            "vet_items": [
                {"key": "recovery", "label": "Recovery", "max": 10, "weight": 10},
                {"key": "hydration", "label": "Hydration", "max": 10, "weight": 10},
                {"key": "lesions", "label": "Lesions", "max": 10, "weight": 10},
                {"key": "soundness", "label": "Soundness", "max": 10, "weight": 10},
                {"key": "movement", "label": "Quality of movement", "max": 10, "weight": 10},
            ],
            "time_base": 200,
            "time_per_minute": 1,
            "weight": {"base": 100, "per_kg": 1},
        },
    },
    "governing_body": "FEI",
    "rulebook": "FEI Endurance Rules (VERIFY the current edition)",
    "local_body": "SA Equestrian Federation (SAEF) / Endurance Ride Association of SA",
    "rules": [
        *WELFARE_RULES,
        {
            "name": "Vet gates",
            "description": (
                "After each loop the horse is presented within 15 minutes (VERIFY), must be at or "
                "below 64 bpm (VERIFY per class) and must be sound. A failure is FTQ, coded GA for "
                "gait, ME for metabolic, and so on."
            ),
        },
        {
            "name": "Riding time",
            "description": (
                "Hold times at the vet gates do not count. The fastest total riding time among "
                "horses that pass every gate, and the final inspection, wins. Average speed is "
                "shown, and classes with a speed limit eliminate a ride outside it (VERIFY)."
            ),
        },
        {
            "name": "Ride classes",
            "description": (
                "Each ride names its class: 40, 80, 120 or 160 km, with the loops as data (VERIFY "
                "the loop distances for the venue)."
            ),
        },
        {
            "name": "Best Condition",
            "description": (
                "Among the first ten finishers who present, the vets mark recovery, hydration, "
                "lesions, soundness and quality of movement. The award adds those marks (x10), "
                "time points (200, less 1 per minute behind the winner) and weight points (100, "
                "less 1 per kg lighter than the heaviest rider). VERIFY against the current FEI "
                "formula."
            ),
        },
        {
            "name": "Series table",
            "description": (
                "Each ride awards placing points: 10, 8, 6, 5, 4, 3, 2 and 1. A horse that fails "
                "to qualify scores nothing."
            ),
        },
    ],
}

HORSEBALL = {
    "label": "Horseball",
    "icon": "football-outline",
    "description": (
        "Horseball under FIHB rules (VERIFY). Four riders a side on the field. Two halves of 10 "
        "minutes with a 3-minute break. A goal is 1, and a team must make at least three passes "
        "between three different players before it shoots. A league win is 3 points and a draw 1. "
        "A level knockout goes to extra time, then the next goal wins (VERIFY). The table uses "
        "points, then goal difference, then goals scored, then the head-to-head result."
    ),
    "sport": "horseball",
    "kind": "sport",
    "format": "league",
    "formats_allowed": ["league", "knockout", "groups_knockout", "round_robin"],
    "contest_type": "head_to_head",
    "participant_type": "team",
    "score_types": [
        {"key": "goal", "label": "Goal", "value": 1, "affects_score": True},
        {
            "key": "penalty-goal",
            "label": "Penalty goal",
            "value": 1,
            "affects_score": True,
            "description": "A goal scored from a penalty.",
        },
        {"key": "yellow-card", "label": "Yellow card", "value": 0, "affects_score": False},
        {"key": "red-card", "label": "Red card", "value": 0, "affects_score": False},
    ],
    "match_structure": [
        {"unit": "half", "count": 2, "minutes": 10},
        {"unit": "extra_time", "count": 2, "minutes": 5, "extra": True},
        {"unit": "sudden_death", "count": 1, "repeat": True, "golden": True, "extra": True},
    ],
    "win_condition": "highest_total",
    "draw_allowed": True,
    "draw_resolution": "sudden_death",
    "league_points": {"win": 3, "draw": 1, "loss": 0},
    "tiebreakers": ["points", "score_difference", "score_for", "head_to_head"],
    "locked": True,
    "official_results": True,
    "player_stats": [{"key": "goals", "label": "Goals", "codes": ["goal", "penalty-goal"]}],
    "governing_body": "FIHB",
    "rulebook": "FIHB Rules of Horseball (VERIFY the edition)",
    "local_body": "VERIFY the South African horseball body",
    "rules": [
        *WELFARE_RULES[:2],
        {
            "name": "Officials",
            "description": (
                "The referees decide the match. Only they confirm or change a result, and every "
                "change is logged with a reason."
            ),
        },
        {
            "name": "Teams",
            "description": "Four riders a side on the field, with substitutes (VERIFY the squad size).",
        },
        {
            "name": "Match",
            "description": "Two halves of 10 minutes with a 3-minute break.",
        },
        {
            "name": "Passing rule",
            "description": (
                "Before shooting, a team makes at least three passes between three different "
                "players. The referees enforce it; the app records goals only."
            ),
        },
        {
            "name": "Level at the end",
            "description": (
                "In a league a draw shares the points. In a knockout, two 5-minute periods of extra "
                "time, then the next goal wins (VERIFY)."
            ),
        },
    ],
}

PEG_OUTCOMES = [
    {"key": "carried", "label": "Peg carried past the line", "points": 6},
    {"key": "drawn", "label": "Peg drawn (pulled out, dropped)", "points": 4},
    {"key": "strike", "label": "Peg struck", "points": 2},
    {"key": "miss", "label": "Miss", "points": 0},
]

PEGGING_RULES = [
    *WELFARE_RULES,
    {
        "name": "Points",
        "description": (
            "Lance: carrying the peg past the line is 6, drawing it (pulled out but dropped) is 4, "
            "and a strike is 2. Sword uses the same points (VERIFY the ITPF table for each "
            "discipline)."
        ),
    },
    {
        "name": "Time limit",
        "description": (
            "Each run must finish inside the time limit: 6.4 seconds with the lance and 7 seconds "
            "with the sword over the standard course (VERIFY). An over-time run scores 0."
        ),
    },
    {
        "name": "Ranking and ties",
        "description": "The highest total over all runs wins. A tie is decided by a run-off.",
    },
]


def _pegging(*, label: str, team: bool) -> dict:
    return {
        "label": label,
        "icon": "flag-outline",
        "description": (
            "Tent pegging under ITPF rules (VERIFY). Each run scores 6 for a carried peg, 4 for a "
            "drawn peg and 2 for a strike; a run over the time limit scores 0. "
            + (
                "A team's score is the sum of its four riders' runs. "
                if team
                else ""
            )
            + "The highest total wins, and a tie goes to a run-off."
        ),
        "sport": "tent pegging",
        "kind": "sport",
        "format": "league",
        "formats_allowed": ["league"],
        "contest_type": "accumulation",
        "participant_type": "team" if team else "combination",
        "score_types": [],
        "match_structure": [],
        "win_condition": "highest_total",
        "draw_allowed": True,
        "draw_resolution": "replay",
        "league_points": {"win": 0, "draw": 0, "loss": 0},
        "tiebreakers": ["points", "placings", "name"],
        "accumulation_ranking": "highest_first",
        "placing_points": SERIES_POINTS,
        "dead_heat_points": "shared",
        "locked": True,
        "official_results": True,
        "result_type": "points_per_run",
        "statuses": JUMPING_STATUSES,
        "result_config": {
            "runs": 3,
            "outcomes": PEG_OUTCOMES,
            "test_label": "Discipline",
            "test": "lance",
            **({"team_size": 4} if team else {}),
            "tests": {
                "lance": {"label": "Lance (VERIFY time limit)", "time_limit_seconds": "6.4"},
                "sword": {"label": "Sword (VERIFY time limit and points)", "time_limit_seconds": "7"},
            },
        },
        "governing_body": "ITPF",
        "rulebook": "ITPF Rules (VERIFY the edition)",
        "local_body": "SA Tent Pegging Association (VERIFY)",
        "rules": [
            *PEGGING_RULES,
            *(
                [
                    {
                        "name": "Teams",
                        "description": "Four riders ride for the team, and their points are added up.",
                    }
                ]
                if team
                else []
            ),
        ],
    }


TENT_PEGGING = _pegging(label="Tent pegging", team=False)
TENT_PEGGING_TEAM = _pegging(label="Tent pegging (team of 4)", team=True)

EQUESTRIAN_PRESETS: dict[str, dict] = {
    "horse_racing_flat": HORSE_RACING_FLAT,
    "horse_racing_jumps": HORSE_RACING_JUMPS,
    "polo_handicap": POLO_HANDICAP,
    "polo_open": POLO_OPEN,
    "show_jumping": SHOW_JUMPING,
    "show_jumping_table_a": SHOW_JUMPING_TABLE_A,
    "show_jumping_two_phase": SHOW_JUMPING_TWO_PHASE,
    "show_jumping_table_c": SHOW_JUMPING_TABLE_C,
    "dressage": DRESSAGE,
    "dressage_freestyle": DRESSAGE_FREESTYLE,
    "eventing": EVENTING,
    "endurance": ENDURANCE,
    "horseball": HORSEBALL,
    "tent_pegging": TENT_PEGGING,
    "tent_pegging_team": TENT_PEGGING_TEAM,
}
