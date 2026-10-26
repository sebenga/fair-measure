"""Where a player actually lined up, taken from team sheets.

A roster shirt is only a hint. The positions they started or came on in are what
put them in Defenders, Midfielders or Forwards — and a player who has played more
than one line belongs in each of those categories as the same person.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from django.db.models import Exists, OuterRef, Q

from .models import Fixture, LineupEntry, Substitution

COUNTED = {Fixture.Status.COMPLETED, Fixture.Status.LIVE, Fixture.Status.FORFEIT}


def lineup_positions(competition, player_ids=None) -> dict[object, list[str]]:
    """Position labels each player has lined up in, most used first."""

    counted = lineup_position_counts(competition, player_ids)
    return {
        player_id: [label for label, _ in counter.most_common() if label]
        for player_id, counter in counted.items()
    }


def lineup_position_by_match(competition, player_ids=None) -> dict[tuple, str]:
    """The shirt they wore in one fixture: {(fixture_id, player_id): position}."""

    by_match: dict[tuple, str] = {}
    for fixture_id, player_id, position in _entries(competition, player_ids).values_list(
        "lineup__fixture_id", "player_id", "position"
    ):
        if position:
            by_match[(fixture_id, player_id)] = position
    return by_match


def lineup_position_counts(competition, player_ids=None) -> dict[object, Counter]:
    counted: dict[object, Counter] = defaultdict(Counter)
    for player_id, position in _entries(competition, player_ids).values_list(
        "player_id", "position"
    ):
        if position:
            counted[player_id][position] += 1
    return counted


def _entries(competition, player_ids=None):
    came_on = Substitution.objects.filter(
        fixture_id=OuterRef("lineup__fixture_id"),
        player_on_id=OuterRef("player_id"),
    )
    entries = LineupEntry.objects.filter(
        lineup__fixture__competition=competition,
        lineup__fixture__status__in=COUNTED,
    ).filter(Q(role=LineupEntry.Role.STARTER) | Exists(came_on))
    if player_ids is not None:
        entries = entries.filter(player_id__in=player_ids)
    return entries
