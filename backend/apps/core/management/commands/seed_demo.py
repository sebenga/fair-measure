"""Populate a database with a competition that already looks lived-in.

Running the app against empty tables makes it hard to tell whether a screen is
broken or simply has nothing to show. This builds a rugby league mid-season:
played fixtures with scores, upcoming ones, a standings table, and some chatter
in the feed.
"""

from __future__ import annotations

import random
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.competitions.models import Competition, Membership, Participant
from apps.competitions.presets import apply_preset
from apps.core.permissions import Role
from apps.fixtures.models import Fixture, ScoreEvent
from apps.fixtures.services import ScheduleOptions, generate_round_robin
from apps.social.models import Comment, Post, Reaction
from apps.standings.services import refresh_standings

User = get_user_model()

TEAMS = [
    ("Harbour Hawks", "Hawks"),
    ("Northside Nomads", "Nomads"),
    ("Riverbend Rovers", "Rovers"),
    ("Kingsley Kestrels", "Kestrels"),
    ("Old Quarry Oaks", "Oaks"),
    ("Seaview Sharks", "Sharks"),
]

MEMBERS = [
    ("ama@example.com", "Ama Boateng"),
    ("dev@example.com", "Dev Patel"),
    ("noor@example.com", "Noor Haddad"),
    ("tomas@example.com", "Tomás Rivera"),
]

POSTS = [
    "Pitch 2 is waterlogged — we're all on pitch 1 this week. Bring boots you don't mind ruining.",
    "That comeback in the second half was genuinely unreasonable. Well played Nomads.",
    "Reminder: if your team is short, message me before Thursday and we'll sort a ringer.",
    "Sharks are top of the table and I refuse to elaborate further.",
    "Anyone find a black kit bag at the clubhouse? Asking for a very sad teammate.",
]

COMMENTS = [
    "Unreal.",
    "Robbed. Absolutely robbed.",
    "See you Saturday.",
    "Someone get this man a contract.",
    "I was there. Can confirm.",
]


class Command(BaseCommand):
    help = "Create a demo competition with fixtures, scores, standings and feed activity."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--email",
            default="owner@example.com",
            help="Owner account to create or reuse.",
        )
        parser.add_argument(
            "--password",
            default="fairmeasure",
            help="Password for every account this command creates.",
        )
        parser.add_argument(
            "--name",
            default="Thursday Night Rugby",
            help="Competition name.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete an existing competition with the same name first.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=7,
            help="Random seed, so repeated runs produce the same scores.",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        random.seed(options["seed"])

        owner = self._ensure_user(options["email"], "Sam Okafor", options["password"])
        members = [
            self._ensure_user(email, name, options["password"]) for email, name in MEMBERS
        ]

        existing = Competition.objects.filter(name=options["name"]).first()
        if existing:
            if not options["reset"]:
                raise CommandError(
                    f"A competition named {options['name']!r} already exists. "
                    "Re-run with --reset to replace it."
                )
            existing.delete()

        competition = self._create_competition(options["name"], owner, members)
        participants = self._create_participants(competition)
        fixtures = self._create_fixtures(competition, participants)
        played = self._play_fixtures(competition, fixtures)
        refresh_standings(competition)
        self._create_feed(competition, [owner, *members], fixtures)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeeded {competition.name}\n"
                f"  {len(participants)} teams, {len(fixtures)} fixtures ({played} played)\n"
                f"  Sign in as {owner.email} / {options['password']}\n"
                f"  Competition id: {competition.id}\n"
            )
        )

    # --- Steps ----------------------------------------------------------------

    def _ensure_user(self, email: str, display_name: str, password: str):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"display_name": display_name, "email_verified": True},
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(f"  created user {email}")
        return user

    def _create_competition(self, name: str, owner, members: list) -> Competition:
        competition = Competition.objects.create(
            name=name,
            description=(
                "Six teams, one pitch, and a points system nobody fully agrees with. "
                "Bonus point for winning by 15 or more."
            ),
            sport="rugby",
            format="league",
            status=Competition.Status.ACTIVE,
            owner=owner,
            starts_on=date.today() - timedelta(days=28),
            match_weekdays=[3],
            timezone="Europe/London",
        )

        Membership.objects.create(competition=competition, user=owner, role=Role.OWNER)
        # One scorer so the demo shows a non-admin who can still record events.
        roles = [Role.SCORER, Role.MEMBER, Role.MEMBER, Role.ADMIN]
        Membership.objects.bulk_create(
            [
                Membership(competition=competition, user=user, role=role)
                for user, role in zip(members, roles, strict=False)
            ]
        )

        apply_preset(competition, "rugby")
        self.stdout.write(f"  created competition {competition.name}")
        return competition

    def _create_participants(self, competition: Competition) -> list[Participant]:
        participants = Participant.objects.bulk_create(
            [
                Participant(
                    competition=competition,
                    name=name,
                    short_name=short,
                    seed=index + 1,
                )
                for index, (name, short) in enumerate(TEAMS)
            ]
        )
        self.stdout.write(f"  created {len(participants)} teams")
        return list(participants)

    def _create_fixtures(
        self, competition: Competition, participants: list[Participant]
    ) -> list[Fixture]:
        # Start four weeks back so roughly half the season is already history.
        options = ScheduleOptions(
            starts_on=date.today() - timedelta(days=28),
            weekdays=[3],
            kickoff=time(hour=19, minute=30),
            minutes_between_fixtures=75,
            location="Clubhouse Pitch 1",
        )
        fixtures = generate_round_robin(competition, participants, options)
        self.stdout.write(f"  scheduled {len(fixtures)} fixtures")
        return fixtures

    def _play_fixtures(self, competition: Competition, fixtures: list[Fixture]) -> int:
        categories = {
            category.code: category for category in competition.scoring_categories.all()
        }
        try_category = categories.get("try")
        conversion = categories.get("conversion")
        penalty = categories.get("penalty")
        if try_category is None:
            return 0

        now = timezone.now()
        played = 0

        for fixture in fixtures:
            if fixture.scheduled_at is None or fixture.scheduled_at > now:
                continue

            sides = list(fixture.sides.all())
            for side in sides:
                for _ in range(random.randint(0, 5)):
                    ScoreEvent.objects.create(
                        fixture=fixture,
                        side=side,
                        scoring_category=try_category,
                        quantity=Decimal("1"),
                        minute=random.randint(1, 80),
                        recorded_by=competition.owner,
                    )
                if conversion:
                    for _ in range(random.randint(0, 3)):
                        ScoreEvent.objects.create(
                            fixture=fixture,
                            side=side,
                            scoring_category=conversion,
                            quantity=Decimal("1"),
                            minute=random.randint(1, 80),
                            recorded_by=competition.owner,
                        )
                if penalty and random.random() < 0.6:
                    ScoreEvent.objects.create(
                        fixture=fixture,
                        side=side,
                        scoring_category=penalty,
                        quantity=Decimal("1"),
                        minute=random.randint(1, 80),
                        recorded_by=competition.owner,
                    )

            fixture.status = Fixture.Status.COMPLETED
            fixture.started_at = fixture.scheduled_at
            fixture.completed_at = fixture.scheduled_at + timedelta(minutes=95)
            fixture.save(update_fields=["status", "started_at", "completed_at"])
            fixture.recalculate_scores()
            played += 1

        # Leave one match in progress so the live scoring screen has something
        # to show without needing to start one by hand.
        upcoming = [
            fixture
            for fixture in fixtures
            if fixture.scheduled_at and fixture.scheduled_at > now
        ]
        if upcoming:
            live = upcoming[0]
            live.status = Fixture.Status.LIVE
            live.started_at = now - timedelta(minutes=22)
            live.save(update_fields=["status", "started_at"])
            side = live.sides.first()
            if side:
                ScoreEvent.objects.create(
                    fixture=live,
                    side=side,
                    scoring_category=try_category,
                    quantity=Decimal("1"),
                    minute=18,
                    recorded_by=competition.owner,
                )
                live.recalculate_scores()

        self.stdout.write(f"  played {played} fixtures")
        return played

    def _create_feed(self, competition: Competition, users: list, fixtures: list) -> None:
        completed = [f for f in fixtures if f.status == Fixture.Status.COMPLETED]

        for index, body in enumerate(POSTS):
            post = Post.objects.create(
                competition=competition,
                author=users[index % len(users)],
                body=body,
                is_announcement=index == 0,
                is_pinned=index == 0,
                fixture=completed[index] if index < len(completed) else None,
            )
            # Backdate so the feed isn't five posts with the same timestamp.
            Post.objects.filter(pk=post.pk).update(
                created_at=timezone.now() - timedelta(hours=index * 9 + 1)
            )

            comment_total = random.randint(0, 3)
            for comment_index in range(comment_total):
                Comment.objects.create(
                    post=post,
                    author=users[(index + comment_index + 1) % len(users)],
                    body=random.choice(COMMENTS),
                )

            reactors = random.sample(users, k=random.randint(0, len(users)))
            Reaction.objects.bulk_create(
                [Reaction(post=post, user=user, kind=Reaction.Kind.LIKE) for user in reactors]
            )

            # The API keeps these counters in step as activity happens; seeding
            # writes the rows directly, so set them once at the end instead.
            Post.objects.filter(pk=post.pk).update(
                comment_count=comment_total, reaction_count=len(reactors)
            )

        self.stdout.write(f"  created {len(POSTS)} posts")
