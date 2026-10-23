"""Word and move totals. The server always recomputes these; the client total is ignored."""

from __future__ import annotations

from typing import Any

from rest_framework.exceptions import ValidationError

from .tiles import DEFAULT_SET, blank_count, tile_value

LETTER_MULTS = {1, 2, 3}
WORD_MULTS = {1, 2, 3, 4, 9}
MAX_NEW_TILES = 7
PLAY_TYPES = {"play", "pass", "exchange", "challenge_lost"}


def _letter(tile: dict) -> str:
    return str(tile.get("letter") or "").strip().upper()


def _is_blank(tile: dict) -> bool:
    return bool(tile.get("blank")) or _letter(tile) in {"?", "_"}


def _is_new(tile: dict) -> bool:
    return bool(tile.get("new", True))


def _letter_mult(tile: dict) -> int:
    try:
        mult = int(tile.get("letter_mult") or 1)
    except (TypeError, ValueError):
        return 1
    if mult not in LETTER_MULTS:
        return 1
    # Premiums only apply to a newly placed, non-blank tile.
    if _is_blank(tile) or not _is_new(tile):
        return 1
    return mult


def _word_mult(word: dict) -> int:
    try:
        mult = int(word.get("word_mult") or 1)
    except (TypeError, ValueError):
        return 1
    if mult not in WORD_MULTS:
        return 1
    tiles = list(word.get("tiles") or [])
    if tiles and not any(_is_new(tile) for tile in tiles):
        return 1
    return mult


def unique_new_tiles(words: list[dict]) -> int:
    """Physical tiles placed this turn. A shared new tile (same id) counts once."""

    seen: list[str] = []
    anonymous = 0
    for word_index, word in enumerate(words or []):
        for tile_index, tile in enumerate(word.get("tiles") or []):
            if not _is_new(tile):
                continue
            key = str(tile.get("id") or "").strip()
            if key:
                if key not in seen:
                    seen.append(key)
            else:
                anonymous += 1
    return len(seen) + anonymous


def score_word(word: dict, tile_set: str = DEFAULT_SET) -> int:
    """sum(tile value × letter_mult, blank = 0) × word_mult."""

    letter_sum = 0
    for tile in word.get("tiles") or []:
        letter = _letter(tile)
        value = tile_value(letter, tile_set, blank=_is_blank(tile))
        letter_sum += value * _letter_mult(tile)
    return letter_sum * _word_mult(word)


def breakdown_word(word: dict, tile_set: str = DEFAULT_SET) -> str:
    parts: list[str] = []
    letter_sum = 0
    for tile in word.get("tiles") or []:
        letter = _letter(tile) or "?"
        blank = _is_blank(tile)
        value = tile_value(letter, tile_set, blank=blank)
        mult = _letter_mult(tile)
        letter_sum += value * mult
        if blank:
            parts.append(f"{letter}(0)")
        elif mult > 1:
            parts.append(f"{letter}({value}×{mult})")
        elif value != 1:
            parts.append(f"{letter}({value})")
        else:
            parts.append(letter)
    word_mult = _word_mult(word)
    joined = " + ".join(parts) if parts else "0"
    if word_mult > 1:
        return f"{joined} = {letter_sum} × {word_mult} = {letter_sum * word_mult}"
    return f"{joined} = {letter_sum}"


def score_move(move: dict, tile_set: str = DEFAULT_SET) -> tuple[int, bool]:
    """Sum of all words formed + 50 if 7 tiles were placed this turn."""

    kind = str(move.get("type") or "play")
    if kind in {"pass", "exchange", "challenge_lost"}:
        return 0, False
    words = list(move.get("words") or [])
    total = sum(score_word(word, tile_set) for word in words)
    override = move.get("bingo")
    if override is None:
        bingo = unique_new_tiles(words) >= MAX_NEW_TILES
    else:
        bingo = bool(override)
    if bingo:
        total += 50
    return total, bingo


def rack_value(letters: str, tile_set: str = DEFAULT_SET) -> int:
    total = 0
    for char in str(letters or "").upper():
        if char in {" ", ",", "-", "?", "_"}:
            continue
        total += tile_value(char, tile_set)
    return total


def apply_endgame(racks: list[dict], tile_set: str = DEFAULT_SET) -> list[dict]:
    """Subtract each remaining rack. The player who went out also takes the others' tiles."""

    scored = []
    for row in racks:
        letters = "".join(ch for ch in str(row.get("letters") or "").upper() if ch.isalpha() or ch in {"?", "_"})
        scored.append(
            {
                "side": row.get("side"),
                "letters": letters,
                "value": rack_value(letters, tile_set),
            }
        )
    went_out = next((row for row in scored if not row["letters"]), None)
    adjustments = [{**row, "unplayed": -row["value"], "tiles_out": 0} for row in scored]
    if went_out:
        bonus = sum(row["value"] for row in scored if row["side"] != went_out["side"])
        for row in adjustments:
            if row["side"] == went_out["side"]:
                row["tiles_out"] = bonus
    return adjustments


def _clean_tile(tile: dict, *, require_letter: bool = True) -> dict:
    letter = _letter(tile)
    if require_letter and not letter.isalpha():
        raise ValidationError({"words": "Letters must be A–Z."})
    if letter and not letter.isalpha():
        raise ValidationError({"words": "Letters must be A–Z."})
    try:
        letter_mult = int(tile.get("letter_mult") or 1)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"words": "Letter premiums are 1, 2 or 3."}) from exc
    if letter_mult not in LETTER_MULTS:
        raise ValidationError({"words": "Letter premiums are 1, 2 or 3."})
    return {
        "letter": letter,
        "blank": _is_blank(tile),
        "letter_mult": letter_mult,
        "new": _is_new(tile),
        **({"id": str(tile["id"])} if tile.get("id") else {}),
    }


def _clean_word(word: dict) -> dict:
    text = str(word.get("text") or "").strip().upper()
    raw_tiles = list(word.get("tiles") or [])
    if not raw_tiles and text:
        raw_tiles = [{"letter": char, "blank": False, "letter_mult": 1, "new": True} for char in text]
    tiles = [_clean_tile(tile) for tile in raw_tiles]
    if not tiles:
        raise ValidationError({"words": "Each word needs letters."})
    if not text:
        text = "".join(tile["letter"] for tile in tiles)
    if not text.isalpha():
        raise ValidationError({"words": "Letters must be A–Z."})
    try:
        word_mult = int(word.get("word_mult") or 1)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"words": "Word premiums are 1, 2, 3, 4 or 9."}) from exc
    if word_mult not in WORD_MULTS:
        raise ValidationError({"words": "Word premiums are 1, 2, 3, 4 or 9."})
    return {"text": text, "tiles": tiles, "word_mult": word_mult}


def validate_move(move: dict, *, used_blanks: int = 0, tile_set: str = DEFAULT_SET) -> dict:
    kind = str(move.get("type") or "play").strip().lower()
    if kind not in PLAY_TYPES:
        raise ValidationError({"type": "Use play, pass, exchange or challenge_lost."})
    if kind != "play":
        return {"type": kind, "words": [], "bingo": False}
    words = [_clean_word(word) for word in (move.get("words") or [])]
    if not words:
        raise ValidationError({"words": "Type the word that was played."})
    placed = unique_new_tiles(words)
    if placed > MAX_NEW_TILES:
        raise ValidationError({"words": f"At most {MAX_NEW_TILES} tiles can be placed in one turn."})
    blanks = sum(
        1
        for word in words
        for tile in word["tiles"]
        if tile["blank"] and tile["new"]
    )
    allowed = blank_count(tile_set)
    if used_blanks + blanks > allowed:
        raise ValidationError({"words": f"This set has {allowed} blanks."})
    bingo = move.get("bingo")
    if bingo is not None:
        bingo = bool(bingo)
    return {"type": "play", "words": words, "bingo": bingo}


def preview_move(move: dict, tile_set: str = DEFAULT_SET) -> dict[str, Any]:
    cleaned = validate_move(move, tile_set=tile_set)
    total, bingo = score_move(cleaned, tile_set)
    return {
        "type": cleaned["type"],
        "words": [
            {
                **word,
                "subtotal": score_word({**word, "word_mult": 1}, tile_set),
                "total": score_word(word, tile_set),
                "breakdown": breakdown_word(word, tile_set),
            }
            for word in cleaned["words"]
        ],
        "bingo": bingo,
        "bingo_bonus": 50 if bingo else 0,
        "total": total,
    }
