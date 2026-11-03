"""The order a timed game moves through, and the penalty shootout that settles a level knockout.

first_half -> half_time -> second_half -> full time
In a knockout that is level at full time:
  extra_time -> extra_first -> extra_half_time -> extra_second -> (still level) penalties
"""

from __future__ import annotations

from rest_framework.exceptions import ValidationError

from .models import Fixture

FIRST_HALF = "first_half"
HALF_TIME = "half_time"
SECOND_HALF = "second_half"
EXTRA_TIME = "extra_time"
EXTRA_FIRST = "extra_first"
EXTRA_HALF_TIME = "extra_half_time"
EXTRA_SECOND = "extra_second"
PENALTIES = "penalties"
FULL_TIME = "full_time"

PLAYING = {FIRST_HALF, SECOND_HALF, EXTRA_FIRST, EXTRA_SECOND}
# Phases a game cannot be closed from by marking it completed.
UNFINISHED = {FIRST_HALF, HALF_TIME, SECOND_HALF, EXTRA_TIME, EXTRA_FIRST, EXTRA_HALF_TIME,
              EXTRA_SECOND, PENALTIES}

ACTIONS = {"kick_off", "end_half", "start_second_half", "end_game", "start_extra_time"}

# Five kicks each, then sudden death.
SHOOTOUT_ROUNDS = 5


def current_phase(fixture: Fixture) -> str:
    """A live game started before phases were tracked counts as the first half."""

    if fixture.phase:
        return fixture.phase
    if fixture.status == Fixture.Status.LIVE:
        return FIRST_HALF
    return ""


def is_knockout(fixture: Fixture) -> bool:
    competition = fixture.competition
    if competition.format == "knockout":
        return True
    stage = fixture.stage
    return stage is not None and stage.kind == "knockout"


def _two_sides(fixture: Fixture) -> list:
    return list(fixture.sides.order_by("position", "created_at"))


def is_level(fixture: Fixture) -> bool:
    fixture.recalculate_scores()
    sides = _two_sides(fixture)
    return len(sides) == 2 and sides[0].score == sides[1].score


def next_phase(fixture: Fixture, action: str) -> str:
    """Where this action takes the game, or a clear error if it is not allowed now."""

    phase = current_phase(fixture)
    if action == "kick_off":
        if fixture.status != Fixture.Status.SCHEDULED or phase:
            raise ValidationError({"action": "This game has already kicked off."})
        return FIRST_HALF
    if action == "end_half":
        if phase == FIRST_HALF:
            return HALF_TIME
        if phase == EXTRA_FIRST:
            return EXTRA_HALF_TIME
        if phase in {SECOND_HALF, EXTRA_SECOND}:
            raise ValidationError(
                {"action": "This is the second half. Use End game to finish the match."}
            )
        raise ValidationError({"action": "You can only end a half while the first half is played."})
    if action == "start_second_half":
        if phase == HALF_TIME:
            return SECOND_HALF
        if phase == EXTRA_HALF_TIME:
            return EXTRA_SECOND
        raise ValidationError({"action": "The second half starts at half-time."})
    if action == "end_game":
        if phase in {FIRST_HALF, EXTRA_FIRST}:
            raise ValidationError(
                {"action": "End the first half first. The game can only end in the second half."}
            )
        if phase not in {SECOND_HALF, EXTRA_SECOND}:
            raise ValidationError({"action": "The game can only end in the second half."})
        if is_knockout(fixture) and is_level(fixture):
            if phase == SECOND_HALF and (fixture.overtime_minutes or 0) > 0:
                return EXTRA_TIME
            return PENALTIES
        return FULL_TIME
    if action == "start_extra_time":
        if phase != EXTRA_TIME:
            raise ValidationError(
                {"action": "Extra time is only played when a knockout game is level."}
            )
        return EXTRA_FIRST
    raise ValidationError({"action": f"Unknown action. Use one of: {', '.join(sorted(ACTIONS))}."})


def assert_can_complete(fixture: Fixture) -> None:
    """Marking a timed game completed must go through End game (and a shootout if one is due)."""

    phase = fixture.phase
    if phase == PENALTIES:
        if shootout_winner(fixture) is None:
            raise ValidationError(
                {"status": "The penalty shootout is not decided yet. Keep recording kicks."}
            )
        return
    if phase in UNFINISHED:
        raise ValidationError(
            {"status": "The game can only end in the second half. Use End game."}
        )


# --- Shootout ----------------------------------------------------------------


def _score(kicks: list[dict], side_id: str) -> tuple[int, int]:
    taken = [kick for kick in kicks if kick["side"] == side_id]
    return sum(1 for kick in taken if kick["scored"]), len(taken)


def shootout_winner(fixture: Fixture) -> str | None:
    sides = [str(side.id) for side in _two_sides(fixture)]
    if len(sides) != 2:
        return None
    return decide_shootout(fixture.shootout or [], sides[0], sides[1])


def decide_shootout(kicks: list[dict], first: str, second: str) -> str | None:
    """The winning side id once the shootout cannot be caught, else None."""

    goals_a, taken_a = _score(kicks, first)
    goals_b, taken_b = _score(kicks, second)
    if taken_a <= SHOOTOUT_ROUNDS and taken_b <= SHOOTOUT_ROUNDS:
        left_a = SHOOTOUT_ROUNDS - taken_a
        left_b = SHOOTOUT_ROUNDS - taken_b
        if goals_a > goals_b + left_b:
            return first
        if goals_b > goals_a + left_a:
            return second
        if taken_a < SHOOTOUT_ROUNDS or taken_b < SHOOTOUT_ROUNDS:
            return None
    # Sudden death: decided once both have kicked the same number of times.
    if taken_a == taken_b and goals_a != goals_b:
        return first if goals_a > goals_b else second
    return None


def next_kicker_side(kicks: list[dict], first: str, second: str) -> str:
    _, taken_a = _score(kicks, first)
    _, taken_b = _score(kicks, second)
    return first if taken_a <= taken_b else second


def eligible_kickers(fixture: Fixture, side) -> list[dict]:
    """Players on the pitch at the final whistle, from the team sheet and its substitutions."""

    from .cards import sent_off_ids
    from .matchday import _field_state, _subs

    lineup = getattr(side, "lineup", None)
    subs = [sub for sub in _subs(fixture) if sub.side_id == side.id]
    on, _, _ = _field_state(lineup, subs, sent_off_ids(fixture))
    if lineup is not None:
        numbers = {entry.player_id: entry.number for entry in lineup.entries.all()}
        members = side.participant.roster.filter(id__in=on)
    else:
        numbers = {}
        members = side.participant.roster.filter(is_active=True)
    rows = [
        {
            "player_id": str(member.id),
            "name": member.name,
            "number": numbers.get(member.id) or member.number,
        }
        for member in members
    ]
    rows.sort(key=lambda row: (row["number"] is None, row["number"] or 0, row["name"]))
    return rows


def shootout_state(fixture: Fixture) -> dict | None:
    if current_phase(fixture) != PENALTIES and not fixture.shootout:
        return None
    sides = _two_sides(fixture)
    if len(sides) != 2:
        return None
    first, second = str(sides[0].id), str(sides[1].id)
    kicks = list(fixture.shootout or [])
    winner = decide_shootout(kicks, first, second)
    taken: dict[str, int] = {}
    for kick in kicks:
        if kick.get("player"):
            taken[kick["player"]] = taken.get(kick["player"], 0) + 1
    eligible = {}
    for side in sides:
        rows = eligible_kickers(fixture, side)
        for row in rows:
            row["kicks"] = taken.get(row["player_id"], 0)
        eligible[str(side.id)] = rows
    return {
        "kicks": kicks,
        "score": {side_id: _score(kicks, side_id)[0] for side_id in (first, second)},
        "taken": {side_id: _score(kicks, side_id)[1] for side_id in (first, second)},
        "next_side": None if winner else next_kicker_side(kicks, first, second),
        "winner": winner,
        "eligible": eligible,
    }


def add_kick(fixture: Fixture, side_id: str, player_id: str, scored: bool) -> None:
    if current_phase(fixture) != PENALTIES:
        raise ValidationError({"shootout": "There is no penalty shootout in this game."})
    sides = _two_sides(fixture)
    first, second = str(sides[0].id), str(sides[1].id)
    kicks = list(fixture.shootout or [])
    if decide_shootout(kicks, first, second):
        raise ValidationError({"shootout": "The shootout is already decided."})
    expected = next_kicker_side(kicks, first, second)
    if side_id != expected:
        team = next(side for side in sides if str(side.id) == expected)
        raise ValidationError({"side": f"It is {team.participant.name}'s turn to kick."})
    side = next(side for side in sides if str(side.id) == side_id)
    rows = eligible_kickers(fixture, side)
    by_id = {row["player_id"]: row for row in rows}
    if player_id not in by_id:
        raise ValidationError(
            {"player": "Pick a player who finished the game on the pitch for this team."}
        )
    counts = {row["player_id"]: 0 for row in rows}
    for kick in kicks:
        if kick.get("player") in counts:
            counts[kick["player"]] += 1
    if counts[player_id] > min(counts.values()):
        raise ValidationError(
            {"player": "Every team-mate on the pitch kicks once before anyone kicks again."}
        )
    kicks.append(
        {"side": side_id, "player": player_id, "name": by_id[player_id]["name"], "scored": scored}
    )
    fixture.shootout = kicks
    fixture.save(update_fields=["shootout", "updated_at"])


def undo_kick(fixture: Fixture) -> None:
    if current_phase(fixture) != PENALTIES or not fixture.shootout:
        raise ValidationError({"shootout": "There is no kick to undo."})
    fixture.shootout = list(fixture.shootout)[:-1]
    fixture.save(update_fields=["shootout", "updated_at"])
