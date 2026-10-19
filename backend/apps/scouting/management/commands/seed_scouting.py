"""Demo data for talent scouting: one of every kind of user, and players to find.

Safe to re-run: people are found by email and profiles by user.

    python manage.py seed_profiles   # the 200 fictional people, if not there yet
    python manage.py seed_scouting
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.competitions.models import Competition, Participant
from apps.scouting import catalog
from apps.scouting.models import (
    ConsentRecord,
    GuardianLink,
    HighlightVideo,
    InjuryRecord,
    LeagueScout,
    Measurement,
    Organisation,
    PlayerProfile,
    PlayerSport,
)
from apps.scouting.services import grant_role, record_consent

User = get_user_model()

# One account per scouting role, so every screen can be tried by signing in.
PEOPLE = {
    "scout_admin": ("scoutadmin@example.com", "Lerato", "Mokoena"),
    "scout": ("scout@example.com", "Pieter", "van Wyk"),
    "rival_scout": ("scout.cape@example.com", "Aisha", "Daniels"),
    "coach": ("coach@example.com", "Sam", "Dlamini"),
    "guardian": ("guardian@example.com", "Nomsa", "Khumalo"),
    "junior": ("junior@example.com", "Ayanda", "Khumalo"),
    "junior_pending": ("junior2@example.com", "Lwazi", "Ndlovu"),
    "adult_player": ("player@example.com", "Kagiso", "Rabada"),
}

# Sports for the extra demo players, with how many of each. Keys are catalogue keys.
SPREAD = [
    ("rugby_union", 6),
    ("netball", 5),
    ("basketball", 4),
    ("athletics", 4),
    ("cricket", 4),
    ("volleyball", 2),
    ("swimming", 2),
]


class Command(BaseCommand):
    help = "Seed talent scouting demo data (organisations, roles, player profiles, consent)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--password", default="fairmeasure")

    def handle(self, *args, **options) -> None:
        self.password = options["password"]
        self.rng = random.Random(42)  # noqa: S311 - repeatable demo data, not security
        with transaction.atomic():
            self._seed()
        # Phase 2: existing demo competitions record player stats (assists, tackles, ...).
        call_command("add_player_stat_types", stdout=self.stdout)
        # Phase 3: a league with tagged match stats, minutes and physical tests.
        call_command("seed_scouting_stats", password=self.password, stdout=self.stdout)
        # Phase 4: dated scout ratings, private to each organisation.
        call_command("seed_scout_ratings", stdout=self.stdout)
        # Phase 5: competition levels, a shortlist, a saved search and contact requests.
        call_command("seed_scouting_discovery", stdout=self.stdout)

    def _person(self, key: str):
        email, given, family = PEOPLE[key]
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "display_name": f"{given} {family}",
                "given_name": given,
                "family_name": family,
                "email_verified": True,
            },
        )
        if created:
            user.set_password(self.password)
            user.save(update_fields=["password"])
        return user

    def _seed(self) -> None:
        owner = User.objects.filter(email="owner@example.com").first()

        lions, _ = Organisation.objects.get_or_create(
            name="Highveld Lions Academy",
            defaults={"kind": Organisation.Kind.ACADEMY, "region": "gauteng"},
        )
        cape, _ = Organisation.objects.get_or_create(
            name="Cape Coastal FC",
            defaults={"kind": Organisation.Kind.CLUB, "region": "western-cape"},
        )
        admin = self._person("scout_admin")
        grant_role(admin, "scout_admin", organisation=lions, granted_by=admin)
        grant_role(self._person("scout"), "scout", organisation=lions, granted_by=admin)
        rival = self._person("rival_scout")
        grant_role(rival, "scout_admin", organisation=cape, granted_by=rival)
        if owner:
            grant_role(owner, "scout_admin", organisation=lions, granted_by=admin)

        # Players on real teams, so the coach can verify their measurements.
        teams = list(
            Participant.objects.filter(kind="team", roster__user__isnull=False)
            .distinct()
            .order_by("created_at")[:6]
        )
        coach = self._person("coach")
        if teams:
            grant_role(coach, "coach", team=teams[0], granted_by=coach)

        # The demo leagues with rostered teams are opened to scouts, and the scout
        # follows the first one, so league squads can be tried straight away.
        demo_leagues = [
            league
            for league in Competition.objects.filter(participants__in=teams).distinct()
            if catalog.sport_for_competition(league.sport)
        ]
        Competition.objects.filter(pk__in=[league.pk for league in demo_leagues]).update(
            open_to_scouts=True
        )
        if demo_leagues:
            LeagueScout.objects.get_or_create(
                competition=demo_leagues[0],
                user=self._person("scout"),
                defaults={"organisation": lions, "added_by": admin},
            )
        team_users = []
        for team in teams:
            for member in team.roster.filter(user__isnull=False, is_active=True):
                team_users.append((member.user, member.position))
        made = 0
        for index, (user, roster_position) in enumerate(team_users):
            positions = [item["key"] for item in catalog.SPORTS["soccer"]["positions"]]
            primary = (
                roster_position
                if roster_position in positions
                else positions[index % len(positions)]
            )
            profile, created = self._profile(user, age=self.rng.randint(17, 29), index=index)
            if created:
                self._sport(profile, "soccer", primary)
                self._body(profile, index, verified_by=coach if teams and index < 14 else None)
                made += 1

        # A spread of other sports from the fictional people.
        on_teams = {user.id for user, _ in team_users}
        spare = [
            user
            for user in User.objects.filter(email__endswith="@example.com")
            .exclude(email__in=[row[0] for row in PEOPLE.values()])
            .exclude(email="owner@example.com")
            .order_by("email")
            if user.id not in on_teams
        ]
        cursor = 0
        for sport_key, count in SPREAD:
            positions = [item["key"] for item in catalog.SPORTS[sport_key]["positions"]]
            for offset in range(count):
                if cursor >= len(spare):
                    break
                user = spare[cursor]
                cursor += 1
                profile, created = self._profile(user, age=self.rng.randint(18, 27), index=cursor)
                if created:
                    self._sport(profile, sport_key, positions[offset % len(positions)])
                    self._body(profile, cursor)
                    made += 1

        # A named adult player with a full profile.
        adult = self._person("adult_player")
        profile, created = self._profile(adult, age=21, index=1, visibility="scouts")
        if created:
            self._sport(profile, "cricket", "fast-bowler", ["all-rounder"])
            self._body(profile, 3)
            HighlightVideo.objects.create(
                profile=profile,
                title="Five-wicket haul, provincial final",
                url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            )
            InjuryRecord.objects.create(
                profile=profile, description="Side strain", injured_on=date(2025, 11, 2)
            )

        # A minor whose guardian has consented (visible to scouts).
        guardian = self._person("guardian")
        junior = self._person("junior")
        profile, created = self._profile(junior, age=15, index=2, visibility="scouts")
        if created:
            self._sport(profile, "soccer", "winger", ["striker"])
            self._body(profile, 5)
            link = GuardianLink.objects.create(
                profile=profile,
                guardian=guardian,
                invited_email=guardian.email,
                relationship="Mother",
                status=GuardianLink.Status.ACTIVE,
            )
            grant_role(guardian, "guardian")
            record_consent(
                profile,
                by=link.guardian,
                given_as="guardian",
                action=ConsentRecord.Action.GRANTED,
                visibility="scouts",
                sections=["identity", "sports", "physical", "videos"],
                note="Demo consent",
            )

        # A minor still waiting for a guardian (hidden from everyone else).
        pending = self._person("junior_pending")
        profile, created = self._profile(pending, age=16, index=3, visibility="scouts")
        if created:
            self._sport(profile, "netball", "gs")
            GuardianLink.objects.create(
                profile=profile, invited_email=guardian.email, relationship="Aunt"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Scouting demo ready: {PlayerProfile.objects.count()} player profiles "
                f"({made} new), organisations {lions.name} and {cape.name}. "
                f"Sign in as any of: {', '.join(row[0] for row in PEOPLE.values())} "
                f"(password '{self.password}')."
            )
        )

    def _profile(self, user, *, age: int, index: int, visibility: str | None = None):
        existing = PlayerProfile.objects.filter(user=user).first()
        if existing:
            if not existing.teams.exists():
                self._attach_teams(existing, index)
            return existing, False
        today = date.today()
        born = date(today.year - age, 1 + index % 12, 1 + index % 27)
        profile = PlayerProfile.objects.create(
            user=user,
            first_name=user.given_name or user.display_name.split(" ")[0],
            last_name=user.family_name,
            date_of_birth=born,
            gender_category=catalog.GENDER_CATEGORIES[index % 2]["key"],
            nationality="South African",
            region=catalog.REGIONS[index % 9]["key"],
            bio="Demo player profile.",
            visibility=visibility or ("public" if index % 3 == 0 else "scouts"),
        )
        if not (age < catalog.AGE_OF_CONSENT):
            record_consent(
                profile,
                by=user,
                given_as="player",
                action=ConsentRecord.Action.GRANTED,
                visibility=profile.visibility,
                sections=sorted(catalog.keys(catalog.CONSENT_SECTIONS)),
                note="Demo profile made visible.",
            )
        grant_role(user, "player")
        self._attach_teams(profile, index)
        return profile, True

    @staticmethod
    def _attach_teams(profile, index: int) -> None:
        """Link demo profiles to real competition teams, possibly more than one."""

        from apps.scouting.services import affiliated_teams, school_or_club_label

        sides = list(
            Participant.objects.filter(kind="team", is_active=True).select_related("competition")
        )
        if not sides:
            return
        chosen = [sides[index % len(sides)]]
        if len(sides) > 1:
            extra = sides[(index + 3) % len(sides)]
            if extra.id != chosen[0].id:
                chosen.append(extra)
        profile.teams.set(chosen)
        profile.school_or_club = school_or_club_label(affiliated_teams(profile))
        profile.save(update_fields=["school_or_club"])

    @staticmethod
    def _sport(profile, sport_key: str, primary: str, secondary: list[str] | None = None) -> None:
        PlayerSport.objects.create(
            profile=profile,
            sport=sport_key,
            primary_position=primary,
            secondary_positions=[item for item in (secondary or []) if item != primary],
            is_primary=True,
        )

    def _body(self, profile, index: int, verified_by=None) -> None:
        measured = date.today() - timedelta(days=30 + index)
        height = Decimal(160 + self.rng.randint(0, 35))
        weight = Decimal(55 + self.rng.randint(0, 40))
        source = Measurement.Source.COACH if verified_by else Measurement.Source.SELF
        for kind, value in (("height", height), ("weight", weight)):
            spec = catalog.measurement(kind)
            Measurement.objects.create(
                profile=profile,
                kind=kind,
                value=value,
                unit=spec["unit"],
                measured_on=measured,
                source=source,
                verified_by=verified_by,
                recorded_by=verified_by or profile.user,
            )
        Measurement.objects.create(
            profile=profile,
            kind="dominant_foot",
            text_value=["right", "left", "right", "both"][index % 4],
            measured_on=measured,
            recorded_by=profile.user,
        )
