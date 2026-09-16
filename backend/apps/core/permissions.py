"""Permission classes driven by a user's role within a competition.

Every object in the system ultimately belongs to a competition, so each model
exposes a `competition` attribute (or the view exposes `get_competition()`) and
these classes resolve the caller's membership from there.
"""

from __future__ import annotations

from typing import Any

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView


class Role:
    OWNER = "owner"
    ADMIN = "admin"
    SCORER = "scorer"
    MEMBER = "member"

    CHOICES = (
        (OWNER, "Owner"),
        (ADMIN, "Admin"),
        (SCORER, "Scorer"),
        (MEMBER, "Member"),
    )

    # Ordered least to most privileged; used for "at least this role" checks.
    RANK = {MEMBER: 0, SCORER: 1, ADMIN: 2, OWNER: 3}


def role_in(competition: Any, user: Any) -> str | None:
    """Return the user's role code in `competition`, or None if not a member."""

    if not user or not user.is_authenticated or competition is None:
        return None
    if competition.owner_id == user.id:
        return Role.OWNER

    from apps.competitions.models import Membership

    membership = Membership.objects.filter(
        competition=competition, user=user
    ).only("role").first()
    return membership.role if membership else None


def has_at_least(competition: Any, user: Any, minimum: str) -> bool:
    role = role_in(competition, user)
    if role is None:
        return False
    return Role.RANK[role] >= Role.RANK[minimum]


def _competition_of(obj: Any) -> Any:
    if obj is None:
        return None
    # Walk the well-known relations until we find the owning competition.
    for attr in ("competition", "fixture", "post", "stage"):
        if attr == "competition" and hasattr(obj, "competition"):
            return obj.competition
        if hasattr(obj, attr):
            return _competition_of(getattr(obj, attr))
    return obj if hasattr(obj, "owner_id") else None


class IsCompetitionMember(permissions.BasePermission):
    """Read access for members; private competitions are invisible to everyone else."""

    message = "You are not a member of this competition."

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        competition = _competition_of(obj)
        if competition is None:
            return False
        if request.method in permissions.SAFE_METHODS and not competition.is_private:
            return True
        return role_in(competition, request.user) is not None


class IsCompetitionAdminOrReadOnly(permissions.BasePermission):
    """Anyone who can see the competition may read; only admins may change it."""

    message = "Only competition admins can make this change."

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        competition = _competition_of(obj)
        if competition is None:
            return False
        if request.method in permissions.SAFE_METHODS:
            if not competition.is_private:
                return True
            return role_in(competition, request.user) is not None
        return has_at_least(competition, request.user, Role.ADMIN)


class CanRecordScores(permissions.BasePermission):
    """Scorers and above may record fixture events."""

    message = "You need scorer access to record results for this competition."

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        competition = _competition_of(obj)
        if competition is None:
            return False
        if request.method in permissions.SAFE_METHODS:
            if not competition.is_private:
                return True
            return role_in(competition, request.user) is not None
        return has_at_least(competition, request.user, Role.SCORER)


class IsAuthorOrCompetitionAdmin(permissions.BasePermission):
    """Users edit their own posts and comments; admins can moderate anything."""

    message = "You can only edit your own content."

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        competition = _competition_of(obj)
        if request.method in permissions.SAFE_METHODS:
            if competition is not None and not competition.is_private:
                return True
            return role_in(competition, request.user) is not None
        if getattr(obj, "author_id", None) == request.user.id:
            return True
        return has_at_least(competition, request.user, Role.ADMIN)
