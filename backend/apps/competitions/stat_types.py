"""Stat-only score types, per preset, so player stats come from the engine.

They record what a player did (an assist, a tackle, a rebound) without changing
the score: ``affects_score`` is False and ``stat`` is True, so the scoring screen
groups them under "Player stats". The scouting catalogue's match stats read them.
"""

from __future__ import annotations


# Stat-only score types the presets record so the stats above come from the engine.
# They never change a score (affects_score False) and are tagged `stat` so the
# scoring screen can group them under "Player stats".
def _stat_type(key: str, label: str, description: str = "") -> dict:
    return {
        "key": key,
        "label": label,
        "value": 1,
        "affects_score": False,
        "stat": True,
        "description": description,
    }


STAT_SCORE_TYPES: dict[str, list[dict]] = {
    "soccer": [
        _stat_type("assist", "Assist"),
        _stat_type("shot", "Shot"),
        _stat_type("shot-on-target", "Shot on target", "Also record it as a shot."),
        _stat_type("tackle", "Tackle won"),
        _stat_type("interception", "Interception"),
        _stat_type("save", "Save"),
    ],
    "rugby_union": [
        _stat_type("tackle", "Tackle made"),
        _stat_type("missed-tackle", "Missed tackle"),
        _stat_type("carry", "Carry"),
        _stat_type("metres-gained", "Metres gained", "Record the metres as the quantity."),
        _stat_type("line-break", "Line break"),
        _stat_type("turnover-won", "Turnover won"),
    ],
    "cricket_t20": [
        _stat_type("dismissed", "Batter out", "Tag the batter who was dismissed."),
        _stat_type("ball-faced", "Ball faced", "Tag the batter on strike."),
        _stat_type("run-conceded", "Run conceded", "Tag the bowler; the quantity is the runs."),
        _stat_type("catch", "Catch"),
    ],
    "netball": [
        _stat_type("missed-shot", "Missed shot"),
        _stat_type("centre-pass-receive", "Centre-pass receive"),
        _stat_type("gain", "Gain"),
        _stat_type("intercept", "Intercept"),
    ],
    "basketball": [
        _stat_type("missed-field-goal", "Missed 2"),
        _stat_type("missed-three", "Missed 3"),
        _stat_type("missed-free-throw", "Missed free throw"),
        _stat_type("rebound", "Rebound"),
        _stat_type("assist", "Assist"),
        _stat_type("steal", "Steal"),
        _stat_type("block", "Block"),
    ],
    "tennis": [
        _stat_type("ace", "Ace"),
        _stat_type("double-fault", "Double fault"),
        _stat_type("first-serve-in", "First serve in"),
        _stat_type("first-serve-fault", "First-serve fault"),
        _stat_type("unforced-error", "Unforced error"),
    ],
    "squash": [_stat_type("unforced-error", "Unforced error")],
    "badminton": [_stat_type("unforced-error", "Unforced error")],
    "volleyball": [
        _stat_type("kill", "Kill"),
        _stat_type("attack-error", "Attack error"),
        _stat_type("attack-attempt", "Attack attempt", "Every attack, including kills and errors."),
        _stat_type("ace", "Ace"),
        _stat_type("block", "Block point"),
        _stat_type("dig", "Dig"),
    ],
    "golf_stroke": [
        _stat_type("green-in-regulation", "Green in regulation"),
        _stat_type("putt", "Putt"),
        _stat_type("fairway-hit", "Fairway hit"),
    ],
    "field_hockey": [
        _stat_type("assist", "Assist"),
        _stat_type("shot", "Shot"),
        _stat_type("circle-entry", "Circle entry"),
        _stat_type("tackle", "Tackle"),
    ],
}
# Presets that share a sport's stats.
STAT_SCORE_TYPES["padel"] = STAT_SCORE_TYPES["tennis"]
STAT_SCORE_TYPES["beach_volleyball"] = STAT_SCORE_TYPES["volleyball"]
STAT_SCORE_TYPES["rugby_sevens"] = STAT_SCORE_TYPES["rugby_union"]
STAT_SCORE_TYPES["rugby_tens"] = STAT_SCORE_TYPES["rugby_union"]
STAT_SCORE_TYPES["rugby_beach"] = STAT_SCORE_TYPES["rugby_union"]
STAT_SCORE_TYPES["touch_rugby"] = STAT_SCORE_TYPES["rugby_union"]
STAT_SCORE_TYPES["tag_rugby"] = STAT_SCORE_TYPES["rugby_union"]
STAT_SCORE_TYPES["rugby_league"] = [
    *STAT_SCORE_TYPES["rugby_union"],
    _stat_type("tackle-set", "Tackle in set", "Count toward the 6-tackle set. Does not change the score."),
]
STAT_SCORE_TYPES["rugby_nines"] = STAT_SCORE_TYPES["rugby_league"]
STAT_SCORE_TYPES["wheelchair_rugby_league"] = STAT_SCORE_TYPES["rugby_league"]
for _soccer_key in (
    "soccer_women",
    "futsal",
    "beach_soccer",
    "soccer_5",
    "soccer_6",
    "soccer_7",
    "youth_4v4",
    "youth_7v7",
    "youth_9v9",
    "blind_football",
    "cp_football",
    "amputee_football",
    "powerchair_football",
    "walking_football",
    "arena_soccer",
    "street_football",
):
    STAT_SCORE_TYPES[_soccer_key] = STAT_SCORE_TYPES["soccer"]
