"""Cautions and send-offs from card events.

Association football: two yellow cards become a red. A red card sends the
player off for the rest of the match.

Rugby: a yellow is a timed sin bin (10 minutes). An upgraded yellow is a
longer sin bin (20 minutes). A straight red, or a second yellow in the same
match, sends the player off for the rest of the match.
"""

from __future__ import annotations

from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .models import ScoreEvent

YELLOW = "yellow-card"
UPGRADED_YELLOW = "upgraded-yellow-card"
RED = "red-card"
CAUTIONS_FOR_SEND_OFF = 2
SECOND_YELLOW_NOTE = "Second yellow"

CARD_CODES = (YELLOW, UPGRADED_YELLOW, RED)


def card_code(category) -> str:
    return (getattr(category, "code", "") or "").strip().lower()


def is_yellow(category) -> bool:
    return card_code(category) == YELLOW


def is_upgraded_yellow(category) -> bool:
    return card_code(category) == UPGRADED_YELLOW


def is_red(category) -> bool:
    return card_code(category) == RED


def is_card(category) -> bool:
    return card_code(category) in CARD_CODES


def is_rugby_competition(competition) -> bool:
    settings = getattr(competition, "settings_json", None) or {}
    family = str(settings.get("family") or "")
    preset = str(settings.get("preset") or "")
    sport = str(getattr(competition, "sport", "") or "").lower()
    style = str((settings.get("discipline") or {}).get("style") or "")
    return (
        style == "rugby"
        or family.startswith("rugby")
        or preset.startswith("rugby")
        or "rugby" in sport
    )


def rugby_bin_minutes(competition) -> dict[str, int]:
    settings = getattr(competition, "settings_json", None) or {}
    rules = settings.get("discipline") if isinstance(settings.get("discipline"), dict) else {}
    return {
        YELLOW: int(rules.get("yellow_sin_bin_minutes") or 10),
        UPGRADED_YELLOW: int(rules.get("upgraded_yellow_minutes") or 20),
    }


def _card_events(fixture, player_id):
    return (
        ScoreEvent.objects.filter(fixture=fixture, player_id=player_id)
        .select_related("scoring_category")
        .order_by("minute", "created_at")
    )


def caution_count(fixture, player_id) -> Decimal:
    total = Decimal("0")
    for event in _card_events(fixture, player_id):
        if is_yellow(event.scoring_category):
            total += event.quantity or Decimal("0")
    return total


def is_sent_off(fixture, player_id) -> bool:
    return any(is_red(event.scoring_category) for event in _card_events(fixture, player_id))


def sent_off_ids(fixture) -> set:
    return set(
        ScoreEvent.objects.filter(
            fixture=fixture,
            player__isnull=False,
            scoring_category__code=RED,
        ).values_list("player_id", flat=True)
    )


def card_counts(fixture) -> dict:
    """Yellow / upgraded-yellow / red cards per player in one match, for marking shirts."""

    counts: dict = {}
    rows = ScoreEvent.objects.filter(
        fixture=fixture,
        player__isnull=False,
        scoring_category__code__in=CARD_CODES,
    ).values_list("player_id", "scoring_category__code", "quantity")
    for player_id, code, quantity in rows:
        cards = counts.setdefault(
            player_id, {"yellow": 0, "upgraded_yellow": 0, "red": 0}
        )
        amount = int(quantity or 1)
        if code == YELLOW:
            cards["yellow"] += amount
        elif code == UPGRADED_YELLOW:
            cards["upgraded_yellow"] += amount
        else:
            cards["red"] += amount
    return counts


def sin_bins(fixture, *, as_of_minute: int | None = None) -> dict:
    """Active rugby sin bins keyed by player id.

    A yellow (10') or upgraded yellow (20') removes the player until the
    match minute reaches the bin end. Without a clock minute, the bin stays
    active for the rest of the payload so the shirt shows as off.
    """

    if not is_rugby_competition(fixture.competition):
        return {}
    durations = rugby_bin_minutes(fixture.competition)
    dismissed = sent_off_ids(fixture)
    active: dict = {}
    rows = (
        ScoreEvent.objects.filter(
            fixture=fixture,
            player__isnull=False,
            scoring_category__code__in=(YELLOW, UPGRADED_YELLOW),
        )
        .select_related("scoring_category")
        .order_by("minute", "created_at")
    )
    for event in rows:
        player_id = event.player_id
        if player_id in dismissed:
            continue
        code = card_code(event.scoring_category)
        length = durations.get(code) or 10
        start = int(event.minute) if event.minute is not None else 0
        until = start + length
        if as_of_minute is not None and as_of_minute >= until:
            active.pop(player_id, None)
            continue
        active[player_id] = {
            "kind": "upgraded_yellow" if code == UPGRADED_YELLOW else "yellow",
            "minutes": length,
            "from_minute": start,
            "until_minute": until,
        }
    return active


def assert_can_record_card(fixture, player_id, category) -> None:
    """A player who is already off cannot pick up another card."""

    if player_id is None or not is_card(category):
        return
    if is_sent_off(fixture, player_id):
        raise ValidationError({"player": "That player has already been sent off."})


def reconcile_cards(fixture, player_id) -> ScoreEvent | None:
    """Turn two yellows into a red, and drop an automatic red if a yellow is removed."""

    if player_id is None:
        return None
    events = list(_card_events(fixture, player_id))
    yellows = sum(
        (event.quantity or Decimal("0") for event in events if is_yellow(event.scoring_category)),
        Decimal("0"),
    )
    reds = [event for event in events if is_red(event.scoring_category)]
    automatic = [event for event in reds if event.note == SECOND_YELLOW_NOTE]

    if yellows < CAUTIONS_FOR_SEND_OFF:
        for event in automatic:
            event.delete()
        return None
    if reds:
        return None

    category = fixture.competition.scoring_categories.filter(code=RED).first()
    if category is None:
        return None
    last_yellow = next(
        (event for event in reversed(events) if is_yellow(event.scoring_category)), None
    )
    if last_yellow is None:
        return None
    return ScoreEvent.objects.create(
        fixture=fixture,
        side=last_yellow.side,
        scoring_category=category,
        player_id=player_id,
        player_name=last_yellow.player_name,
        quantity=Decimal("1"),
        minute=last_yellow.minute,
        period=last_yellow.period,
        unit_index=last_yellow.unit_index,
        note=SECOND_YELLOW_NOTE,
        recorded_by=last_yellow.recorded_by,
    )
