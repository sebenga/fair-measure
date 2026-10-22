"""Locked presets for the Summer Olympic sports, as data.

Each preset follows its International Federation's rules and names that body and
its rulebook. Performance sports use a result type (apps.results.calculators);
team, racket and combat sports use the head-to-head engine. Items marked VERIFY
change between editions and should be checked against the current rulebook and
the event list of the Games being modelled. The engine never branches on these
keys.
"""

from __future__ import annotations

from .catalog import RED_CARD, YELLOW_CARD, _sport

PLACING = [8, 7, 6, 5, 4, 3, 2, 1]

TIMED_STATUSES = [
    {"code": "DQ", "label": "Disqualified"},
    {"code": "DNF", "label": "Did not finish"},
    {"code": "DNS", "label": "Did not start"},
]
FIELD_STATUSES = [
    {"code": "NM", "label": "No mark"},
    {"code": "DQ", "label": "Disqualified"},
    {"code": "DNS", "label": "Did not start"},
]
JUDGED_STATUSES = [
    {"code": "DQ", "label": "Disqualified"},
    {"code": "DNS", "label": "Did not start"},
    {"code": "WD", "label": "Withdrawn"},
]
BOUT_STATUSES = [
    {"code": "DQ", "label": "Disqualified"},
    {"code": "WO", "label": "Walkover"},
]


def _performance(
    *,
    label: str,
    icon: str,
    sport: str,
    governing_body: str,
    rulebook: str,
    result_type: str,
    result_config: dict,
    description: str,
    participant_type: str = "individual",
    statuses: list[dict] | None = None,
    rules: list[dict] | None = None,
) -> dict:
    """A sport ranked per event (a heat, a final) rather than by match results."""

    return {
        "label": label,
        "icon": icon,
        "description": description,
        "sport": sport,
        "kind": "sport",
        "format": "league",
        "formats_allowed": ["league"],
        "contest_type": "accumulation",
        "participant_type": participant_type,
        "score_types": [],
        "match_structure": [],
        "win_condition": "highest_total",
        "draw_allowed": True,
        "draw_resolution": "replay",
        "league_points": {"win": 0, "draw": 0, "loss": 0},
        "tiebreakers": ["points", "placings", "name"],
        "accumulation_ranking": "highest_first",
        "placing_points": PLACING,
        "locked": True,
        "official_results": True,
        "result_type": result_type,
        "result_config": result_config,
        "statuses": statuses or TIMED_STATUSES,
        "governing_body": governing_body,
        "rulebook": rulebook,
        "rules": rules or [],
    }


def _match(*, governing_body: str, rulebook: str, **overrides) -> dict:
    """A head-to-head sport, confirmed by officials."""

    return _sport(
        official_results=True, governing_body=governing_body, rulebook=rulebook, **overrides
    )


TIMED = {"decimals": 2}
SWIM = _performance(
    label="Swimming",
    icon="water-outline",
    sport="swimming",
    governing_body="World Aquatics",
    rulebook="World Aquatics Competition Regulations (Swimming)",
    result_type="timed_lowest",
    result_config={"decimals": 2},
    description=(
        "Fastest time wins, to a hundredth of a second; equal times share the place. "
        "Heats, then semi-finals, then a final of eight. A false start or a stroke "
        "infringement disqualifies."
    ),
)

OLYMPIC_PRESETS: dict[str, dict] = {
    # --- Aquatics -----------------------------------------------------------
    "swimming": SWIM,
    "marathon_swimming": _performance(
        label="Marathon swimming (10 km)",
        icon="water-outline",
        sport="marathon swimming",
        governing_body="World Aquatics",
        rulebook="World Aquatics Open Water Swimming Regulations",
        result_type="finishing_order",
        result_config={"record_fields": ["time"]},
        description="A 10 km open-water race. The order across the line decides the places.",
    ),
    "diving": _performance(
        label="Diving",
        icon="water-outline",
        sport="diving",
        governing_body="World Aquatics",
        rulebook="World Aquatics Competition Regulations (Diving)",
        result_type="judged_score",
        result_config={
            "judges": 7,
            "drop_high": 2,
            "drop_low": 2,
            "multiply_by_difficulty": True,
            "max_score": 10,
            "score_step": "0.5",
        },
        statuses=JUDGED_STATUSES,
        description=(
            "Seven judges mark each dive from 0 to 10. The two highest and two lowest "
            "marks are dropped, and the middle three are added and multiplied by the "
            "dive's degree of difficulty. The total of all dives ranks the divers. "
            "Women dive five times and men six (set per event); synchronised diving uses "
            "11 judges (VERIFY)."
        ),
    ),
    "artistic_swimming": _performance(
        label="Artistic swimming",
        icon="water-outline",
        sport="artistic swimming",
        governing_body="World Aquatics",
        rulebook="World Aquatics Artistic Swimming Rules",
        result_type="judged_score",
        result_config={"combine": "average", "decimals": 4},
        participant_type="team",
        statuses=JUDGED_STATUSES,
        description=(
            "Routines are scored for execution, artistic impression and difficulty; "
            "the technical and free routines add up (VERIFY the current formula)."
        ),
    ),
    "water_polo": _match(
        label="Water polo",
        icon="water-outline",
        sport="water polo",
        governing_body="World Aquatics",
        rulebook="World Aquatics Water Polo Rules",
        description=(
            "A goal is 1. Four quarters of 8 minutes. A level knockout game goes to a "
            "penalty shoot-out. Exclusions are recorded without points."
        ),
        score_types=[
            {"key": "goal", "label": "Goal", "value": 1, "affects_score": True},
            {"key": "exclusion", "label": "Exclusion", "value": 0, "affects_score": False},
            {
                "key": "shootout-goal",
                "label": "Shoot-out goal",
                "value": 1,
                "affects_score": True,
            },
        ],
        match_structure=[
            {"unit": "quarter", "count": 4, "minutes": 8},
            {"unit": "penalties", "count": 1, "affects_total": False, "resolves_draw": True},
        ],
        draw_resolution="penalties",
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
    ),
    # --- Athletics ------------------------------------------------------------
    "athletics_track": _performance(
        label="Athletics: track",
        icon="stopwatch-outline",
        sport="athletics",
        governing_body="World Athletics",
        rulebook="World Athletics Competition and Technical Rules",
        result_type="timed_lowest",
        result_config={"decimals": 2, "reaction_limit": "0.100"},
        description=(
            "Fastest time wins, rounded up to the hundredth. Heats, semi-finals and a "
            "final; qualifiers go through by place (Q) or by time (q). A reaction under "
            "0.100 s is a false start and disqualifies."
        ),
    ),
    "athletics_field_attempts": _performance(
        label="Athletics: throws and horizontal jumps",
        icon="stopwatch-outline",
        sport="athletics",
        governing_body="World Athletics",
        rulebook="World Athletics Competition and Technical Rules",
        result_type="measured_highest",
        result_config={"max_attempts": 6},
        statuses=FIELD_STATUSES,
        description=(
            "Three attempts each, then the best eight take three more. The best mark "
            "wins; a tie goes to the better second-best mark, and so on. A foul is "
            "recorded as x."
        ),
    ),
    "athletics_field_heights": _performance(
        label="Athletics: high jump and pole vault",
        icon="stopwatch-outline",
        sport="athletics",
        governing_body="World Athletics",
        rulebook="World Athletics Competition and Technical Rules",
        result_type="measured_highest",
        result_config={"mode": "heights", "failures_to_eliminate": 3},
        statuses=FIELD_STATUSES,
        description=(
            "Three consecutive failures eliminate. The highest height cleared wins; a "
            "tie goes to fewest failures at that height, then fewest failures in total. "
            "A jump-off decides a tie for first (VERIFY)."
        ),
    ),
    "athletics_road": _performance(
        label="Athletics: road events",
        icon="walk-outline",
        sport="athletics",
        governing_body="World Athletics",
        rulebook="World Athletics Competition and Technical Rules",
        result_type="finishing_order",
        result_config={"record_fields": ["time"]},
        description=(
            "Marathon and race walk: the order across the line decides the places. In "
            "race walk, enough red cards from the judges disqualify (VERIFY the limit)."
        ),
    ),
    "combined_events_decathlon": _performance(
        label="Athletics: decathlon",
        icon="medal-outline",
        sport="athletics",
        governing_body="World Athletics",
        rulebook="World Athletics Scoring Tables for Combined Events",
        result_type="combined_events",
        result_config={"table": "decathlon"},
        statuses=TIMED_STATUSES,
        description=(
            "Ten events over two days. Each mark earns points from the World Athletics "
            "tables, and the highest total wins. Level totals go to the athlete with "
            "more points in more events."
        ),
    ),
    "combined_events_heptathlon": _performance(
        label="Athletics: heptathlon",
        icon="medal-outline",
        sport="athletics",
        governing_body="World Athletics",
        rulebook="World Athletics Scoring Tables for Combined Events",
        result_type="combined_events",
        result_config={"table": "heptathlon"},
        statuses=TIMED_STATUSES,
        description="Seven events scored from the World Athletics tables; the highest total wins.",
    ),
    # --- Team and racket sports --------------------------------------------------
    "softball": _match(
        label="Softball",
        icon="baseball-outline",
        sport="softball",
        governing_body="WBSC",
        rulebook="WBSC Official Rules of Softball",
        description="A run is 1. Seven innings; extra innings until there is a winner. No draws.",
        draw_allowed=False,
        score_types=[{"key": "run", "label": "Run", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "inning", "count": 7},
            {"unit": "extra_inning", "count": 1, "repeat": True},
        ],
        draw_resolution="sudden_death",
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
    ),
    "basketball_3x3": _match(
        label="3x3 basketball",
        icon="basketball-outline",
        sport="3x3 basketball",
        governing_body="FIBA",
        rulebook="FIBA 3x3 Official Rules",
        description=(
            "A shot inside the arc is 1, beyond it 2. First to 21 wins; otherwise the "
            "higher score after 10 minutes. Level at time goes to overtime, first to 2 "
            "points (VERIFY)."
        ),
        draw_allowed=False,
        score_types=[
            {"key": "one-point", "label": "1-point shot", "value": 1, "affects_score": True},
            {"key": "two-point", "label": "2-point shot", "value": 2, "affects_score": True},
        ],
        match_structure=[{"unit": "game", "count": 1, "minutes": 10, "target": 21}],
        win_condition="first_to_target",
        target=21,
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
    ),
    "beach_volleyball": _match(
        label="Beach volleyball",
        icon="football-outline",
        sport="beach volleyball",
        governing_body="FIVB",
        rulebook="FIVB Official Beach Volleyball Rules",
        description="Teams of two. Best of three sets: 21, 21, then 15, each won by two points.",
        participant_type="team",
        draw_allowed=False,
        score_types=[{"key": "point", "label": "Point", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "set", "count": 2, "best_of": 3, "first_to": 21, "win_by": 2},
            {"unit": "set", "count": 1, "first_to": 15, "win_by": 2},
        ],
        win_condition="most_units_won",
        tiebreakers=["points", "wins", "units_ratio", "score_ratio"],
    ),
    "handball": _match(
        label="Handball",
        icon="hand-left-outline",
        sport="handball",
        governing_body="IHF",
        rulebook="IHF Rules of the Game",
        description=(
            "A goal is 1. Two halves of 30 minutes. A level knockout game has two "
            "periods of 5 minutes' extra time, then a 7 m throw shoot-out."
        ),
        score_types=[
            {"key": "goal", "label": "Goal", "value": 1, "affects_score": True},
            {
                "key": "suspension",
                "label": "2-minute suspension",
                "value": 0,
                "affects_score": False,
            },
            YELLOW_CARD,
            RED_CARD,
            {
                "key": "seven-metre",
                "label": "7 m shoot-out goal",
                "value": 1,
                "affects_score": True,
            },
        ],
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 30},
            {"unit": "extra_time", "count": 2, "minutes": 5},
            {"unit": "shootout", "count": 1, "affects_total": False, "resolves_draw": True},
        ],
        draw_resolution="penalties",
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
    ),
    "rugby_sevens": _match(
        label="Rugby sevens",
        icon="american-football-outline",
        sport="rugby sevens",
        family="rugby_union",
        variant="sevens",
        family_label="Rugby union",
        variant_label="Sevens",
        governing_body="World Rugby",
        rulebook="World Rugby Laws of the Game (Sevens variations)",
        description=(
            "A try is 5, a conversion 2 (drop-kicked), a penalty or drop goal 3. "
            "Two halves of 7 minutes; finals are 2 × 10. Pool points are win 3, "
            "draw 2, loss 1. A level knockout goes to sudden-death extra time in "
            "5-minute periods. Usually run as pools, then cup, plate and bowl."
        ),
        score_types=[
            {"key": "try", "label": "Try", "value": 5, "affects_score": True},
            {"key": "conversion", "label": "Conversion", "value": 2, "affects_score": True},
            {"key": "penalty-goal", "label": "Penalty goal", "value": 3, "affects_score": True},
            {"key": "drop-goal", "label": "Drop goal", "value": 3, "affects_score": True},
            {"key": "penalty-try", "label": "Penalty try", "value": 7, "affects_score": True},
            YELLOW_CARD,
            RED_CARD,
        ],
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 7, "clock": "running"},
            {"unit": "sudden_death", "count": 1, "minutes": 5, "repeat": True, "extra": True},
        ],
        draw_resolution="sudden_death",
        league_points={"win": 3, "draw": 2, "loss": 1},
        tiebreakers=["points", "score_difference", "category:try", "head_to_head"],
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
        team_sheet={
            "starters": 7,
            "min_on_field": 5,
            "min_squad": 7,
            "bench_max": 5,
            "max_substitutions": 5,
            "rolling_substitutions": True,
        },
        rules=[
            {
                "name": "League points",
                "description": "In a pool, a win is 3, a draw is 2, a loss is 1.",
            },
            {"name": "Players", "description": "7 start, with 5 on the bench. Substitutions are rolling."},
            {
                "name": "Format",
                "description": "Pools, then cup, plate and bowl knockout brackets.",
            },
            {
                "name": "Knockout",
                "description": "A level game goes to sudden-death extra time in 5-minute periods.",
            },
        ],
    ),
    "flag_football": _match(
        label="Flag football",
        icon="american-football-outline",
        sport="flag football",
        governing_body="IFAF",
        rulebook="IFAF Flag Football Rules",
        description=(
            "A touchdown is 6, the try after it 1 or 2, a safety 2. Two halves of 20 "
            "minutes (VERIFY). No contact: a play ends when the flag is pulled."
        ),
        score_types=[
            {"key": "touchdown", "label": "Touchdown", "value": 6, "affects_score": True},
            {"key": "pat-one", "label": "Try (1 point)", "value": 1, "affects_score": True},
            {"key": "pat-two", "label": "Try (2 points)", "value": 2, "affects_score": True},
            {"key": "safety", "label": "Safety", "value": 2, "affects_score": True},
        ],
        match_structure=[
            {"unit": "half", "count": 2, "minutes": 20},
            {"unit": "overtime", "count": 1, "repeat": True},
        ],
        draw_resolution="sudden_death",
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
    ),
    "lacrosse_sixes": _match(
        label="Lacrosse sixes",
        icon="ellipse-outline",
        sport="lacrosse",
        governing_body="World Lacrosse",
        rulebook="World Lacrosse Sixes Rules",
        description=(
            "A goal is 1. Four quarters of 8 minutes (VERIFY); sudden-death overtime if level."
        ),
        score_types=[{"key": "goal", "label": "Goal", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "quarter", "count": 4, "minutes": 8},
            {"unit": "overtime", "count": 1, "repeat": True},
        ],
        draw_resolution="sudden_death",
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
    ),
    "fencing": _match(
        label="Fencing (individual)",
        icon="flash-outline",
        sport="fencing",
        governing_body="FIE",
        rulebook="FIE Technical Rules",
        description=(
            "A hit is 1. Pool bouts go to 5; direct-elimination bouts go to 15 over "
            "three periods of 3 minutes, and the higher score wins at time. A level "
            "bout goes to a one-minute priority period (VERIFY)."
        ),
        participant_type="individual",
        draw_allowed=False,
        score_types=[{"key": "hit", "label": "Hit", "value": 1, "affects_score": True}],
        match_structure=[{"unit": "period", "count": 3, "minutes": 3, "target": 15}],
        win_condition="first_to_target",
        target=15,
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
    ),
    "fencing_team": _match(
        label="Fencing (team relay)",
        icon="flash-outline",
        sport="fencing",
        governing_body="FIE",
        rulebook="FIE Technical Rules",
        description=(
            "Nine relay bouts; the first team to 45 hits, or the higher score at the end, wins."
        ),
        draw_allowed=False,
        score_types=[{"key": "hit", "label": "Hit", "value": 1, "affects_score": True}],
        match_structure=[{"unit": "relay", "count": 9, "minutes": 3, "target": 45}],
        win_condition="first_to_target",
        target=45,
        formats_allowed=["knockout", "league"],
    ),
    # --- Combat sports ----------------------------------------------------------------
    "boxing": _performance(
        label="Boxing",
        icon="fitness-outline",
        sport="boxing",
        governing_body="World Boxing",
        rulebook="World Boxing Technical and Competition Rules (VERIFY the governing body)",
        result_type="combat_decision",
        result_config={
            "decide_by": "cards",
            "rounds": 3,
            "methods": [
                {"code": "DEC", "label": "Judges' decision"},
                {"code": "RSC", "label": "Referee stops contest"},
                {"code": "KO", "label": "Knockout"},
                {"code": "DQ", "label": "Disqualification"},
                {"code": "WO", "label": "Walkover"},
            ],
        },
        statuses=BOUT_STATUSES,
        description=(
            "Three rounds of 3 minutes. Five judges score every round 10-9 (or wider). "
            "A knockout, referee stoppage or disqualification ends the bout; otherwise "
            "the boxer who wins more judges' cards wins. Both losing semi-finalists win "
            "bronze."
        ),
    ),
    "judo": _performance(
        label="Judo",
        icon="fitness-outline",
        sport="judo",
        governing_body="IJF",
        rulebook="IJF Sport and Organisation Rules",
        result_type="combat_decision",
        result_config={
            "decide_by": "score",
            "methods": [
                {"code": "IPP", "label": "Ippon"},
                {"code": "WAZ", "label": "Waza-ari"},
                {"code": "GS", "label": "Golden score"},
                {"code": "HSM", "label": "Hansoku-make (3 shido or a direct penalty)"},
            ],
        },
        statuses=BOUT_STATUSES,
        description=(
            "Four minutes. Ippon wins outright, and two waza-ari make ippon. If level, "
            "golden score continues until the next score. Three shido penalties are "
            "hansoku-make. Repechage gives two bronzes."
        ),
    ),
    "taekwondo": _performance(
        label="Taekwondo",
        icon="fitness-outline",
        sport="taekwondo",
        governing_body="World Taekwondo",
        rulebook="World Taekwondo Competition Rules",
        result_type="combat_decision",
        result_config={
            "decide_by": "score",
            "methods": [
                {"code": "RND", "label": "Won two of three rounds"},
                {"code": "PTG", "label": "Point gap"},
                {"code": "RSC", "label": "Referee stops contest"},
                {"code": "DSQ", "label": "Disqualification (penalties)"},
            ],
        },
        statuses=BOUT_STATUSES,
        description=(
            "Best of three rounds. Points come from punches and kicks, 1 to 5 by "
            "technique and target (VERIFY the table); the score here is rounds won. "
            "Both losing semi-finalists after repechage win bronze."
        ),
    ),
    "wrestling": _performance(
        label="Wrestling",
        icon="fitness-outline",
        sport="wrestling",
        governing_body="UWW",
        rulebook="UWW International Wrestling Rules",
        result_type="combat_decision",
        result_config={
            "decide_by": "score",
            "methods": [
                {"code": "VFA", "label": "Victory by fall"},
                {"code": "VSU", "label": "Technical superiority"},
                {"code": "VPO", "label": "Decision on points"},
                {"code": "DSQ", "label": "Disqualification"},
            ],
        },
        statuses=BOUT_STATUSES,
        description=(
            "Two periods of 3 minutes. A fall ends the bout; so does a lead of 10 "
            "(freestyle) or 8 (Greco-Roman) points (VERIFY). Otherwise the higher score "
            "wins. Repechage gives two bronzes."
        ),
    ),
    "breaking": _performance(
        label="Breaking",
        icon="musical-notes-outline",
        sport="breaking",
        governing_body="WDSF",
        rulebook="WDSF Breaking Competition Rules",
        result_type="combat_decision",
        result_config={
            "decide_by": "cards",
            "methods": [{"code": "DEC", "label": "Judges' votes"}],
        },
        statuses=BOUT_STATUSES,
        description=(
            "Head-to-head battles. Judges vote for the better dancer each round; the "
            "majority wins. Paris 2024 only, not on the LA 2028 programme (VERIFY)."
        ),
    ),
    # --- Water and wheels -----------------------------------------------------------------
    "canoe_sprint": _performance(
        label="Canoe sprint",
        icon="boat-outline",
        sport="canoe sprint",
        governing_body="ICF",
        rulebook="ICF Canoe Sprint Competition Rules",
        result_type="timed_lowest",
        result_config={"decimals": 3},
        description="Fastest time over 200, 500 or 1000 m wins. Heats, semi-finals and a final.",
    ),
    "canoe_slalom": _performance(
        label="Canoe slalom",
        icon="boat-outline",
        sport="canoe slalom",
        governing_body="ICF",
        rulebook="ICF Canoe Slalom Competition Rules",
        result_type="multi_run_aggregate",
        result_config={
            "aggregate": "best",
            "decimals": 2,
            "penalties": [
                {"key": "touches", "label": "Gate touches", "seconds": 2},
                {"key": "missed", "label": "Gates missed", "seconds": 50},
            ],
        },
        description=(
            "Time plus penalties: 2 s for touching a gate and 50 s for missing one "
            "(VERIFY). The best run counts in qualification; semi-final and final are "
            "single runs."
        ),
    ),
    "rowing": _performance(
        label="Rowing",
        icon="boat-outline",
        sport="rowing",
        governing_body="World Rowing",
        rulebook="World Rowing Rules of Racing",
        result_type="timed_lowest",
        result_config={"decimals": 2},
        description="2000 m. Fastest crew wins. Heats, repechage, semi-finals and A/B finals.",
    ),
    "sailing": _performance(
        label="Sailing",
        icon="boat-outline",
        sport="sailing",
        governing_body="World Sailing",
        rulebook="Racing Rules of Sailing",
        result_type="points_lowest",
        result_config={"discard_worst": 1, "double_last": True, "tie_break": "last_round"},
        description=(
            "Low-point scoring: 1 point for 1st, 2 for 2nd, and so on. The worst opening "
            "race is discarded (VERIFY), and the medal race counts double. A tie goes to "
            "the better medal-race place."
        ),
    ),
    "triathlon": _performance(
        label="Triathlon",
        icon="bicycle-outline",
        sport="triathlon",
        governing_body="World Triathlon",
        rulebook="World Triathlon Competition Rules",
        result_type="finishing_order",
        result_config={"record_fields": ["swim", "t1", "bike", "t2", "run", "time"]},
        description=(
            "Swim, bike and run. The order across the line decides the places; splits are recorded."
        ),
    ),
    "cycling_road": _performance(
        label="Cycling: road race",
        icon="bicycle-outline",
        sport="cycling",
        governing_body="UCI",
        rulebook="UCI Cycling Regulations: Road Races",
        result_type="finishing_order",
        result_config={"record_fields": ["time"]},
        description="A mass-start race; the order across the line decides the places.",
    ),
    "cycling_time_trial": _performance(
        label="Cycling: time trial",
        icon="bicycle-outline",
        sport="cycling",
        governing_body="UCI",
        rulebook="UCI Cycling Regulations: Road Races",
        result_type="timed_lowest",
        result_config={"decimals": 2},
        description="Riders start one at a time; the fastest time wins.",
    ),
    "cycling_track": _performance(
        label="Cycling: track omnium",
        icon="bicycle-outline",
        sport="cycling",
        governing_body="UCI",
        rulebook="UCI Cycling Regulations: Track Races",
        result_type="points_highest",
        result_config={"tie_break": "last_round"},
        description=(
            "Points from each race of the omnium add up; a tie goes to the better "
            "place in the final points race. Sprint, keirin and pursuit events follow "
            "their own formats (VERIFY)."
        ),
    ),
    "cycling_sprint": _match(
        label="Cycling: track sprint",
        icon="bicycle-outline",
        sport="cycling",
        governing_body="UCI",
        rulebook="UCI Cycling Regulations: Track Races",
        description="Two riders race head to head; the first to win two races takes the match.",
        participant_type="individual",
        draw_allowed=False,
        score_types=[{"key": "race-win", "label": "Race won", "value": 1, "affects_score": True}],
        match_structure=[{"unit": "race", "count": 3, "best_of": 3, "first_to": 1}],
        win_condition="most_units_won",
        tiebreakers=["points", "units_difference", "head_to_head"],
        formats_allowed=["knockout", "league"],
    ),
    "cycling_keirin": _performance(
        label="Cycling: keirin",
        icon="bicycle-outline",
        sport="cycling",
        governing_body="UCI",
        rulebook="UCI Cycling Regulations: Track Races",
        result_type="finishing_order",
        result_config={},
        description=(
            "Riders follow a pacer, then sprint the final laps; the order across the line "
            "decides the places."
        ),
    ),
    "cycling_team_pursuit": _performance(
        label="Cycling: team pursuit",
        icon="bicycle-outline",
        sport="cycling",
        governing_body="UCI",
        rulebook="UCI Cycling Regulations: Track Races",
        result_type="timed_lowest",
        result_config={"decimals": 3},
        participant_type="team",
        description="Teams of four over 4 km; the time of the third rider across the line counts.",
    ),
    "bmx": _performance(
        label="BMX racing",
        icon="bicycle-outline",
        sport="bmx",
        governing_body="UCI",
        rulebook="UCI Cycling Regulations: BMX",
        result_type="finishing_order",
        result_config={},
        description="Motos lead to a final of eight; the order across the line decides the medals.",
    ),
    "bmx_freestyle": _performance(
        label="BMX freestyle",
        icon="bicycle-outline",
        sport="bmx",
        governing_body="UCI",
        rulebook="UCI Cycling Regulations: BMX Freestyle",
        result_type="judged_score",
        result_config={"combine": "average", "count_best": 1, "max_score": 100, "decimals": 2},
        statuses=JUDGED_STATUSES,
        description="Two runs judged from 0 to 100; the better run counts.",
    ),
    "mountain_bike": _performance(
        label="Mountain bike cross-country",
        icon="bicycle-outline",
        sport="mountain bike",
        governing_body="UCI",
        rulebook="UCI Cycling Regulations: Mountain Bike",
        result_type="finishing_order",
        result_config={"record_fields": ["time"]},
        description="A mass-start race over laps; the order across the line decides the places.",
    ),
    # --- Gymnastics and judged sports ---------------------------------------------------------
    "gymnastics_artistic": _performance(
        label="Artistic gymnastics",
        icon="body-outline",
        sport="gymnastics",
        governing_body="FIG",
        rulebook="FIG Code of Points (Artistic Gymnastics)",
        result_type="judged_score",
        result_config={
            "drop_high": 1,
            "drop_low": 1,
            "combine": "average",
            "decimals": 3,
            "max_score": 10,
        },
        statuses=JUDGED_STATUSES,
        description=(
            "Each routine scores a D-score (difficulty) plus an E-score (execution, "
            "out of 10, after the highest and lowest judges are dropped), minus neutral "
            "deductions. Apparatus finals rank one routine; the all-around adds every "
            "apparatus."
        ),
    ),
    "gymnastics_rhythmic": _performance(
        label="Rhythmic gymnastics",
        icon="body-outline",
        sport="gymnastics",
        governing_body="FIG",
        rulebook="FIG Code of Points (Rhythmic Gymnastics)",
        result_type="judged_score",
        result_config={"drop_high": 1, "drop_low": 1, "combine": "average", "decimals": 3},
        statuses=JUDGED_STATUSES,
        description=(
            "Difficulty plus artistry and execution, minus penalties, per routine (VERIFY the "
            "panels)."
        ),
    ),
    "trampoline": _performance(
        label="Trampoline",
        icon="body-outline",
        sport="trampoline",
        governing_body="FIG",
        rulebook="FIG Code of Points (Trampoline)",
        result_type="judged_score",
        result_config={
            "drop_high": 1,
            "drop_low": 1,
            "decimals": 3,
            "extras": [
                {"key": "time_of_flight", "label": "Time of flight"},
                {"key": "horizontal_displacement", "label": "Horizontal displacement"},
            ],
        },
        statuses=JUDGED_STATUSES,
        description=(
            "Difficulty plus execution plus time of flight plus horizontal "
            "displacement, minus penalties (VERIFY the execution panel)."
        ),
    ),
    "skateboarding": _performance(
        label="Skateboarding",
        icon="color-wand-outline",
        sport="skateboarding",
        governing_body="World Skate",
        rulebook="World Skate Skateboarding Rules",
        result_type="judged_score",
        result_config={
            "drop_high": 1,
            "drop_low": 1,
            "combine": "average",
            "count_best": 1,
            "max_score": 100,
            "decimals": 2,
        },
        statuses=JUDGED_STATUSES,
        description=(
            "Runs judged from 0 to 100; park counts the best run, street adds runs and best "
            "tricks (VERIFY)."
        ),
    ),
    "surfing": _performance(
        label="Surfing",
        icon="water-outline",
        sport="surfing",
        governing_body="ISA",
        rulebook="ISA Rule Book",
        result_type="judged_score",
        result_config={
            "drop_high": 1,
            "drop_low": 1,
            "combine": "average",
            "count_best": 2,
            "max_score": 10,
            "decimals": 2,
        },
        statuses=JUDGED_STATUSES,
        description=(
            "Each wave is judged from 0 to 10; the best two waves add up to the heat score."
        ),
    ),
    "sport_climbing": _performance(
        label="Sport climbing: boulder and lead",
        icon="trending-up-outline",
        sport="sport climbing",
        governing_body="IFSC",
        rulebook="IFSC Rules",
        result_type="points_highest",
        result_config={"tie_break": "countback"},
        description=(
            "Boulder and lead are each scored out of 100; the combined total ranks the climbers."
        ),
    ),
    "climbing_speed": _performance(
        label="Sport climbing: speed",
        icon="trending-up-outline",
        sport="sport climbing",
        governing_body="IFSC",
        rulebook="IFSC Rules",
        result_type="timed_lowest",
        result_config={"decimals": 3},
        description="Two climbers race side by side up a standard 15 m wall; the faster time wins.",
    ),
    # --- Targets and strength -------------------------------------------------------------
    "shooting": _performance(
        label="Shooting",
        icon="locate-outline",
        sport="shooting",
        governing_body="ISSF",
        rulebook="ISSF General Technical Rules",
        result_type="points_highest",
        result_config={"tie_break": "countback"},
        description=(
            "Qualification adds every shot; finals score in tenths (10.9 at most) and "
            "eliminate the lowest shooter in stages. Shotgun counts targets hit. A tie "
            "for a medal goes to a shoot-off."
        ),
    ),
    "modern_pentathlon": _performance(
        label="Modern pentathlon",
        icon="medal-outline",
        sport="modern pentathlon",
        governing_body="UIPM",
        rulebook="UIPM Competition Rules",
        result_type="points_highest",
        result_config={"tie_break": "none"},
        description=(
            "Points from fencing, swimming and the obstacle discipline (riding until "
            "Paris 2024) set a handicap start for the laser run; the first across the "
            "line wins (VERIFY)."
        ),
    ),
    "weightlifting": _performance(
        label="Weightlifting",
        icon="barbell-outline",
        sport="weightlifting",
        governing_body="IWF",
        rulebook="IWF Technical and Competition Rules",
        result_type="measured_highest",
        result_config={
            "mode": "total_of_best",
            "lifts": [
                {"key": "snatch", "label": "Snatch"},
                {"key": "clean_jerk", "label": "Clean and jerk"},
            ],
        },
        statuses=FIELD_STATUSES,
        description=(
            "Three attempts at the snatch and three at the clean and jerk. The best of "
            "each adds up to the total; a lifter without a successful lift in either has "
            "no total. A tie goes to whoever reached the total first (VERIFY)."
        ),
    ),
}

SKI_STATUSES = [
    {"code": "DNF", "label": "Did not finish"},
    {"code": "DNS", "label": "Did not start"},
    {"code": "DSQ", "label": "Disqualified"},
]
FIS = "FIS"
FIS_ALPINE = "FIS International Competition Rules (ICR): Alpine"
FIS_FREESTYLE = "FIS International Competition Rules (ICR): Freestyle and Snowboard"
FIS_NORDIC = "FIS International Competition Rules (ICR): Cross-Country"
FIS_JUMPING = "FIS International Competition Rules (ICR): Ski Jumping"
ISU_SPEED = "ISU Special Regulations and Technical Rules: Speed Skating"
ISU_SHORT = "ISU Special Regulations and Technical Rules: Short Track"
ISU_FIGURE = "ISU Special Regulations and Technical Rules: Single and Pair Skating, Ice Dance"
FREESTYLE_JUDGED = {
    "drop_high": 1,
    "drop_low": 1,
    "combine": "average",
    "count_best": 1,
    "max_score": 100,
    "decimals": 2,
}


def _ski_jumping(label: str, *, target: int, per_unit: str, hill: str) -> dict:
    return _performance(
        label=label,
        icon="airplane-outline",
        sport="ski jumping",
        governing_body=FIS,
        rulebook=FIS_JUMPING,
        result_type="judged_score",
        result_config={
            "judges": 5,
            "drop_high": 1,
            "drop_low": 1,
            "max_score": 20,
            "score_step": "0.5",
            "decimals": 1,
            "attempts": 2,
            "mark_points": {
                "field": "distance",
                "label": "Distance (m)",
                "base": 60,
                "target": target,
                "per_unit": per_unit,
            },
            "extras": [
                {"key": "wind", "label": "Wind compensation (+/-)"},
                {"key": "gate", "label": "Gate compensation (+/-)"},
            ],
        },
        statuses=SKI_STATUSES,
        description=(
            f"Two jumps on the {hill}. Distance points are 60 at the K-point "
            f"({target} m) plus or minus {per_unit} per metre. Five judges give style "
            "marks out of 20; the highest and lowest are dropped. Wind and gate "
            "compensation are added or taken away. The best total of both jumps wins "
            "(VERIFY the hill size)."
        ),
    )


WINTER_PRESETS: dict[str, dict] = {
    # --- Alpine skiing ------------------------------------------------------------
    "alpine_single_run": _performance(
        label="Alpine skiing: downhill and super-G",
        icon="snow-outline",
        sport="alpine skiing",
        governing_body=FIS,
        rulebook=FIS_ALPINE,
        result_type="timed_lowest",
        result_config={"decimals": 2},
        statuses=SKI_STATUSES,
        description="One run; the fastest time to a hundredth wins. Equal times share the place.",
    ),
    "alpine_two_runs": _performance(
        label="Alpine skiing: giant slalom, slalom and team combined",
        icon="snow-outline",
        sport="alpine skiing",
        governing_body=FIS,
        rulebook=FIS_ALPINE,
        result_type="multi_run_aggregate",
        result_config={"runs": 2, "decimals": 2},
        statuses=SKI_STATUSES,
        description=(
            "Two runs; the lowest combined time wins. In the team combined one skier "
            "runs the downhill and the other the slalom. Missing a gate is a DNF."
        ),
    ),
    # --- Biathlon -------------------------------------------------------------------
    "biathlon": _performance(
        label="Biathlon: sprint",
        icon="locate-outline",
        sport="biathlon",
        governing_body="IBU",
        rulebook="IBU Event and Competition Rules",
        result_type="timed_lowest",
        result_config={"decimals": 1, "record_fields": ["misses"]},
        statuses=SKI_STATUSES,
        description=(
            "Interval start; the fastest time wins. Each missed target means a 150 m "
            "penalty loop, which is already in the skier's time. Misses are recorded."
        ),
    ),
    "biathlon_individual": _performance(
        label="Biathlon: individual",
        icon="locate-outline",
        sport="biathlon",
        governing_body="IBU",
        rulebook="IBU Event and Competition Rules",
        result_type="timed_lowest",
        result_config={
            "decimals": 1,
            "penalties": [{"key": "misses", "label": "Missed targets", "seconds": 60}],
        },
        statuses=SKI_STATUSES,
        description=(
            "Interval start over four shootings. One minute is added for every missed "
            "target (VERIFY: a shorter penalty is being trialled); the lowest total wins."
        ),
    ),
    "biathlon_mass": _performance(
        label="Biathlon: pursuit, mass start and relays",
        icon="locate-outline",
        sport="biathlon",
        governing_body="IBU",
        rulebook="IBU Event and Competition Rules",
        result_type="finishing_order",
        result_config={"record_fields": ["misses", "time"]},
        statuses=SKI_STATUSES,
        description=(
            "First across the line wins. Each miss means a penalty loop (relays have "
            "three spare rounds per shooting first). Pursuit starts are staggered by "
            "the sprint result."
        ),
    ),
    # --- Sliding ----------------------------------------------------------------------
    "sliding": _performance(
        label="Bobsleigh and skeleton",
        icon="speedometer-outline",
        sport="sliding",
        governing_body="IBSF",
        rulebook="IBSF International Rules",
        result_type="multi_run_aggregate",
        result_config={"runs": 4, "decimals": 2},
        statuses=SKI_STATUSES,
        description="Four runs over two days; the lowest combined time to a hundredth wins.",
    ),
    "luge": _performance(
        label="Luge: singles",
        icon="speedometer-outline",
        sport="luge",
        governing_body="FIL",
        rulebook="FIL International Luge Regulations",
        result_type="multi_run_aggregate",
        result_config={"runs": 4, "decimals": 3},
        statuses=SKI_STATUSES,
        description="Four runs; the lowest combined time to a thousandth wins.",
    ),
    "luge_doubles": _performance(
        label="Luge: doubles",
        icon="speedometer-outline",
        sport="luge",
        governing_body="FIL",
        rulebook="FIL International Luge Regulations",
        result_type="multi_run_aggregate",
        result_config={"runs": 2, "decimals": 3},
        participant_type="team",
        statuses=SKI_STATUSES,
        description="Two runs; the lowest combined time to a thousandth wins (VERIFY).",
    ),
    "luge_relay": _performance(
        label="Luge: team relay",
        icon="speedometer-outline",
        sport="luge",
        governing_body="FIL",
        rulebook="FIL International Luge Regulations",
        result_type="timed_lowest",
        result_config={"decimals": 3},
        participant_type="team",
        statuses=SKI_STATUSES,
        description="Each sled hits a touch pad to release the next; the lowest team time wins.",
    ),
    # --- Cross-country, Nordic combined and ski mountaineering --------------------------
    "cross_country": _performance(
        label="Cross-country skiing: interval start",
        icon="snow-outline",
        sport="cross-country skiing",
        governing_body=FIS,
        rulebook=FIS_NORDIC,
        result_type="timed_lowest",
        result_config={"decimals": 1},
        statuses=SKI_STATUSES,
        description="Skiers start one by one; the fastest time wins.",
    ),
    "cross_country_mass": _performance(
        label="Cross-country skiing: sprint, mass start and relay",
        icon="snow-outline",
        sport="cross-country skiing",
        governing_body=FIS,
        rulebook=FIS_NORDIC,
        result_type="finishing_order",
        result_config={"record_fields": ["time"]},
        statuses=SKI_STATUSES,
        description=(
            "First across the line wins; a photo finish decides close races. Sprints "
            "run qualification, then heats of six to a final."
        ),
    ),
    "nordic_combined": _performance(
        label="Nordic combined",
        icon="snow-outline",
        sport="nordic combined",
        governing_body=FIS,
        rulebook="FIS International Competition Rules (ICR): Nordic Combined",
        result_type="finishing_order",
        result_config={"record_fields": ["jump_points", "start_gap", "time"]},
        statuses=SKI_STATUSES,
        description=(
            "Ski jumping first: the points gap to the leader becomes a time gap "
            "(Gundersen start). Then the cross-country race: first across the line wins."
        ),
    ),
    "ski_mountaineering": _performance(
        label="Ski mountaineering",
        icon="trending-up-outline",
        sport="ski mountaineering",
        governing_body="ISMF",
        rulebook="ISMF Sporting Rules",
        result_type="finishing_order",
        result_config={"record_fields": ["time"]},
        statuses=SKI_STATUSES,
        description=(
            "Sprint heats up and down the course, then a final; first across the line "
            "wins. New for Milano Cortina 2026."
        ),
    ),
    # --- Skating --------------------------------------------------------------------------
    "speed_skating": _performance(
        label="Speed skating",
        icon="stopwatch-outline",
        sport="speed skating",
        governing_body="ISU",
        rulebook=ISU_SPEED,
        result_type="timed_lowest",
        result_config={"decimals": 2},
        statuses=SKI_STATUSES,
        description=(
            "Skaters race in pairs against the clock; the fastest time to a hundredth wins."
        ),
    ),
    "speed_skating_mass_start": _performance(
        label="Speed skating: mass start",
        icon="stopwatch-outline",
        sport="speed skating",
        governing_body="ISU",
        rulebook=ISU_SPEED,
        result_type="points_highest",
        result_config={"tie_break": "last_round"},
        statuses=SKI_STATUSES,
        description=(
            "16 laps with intermediate sprints for points; the final sprint gives the "
            "most points (60, 40, 20; VERIFY). The highest total wins."
        ),
    ),
    "short_track": _performance(
        label="Short track speed skating",
        icon="stopwatch-outline",
        sport="short track",
        governing_body="ISU",
        rulebook=ISU_SHORT,
        result_type="finishing_order",
        result_config={"record_fields": ["time"]},
        statuses=[
            {"code": "PEN", "label": "Penalty (disqualified)"},
            {"code": "DNF", "label": "Did not finish"},
            {"code": "DNS", "label": "Did not start"},
        ],
        description=(
            "Heats, quarter-finals and semi-finals lead to a final; first across the "
            "line wins. A penalty from the referee disqualifies (PEN)."
        ),
    ),
    "figure_skating": _performance(
        label="Figure skating",
        icon="sparkles-outline",
        sport="figure skating",
        governing_body="ISU",
        rulebook=ISU_FIGURE,
        result_type="judged_score",
        result_config={
            "attempts": 2,
            "decimals": 2,
            "extras": [
                {"key": "tes", "label": "Technical elements score"},
                {"key": "pcs", "label": "Programme components score"},
            ],
        },
        statuses=JUDGED_STATUSES,
        description=(
            "A short programme and a free skate (rhythm and free dance in ice dance). "
            "Each segment is the technical elements score plus the programme "
            "components score, minus deductions. The total of both ranks the skaters."
        ),
    ),
    "figure_skating_team": _performance(
        label="Figure skating: team event",
        icon="sparkles-outline",
        sport="figure skating",
        governing_body="ISU",
        rulebook=ISU_FIGURE,
        result_type="points_highest",
        result_config={"tie_break": "none"},
        participant_type="team",
        statuses=JUDGED_STATUSES,
        description=(
            "Teams earn placement points in each segment (10 for first down to 1); the "
            "highest total wins (VERIFY)."
        ),
    ),
    # --- Freestyle skiing and snowboard ------------------------------------------------------
    "freestyle_judged": _performance(
        label="Freestyle: halfpipe and slopestyle",
        icon="snow-outline",
        sport="freestyle",
        governing_body=FIS,
        rulebook=FIS_FREESTYLE,
        result_type="judged_score",
        result_config=FREESTYLE_JUDGED,
        statuses=SKI_STATUSES,
        description=(
            "Judges score each run from 0 to 100; the highest and lowest are dropped "
            "and the rest averaged. The best run counts."
        ),
    ),
    "freestyle_big_air": _performance(
        label="Freestyle: big air",
        icon="snow-outline",
        sport="freestyle",
        governing_body=FIS,
        rulebook=FIS_FREESTYLE,
        result_type="judged_score",
        result_config={**FREESTYLE_JUDGED, "count_best": 2},
        statuses=SKI_STATUSES,
        description=(
            "Three jumps judged from 0 to 100; the best two (in different directions, "
            "VERIFY) add up."
        ),
    ),
    "freestyle_moguls": _performance(
        label="Freestyle: moguls",
        icon="snow-outline",
        sport="freestyle",
        governing_body=FIS,
        rulebook=FIS_FREESTYLE,
        result_type="judged_score",
        result_config={
            **FREESTYLE_JUDGED,
            "extras": [{"key": "time_points", "label": "Time points"}],
        },
        statuses=SKI_STATUSES,
        description="Judges score turns and air; points for speed are added (VERIFY the split).",
    ),
    "freestyle_aerials": _performance(
        label="Freestyle: aerials",
        icon="snow-outline",
        sport="freestyle",
        governing_body=FIS,
        rulebook=FIS_FREESTYLE,
        result_type="judged_score",
        result_config={
            "judges": 5,
            "drop_high": 1,
            "drop_low": 1,
            "multiply_by_difficulty": True,
            "count_best": 1,
            "decimals": 2,
        },
        statuses=SKI_STATUSES,
        description=(
            "Five judges score air, form and landing; the highest and lowest are "
            "dropped and the rest multiplied by the degree of difficulty (VERIFY)."
        ),
    ),
    "ski_cross": _performance(
        label="Ski cross and snowboard cross",
        icon="snow-outline",
        sport="freestyle",
        governing_body=FIS,
        rulebook=FIS_FREESTYLE,
        result_type="finishing_order",
        result_config={},
        statuses=SKI_STATUSES,
        description=(
            "Seeding run, then heats of four; the first two go through. First across the line wins."
        ),
    ),
    "parallel_giant_slalom": _match(
        label="Snowboard: parallel giant slalom",
        icon="snow-outline",
        sport="freestyle",
        governing_body=FIS,
        rulebook=FIS_FREESTYLE,
        description="Two riders race side by side; the faster time wins the heat.",
        participant_type="individual",
        draw_allowed=False,
        score_types=[
            {
                "key": "run-time",
                "label": "Run time (s)",
                "value": 1,
                "affects_score": True,
                "better": "lower",
            }
        ],
        match_structure=[{"unit": "run", "count": 1, "better": "lower"}],
        win_condition="lowest_total",
        formats_allowed=["knockout", "league"],
    ),
    # --- Ski jumping ---------------------------------------------------------------------------
    "ski_jumping": _ski_jumping(
        "Ski jumping: normal hill", target=98, per_unit="2.0", hill="normal hill"
    ),
    "ski_jumping_large": _ski_jumping(
        "Ski jumping: large hill", target=125, per_unit="1.8", hill="large hill"
    ),
    # --- Team sports -----------------------------------------------------------------------------
    "ice_hockey": _match(
        label="Ice hockey (Olympic)",
        icon="disc-outline",
        sport="ice hockey",
        governing_body="IIHF",
        rulebook="IIHF Official Rule Book",
        description=(
            "A goal is 1. Three periods of 20 minutes; a level game goes to overtime, "
            "then a shoot-out. Olympic group points: 3 for a regulation win, 2 for an "
            "overtime or shoot-out win, 1 for an overtime or shoot-out loss, 0 for a "
            "regulation loss (VERIFY). Leagues that want 3/1/0 should use a league "
            "preset; this locked Olympic preset keeps IIHF 3-2-1-0."
        ),
        draw_allowed=False,
        score_types=[
            {"key": "goal", "label": "Goal", "value": 1, "affects_score": True},
            {
                "key": "penalty-minutes",
                "label": "Penalty minutes",
                "value": 0,
                "affects_score": False,
            },
            {
                "key": "shootout-goal",
                "label": "Shoot-out goal",
                "value": 1,
                "affects_score": True,
            },
        ],
        match_structure=[
            {"unit": "period", "count": 3, "minutes": 20},
            {"unit": "overtime", "count": 1, "minutes": 5, "extra": True},
            {
                "unit": "shootout",
                "count": 1,
                "affects_total": False,
                "resolves_draw": True,
                "extra": True,
            },
        ],
        draw_resolution="penalties",
        league_points={"win": 3, "draw": 0, "loss": 0, "extra_time_win": 2, "extra_time_loss": 1},
        tiebreakers=["points", "head_to_head", "score_difference", "score_for"],
        formats_allowed=["league", "knockout", "groups_knockout", "round_robin"],
    ),
    "curling": _match(
        label="Curling",
        icon="ellipse-outline",
        sport="curling",
        governing_body="World Curling",
        rulebook="The Rules of Curling and Rules of Competition",
        description=(
            "Ten ends (eight in mixed doubles). After each end, one team scores a point "
            "for every stone closer to the button than the opponent's best. A level "
            "game plays an extra end. Round robin, then semi-finals and medal games."
        ),
        draw_allowed=False,
        score_types=[{"key": "stone", "label": "Stone counted", "value": 1, "affects_score": True}],
        match_structure=[
            {"unit": "end", "count": 10},
            {"unit": "extra_end", "count": 1, "repeat": True, "extra": True},
        ],
        draw_resolution="sudden_death",
        league_points={"win": 1, "draw": 0, "loss": 0},
        tiebreakers=["points", "head_to_head", "score_difference"],
        formats_allowed=["league", "round_robin", "knockout", "groups_knockout"],
    ),
}
OLYMPIC_PRESETS.update(WINTER_PRESETS)

# Existing presets reused in the Olympic catalogue: their federation and rulebook.
GOVERNANCE = {
    "soccer": ("FIFA", "IFAB Laws of the Game"),
    "basketball": ("FIBA", "FIBA Official Basketball Rules"),
    "tennis": ("ITF", "ITF Rules of Tennis"),
    "table_tennis": ("ITTF", "ITTF Handbook: Laws of Table Tennis"),
    "badminton": ("BWF", "BWF Laws of Badminton"),
    "volleyball": ("FIVB", "FIVB Official Volleyball Rules"),
    "field_hockey": ("FIH", "FIH Rules of Hockey"),
    "golf_stroke": ("IGF (R&A and USGA rules)", "The Rules of Golf"),
    "archery": ("World Archery", "World Archery Rulebook"),
    "cricket_t20": ("ICC", "ICC Men's and Women's T20I Playing Conditions"),
    "squash": ("WSF", "WSF World Singles Squash Rules"),
    "baseball": ("WBSC", "WBSC Official Baseball Rules"),
    "athletics": ("World Athletics", "World Athletics Competition and Technical Rules"),
}
