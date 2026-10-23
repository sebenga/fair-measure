"""Tile sets as data. English is the default official set; other languages sit beside it."""

from __future__ import annotations

DEFAULT_SET = "english"

# Face values. Counts are the bag (including blanks) so a language can add a set
# without touching scoring code.
TILE_SETS: dict[str, dict] = {
    "english": {
        "label": "English",
        "blanks": 2,
        "values": {
            "A": 1,
            "B": 3,
            "C": 3,
            "D": 2,
            "E": 1,
            "F": 4,
            "G": 2,
            "H": 4,
            "I": 1,
            "J": 8,
            "K": 5,
            "L": 1,
            "M": 3,
            "N": 1,
            "O": 1,
            "P": 3,
            "Q": 10,
            "R": 1,
            "S": 1,
            "T": 1,
            "U": 1,
            "V": 4,
            "W": 4,
            "X": 8,
            "Y": 4,
            "Z": 10,
        },
        "counts": {
            "A": 9,
            "B": 2,
            "C": 2,
            "D": 4,
            "E": 12,
            "F": 2,
            "G": 3,
            "H": 2,
            "I": 9,
            "J": 1,
            "K": 1,
            "L": 4,
            "M": 2,
            "N": 6,
            "O": 8,
            "P": 2,
            "Q": 1,
            "R": 6,
            "S": 4,
            "T": 6,
            "U": 4,
            "V": 2,
            "W": 2,
            "X": 1,
            "Y": 2,
            "Z": 1,
            "?": 2,
        },
    },
    "afrikaans": {
        "label": "Afrikaans",
        "blanks": 2,
        "values": {
            "A": 1,
            "B": 4,
            "D": 2,
            "E": 1,
            "F": 4,
            "G": 3,
            "H": 4,
            "I": 1,
            "J": 8,
            "K": 3,
            "L": 2,
            "M": 4,
            "N": 1,
            "O": 1,
            "P": 4,
            "R": 1,
            "S": 1,
            "T": 1,
            "U": 2,
            "V": 4,
            "W": 5,
            "Y": 8,
        },
        "counts": {
            "A": 9,
            "B": 2,
            "D": 4,
            "E": 16,
            "F": 2,
            "G": 4,
            "H": 3,
            "I": 8,
            "J": 1,
            "K": 6,
            "L": 4,
            "M": 3,
            "N": 9,
            "O": 6,
            "P": 2,
            "R": 6,
            "S": 6,
            "T": 6,
            "U": 4,
            "V": 3,
            "W": 2,
            "Y": 1,
            "?": 2,
        },
    },
}


def default_tile_set(settings: dict | None) -> str:
    key = str((settings or {}).get("tile_set") or DEFAULT_SET).lower()
    return key if key in TILE_SETS else DEFAULT_SET


def tile_value(letter: str, tile_set: str = DEFAULT_SET, *, blank: bool = False) -> int:
    if blank or letter in {"?", "_"}:
        return 0
    values = TILE_SETS.get(tile_set, TILE_SETS[DEFAULT_SET])["values"]
    return int(values.get(letter.upper(), 0))


def blank_count(tile_set: str = DEFAULT_SET) -> int:
    return int(TILE_SETS.get(tile_set, TILE_SETS[DEFAULT_SET]).get("blanks") or 2)


def public_tiles(tile_set: str = DEFAULT_SET) -> dict:
    pack = TILE_SETS.get(tile_set, TILE_SETS[DEFAULT_SET])
    return {
        "key": tile_set if tile_set in TILE_SETS else DEFAULT_SET,
        "label": pack["label"],
        "blanks": pack["blanks"],
        "values": dict(pack["values"]),
    }
