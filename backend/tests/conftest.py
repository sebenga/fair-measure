from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.competitions.models import (
    Competition,
    Membership,
    Participant,
    PointsPolicy,
    ScoringCategory,
)
from apps.core.permissions import Role

User = get_user_model()


class RecordingRedis:
    """Stands in for Redis so the real bus code runs without a live server."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self.pushed: list[tuple[str, str]] = []

    def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))

    def lpush(self, key: str, message: str) -> None:
        self.pushed.append((key, message))

    def ping(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def bus_redis(monkeypatch) -> RecordingRedis:
    """Swap the bus's Redis connection rather than stubbing its functions.

    Patching `publish_event` itself would hide bugs in the envelope it builds,
    which is the contract the Node service parses.
    """

    fake = RecordingRedis()
    monkeypatch.setattr("apps.core.bus.get_redis", lambda: fake)
    return fake


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="owner@example.com", password="s3cret-password", display_name="Owner"
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        email="member@example.com", password="s3cret-password", display_name="Member"
    )


@pytest.fixture
def api(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def anon_api() -> APIClient:
    return APIClient()


@pytest.fixture
def competition(db, user) -> Competition:
    comp = Competition.objects.create(
        name="Fourways Winter League",
        owner=user,
        sport="rugby",
        status=Competition.Status.ACTIVE,
    )
    Membership.objects.create(competition=comp, user=user, role=Role.OWNER)
    return comp


@pytest.fixture
def rugby_scoring(competition) -> dict[str, ScoringCategory]:
    categories = {
        "try": ScoringCategory.objects.create(
            competition=competition, name="Try", code="try", points=Decimal("5")
        ),
        "conversion": ScoringCategory.objects.create(
            competition=competition, name="Conversion", code="conversion", points=Decimal("2")
        ),
        "penalty": ScoringCategory.objects.create(
            competition=competition, name="Penalty", code="penalty", points=Decimal("3")
        ),
        "yellow": ScoringCategory.objects.create(
            competition=competition,
            name="Yellow card",
            code="yellow-card",
            points=Decimal("0"),
            affects_score=False,
        ),
    }
    return categories


@pytest.fixture
def points_policy(competition) -> PointsPolicy:
    policy, _ = PointsPolicy.objects.get_or_create(competition=competition)
    policy.win_points = Decimal("4")
    policy.draw_points = Decimal("2")
    policy.loss_points = Decimal("0")
    policy.bonus_loss_margin = 7
    policy.bonus_loss_points = Decimal("1")
    policy.tiebreakers = ["points", "score_difference", "score_for", "name"]
    policy.save()
    return policy


@pytest.fixture
def participants(competition) -> list[Participant]:
    return [
        Participant.objects.create(competition=competition, name=name)
        for name in ["Tank United", "Real United", "Fourways FC", "Bryanston BC"]
    ]
