"""Scouting Phase 3 demo: a soccer league whose players have match stats and tests.

    python manage.py seed_scouting_stats

Creates "Fair Measure Stats League": 4 teams of 6 adult strikers (one comparison
group of 24, so percentiles show), 6 completed fixtures with goals, shots and
assists tagged to players and their minutes, and 40 m sprint and Yo-Yo results
(most verified by coach@example.com, a few self-reported). Then caches every
player's stats. Safe to re-run: an existing league is left as it is.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.competitions.models import Competition, Membership, Participant, RosterMember
from apps.competitions.presets import apply_preset
from apps.core.permissions import Role
from apps.fixtures.models import Fixture, FixtureSide, PlayerAppearance, ScoreEvent
from apps.scouting import stats
from apps.scouting.models import PhysicalTestResult, PlayerProfile, PlayerSport
from apps.scouting.services import grant_role

User = get_user_model()
NAME = "Fair Measure Stats League"
TEAMS = ["Soweto Strikers", "Durban Dolphins", "Cape Comets", "Pretoria Pumas"]
GIVEN = [
    "Sipho",
    "Thabo",
    "Lebo",
    "Musa",
    "Kabelo",
    "Neo",
    "Tumelo",
    "Bongani",
    "Andile",
    "Kagiso",
    "Lwazi",
    "Tshepo",
]
FAMILY = ["Mokoena", "Dlamini", "Nkosi", "Zulu", "Mahlangu", "Khumalo"]


class Command(BaseCommand):
    help = "Seed a soccer league with tagged player stats, minutes and physical tests."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--password", default="fairmeasure")

    def handle(self, *args, **options) -> None:
        owner = User.objects.filter(email="owner@example.com").first()
        coach = User.objects.filter(email="coach@example.com").first()
        if owner is None:
            self.stderr.write("Run seed_demo first (owner@example.com is needed).")
            return
        if Competition.objects.filter(name=NAME).exists():
            self.stdout.write("The stats league already exists; nothing changed.")
            return
        rng = random.Random(7)  # noqa: S311 - repeatable demo data, not security
        with transaction.atomic():
            competition = self._league(owner, coach, rng, options["password"])
        rows = stats.recompute_competition(competition)
        self.stdout.write(
            self.style.SUCCESS(
                f"Stats league ready: 24 strikers, 6 completed fixtures, {rows} cached stat lines. "
                "Sign in as scout@example.com and open Browse players, or as coach@example.com "
                "to record a test."
            )
        )

    def _league(self, owner, coach, rng, password):
        competition = Competition.objects.create(
            name=NAME, owner=owner, sport="soccer", open_to_scouts=True
        )
        Membership.objects.get_or_create(
            competition=competition, user=owner, defaults={"role": Role.OWNER}
        )
        apply_preset(competition, "soccer")
        teams, members = [], {}
        today = date.today()
        for team_index, team_name in enumerate(TEAMS):
            team = Participant.objects.create(competition=competition, name=team_name, kind="team")
            teams.append(team)
            members[team.id] = []
            for slot in range(6):
                number = team_index * 6 + slot
                given, family = GIVEN[number % len(GIVEN)], FAMILY[(number // 2) % len(FAMILY)]
                user = User.objects.create_user(
                    email=f"striker{number + 1:02d}@example.com",
                    password=password,
                    display_name=f"{given} {family}",
                    given_name=given,
                    family_name=family,
                )
                profile = PlayerProfile.objects.create(
                    user=user,
                    first_name=given,
                    last_name=family,
                    date_of_birth=date(today.year - 22 - number % 8, 1 + number % 12, 10),
                    gender_category="men",
                    region="gauteng",
                    visibility=PlayerProfile.Visibility.SCOUTS,
                )
                PlayerSport.objects.create(
                    profile=profile, sport="soccer", primary_position="striker", is_primary=True
                )
                grant_role(user, "player")
                members[team.id].append(
                    (
                        RosterMember.objects.create(
                            participant=team,
                            name=f"{given} {family}",
                            number=9 + slot,
                            position="striker",
                            user=user,
                        ),
                        profile,
                        rng.random(),
                    )
                )
        if coach is not None:
            grant_role(coach, "coach", team=teams[0])

        categories = {
            code: competition.scoring_categories.get(code=code)
            for code in ("goal", "shot", "shot-on-target", "assist")
        }
        pairings = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2)]
        for week, (home_index, away_index) in enumerate(pairings):
            fixture = Fixture.objects.create(
                competition=competition,
                label=f"Week {week + 1}",
                round_number=week + 1,
                status=Fixture.Status.LIVE,
                scheduled_at=timezone.now() - timedelta(days=7 * (len(pairings) - week)),
            )
            for position, team in enumerate((teams[home_index], teams[away_index])):
                side = FixtureSide.objects.create(
                    fixture=fixture, participant=team, position=position, is_home=position == 0
                )
                for member, _profile, talent in members[team.id]:
                    minutes = rng.choice([90, 90, 90, 75, 60, 45, 30])
                    PlayerAppearance.objects.create(fixture=fixture, player=member, minutes=minutes)
                    shots = max(0, int(rng.gauss(1 + 3 * talent, 1)))
                    on_target = min(shots, int(shots * (0.3 + 0.5 * talent)))
                    goals = min(
                        on_target,
                        int(rng.random() < 0.15 + 0.5 * talent) + int(rng.random() < 0.2 * talent),
                    )
                    assists = int(rng.random() < 0.15 + 0.2 * talent)
                    for code, count in (
                        ("shot", shots),
                        ("shot-on-target", on_target),
                        ("goal", goals),
                        ("assist", assists),
                    ):
                        for _ in range(count):
                            ScoreEvent.objects.create(
                                fixture=fixture,
                                side=side,
                                scoring_category=categories[code],
                                player=member,
                                player_name=member.name,
                                minute=rng.randint(1, minutes),
                            )
            fixture.status = Fixture.Status.COMPLETED
            fixture.completed_at = fixture.scheduled_at + timedelta(hours=2)
            fixture.save()
            fixture.recalculate_scores()

        for team in teams:
            for index, (_member, profile, talent) in enumerate(members[team.id]):
                verified = coach is not None and (team == teams[0] or index % 3)
                for months_ago, drift in ((5, Decimal("0.08")), (1, Decimal("0"))):
                    PhysicalTestResult.objects.create(
                        profile=profile,
                        sport="soccer",
                        test_key="sprint_40m",
                        value=Decimal(str(round(5.6 - 0.5 * talent + rng.uniform(-0.05, 0.05), 2)))
                        + drift,
                        unit="s",
                        tested_on=today - timedelta(days=30 * months_ago),
                        venue=f"{team.name} training ground",
                        source=PhysicalTestResult.Source.COACH
                        if verified
                        else PhysicalTestResult.Source.SELF,
                        verified_by=coach if verified else None,
                        recorded_by=coach if verified else profile.user,
                    )
                PhysicalTestResult.objects.create(
                    profile=profile,
                    sport="soccer",
                    test_key="yo_yo_ir1",
                    value=Decimal(int(1400 + 1000 * talent + rng.randint(-80, 80))),
                    unit="m",
                    tested_on=today - timedelta(days=20),
                    venue=f"{team.name} training ground",
                    source=PhysicalTestResult.Source.COACH
                    if verified
                    else PhysicalTestResult.Source.SELF,
                    verified_by=coach if verified else None,
                    recorded_by=coach if verified else profile.user,
                )
        return competition
