"""Locked preset data. The engine never branches on these keys."""

from __future__ import annotations


def _sport(**overrides) -> dict:
    row = {
        "kind": "sport",
        "format": "league",
        "formats_allowed": ["league", "knockout", "round_robin"],
        "contest_type": "head_to_head",
        "participant_type": "team",
        "win_condition": "highest_total",
        "draw_allowed": True,
        "draw_resolution": "replay",
        "league_points": {"win": 3, "draw": 1, "loss": 0},
        "tiebreakers": ["points", "score_difference", "score_for", "head_to_head"],
        "locked": True,
        "rules": [],
    }
    row.update(overrides)
    return row


TENNIS_STRUCTURE = [
    {
        "unit": "set",
        "count": 3,
        "best_of": 3,
        "first_to": 6,
        "win_by": 2,
        "tiebreak_at": 6,
        "tiebreak_first_to": 7,
        "tiebreak_win_by": 2,
    }
]

YELLOW_CARD = {"key": "yellow-card", "label": "Yellow card", "value": 0, "affects_score": False}
RED_CARD = {"key": "red-card", "label": "Red card", "value": 0, "affects_score": False}
OWN_GOAL = {
    "key": "own-goal",
    "label": "Own goal",
    "value": 1,
    "affects_score": True,
    "awards": "opponent",
    "description": "A goal in your own net. The other side scores 1.",
}

TENNIS_SCORES = [
    {"key": "game", "label": "Game", "value": 1, "affects_score": True},
    {
        "key": "tiebreak",
        "label": "Tie-break point",
        "value": 1,
        "affects_score": True,
        "role": "tiebreak",
    },
]

CATALOG: dict[str, dict] = {
    "rugby_union": _sport(
        label="Rugby union (fifteens)",
        icon="american-football-outline",
        sport="rugby union",
        family="rugby_union",
        variant="fifteens",
        family_label="Rugby union",
        variant_label="Fifteens",
        governing_body="World Rugby",
        rulebook="World Rugby Laws of the Game",
        description=(
            "A try is 5, a conversion 2, a penalty goal or drop goal 3, and a "
            "penalty try 7. Yellow and red cards are recorded without points. "
            "A match is two halves of 40 minutes. A league win is 4, a draw 2. "
            "A side that scores 4 or more tries, or loses by 7 or fewer, gets "
            "1 bonus point. In a knockout, extra time, then sudden death, then "
            "a kicking competition."
        ),
        score_types=[
            {"key": "try", "label": "Try", "value": 5, "affects_score": True},
            {"key": "conversion", "label": "Conversion", "value": 2, "affects_score": True},
            {"key": "penalty-goal", "label": "Penalty goal", "value": 3, "affects_score": True},
            {"key": "drop-goal", "label": "Drop goal", "value": 3, "affects_score": True},
            {"key": "penalty-try", "label": "Penalty try", "value": 7, "affects_score": True},
            {"key": "yellow-card", "label": "Yellow card", "value": 0, "affects_score": False},
            {"key": "red-card", "label": "Red card", "value": 0, "affects_score": False},
        ],
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 40, "clock": "running"},
            {"unit": "extra_time", "count": 2, "minutes": 10, "extra": True},
            {"unit": "sudden_death", "count": 1, "minutes": 10, "extra": True},
            {"unit": "kicking", "count": 1, "affects_total": False, "resolves_draw": True, "extra": True},
        ],
        draw_resolution="penalties",
        league_points={"win": 4, "draw": 2, "loss": 0},
        table_bonus={
            "enabled": True,
            "scoring_codes": ["try", "penalty-try"],
            "scoring_code": "try",
            "scoring_threshold": 4,
            "scoring_points": 1,
            "loss_margin": 7,
            "loss_points": 1,
        },
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
        tiebreakers=["points", "score_difference", "category:try", "head_to_head"],
        team_sheet={
            "starters": 15,
            "min_on_field": 11,
            "min_squad": 15,
            "bench_max": 8,
            "max_substitutions": 8,
            "rolling_substitutions": False,
        },
        rules=[
            {
                "name": "League points",
                "description": (
                    "A win is 4, a draw is 2, a loss is 0. "
                    "1 bonus for 4 or more tries, and 1 for losing by 7 or fewer."
                ),
            },
            {
                "name": "Players",
                "description": "15 start, with up to 8 on the bench.",
            },
            {
                "name": "Knockout",
                "description": (
                    "If the match is level, two periods of 10 minutes, then sudden "
                    "death of 10 minutes, then a kicking competition."
                ),
            },
        ],
    ),
    "rugby_league": _sport(
        label="Rugby league (thirteens)",
        icon="american-football-outline",
        sport="rugby league",
        family="rugby_league",
        variant="thirteens",
        family_label="Rugby league",
        variant_label="Thirteens",
        governing_body="International Rugby League",
        rulebook="International Rugby League Laws of the Game",
        description=(
            "A try is 4, a conversion 2, a penalty goal 2, and a field goal 1. "
            "Yellow and red cards are recorded without points. "
            "A match is two halves of 40 minutes. A league win is 2, a draw 1. "
            "A knockout that is level goes to golden point: the next score wins."
        ),
        score_types=[
            {"key": "try", "label": "Try", "value": 4, "affects_score": True},
            {"key": "conversion", "label": "Conversion", "value": 2, "affects_score": True},
            {"key": "penalty-goal", "label": "Penalty goal", "value": 2, "affects_score": True},
            {"key": "field-goal", "label": "Field goal", "value": 1, "affects_score": True},
            {
                "key": "long-field-goal",
                "label": "Field goal (40m+)",
                "value": 2,
                "affects_score": True,
                "description": "Used when the competition awards 2 for a drop from beyond 40 m.",
            },
            YELLOW_CARD,
            RED_CARD,
        ],
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 40, "clock": "running"},
            {"unit": "extra_time", "count": 1, "extra": True, "golden": True},
        ],
        draw_resolution="sudden_death",
        league_points={"win": 2, "draw": 1, "loss": 0},
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
        tiebreakers=["points", "score_difference", "score_for"],
        team_sheet={
            "starters": 13,
            "min_on_field": 9,
            "min_squad": 13,
            "bench_max": 4,
            "max_substitutions": 10,
            "rolling_substitutions": True,
        },
        rules=[
            {
                "name": "League points",
                "description": "A win is 2 points, a draw is 1, a loss is 0.",
            },
            {
                "name": "Players",
                "description": "13 start, with 4 on the bench. Substitutions are rolling.",
            },
            {
                "name": "Tackle set",
                "description": "A team has 6 tackles before handing over the ball. Recorded as a stat, not scoring.",
            },
            {
                "name": "Knockout",
                "description": "If the match is level, golden point extra time decides it.",
            },
        ],
    ),
    "american_football": _sport(
        label="American football",
        icon="american-football-outline",
        sport="american football",
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
        description=(
            "A touchdown is 6, the extra-point kick is 1, a two-point conversion "
            "is 2, a field goal is 3, and a safety is 2. A conversion returned by "
            "the defence is also 2. Penalties are recorded and do not change the "
            "score. Eleven play on each side. A game is four quarters of 15 minutes, "
            "then a 10-minute overtime if the score is level. A league game can end "
            "in a tie. A knockout plays on until one side leads. The table gives 3 "
            "for a win and 1 for a tie, then uses the head-to-head result, points "
            "difference, and points scored."
        ),
        score_types=[
            {"key": "touchdown", "label": "Touchdown", "value": 6, "affects_score": True},
            {
                "key": "extra-point",
                "label": "Extra point",
                "value": 1,
                "affects_score": True,
                "description": "Kick after a touchdown.",
            },
            {
                "key": "two-point",
                "label": "Two-point conversion",
                "value": 2,
                "affects_score": True,
                "description": "Run or pass after a touchdown.",
            },
            {"key": "field-goal", "label": "Field goal", "value": 3, "affects_score": True},
            {
                "key": "safety",
                "label": "Safety",
                "value": 2,
                "affects_score": True,
                "description": "The defence scores 2.",
            },
            {
                "key": "defensive-conversion",
                "label": "Returned conversion",
                "value": 2,
                "affects_score": True,
                "description": "The defence returns an extra point or a two-point try.",
            },
            {
                "key": "penalty",
                "label": "Penalty",
                "value": 0,
                "affects_score": False,
                "description": "Recorded only. It does not change the score.",
            },
        ],
        match_structure=[
            {"unit": "quarter", "count": 4, "minutes": 15},
            {"unit": "overtime", "count": 1, "minutes": 10, "repeat": True},
        ],
        draw_resolution="sudden_death",
        league_points={"win": 3, "draw": 1, "loss": 0},
        tiebreakers=["points", "head_to_head", "score_difference", "score_for"],
    ),
    "basketball": _sport(
        label="Basketball",
        icon="basketball-outline",
        sport="basketball",
        description=(
            "A free throw is 1, a field goal 2, and a three-pointer 3. Fouls are "
            "recorded without points. A match is four quarters of 10 minutes. "
            "A draw is not a result: five-minute overtime periods are played until "
            "one side leads. League points are 3 for a win and 0 for a loss. "
            "The table uses points, then the head-to-head result, then points "
            "difference, then points scored."
        ),
        draw_allowed=False,
        score_types=[
            {"key": "free-throw", "label": "Free throw", "value": 1, "affects_score": True},
            {"key": "field-goal", "label": "Field goal", "value": 2, "affects_score": True},
            {"key": "three-pointer", "label": "Three-pointer", "value": 3, "affects_score": True},
            {"key": "foul", "label": "Foul", "value": 0, "affects_score": False},
        ],
        match_structure=[
            {"unit": "quarter", "count": 4, "minutes": 10},
            {"unit": "overtime", "count": 1, "minutes": 5, "repeat": True},
        ],
        tiebreakers=["points", "head_to_head", "score_difference", "score_for"],
    ),
    "netball": _sport(
        label="Netball",
        icon="fitness-outline",
        sport="netball",
        description=(
            "A goal is 1. A match is four quarters of 15 minutes. A league draw "
            "shares the points. In a knockout, two extra periods of 5 minutes are "
            "played, then the next goal wins. The table uses points, then goal "
            "difference, then goals scored."
        ),
        score_types=[{"key": "goal", "label": "Goal", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "quarter", "count": 4, "minutes": 15},
            {"unit": "extra_time", "count": 2, "minutes": 5},
            {"unit": "golden_goal", "count": 1},
        ],
        draw_resolution="sudden_death",
        tiebreakers=["points", "score_difference", "score_for"],
    ),
    "field_hockey": _sport(
        label="Hockey",
        icon="flash-outline",
        sport="field hockey",
        description=(
            "A field goal, a penalty-corner goal, and a penalty-stroke goal are "
            "each 1. An own goal scores 1 for the other side. Green, yellow, and "
            "red cards are recorded without points. "
            "A match is four quarters of 15 minutes. League points are 3, 1 and 0. "
            "A knockout that is level goes to a shoot-out. The table uses points, "
            "then goal difference, then goals scored, then the head-to-head result."
        ),
        score_types=[
            {"key": "field-goal", "label": "Field goal", "value": 1, "affects_score": True},
            {"key": "penalty-corner", "label": "Penalty corner", "value": 1, "affects_score": True},
            {"key": "penalty-stroke", "label": "Penalty stroke", "value": 1, "affects_score": True},
            OWN_GOAL,
            {"key": "green-card", "label": "Green card", "value": 0, "affects_score": False},
            {"key": "yellow-card", "label": "Yellow card", "value": 0, "affects_score": False},
            {"key": "red-card", "label": "Red card", "value": 0, "affects_score": False},
        ],
        match_structure=[
            {"unit": "quarter", "count": 4, "minutes": 15},
            {"unit": "shootout", "count": 1, "affects_total": False, "resolves_draw": True},
        ],
        draw_resolution="penalties",
        tiebreakers=["points", "score_difference", "score_for", "head_to_head"],
    ),
    "volleyball": _sport(
        label="Volleyball",
        icon="ellipse-outline",
        sport="volleyball",
        description=(
            "A match is best of 5 sets. Sets 1 to 4 are first to 25 and must be "
            "won by 2. The fifth set is first to 15 and must be won by 2. The "
            "side that wins the most sets wins the match. Yellow and red cards are "
            "recorded without points. Draws are not a result. "
            "League points are 3 for a win and 0 for a loss. The table uses points, "
            "then wins, then set ratio, then point ratio."
        ),
        draw_allowed=False,
        win_condition="most_units_won",
        score_types=[
            {"key": "point", "label": "Point", "value": 1, "affects_score": True},
            YELLOW_CARD,
            RED_CARD,
        ],
        match_structure=[
            {"unit": "set", "count": 4, "best_of": 5, "first_to": 25, "win_by": 2},
            {"unit": "set", "count": 1, "first_to": 15, "win_by": 2},
        ],
        tiebreakers=["points", "wins", "units_ratio", "score_ratio"],
    ),
    "cricket_t20": _sport(
        label="Cricket (T20)",
        icon="baseball-outline",
        sport="cricket",
        description=(
            "Each innings is 20 overs of 6 balls, and a side can lose 10 wickets. "
            "Runs score 1 to 6. A wide and a no-ball are 1. Byes and leg-byes are "
            "runs that are not credited to a batter. Wickets are recorded. The "
            "side with more runs wins: the side batting second can win with wickets "
            "in hand. A tie is decided by a super over. A match with no result is "
            "1 point each. The table uses points, then wins, then net run rate, "
            "then the head-to-head result."
        ),
        draw_allowed=False,
        draw_resolution="tiebreak",
        league_points={"win": 3, "draw": 1, "loss": 0, "no_result": 1},
        score_types=[
            {"key": "run", "label": "Run", "value": 1, "affects_score": True},
            {"key": "wide", "label": "Wide", "value": 1, "affects_score": True},
            {"key": "no-ball", "label": "No-ball", "value": 1, "affects_score": True},
            {"key": "bye", "label": "Bye", "value": 1, "affects_score": True},
            {"key": "leg-bye", "label": "Leg bye", "value": 1, "affects_score": True},
            {"key": "wicket", "label": "Wicket", "value": 0, "affects_score": False},
            {"key": "ball", "label": "Ball", "value": 0, "affects_score": False},
            {"key": "no-result", "label": "No result", "value": 0, "affects_score": False, "role": "no_result"},
        ],
        match_structure=[
            {"unit": "innings", "count": 2},
            {"unit": "super_over", "count": 1, "affects_total": False, "resolves_draw": True},
        ],
        rate_basis={
            "for": ["run", "wide", "no-ball", "bye", "leg-bye"],
            "balls": "ball",
            "scale": 6,
        },
        tiebreakers=["points", "wins", "rate", "head_to_head"],
    ),
    "baseball": _sport(
        label="Baseball",
        icon="baseball-outline",
        sport="baseball",
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
        draw_allowed=False,
        description=(
            "A run is 1. A home run scores 1 for the batter, and each other runner "
            "who scores is another run. Hits, RBIs, walks, strikeouts, stolen bases, "
            "errors, and hit-by-pitches are recorded and do not change the score. "
            "Nine bat in order and nine play in the field. A game is 9 innings. The "
            "visiting side bats first in each inning, and the home side bats last. "
            "If the home side leads after the visitor has batted in the 9th, the "
            "game ends. A level score goes to extra innings, and from the 10th each "
            "half-inning starts with a runner on second. There is no draw. The table "
            "gives 3 for a win, then uses the head-to-head result, then run difference, then runs scored."
        ),
        score_types=[
            {"key": "run", "label": "Run", "value": 1, "affects_score": True},
            {
                "key": "home-run",
                "label": "Home run",
                "value": 1,
                "affects_score": True,
                "description": "Scores 1 for the batter. Record a run for each other runner who scores.",
            },
            {"key": "hit", "label": "Hit", "value": 0, "affects_score": False},
            {"key": "rbi", "label": "RBI", "value": 0, "affects_score": False},
            {"key": "walk", "label": "Walk", "value": 0, "affects_score": False},
            {"key": "strikeout", "label": "Strikeout", "value": 0, "affects_score": False},
            {"key": "stolen-base", "label": "Stolen base", "value": 0, "affects_score": False},
            {"key": "error", "label": "Error", "value": 0, "affects_score": False},
            {"key": "hit-by-pitch", "label": "Hit by pitch", "value": 0, "affects_score": False},
        ],
        match_structure=[
            {"unit": "inning", "count": 9},
            {"unit": "extra_inning", "count": 1, "repeat": True},
        ],
        draw_resolution="sudden_death",
        league_points={"win": 3, "draw": 1, "loss": 0},
        tiebreakers=["points", "head_to_head", "score_difference", "score_for"],
    ),
    "tennis": _sport(
        label="Tennis",
        icon="tennisball-outline",
        sport="tennis",
        participant_type="individual",
        participant_types=["individual", "pair"],
        description=(
            "Points in a game are 0, 15, 30, 40, then game. At 40-40 the game "
            "goes to deuce and must be won by two points. A set is first to 6 "
            "games and must be won by 2. At 6-6 a tie-break is first to 7 and "
            "must be won by 2. A match is best of 3 sets. The winner is the side "
            "that takes the most sets. League points are 3 for a win and 0 for a "
            "loss. The table uses points, then sets difference, then games "
            "difference, then the head-to-head result."
        ),
        draw_allowed=False,
        win_condition="most_units_won",
        score_types=TENNIS_SCORES,
        match_structure=TENNIS_STRUCTURE,
        tiebreakers=["points", "units_difference", "score_difference", "head_to_head"],
    ),
    "squash": _sport(
        label="Squash",
        icon="tennisball-outline",
        sport="squash",
        participant_type="individual",
        description=(
            "PAR scoring: a game is first to 11 and must be won by 2. A match is "
            "best of 5 games. The winner is the player who takes the most games. "
            "League points are 3 for a win and 0 for a loss. The table uses points, "
            "then games difference, then points difference, then the head-to-head result."
        ),
        draw_allowed=False,
        win_condition="most_units_won",
        score_types=[{"key": "point", "label": "Point", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "game", "count": 5, "best_of": 5, "first_to": 11, "win_by": 2}
        ],
        tiebreakers=["points", "units_difference", "score_difference", "head_to_head"],
    ),
    "badminton": _sport(
        label="Badminton",
        icon="tennisball-outline",
        sport="badminton",
        participant_type="individual",
        participant_types=["individual", "pair"],
        description=(
            "Rally scoring: a game is first to 21 and must be won by 2, and it "
            "ends at 30 even if the margin is one. A match is best of 3 games. "
            "League points are 3 for a win and 0 for a loss. The table uses points, "
            "then games difference, then points difference."
        ),
        draw_allowed=False,
        win_condition="most_units_won",
        score_types=[{"key": "point", "label": "Point", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "game", "count": 3, "best_of": 3, "first_to": 21, "win_by": 2, "cap": 30}
        ],
        tiebreakers=["points", "units_difference", "score_difference"],
    ),
    "table_tennis": _sport(
        label="Table tennis",
        icon="tennisball-outline",
        sport="table tennis",
        participant_type="individual",
        participant_types=["individual", "pair"],
        description=(
            "A game is first to 11 and must be won by 2. A match is best of 5 "
            "games. League points are 3 for a win and 0 for a loss. The table uses "
            "points, then games ratio, then points ratio, then the head-to-head result."
        ),
        draw_allowed=False,
        win_condition="most_units_won",
        score_types=[{"key": "point", "label": "Point", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "game", "count": 5, "best_of": 5, "first_to": 11, "win_by": 2}
        ],
        tiebreakers=["points", "units_ratio", "score_ratio", "head_to_head"],
    ),
    "padel": _sport(
        label="Padel",
        icon="tennisball-outline",
        sport="padel",
        participant_type="pair",
        participant_types=["pair"],
        description=(
            "A pair plays the same scoring as tennis: best of 3 sets, games to 6 "
            "won by 2, and a tie-break at 6-6. League points are 3 for a win and "
            "0 for a loss."
        ),
        draw_allowed=False,
        win_condition="most_units_won",
        score_types=TENNIS_SCORES,
        match_structure=TENNIS_STRUCTURE,
        tiebreakers=["points", "units_difference", "score_difference", "head_to_head"],
    ),
    "darts_501": _sport(
        label="Darts (501)",
        icon="locate-outline",
        sport="darts",
        participant_type="individual",
        description=(
            "Each leg starts at 501 and counts down. A leg must finish on a double "
            "or the bullseye. A score that would finish on 1, or go below 0, is a "
            "bust and that turn does not count. A match is best of 5 legs. The "
            "player who wins the most legs wins. With an odd number of legs there "
            "is no draw. The table uses points, then legs difference, then legs won, "
            "then the head-to-head result. Three-dart average, checkout percentage, "
            "and 180s are recorded beside the score."
        ),
        draw_allowed=False,
        win_condition="count_down_to_zero",
        score_types=[
            {"key": "visit", "label": "Visit", "value": 1, "affects_score": True},
            {"key": "bust", "label": "Bust", "value": 0, "affects_score": False},
            {"key": "one-eighty", "label": "180", "value": 0, "affects_score": False},
            {"key": "checkout", "label": "Checkout", "value": 0, "affects_score": False},
        ],
        match_structure=[
            {
                "unit": "leg",
                "count": 5,
                "best_of": 5,
                "start": 501,
                "illegal_remaining": [1],
            }
        ],
        tiebreakers=["points", "units_difference", "units_for", "head_to_head"],
    ),
    "snooker": _sport(
        label="Snooker",
        icon="ellipse-outline",
        sport="snooker",
        participant_type="individual",
        description=(
            "Reds are 1, yellow 2, green 3, brown 4, blue 5, pink 6, and black 7. "
            "A foul gives the opponent at least 4. A frame is won by the higher "
            "score. If the frame is tied after the final black, the black is "
            "re-spotted. A match is best of 7 frames. The table uses points, then "
            "frames difference, then the head-to-head result. Highest break and "
            "century breaks are recorded beside the score."
        ),
        draw_allowed=False,
        win_condition="most_units_won",
        score_types=[
            {"key": "red", "label": "Red", "value": 1, "affects_score": True},
            {"key": "yellow", "label": "Yellow", "value": 2, "affects_score": True},
            {"key": "green", "label": "Green", "value": 3, "affects_score": True},
            {"key": "brown", "label": "Brown", "value": 4, "affects_score": True},
            {"key": "blue", "label": "Blue", "value": 5, "affects_score": True},
            {"key": "pink", "label": "Pink", "value": 6, "affects_score": True},
            {"key": "black", "label": "Black", "value": 7, "affects_score": True},
            {"key": "foul", "label": "Foul", "value": 4, "affects_score": True, "awards": "opponent"},
            {"key": "respotted-black", "label": "Re-spotted black", "value": 7, "affects_score": True},
            {"key": "century", "label": "Century break", "value": 0, "affects_score": False},
        ],
        match_structure=[{"unit": "frame", "count": 7, "best_of": 7}],
        tiebreakers=["points", "units_difference", "head_to_head"],
    ),
    "pool_8ball": _sport(
        label="Pool (8-ball)",
        icon="disc-outline",
        sport="pool",
        participant_type="individual",
        description=(
            "A rack is won by legally potting the 8-ball. A match is a race to 5 "
            "racks. League points are 3 for a win and 0 for a loss. The table uses "
            "points, then racks difference, then the head-to-head result."
        ),
        draw_allowed=False,
        win_condition="most_units_won",
        score_types=[{"key": "rack", "label": "8-ball", "value": 1, "affects_score": True}],
        match_structure=[{"unit": "rack", "count": 9, "race_to": 5}],
        tiebreakers=["points", "units_difference", "head_to_head"],
    ),
    "chess": _sport(
        label="Chess",
        icon="grid-outline",
        sport="chess",
        participant_type="individual",
        description=(
            "A won game scores 1, a draw scores 0.5, and a loss scores 0. The "
            "league table also awards 3 for a win, 1 for a draw, and 0 for a loss, "
            "and shows the game score beside it. A knockout draw goes to rapid "
            "games, then an Armageddon game. The table uses points, then the "
            "head-to-head result, then Sonneborn-Berger, then the number of wins."
        ),
        score_types=[
            {"key": "game-point", "label": "Game point", "value": 1, "affects_score": True},
            {"key": "draw-point", "label": "Draw point", "value": 0.5, "affects_score": True},
        ],
        match_structure=[
            {"unit": "game", "count": 1},
            {"unit": "rapid", "count": 1, "affects_total": False, "resolves_draw": True},
            {"unit": "armageddon", "count": 1, "affects_total": False, "resolves_draw": True},
        ],
        draw_resolution="tiebreak",
        tiebreakers=["points", "head_to_head", "sonneborn_berger", "wins"],
    ),
    "scrabble": _sport(
        label="Scrabble",
        icon="extension-puzzle-outline",
        sport="scrabble",
        participant_type="individual",
        description=(
            "Each turn adds letter scores, with double or triple letters and "
            "double or triple words. Using all 7 tiles scores a 50-point bingo. "
            "At the end, unplayed tiles are subtracted from each player and added "
            "to the player who went out. The higher total wins. A draw is possible. "
            "A knockout tie is replayed. The table uses points, then the spread, "
            "then the head-to-head result."
        ),
        draw_resolution="replay",
        score_types=[
            {"key": "turn", "label": "Turn", "value": 1, "affects_score": True},
            {"key": "bingo", "label": "Bingo", "value": 50, "affects_score": True},
            {"key": "unplayed", "label": "Unplayed tiles", "value": -1, "affects_score": True},
            {"key": "tiles-out", "label": "Tiles added", "value": 1, "affects_score": True},
        ],
        match_structure=[{"unit": "game", "count": 1}],
        tiebreakers=["points", "score_difference", "head_to_head"],
    ),
    "backgammon": _sport(
        label="Backgammon",
        icon="dice-outline",
        sport="backgammon",
        participant_type="individual",
        description=(
            "A match is played to 7 points. A single game is 1, a gammon is 2, "
            "and a backgammon is 3, multiplied by the doubling cube. The first "
            "player to 7 wins. The table uses points, then match-points difference, "
            "then the head-to-head result."
        ),
        draw_allowed=False,
        win_condition="first_to_target",
        target=7,
        score_types=[
            {"key": "single", "label": "Single", "value": 1, "affects_score": True},
            {"key": "gammon", "label": "Gammon", "value": 2, "affects_score": True},
            {"key": "backgammon", "label": "Backgammon", "value": 3, "affects_score": True},
        ],
        match_structure=[{"unit": "game", "count": 1, "target": 7}],
        tiebreakers=["points", "score_difference", "head_to_head"],
    ),
    "dominoes_fives": _sport(
        label="Dominoes (All Fives)",
        icon="grid-outline",
        sport="dominoes",
        participant_type="individual",
        participant_types=["individual", "pair"],
        description=(
            "Score whenever the open ends add up to a multiple of 5. The first "
            "side to 250 wins. League points are 3 for a win and 0 for a loss. "
            "The table uses points, then points difference."
        ),
        draw_allowed=False,
        win_condition="first_to_target",
        target=250,
        score_types=[{"key": "fives", "label": "Fives", "value": 1, "affects_score": True}],
        match_structure=[{"unit": "hand", "count": 1, "target": 250}],
        tiebreakers=["points", "score_difference"],
    ),
    "golf_stableford": _sport(
        label="Golf (Stableford)",
        icon="golf-outline",
        sport="golf",
        contest_type="accumulation",
        participant_type="individual",
        formats_allowed=["league"],
        description=(
            "Each hole scores against par: albatross 5, eagle 4, birdie 3, par 2, "
            "bogey 1, and double bogey or worse 0. A handicap adds points. The "
            "highest total ranks first. A tie uses the last 9 holes, then the last "
            "6, the last 3, and then the last hole."
        ),
        win_condition="highest_total",
        accumulation_ranking="highest_first",
        handicap=True,
        countback_windows=[9, 6, 3, 1],
        score_types=[
            {"key": "albatross", "label": "Albatross", "value": 5, "affects_score": True},
            {"key": "eagle", "label": "Eagle", "value": 4, "affects_score": True},
            {"key": "birdie", "label": "Birdie", "value": 3, "affects_score": True},
            {"key": "par", "label": "Par", "value": 2, "affects_score": True},
            {"key": "bogey", "label": "Bogey", "value": 1, "affects_score": True},
            {"key": "double", "label": "Double bogey or worse", "value": 0, "affects_score": True},
        ],
        match_structure=[{"unit": "hole", "count": 18}],
        league_points={"win": 0, "draw": 0, "loss": 0},
        tiebreakers=["countback"],
    ),
    "bowling": _sport(
        label="Ten-pin bowling",
        icon="disc-outline",
        sport="bowling",
        contest_type="accumulation",
        participant_type="individual",
        participant_types=["individual", "team"],
        formats_allowed=["league"],
        description=(
            "Enter every ball in order. A strike is 10 plus the next two balls. "
            "For a spare, enter the pins of the closing ball as Spare: it scores "
            "those pins plus the next ball. Any other ball is Pins. In the tenth "
            "frame, enter the extra balls as Bonus ball: they only pay the strike "
            "or spare before them, so nothing counts twice. The highest score is "
            "300. Ranking is the total of 3 games, and a tie uses the highest "
            "single game."
        ),
        win_condition="highest_total",
        accumulation_ranking="highest_first",
        score_types=[
            {"key": "strike", "label": "Strike", "value": 10, "affects_score": True, "bonus_next": 2},
            {"key": "spare", "label": "Spare (pins)", "value": 1, "affects_score": True, "bonus_next": 1},
            {"key": "pins", "label": "Pins", "value": 1, "affects_score": True},
            {
                "key": "bonus-ball",
                "label": "Bonus ball (pins)",
                "value": 1,
                "affects_score": True,
                "bonus_only": True,
            },
        ],
        match_structure=[{"unit": "frame", "count": 10}],
        league_points={"win": 0, "draw": 0, "loss": 0},
        tiebreakers=["best_single"],
    ),
    "archery": _sport(
        label="Archery",
        icon="locate-outline",
        sport="archery",
        contest_type="accumulation",
        participant_type="individual",
        formats_allowed=["league"],
        description=(
            "Rings score 10 down to 1. A miss is 0. An X counts as 10. An end is "
            "6 arrows, and a round is 72 arrows. The highest total ranks first. "
            "A tie uses the number of 10s, then the number of Xs."
        ),
        win_condition="highest_total",
        accumulation_ranking="highest_first",
        score_types=[
            {"key": "x", "label": "X", "value": 10, "affects_score": True},
            {"key": "ring-10", "label": "10", "value": 10, "affects_score": True},
            {"key": "ring-9", "label": "9", "value": 9, "affects_score": True},
            {"key": "ring-8", "label": "8", "value": 8, "affects_score": True},
            {"key": "ring-7", "label": "7", "value": 7, "affects_score": True},
            {"key": "ring-6", "label": "6", "value": 6, "affects_score": True},
            {"key": "ring-5", "label": "5", "value": 5, "affects_score": True},
            {"key": "ring-4", "label": "4", "value": 4, "affects_score": True},
            {"key": "ring-3", "label": "3", "value": 3, "affects_score": True},
            {"key": "ring-2", "label": "2", "value": 2, "affects_score": True},
            {"key": "ring-1", "label": "1", "value": 1, "affects_score": True},
            {"key": "miss", "label": "Miss", "value": 0, "affects_score": True},
        ],
        match_structure=[{"unit": "end", "count": 12}],
        league_points={"win": 0, "draw": 0, "loss": 0},
        tiebreakers=["category:ring-10+x", "category:x"],
    ),
    "athletics": _sport(
        label="Athletics",
        icon="stopwatch-outline",
        sport="athletics",
        contest_type="accumulation",
        participant_type="individual",
        formats_allowed=["league"],
        description=(
            "Track events record a time, and the lowest time is best. Field events "
            "record a distance or a height, and the highest is best. An event awards "
            "8, 7, 6, 5, 4, 3, 2, and 1 for the first eight places. A tie in a field "
            "event uses the next-best attempt. A tie on the track uses the time to "
            "the hundredth."
        ),
        performance="lower",
        placing_points=[8, 7, 6, 5, 4, 3, 2, 1],
        score_types=[
            {
                "key": "time",
                "label": "Time",
                "value": 1,
                "affects_score": True,
                "aggregate": "best",
                "better": "lower",
                "description": "Seconds. The lowest time ranks first.",
            },
            {
                "key": "distance",
                "label": "Distance or height",
                "value": 1,
                "affects_score": True,
                "aggregate": "best",
                "better": "higher",
                "description": "Metres. The longest or highest mark ranks first.",
            },
        ],
        match_structure=[{"unit": "attempt", "count": 6}],
        league_points={"win": 0, "draw": 0, "loss": 0},
        tiebreakers=["points", "next_attempt"],
        accumulation_ranking="highest_first",
    ),
    "quiz": _sport(
        label="Pub quiz",
        icon="help-circle-outline",
        sport="quiz",
        contest_type="accumulation",
        participant_type="team",
        formats_allowed=["league"],
        description=(
            "Each correct answer in a round is 1 point. One joker round per team "
            "doubles that round. The highest total ranks first. A tie is broken by "
            "a nearest-number question: the closest answer ranks first."
        ),
        win_condition="highest_total",
        accumulation_ranking="highest_first",
        score_types=[
            {"key": "answer", "label": "Correct answer", "value": 1, "affects_score": True},
            {
                "key": "joker",
                "label": "Joker",
                "value": 0,
                "affects_score": False,
                "multiplies_unit": 2,
                "description": "Doubles every point in the round where it is played.",
            },
            {
                "key": "nearest",
                "label": "Nearest-number miss",
                "value": 1,
                "affects_score": False,
                "better": "lower",
                "description": "How far the tie-break guess was from the answer. Lower is better.",
            },
        ],
        match_structure=[{"unit": "round", "count": 8}],
        league_points={"win": 0, "draw": 0, "loss": 0},
        tiebreakers=["category:nearest"],
    ),
    "yahtzee": _sport(
        label="Yahtzee",
        icon="dice-outline",
        sport="yahtzee",
        contest_type="accumulation",
        participant_type="individual",
        formats_allowed=["league"],
        description=(
            "The upper section is ones through sixes. A total of 63 or more scores "
            "a 35 bonus. Three of a kind and four of a kind score the dice total. "
            "A full house is 25, a small straight 30, a large straight 40, Yahtzee "
            "50, and chance the dice total. Each extra Yahtzee is 100. The highest "
            "total over the games ranks first."
        ),
        win_condition="highest_total",
        accumulation_ranking="highest_first",
        bonuses=[{
            "categories": ["ones", "twos", "threes", "fours", "fives", "sixes"],
            "when_at_least": 63,
            "award": 35,
        }],
        score_types=[
            {"key": "ones", "label": "Ones", "value": 1, "affects_score": True},
            {"key": "twos", "label": "Twos", "value": 1, "affects_score": True},
            {"key": "threes", "label": "Threes", "value": 1, "affects_score": True},
            {"key": "fours", "label": "Fours", "value": 1, "affects_score": True},
            {"key": "fives", "label": "Fives", "value": 1, "affects_score": True},
            {"key": "sixes", "label": "Sixes", "value": 1, "affects_score": True},
            {"key": "three-kind", "label": "Three of a kind", "value": 1, "affects_score": True},
            {"key": "four-kind", "label": "Four of a kind", "value": 1, "affects_score": True},
            {"key": "full-house", "label": "Full house", "value": 25, "affects_score": True},
            {"key": "small-straight", "label": "Small straight", "value": 30, "affects_score": True},
            {"key": "large-straight", "label": "Large straight", "value": 40, "affects_score": True},
            {"key": "yahtzee", "label": "Yahtzee", "value": 50, "affects_score": True},
            {"key": "chance", "label": "Chance", "value": 1, "affects_score": True},
            {"key": "extra-yahtzee", "label": "Extra Yahtzee", "value": 100, "affects_score": True},
        ],
        match_structure=[{"unit": "game", "count": 1}],
        league_points={"win": 0, "draw": 0, "loss": 0},
        tiebreakers=["score_for"],
    ),
    "kpi": _sport(
        label="KPIs",
        icon="stats-chart-outline",
        sport="",
        kind="work",
        contest_type="accumulation",
        participant_type="individual",
        participant_types=["individual", "team"],
        formats_allowed=["league"],
        locked=False,
        lock_when_started=True,
        description=(
            "Each competition names its own criteria when it is created, such as "
            "a closed sale or a logged call, and each criterion explains itself on "
            "the league page. Scoring locks once the competition starts. The "
            "highest total ranks first. A tie uses the most recent activity."
        ),
        win_condition="highest_total",
        accumulation_ranking="highest_first",
        score_types=[],
        match_structure=[],
        league_points={"win": 0, "draw": 0, "loss": 0},
        tiebreakers=["recent"],
        table_mode="points",
    ),
    "cleaning": _sport(
        label="Cleaning rota",
        icon="water-outline",
        sport="",
        kind="home",
        contest_type="accumulation",
        participant_type="individual",
        formats_allowed=["league"],
        locked=False,
        lock_when_started=True,
        description=(
            "Dishes are 2, the bathroom is 5, and laundry is 3. Finishing on time "
            "adds a bonus. Each task's points are described on the league page. "
            "Scoring locks once the week starts. The highest total ranks first "
            "for the week and across the season."
        ),
        win_condition="highest_total",
        accumulation_ranking="highest_first",
        score_types=[
            {"key": "dishes", "label": "Dishes", "value": 2, "affects_score": True, "description": "Washed and put away."},
            {"key": "bathroom", "label": "Bathroom", "value": 5, "affects_score": True, "description": "Sink, toilet, and floor."},
            {"key": "laundry", "label": "Laundry", "value": 3, "affects_score": True, "description": "Washed, dried, and folded."},
            {"key": "on-time", "label": "On time", "value": 1, "affects_score": True, "description": "Finished on the day it was due."},
        ],
        match_structure=[{"unit": "week", "count": 1}],
        league_points={"win": 0, "draw": 0, "loss": 0},
        tiebreakers=["score_for"],
        table_mode="points",
    ),
}
