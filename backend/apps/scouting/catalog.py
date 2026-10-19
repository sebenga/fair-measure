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
    }
