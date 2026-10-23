"""Official tile values and word-entry scoring. The engine does not import this."""

from .scoring import (
    apply_endgame,
    breakdown_word,
    rack_value,
    score_move,
    score_word,
    unique_new_tiles,
    validate_move,
)
from .tiles import TILE_SETS, blank_count, default_tile_set, tile_value

__all__ = [
    "TILE_SETS",
    "apply_endgame",
    "blank_count",
    "breakdown_word",
    "default_tile_set",
    "rack_value",
    "score_move",
    "score_word",
    "tile_value",
    "unique_new_tiles",
    "validate_move",
]
