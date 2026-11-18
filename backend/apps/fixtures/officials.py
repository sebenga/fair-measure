"""Appointed match officials: roles, acceptance, live scoring rights."""

from __future__ import annotations

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.permissions import Role, has_at_least

from .models import Fixture, FixtureReferee


LIVE_STATUSES = {Fixture.Status.SCHEDULED, Fixture.Status.LIVE}
POST_MATCH = {
    Fixture.Status.COMPLETED,
    Fixture.Status.CONFIRMED,
    Fixture.Status.FORFEIT,
    Fixture.Status.DISPUTED,
}

# Roles that may start/stop the clock and record live events once accepted.
LIVE_ROLES = {
    FixtureReferee.Role.REFEREE,
    FixtureReferee.Role.ASSISTANT_1,
    FixtureReferee.Role.ASSISTANT_2,
    FixtureReferee.Role.FOURTH_OFFICIAL,
    FixtureReferee.Role.TMO,
}


def accepted_officials(fixture: Fixture):
    return fixture.referees.filter(status=FixtureReferee.Status.ACCEPTED)


def accepted_referee(fixture: Fixture) -> FixtureReferee | None:
    return (
        accepted_officials(fixture)
        .filter(role=FixtureReferee.Role.REFEREE)
        .select_related("user")
        .first()
    )


def live_official_for(fixture: Fixture, user) -> FixtureReferee | None:
    """The caller's accepted appointment that may run the live match, if any."""

    if not user or not getattr(user, "is_authenticated", False):
        return None
    return (
        accepted_officials(fixture)
        .filter(user=user, role__in=LIVE_ROLES)
        .select_related("user")
        .first()
    )


def user_can_live_score(fixture: Fixture, user) -> bool:
    """Only the accepted referee (or a delegated live official) may score live."""

    return live_official_for(fixture, user) is not None


def user_can_score_fixture(fixture: Fixture, user) -> bool:
    """Live: appointed officials only. After full time: officials or admins (corrections)."""

    if fixture.status in LIVE_STATUSES or fixture.status == Fixture.Status.POSTPONED:
        return user_can_live_score(fixture, user)
    if fixture.referees.filter(
        user=user, status=FixtureReferee.Status.ACCEPTED
    ).exists():
        return True
    return has_at_least(fixture.competition, user, Role.ADMIN)


def assert_can_live_score(fixture: Fixture, user) -> FixtureReferee:
    official = live_official_for(fixture, user)
    if official is None:
        raise PermissionDenied(
            "Only the appointed referee (or an official they delegated) can record live events."
        )
    return official


def assert_has_accepted_referee(fixture: Fixture) -> FixtureReferee:
    referee = accepted_referee(fixture)
    if referee is None:
        raise ValidationError(
            {"referees": "Appoint a referee and wait for them to accept before kickoff."}
        )
    return referee


def appoint_official(
    *,
    fixture: Fixture,
    user,
    role: str = FixtureReferee.Role.REFEREE,
    appointed_by,
    stand_in: bool = False,
    note: str = "",
) -> FixtureReferee:
    """Create or update an appointment. New appointments start as invited."""

    if role == FixtureReferee.Role.REFEREE:
        existing_ref = (
            fixture.referees.filter(role=FixtureReferee.Role.REFEREE)
            .exclude(user=user)
            .first()
        )
        if existing_ref is not None:
            raise ValidationError({"role": "This match already has a referee."})

    defaults = {
        "role": role,
        "status": FixtureReferee.Status.INVITED,
        "appointed_by": appointed_by,
        "stand_in": stand_in,
        "appointment_note": (note or "")[:400],
    }
    row, created = FixtureReferee.objects.get_or_create(
        fixture=fixture, user=user, defaults=defaults
    )
    if not created:
        row.role = role
        row.appointed_by = appointed_by
        row.stand_in = stand_in or row.stand_in
        if note:
            row.appointment_note = note[:400]
        # Re-invite if they previously declined.
        if row.status == FixtureReferee.Status.DECLINED:
            row.status = FixtureReferee.Status.INVITED
            row.responded_at = None
        row.save()
    return row


def respond_to_appointment(official: FixtureReferee, *, user, accept: bool) -> FixtureReferee:
    if official.user_id != user.id:
        raise PermissionDenied("Only the appointed official can accept or decline.")
    if official.status == FixtureReferee.Status.ACCEPTED and accept:
        return official
    official.status = (
        FixtureReferee.Status.ACCEPTED if accept else FixtureReferee.Status.DECLINED
    )
    official.responded_at = timezone.now()
    official.save(update_fields=["status", "responded_at", "updated_at"])
    return official


def log_match_action(
    *,
    fixture: Fixture,
    user,
    action: str,
    detail: str = "",
    source: str = "admin",
    device: str = "",
    payload: dict | None = None,
):
    from .models import MatchAuditLog

    return MatchAuditLog.objects.create(
        fixture=fixture,
        actor=user if getattr(user, "is_authenticated", False) else None,
        action=action[:80],
        detail=(detail or "")[:2000],
        source=(source or "")[:40],
        device=(device or "")[:120],
        payload=payload or {},
    )
