"""Things SQLite lets through that Postgres (production) rejects.

Run against Postgres with TEST_DATABASE_URL to catch them before a deploy.
"""

from __future__ import annotations

import pytest

from apps.competitions.models import Competition, Membership
from apps.core.permissions import Role
from apps.fixtures.models import Fixture
from apps.notifications.models import Notification
from apps.notifications.services import notify_users

pytestmark = pytest.mark.django_db


def test_blank_values_sort_last_like_postgres(competition):
    from apps.competitions.models import Participant

    Participant.objects.create(competition=competition, name="Unseeded", seed=None)
    Participant.objects.create(competition=competition, name="Top seed", seed=1)
    names = list(
        competition.participants.filter(name__in=["Unseeded", "Top seed"])
        .order_by("seed")
        .values_list("name", flat=True)
    )
    newest_first = list(
        competition.participants.filter(name__in=["Unseeded", "Top seed"])
        .order_by("-seed")
        .values_list("name", flat=True)
    )

    assert names == ["Top seed", "Unseeded"]
    assert newest_first == ["Unseeded", "Top seed"]


def test_server_built_labels_are_trimmed_to_the_column(competition):
    fixture = Fixture.objects.create(competition=competition, label="Harbour Hawks v " * 20)

    fixture.refresh_from_db()
    assert len(fixture.label) == Fixture._meta.get_field("label").max_length


def test_notification_titles_with_long_competition_names_still_send(user, other_user):
    long_name = "Northern Regional Inter-Club Championship " * 5
    competition = Competition.objects.create(name=long_name[:200], owner=user)
    Membership.objects.create(competition=competition, user=other_user, role=Role.MEMBER)

    notify_users(
        [other_user],
        kind="invite",
        title=f"You were added to {competition.name}",
        competition=competition,
        category="announcements",
    )

    title = Notification.objects.get(user=other_user).title
    assert len(title) == Notification._meta.get_field("title").max_length
