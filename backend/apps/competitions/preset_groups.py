"""Sections for the competition create page.

This is display data. The scoring engine does not read it and does not branch
on these keys.
"""

from __future__ import annotations

from .olympic_presets import OLYMPIC_PRESETS, WINTER_PRESETS

# Everyday catalogue sports. Olympic event presets are assigned from the
# Olympic catalogues below, so a new Olympic preset lands in a section
# without a second list.
BALL = frozenset(
    {
        "soccer",
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
        "freestyle_football",
        "rugby_union",
        "rugby_sevens",
        "rugby_tens",
        "rugby_beach",
        "wheelchair_rugby",
        "touch_rugby",
        "tag_rugby",
        "rugby_league",
        "rugby_nines",
        "wheelchair_rugby_league",
        "american_football",
        "basketball",
        "netball",
        "field_hockey",
        "volleyball",
        "cricket_t20",
        "baseball",
    }
)
RACKET = frozenset({"tennis", "squash", "badminton", "table_tennis", "padel"})
GOLF = frozenset({"golf_stroke", "golf_stableford"})
TARGET = frozenset({"darts_501", "snooker", "pool_8ball", "bowling", "archery"})
BOARD = frozenset(
    {"chess", "scrabble", "backgammon", "dominoes_fives", "quiz", "yahtzee"}
)
EQUESTRIAN = frozenset(
    {
        "horse_racing_flat",
        "horse_racing_jumps",
        "polo_handicap",
        "polo_open",
        "show_jumping",
        "show_jumping_table_a",
        "show_jumping_two_phase",
        "show_jumping_table_c",
        "dressage",
        "dressage_freestyle",
        "eventing",
        "endurance",
        "horseball",
        "tent_pegging",
        "tent_pegging_team",
    }
)

GROUP_ORDER = (
    ("ball", "Ball sports"),
    ("racket", "Racket sports"),
    ("golf", "Golf"),
    ("target", "Target and cue"),
    ("board", "Board and table"),
    ("equestrian", "Horse sports"),
    ("olympic", "Olympic sports"),
    ("winter", "Winter Olympic sports"),
)

_LABELS = dict(GROUP_ORDER)

_BY_KEY: dict[str, str] = {}
for _keys, _group in (
    (BALL, "ball"),
    (RACKET, "racket"),
    (GOLF, "golf"),
    (TARGET, "target"),
    (BOARD, "board"),
    (EQUESTRIAN, "equestrian"),
):
    for _key in _keys:
        _BY_KEY[_key] = _group

# The everyday athletics preset sits with the Olympic track and field events.
_BY_KEY["athletics"] = "olympic"

for _key in WINTER_PRESETS:
    _BY_KEY.setdefault(_key, "winter")
for _key in OLYMPIC_PRESETS:
    _BY_KEY.setdefault(_key, "olympic")


def group_for(key: str) -> str:
    return _BY_KEY.get(key, "")


def group_label(key: str) -> str:
    return _LABELS.get(group_for(key), "")
