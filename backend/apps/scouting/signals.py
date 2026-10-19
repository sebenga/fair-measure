"""Keep a talent profile's club label in step with the teams the player is on."""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.competitions.models import RosterMember
from apps.core.signals import results_changed

from . import catalog
from .models import PlayerProfile
from .services import affiliated_teams, school_or_club_label


@receiver(post_save, sender=RosterMember)
@receiver(post_delete, sender=RosterMember)
def _refresh_school_or_club(sender, instance: RosterMember, **kwargs) -> None:
    # Accepting a team invite puts the player on the roster; the team then shows
    # on their talent profile without them adding it by hand.
    if not instance.user_id:
        return
    profile = PlayerProfile.objects.filter(user_id=instance.user_id).first()
    if profile is None:
        return
    label = school_or_club_label(affiliated_teams(profile))
    if label != profile.school_or_club:
        PlayerProfile.objects.filter(pk=profile.pk).update(school_or_club=label)


@receiver(results_changed)
def _queue_player_stats(sender, competition, **kwargs) -> None:
    # Player stats are rebuilt in the background after counted results change, so
    # completing a fixture never waits for them.
    from apps.core.bus import Queues, enqueue_job

    if catalog.sport_for_competition(competition.sport) is None:
        return
    enqueue_job(Queues.STATS, "recompute", {"competition_id": str(competition.id)})
