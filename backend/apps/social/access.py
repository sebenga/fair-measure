"""Who may take part in a competition's conversation."""

from __future__ import annotations

from typing import Any

from apps.core.permissions import role_in


def takes_part(competition: Any, user: Any) -> bool:
    """Members, plus anyone who plays in it: a participant's manager or a rostered player.

    Reading a public feed needs none of this; posting, commenting and reacting do.
    """

    if role_in(competition, user) is not None:
        return True
    if not user or not user.is_authenticated or competition is None:
        return False

    from apps.competitions.models import Participant, RosterMember

    if Participant.objects.filter(competition=competition, managed_by=user).exists():
        return True
    return RosterMember.objects.filter(
        participant__competition=competition, user=user, is_active=True
    ).exists()
