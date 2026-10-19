"""Keep each event's medals in step with its competition's confirmed results."""

from __future__ import annotations

from django.dispatch import receiver

from apps.core.signals import results_changed


@receiver(results_changed)
def _refresh_medals(sender, competition, **kwargs) -> None:
    from .models import GamesEvent
    from .services import sync_medals, touch_games_status

    event = GamesEvent.objects.filter(competition=competition).select_related("games").first()
    if event is None:
        return
    if sync_medals(event):
        touch_games_status(event.games)
