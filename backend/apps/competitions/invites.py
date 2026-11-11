"""Competition invitations: nobody joins a competition until they accept."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.bus import Queues, enqueue_job
from apps.core.permissions import Role

from .models import Competition, CompetitionInvite, Membership

ROLE_WORDS = {
    Role.ADMIN: "an admin",
    Role.SCORER: "a scorer",
    Role.MEMBER: "a member",
}


def role_words(role: str) -> str:
    return ROLE_WORDS.get(role, "a member")


def send_invite(competition: Competition, user, role: str, by) -> CompetitionInvite:
    """Invite `user`; they are told at once and decide whether to join."""

    if Membership.objects.filter(competition=competition, user=user).exists():
        raise ValidationError("That person is already a member.")
    if CompetitionInvite.objects.filter(
        competition=competition, user=user, status=CompetitionInvite.Status.PENDING
    ).exists():
        raise ValidationError("That person already has an invite waiting for their answer.")
    invite = CompetitionInvite.objects.create(
        competition=competition,
        user=user,
        role=role or Role.MEMBER,
        invited_by=by if getattr(by, "is_authenticated", False) else None,
    )
    enqueue_job(Queues.NOTIFICATIONS, "competition-invite", {"invite_id": str(invite.id)})
    return invite


def pending_invites_for(user):
    return (
        CompetitionInvite.objects.filter(user=user, status=CompetitionInvite.Status.PENDING)
        .select_related("competition", "competition__owner", "invited_by", "user")
        .order_by("-created_at")
    )


def own_pending_invite(user, invite_id) -> CompetitionInvite:
    invite = (
        CompetitionInvite.objects.select_related("competition", "invited_by")
        .filter(pk=invite_id, user=user)
        .first()
    )
    if invite is None:
        raise PermissionDenied("That invite is not yours.")
    if invite.status != CompetitionInvite.Status.PENDING:
        raise ValidationError({"status": "This invite has already been answered or withdrawn."})
    return invite


@transaction.atomic
def accept_invite(invite: CompetitionInvite) -> Membership:
    membership, created = Membership.objects.get_or_create(
        competition=invite.competition,
        user=invite.user,
        defaults={"role": invite.role, "invited_by": invite.invited_by},
    )
    if not created and membership.role == Role.MEMBER and invite.role != Role.MEMBER:
        membership.role = invite.role
        membership.save(update_fields=["role", "updated_at"])
    _answer(invite, CompetitionInvite.Status.ACCEPTED)
    return membership


def decline_invite(invite: CompetitionInvite) -> None:
    _answer(invite, CompetitionInvite.Status.DECLINED)


def cancel_invite(invite: CompetitionInvite) -> None:
    if invite.status != CompetitionInvite.Status.PENDING:
        raise ValidationError({"status": "Only a waiting invite can be withdrawn."})
    invite.status = CompetitionInvite.Status.CANCELLED
    invite.responded_at = timezone.now()
    invite.save(update_fields=["status", "responded_at", "updated_at"])


def _answer(invite: CompetitionInvite, status: str) -> None:
    invite.status = status
    invite.responded_at = timezone.now()
    invite.save(update_fields=["status", "responded_at", "updated_at"])
    if invite.invited_by_id:
        enqueue_job(
            Queues.NOTIFICATIONS, "competition-invite-answered", {"invite_id": str(invite.id)}
        )
