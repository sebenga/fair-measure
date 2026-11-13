"""Deleting every competition on the platform in one go."""

from __future__ import annotations

import logging

from django.db import transaction

from .demo import _delete_orphan_demo_users
from .models import Competition, Participant

logger = logging.getLogger(__name__)


def clear_all_competitions(by=None) -> dict:
    """Delete every competition and everything that belongs to it.

    Score events protect their scoring categories and Games events protect their
    competitions, so both go first. Games themselves stay, without their events.
    Accounts made up for demos go too, once nothing else uses them.
    """

    from apps.fixtures.models import Fixture, ScoreEvent
    from apps.games.models import GamesEvent

    demo_users: list = []
    for settings_json in Competition.objects.values_list("settings_json", flat=True):
        demo_users.extend(((settings_json or {}).get("demo_league") or {}).get("user_ids") or [])

    counts = {
        "competitions": Competition.objects.count(),
        "fixtures": Fixture.objects.count(),
        "participants": Participant.objects.count(),
        "games_events": GamesEvent.objects.count(),
    }
    with transaction.atomic():
        ScoreEvent.objects.all().delete()
        GamesEvent.objects.all().delete()
        Competition.objects.all().delete()
        _delete_orphan_demo_users(demo_users)
    logger.warning(
        "All competitions cleared by %s: %s",
        getattr(by, "email", None) or "system",
        counts,
    )
    return counts
