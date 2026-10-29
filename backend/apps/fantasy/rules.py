"""Squad shape, budget and club limits — the same constraints as official FPL."""

from __future__ import annotations

import math
from collections import Counter
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .models import FantasySlot

SQUAD_SIZE = 15
STARTERS = 11
BUDGET = Decimal("100.0")
MAX_PER_CLUB = 3


def max_per_club_for(club_count: int) -> int:
    """FPL's three-per-club rule, relaxed when the league has fewer than five sides."""

    if club_count < 1:
        return MAX_PER_CLUB
    return max(MAX_PER_CLUB, math.ceil(SQUAD_SIZE / club_count))

SLOT_QUOTAS: dict[str, int] = {
    FantasySlot.GKP: 2,
    FantasySlot.DEF: 5,
    FantasySlot.MID: 5,
    FantasySlot.FWD: 3,
}

# Starting XI must keep a goalkeeper and a recognised outfield shape.
VALID_FORMATIONS = {
    (3, 4, 3),
    (3, 5, 2),
    (4, 3, 3),
    (4, 4, 2),
    (4, 5, 1),
    (5, 2, 3),
    (5, 3, 2),
    (5, 4, 1),
}

BASE_PRICES: dict[str, Decimal] = {
    FantasySlot.GKP: Decimal("4.5"),
    FantasySlot.DEF: Decimal("4.5"),
    FantasySlot.MID: Decimal("5.0"),
    FantasySlot.FWD: Decimal("6.5"),
}

RULES_PUBLIC = {
    "budget": str(BUDGET),
    "squad_size": SQUAD_SIZE,
    "starters": STARTERS,
    "max_per_club": MAX_PER_CLUB,
    "slots": [
        {"key": FantasySlot.GKP, "label": "Goalkeepers", "count": SLOT_QUOTAS[FantasySlot.GKP]},
        {"key": FantasySlot.DEF, "label": "Defenders", "count": SLOT_QUOTAS[FantasySlot.DEF]},
        {"key": FantasySlot.MID, "label": "Midfielders", "count": SLOT_QUOTAS[FantasySlot.MID]},
        {"key": FantasySlot.FWD, "label": "Forwards", "count": SLOT_QUOTAS[FantasySlot.FWD]},
    ],
    "formations": ["-".join(str(n) for n in shape) for shape in sorted(VALID_FORMATIONS)],
    "scoring": [
        {"label": "Appearance", "points": "1"},
        {"label": "60+ minutes", "points": "1"},
        {"label": "Goal (GK/DEF)", "points": "6"},
        {"label": "Goal (MID)", "points": "5"},
        {"label": "Goal (FWD)", "points": "4"},
        {"label": "Assist", "points": "3"},
        {"label": "Clean sheet (GK/DEF)", "points": "4"},
        {"label": "Clean sheet (MID)", "points": "1"},
        {"label": "3 saves", "points": "1"},
        {"label": "Penalty save", "points": "5"},
        {"label": "Yellow card", "points": "-1"},
        {"label": "Red card", "points": "-3"},
        {"label": "Own goal", "points": "-2"},
        {"label": "Captain", "points": "2×"},
    ],
}


def formation_of(starters: list[dict]) -> tuple[int, int, int] | None:
    counts = Counter(pick["slot"] for pick in starters)
    if counts.get(FantasySlot.GKP, 0) != 1:
        return None
    shape = (
        counts.get(FantasySlot.DEF, 0),
        counts.get(FantasySlot.MID, 0),
        counts.get(FantasySlot.FWD, 0),
    )
    return shape if shape in VALID_FORMATIONS else None


def validate_picks(picks: list[dict], *, complete: bool, club_count: int = 0) -> None:
    """Raise if the proposed squad breaks a hard rule.

    Incomplete squads are allowed while building: slot counts may be under the
    quota, there may be fewer than 11 starters, and captain can wait. Going
    over a quota, the budget or three-from-one-club is always rejected.
    """

    if len(picks) != len({pick["player"].id for pick in picks}):
        raise ValidationError({"picks": "The same player cannot be picked twice."})

    by_slot = Counter(pick["slot"] for pick in picks)
    for slot, quota in SLOT_QUOTAS.items():
        if by_slot.get(slot, 0) > quota:
            raise ValidationError(
                {"picks": f"A squad can only have {quota} {FantasySlot(slot).label.lower()}s."}
            )

    club_limit = max_per_club_for(club_count)
    by_club = Counter(str(pick["player"].participant_id) for pick in picks)
    over = [count for count in by_club.values() if count > club_limit]
    if over:
        raise ValidationError(
            {"picks": f"You can pick at most {club_limit} players from the same club."}
        )

    spent = sum((pick["price"] for pick in picks), Decimal("0"))
    if spent > BUDGET:
        raise ValidationError({"picks": f"That squad costs {spent} and the budget is {BUDGET}."})

    starters = [pick for pick in picks if pick["is_starter"]]
    captains = [pick for pick in picks if pick["is_captain"]]
    vices = [pick for pick in picks if pick["is_vice"]]

    if len(captains) > 1:
        raise ValidationError({"picks": "Choose one captain."})
    if len(vices) > 1:
        raise ValidationError({"picks": "Choose one vice-captain."})
    if captains and vices and captains[0]["player"].id == vices[0]["player"].id:
        raise ValidationError({"picks": "Captain and vice-captain must be different players."})

    if complete:
        if len(picks) != SQUAD_SIZE:
            raise ValidationError({"picks": f"A complete squad has {SQUAD_SIZE} players."})
        if by_slot != Counter(SLOT_QUOTAS):
            raise ValidationError({"picks": "Fill every position: 2 GK, 5 DEF, 5 MID, 3 FWD."})
        if len(starters) != STARTERS:
            raise ValidationError({"picks": f"Pick {STARTERS} starters."})
        if formation_of(starters) is None:
            raise ValidationError(
                {"picks": "That starting XI is not a valid formation. Use 3-4-3, 3-5-2, 4-3-3, 4-4-2, 4-5-1, 5-2-3, 5-3-2 or 5-4-1."}
            )
        if len(captains) != 1 or len(vices) != 1:
            raise ValidationError({"picks": "Name a captain and a vice-captain."})
        if not captains[0]["is_starter"]:
            raise ValidationError({"picks": "The captain has to start."})
