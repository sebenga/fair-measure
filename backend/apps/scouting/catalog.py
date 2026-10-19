"""The scouting catalogue: every sport-specific fact lives here as data.

Nothing else in the scouting app names a sport. Views, permissions and
serializers read this dictionary, the same way the competition engine reads its
presets. Phase 1 needs positions; later phases add attributes, physical tests
and match stats to the same entries.
"""

from __future__ import annotations


def _positions(*pairs: tuple[str, str]) -> list[dict]:
    return [{"key": key, "label": label} for key, label in pairs]


RACKET_POSITIONS = _positions(("singles", "Singles"), ("doubles", "Doubles"))

SPORTS: dict[str, dict] = {
    "soccer": {
        "label": "Soccer",
        "positions": _positions(
            ("goalkeeper", "Goalkeeper"),
            ("centre-back", "Centre-back"),
            ("full-back", "Full-back"),
            ("wing-back", "Wing-back"),
            ("defensive-midfield", "Defensive midfielder"),
            ("central-midfield", "Central midfielder"),
            ("attacking-midfield", "Attacking midfielder"),
            ("winger", "Winger"),
            ("striker", "Striker"),
        ),
    },
    "rugby_union": {
        "label": "Rugby union",
        "positions": _positions(
            ("loosehead-prop", "Loosehead prop"),
            ("hooker", "Hooker"),
            ("tighthead-prop", "Tighthead prop"),
            ("lock", "Lock"),
            ("flanker", "Flanker"),
            ("number-8", "Number 8"),
            ("scrum-half", "Scrum-half"),
            ("fly-half", "Fly-half"),
            ("centre", "Centre"),
            ("wing", "Wing"),
            ("fullback", "Fullback"),
        ),
    },
    "cricket": {
        "label": "Cricket",
        "positions": _positions(
            ("batter", "Batter"),
            ("fast-bowler", "Fast bowler"),
            ("spin-bowler", "Spin bowler"),
            ("all-rounder", "All-rounder"),
            ("wicket-keeper", "Wicket-keeper"),
        ),
    },
    "netball": {
        "label": "Netball",
        "positions": _positions(
            ("gs", "Goal shooter"),
            ("ga", "Goal attack"),
            ("wa", "Wing attack"),
            ("c", "Centre"),
            ("wd", "Wing defence"),
            ("gd", "Goal defence"),
            ("gk", "Goalkeeper"),
        ),
    },
    "basketball": {
        "label": "Basketball",
        "positions": _positions(
            ("point-guard", "Point guard"),
            ("shooting-guard", "Shooting guard"),
            ("small-forward", "Small forward"),
            ("power-forward", "Power forward"),
            ("centre", "Centre"),
        ),
    },
    "athletics": {
        "label": "Athletics",
        "positions": _positions(
            ("sprints", "Sprints"),
            ("middle-distance", "Middle distance"),
            ("long-distance", "Long distance"),
            ("hurdles", "Hurdles"),
            ("jumps", "Jumps"),
            ("throws", "Throws"),
            ("combined", "Combined events"),
        ),
    },
    "tennis": {"label": "Tennis", "positions": RACKET_POSITIONS},
    "squash": {"label": "Squash", "positions": _positions(("singles", "Singles"))},
    "badminton": {"label": "Badminton", "positions": RACKET_POSITIONS},
    "volleyball": {
        "label": "Volleyball",
        "positions": _positions(
            ("setter", "Setter"),
            ("outside-hitter", "Outside hitter"),
            ("opposite", "Opposite"),
            ("middle-blocker", "Middle blocker"),
            ("libero", "Libero"),
        ),
    },
    "golf": {"label": "Golf", "positions": _positions(("player", "Player"))},
    "swimming": {
        "label": "Swimming",
        "positions": _positions(
            ("freestyle", "Freestyle"),
            ("backstroke", "Backstroke"),
            ("breaststroke", "Breaststroke"),
            ("butterfly", "Butterfly"),
            ("individual-medley", "Individual medley"),
        ),
    },
    "boxing": {
        "label": "Boxing / combat",
        "positions": _positions(
            ("orthodox", "Orthodox"),
            ("southpaw", "Southpaw"),
            ("switch", "Switch hitter"),
        ),
    },
    "hockey": {
        "label": "Hockey",
        "positions": _positions(
            ("goalkeeper", "Goalkeeper"),
            ("defender", "Defender"),
            ("midfielder", "Midfielder"),
            ("forward", "Forward"),
        ),
    },
    "rowing": {
        "label": "Rowing",
        "positions": _positions(
            ("sculler", "Sculler"),
            ("stroke", "Stroke seat"),
            ("bow", "Bow seat"),
            ("engine-room", "Engine room"),
            ("cox", "Coxswain"),
        ),
    },
    "cycling": {
        "label": "Cycling",
        "positions": _positions(
            ("sprinter", "Sprinter"),
            ("climber", "Climber"),
            ("time-trialist", "Time trialist"),
            ("all-rounder", "All-rounder"),
            ("mountain-bike", "Mountain bike"),
        ),
    },
    "esports": {
        "label": "Esports",
        "positions": _positions(
            ("entry", "Entry / fragger"),
            ("support", "Support"),
            ("igl", "In-game leader"),
            ("sniper", "Sniper / AWPer"),
            ("flex", "Flex"),
        ),
    },
}

# How a competition's free-text sport maps onto a catalogue sport. Matching is
# case-insensitive and ignores "_" and "-", so "rugby_union" and "Rugby union" agree.
COMPETITION_SPORT_ALIASES: dict[str, list[str]] = {
    "soccer": ["soccer", "football", "futsal"],
    "rugby_union": ["rugby", "rugby union", "rugby sevens"],
    "cricket": ["cricket", "cricket t20"],
    "netball": ["netball"],
    "basketball": ["basketball"],
    "athletics": ["athletics", "track and field"],
    "tennis": ["tennis", "padel", "table tennis"],
    "squash": ["squash"],
    "badminton": ["badminton"],
    "volleyball": ["volleyball", "beach volleyball"],
    "golf": ["golf"],
    "swimming": ["swimming"],
    "boxing": ["boxing", "mma", "combat"],
    "hockey": ["hockey", "field hockey"],
    "rowing": ["rowing"],
    "cycling": ["cycling"],
    "esports": ["esports", "e-sports", "gaming"],
}

DEFAULT_SQUAD_SIZE = 23

# National-team style squads, one per sport. Each group lists the catalogue
# positions it takes, extra words a roster might use for them, and the fewest and
# most places it may fill. Minimums are filled first; the rest go to the best
# remaining players in groups still under their maximum.
SQUADS: dict[str, dict] = {
    "soccer": {
        "size": 23,
        "groups": [
            {
                "key": "goalkeepers",
                "label": "Goalkeepers",
                "positions": ["goalkeeper"],
                "aliases": ["gk", "keeper", "goalie"],
                "min": 3,
                "max": 3,
            },
            {
                "key": "defenders",
                "label": "Defenders",
                "positions": ["centre-back", "full-back", "wing-back"],
                "aliases": ["defender", "defence", "def", "cb", "lb", "rb", "back"],
                "min": 7,
                "max": 9,
            },
            {
                "key": "midfielders",
                "label": "Midfielders",
                "positions": ["defensive-midfield", "central-midfield", "attacking-midfield"],
                "aliases": ["midfielder", "midfield", "mid", "cm", "dm", "am"],
                "min": 7,
                "max": 9,
            },
            {
                "key": "forwards",
                "label": "Forwards",
                "positions": ["winger", "striker"],
                "aliases": ["forward", "attacker", "fw", "st", "wing"],
                "min": 4,
                "max": 6,
            },
        ],
    },
    "rugby_union": {
        "size": 23,
        "groups": [
            {
                "key": "front-row",
                "label": "Front row",
                "positions": ["loosehead-prop", "hooker", "tighthead-prop"],
                "aliases": ["prop", "front row"],
                "min": 5,
                "max": 6,
            },
            {
                "key": "locks",
                "label": "Locks",
                "positions": ["lock"],
                "aliases": ["second row"],
                "min": 3,
                "max": 4,
            },
            {
                "key": "back-row",
                "label": "Loose forwards",
                "positions": ["flanker", "number-8"],
                "aliases": ["loose forward", "back row", "eighthman"],
                "min": 4,
                "max": 5,
            },
            {
                "key": "halves",
                "label": "Half-backs",
                "positions": ["scrum-half", "fly-half"],
                "aliases": ["half-back", "flyhalf", "scrumhalf"],
                "min": 4,
                "max": 5,
            },
            {
                "key": "outside-backs",
                "label": "Centres and back three",
                "positions": ["centre", "wing", "fullback"],
                "aliases": ["winger", "full back", "outside back"],
                "min": 7,
                "max": 8,
            },
        ],
    },
    "hockey": {
        "size": 23,
        "groups": [
            {
                "key": "goalkeepers",
                "label": "Goalkeepers",
                "positions": ["goalkeeper"],
                "aliases": ["gk", "keeper"],
                "min": 2,
                "max": 3,
            },
            {
                "key": "defenders",
                "label": "Defenders",
                "positions": ["defender"],
                "aliases": ["defence", "back"],
                "min": 6,
                "max": 8,
            },
            {
                "key": "midfielders",
                "label": "Midfielders",
                "positions": ["midfielder"],
                "aliases": ["midfield"],
                "min": 6,
                "max": 8,
            },
            {
                "key": "forwards",
                "label": "Forwards",
                "positions": ["forward"],
                "aliases": ["striker", "attacker"],
                "min": 5,
                "max": 7,
            },
        ],
    },
    "cricket": {
        "size": 23,
        "groups": [
            {
                "key": "batters",
                "label": "Batters",
                "positions": ["batter"],
                "aliases": ["batsman", "opener"],
                "min": 7,
                "max": 9,
            },
            {
                "key": "keepers",
                "label": "Wicket-keepers",
                "positions": ["wicket-keeper"],
                "aliases": ["keeper", "wk"],
                "min": 2,
                "max": 3,
            },
            {
                "key": "all-rounders",
                "label": "All-rounders",
                "positions": ["all-rounder"],
                "aliases": ["allrounder"],
                "min": 4,
                "max": 6,
            },
            {
                "key": "bowlers",
                "label": "Bowlers",
                "positions": ["fast-bowler", "spin-bowler"],
                "aliases": ["bowler", "seamer", "spinner", "pace"],
                "min": 7,
                "max": 9,
            },
        ],
    },
}

# The selection score blends whatever evidence a league has, out of 10. A missing
# source is left out and the other weights are scaled up, and the pick says so.
SELECTION_WEIGHTS: dict[str, float] = {
    "form": 0.5,  # average match rating
    "output": 0.3,  # scoring contribution per game, against the best in the same position group
    "team": 0.2,  # the player's team results
}

# Talent-profile availability values that keep a player out of an automatic pick.
UNAVAILABLE_FOR_SELECTION = {"injured", "unavailable"}


# Age groups by age on 1 January of the current season, youngest first. An
# entry applies while the age is below `under`; the last entry has no limit.
AGE_GROUPS: list[dict] = [
    {"key": "u9", "label": "U9", "under": 9},
    {"key": "u11", "label": "U11", "under": 11},
    {"key": "u13", "label": "U13", "under": 13},
    {"key": "u15", "label": "U15", "under": 15},
    {"key": "u17", "label": "U17", "under": 17},
    {"key": "u19", "label": "U19", "under": 19},
    {"key": "u21", "label": "U21", "under": 21},
    {"key": "senior", "label": "Senior", "under": 35},
    {"key": "masters", "label": "Masters", "under": None},
]

# The age at which a player can consent for themselves (POPIA treats anyone
# under 18 as a child whose data needs a competent person's consent).
AGE_OF_CONSENT = 18

GENDER_CATEGORIES = [
    {"key": "women", "label": "Women / girls"},
    {"key": "men", "label": "Men / boys"},
    {"key": "open", "label": "Open / mixed"},
]

REGIONS = [
    {"key": "eastern-cape", "label": "Eastern Cape"},
    {"key": "free-state", "label": "Free State"},
    {"key": "gauteng", "label": "Gauteng"},
    {"key": "kwazulu-natal", "label": "KwaZulu-Natal"},
    {"key": "limpopo", "label": "Limpopo"},
    {"key": "mpumalanga", "label": "Mpumalanga"},
    {"key": "north-west", "label": "North West"},
    {"key": "northern-cape", "label": "Northern Cape"},
    {"key": "western-cape", "label": "Western Cape"},
    {"key": "outside-sa", "label": "Outside South Africa"},
]

# Body measurements every sport can record. `kind` decides whether the value is
# a number with a unit or a choice.
MEASUREMENTS = [
    {"key": "height", "label": "Height", "kind": "number", "unit": "cm"},
    {"key": "weight", "label": "Weight", "kind": "number", "unit": "kg"},
    {"key": "wingspan", "label": "Wingspan", "kind": "number", "unit": "cm"},
    {"key": "reach", "label": "Standing reach", "kind": "number", "unit": "cm"},
    {
        "key": "dominant_hand",
        "label": "Dominant hand",
        "kind": "choice",
        "choices": ["left", "right", "both"],
    },
    {
        "key": "dominant_foot",
        "label": "Dominant foot",
        "kind": "choice",
        "choices": ["left", "right", "both"],
    },
]

# What a guardian can agree to share. Identity and sport are needed for any
# visible profile; the rest are opt-in.
CONSENT_SECTIONS = [
    {"key": "identity", "label": "Name, photo, age group and region", "required": True},
    {"key": "sports", "label": "Sports and positions", "required": True},
    {"key": "physical", "label": "Height, weight and other measurements", "required": False},
    {"key": "videos", "label": "Highlight videos", "required": False},
    {"key": "availability", "label": "Availability", "required": False},
]


def sport(key: str) -> dict | None:
    return SPORTS.get(key)


def position_keys(sport_key: str) -> set[str]:
    entry = SPORTS.get(sport_key) or {}
    return {item["key"] for item in entry.get("positions", [])}


def _norm(text: str) -> str:
    return " ".join((text or "").lower().replace("_", " ").replace("-", " ").split())


def sport_for_competition(competition_sport: str) -> str | None:
    """The catalogue sport a competition plays, or None if it is not a scouting sport."""

    wanted = _norm(competition_sport)
    if not wanted:
        return None
    for key, aliases in COMPETITION_SPORT_ALIASES.items():
        if wanted == _norm(key) or wanted in {_norm(alias) for alias in aliases}:
            return key
    return None


def squad_template(sport_key: str | None) -> dict:
    """The sport's squad shape, or one open group of the default size."""

    if sport_key and sport_key in SQUADS:
        return SQUADS[sport_key]
    positions = [item["key"] for item in (SPORTS.get(sport_key or "") or {}).get("positions", [])]
    return {
        "size": DEFAULT_SQUAD_SIZE,
        "groups": [
            {
                "key": "squad",
                "label": "Squad",
                "positions": positions,
                "aliases": [],
                "min": 0,
                "max": DEFAULT_SQUAD_SIZE,
            }
        ],
    }


def group_for_position(sport_key: str | None, position: str) -> str | None:
    """Match a catalogue position key or a roster's free-text position to a squad group."""

    template = squad_template(sport_key)
    wanted = _norm(position)
    if not wanted:
        return None
    labels = {
        item["key"]: _norm(item["label"])
        for item in (SPORTS.get(sport_key or "") or {}).get("positions", [])
    }
    for group in template["groups"]:
        names = {_norm(key) for key in group["positions"]}
        names |= {labels[key] for key in group["positions"] if key in labels}
        names |= {_norm(alias) for alias in group.get("aliases", [])}
        names.add(_norm(group["label"]))
        if wanted in names or wanted.rstrip("s") in names:
            return group["key"]
    if len(template["groups"]) == 1:
        return template["groups"][0]["key"]
    return None


def measurement(key: str) -> dict | None:
    return next((item for item in MEASUREMENTS if item["key"] == key), None)


def keys(items: list[dict]) -> set[str]:
    return {item["key"] for item in items}


def public_catalog() -> dict:
    return {
        "sports": [{"key": key, **value} for key, value in SPORTS.items()],
        "age_groups": AGE_GROUPS,
        "age_of_consent": AGE_OF_CONSENT,
        "gender_categories": GENDER_CATEGORIES,
        "regions": REGIONS,
        "measurements": MEASUREMENTS,
        "consent_sections": CONSENT_SECTIONS,
        "competition_sports": COMPETITION_SPORT_ALIASES,
        "squads": SQUADS,
        "default_squad_size": DEFAULT_SQUAD_SIZE,
        "selection_weights": SELECTION_WEIGHTS,
    }
