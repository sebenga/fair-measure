"""Cautions and send-offs from card events.

Two yellow cards become a red. A red card sends the player off and stops
their rating. Nothing here names a sport: it only reads category codes.
"""

from __future__ import annotations

from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .models import ScoreEvent

YELLOW = "yellow-card"
RED = "red-card"
CAUTIONS_FOR_SEND_OFF = 2
SECOND_YELLOW_NOTE = "Second yellow"


def card_code(category) -> str:
    return (getattr(category, "code", "") or "").strip().lower()


def is_yellow(category) -> bool:
    return card_code(category) == YELLOW


def is_red(category) -> bool:
    return card_code(category) == RED


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


def assert_can_record_card(fixture, player_id, category) -> None:
    """A player who is already off cannot pick up another card."""

    if player_id is None or not (is_yellow(category) or is_red(category)):
        return
    if is_sent_off(fixture, player_id):
        raise ValidationError({"player": "That player has already been sent off."})


def reconcile_cards(fixture, player_id) -> ScoreEvent | None:
    """Turn two yellows into a red, and drop an automatic red if a yellow is removed."""

    if player_id is None:
        return None
    events = list(_card_events(fixture, player_id))
    yellows = sum((event.quantity or Decimal("0") for event in events if is_yellow(event.scoring_category)), Decimal("0"))
    reds = [event for event in events if is_red(event.scoring_category)]
    automatic = [event for event in reds if event.note == SECOND_YELLOW_NOTE]
    straight = [event for event in reds if event.note != SECOND_YELLOW_NOTE]

    if yellows < CAUTIONS_FOR_SEND_OFF:
        for event in automatic:
            event.delete()
        return None
    if reds:
        return None

    category = fixture.competition.scoring_categories.filter(code=RED).first()
    if category is None:
        return None
    last_yellow = next((event for event in reversed(events) if is_yellow(event.scoring_category)), None)
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
