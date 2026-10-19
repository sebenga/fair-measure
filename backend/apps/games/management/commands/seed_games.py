"""A small demo Games: 5 NOCs, 6 sports, and two events played through to medals.

    python manage.py seed_games

Safe to re-run: an existing demo Games is left as it is.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.fixtures.models import Fixture, FixtureSide, ScoreEvent
from apps.games import services
from apps.games.models import NOC, Athlete, Games, GamesEvent, GamesOfficial

User = get_user_model()
NAME = "Fair Measure Summer Games 2026"
NOCS = [
    ("RSA", "South Africa", "#007749"),
    ("KEN", "Kenya", "#BB0000"),
    ("BRA", "Brazil", "#009C3B"),
    ("JPN", "Japan", "#BC002D"),
    ("NZL", "New Zealand", "#00247D"),
]
SPORTS = ["football", "basketball", "tennis", "athletics", "golf", "archery"]
SPRINTERS = {
    "RSA": ("Thabo Nkosi", "9.91"),
    "KEN": ("Daniel Kiprop", "9.97"),
    "BRA": ("Lucas Silva", "10.02"),
    "JPN": ("Haruto Sato", "10.05"),
    "NZL": ("Liam Walker", "10.11"),
}


class Command(BaseCommand):
    help = "Seed a demo Games with 5 NOCs and 6 sports."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--password", default="fairmeasure")

    def _person(self, email: str, given: str, family: str):
        person, created = User.objects.get_or_create(
            email=email,
            defaults={
                "display_name": f"{given} {family}",
                "given_name": given,
                "family_name": family,
            },
        )
        if created:
            person.set_password(self.password)
            person.save()
        return person

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        self.password = options["password"]
        owner = User.objects.filter(email="owner@example.com").first() or self._person(
            "owner@example.com", "Olivia", "Owner"
        )
        delegate = self._person("delegate@example.com", "Tumi", "Delegate")
        existing = Games.objects.filter(name=NAME).first()
        if existing is not None:
            added = self._experience(existing, delegate)
            self.stdout.write(
                "The demo Games already exists; "
                + (f"added {added}." if added else "nothing changed.")
            )
            return

        start = date.today()
        games = Games.objects.create(
            name=NAME,
            edition="Demo",
            kind=Games.Kind.SUMMER,
            host="Cape Town",
            starts_on=start,
            ends_on=start + timedelta(days=9),
            owner=owner,
        )
        GamesOfficial.objects.create(games=games, user=delegate)
        nocs = {
            code: NOC.objects.create(games=games, code=code, name=name, colour=colour)
            for code, name, colour in NOCS
        }
        services.add_catalog_events(games, services.keys_for(sports=SPORTS))

        day = 0
        for event in games.events.order_by("display_order"):
            event.scheduled_at = timezone.make_aware(
                datetime.combine(start + timedelta(days=day % 9), time(9 + (day % 8), 0))
            )
            event.venue = (
                "Stadium" if event.sport_key == "athletics" else f"{event.sport_label} venue"
            )
            event.save(update_fields=["scheduled_at", "venue", "updated_at"])
            day += 1

        self._football(games, nocs, delegate)
        self._sprint(games, nocs, delegate)
        self._experience(games, delegate)
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo Games ready: {games.events.count()} events across {len(SPORTS)} sports, "
                f"5 NOCs. Organiser owner@example.com; technical delegate delegate@example.com "
                f"(password '{self.password}')."
            )
        )

    def _football(self, games, nocs, delegate) -> None:
        event = games.events.filter(sport_key="football", gender="men").first()
        if event is None:
            return
        entries = {
            code: services.add_entry(event, nocs[code]) for code in ("RSA", "BRA", "JPN", "KEN")
        }
        goal = event.competition.scoring_categories.get(code="goal")

        def play(round_number, home, away, home_goals, away_goals, label):
            fixture = Fixture.objects.create(
                competition=event.competition,
                round_number=round_number,
                label=label,
                status=Fixture.Status.LIVE,
            )
            sides = [
                FixtureSide.objects.create(
                    fixture=fixture, participant=entries[home].participant, position=0, is_home=True
                ),
                FixtureSide.objects.create(
                    fixture=fixture, participant=entries[away].participant, position=1
                ),
            ]
            for side, goals in zip(sides, (home_goals, away_goals), strict=True):
                for minute in range(goals):
                    ScoreEvent.objects.create(
                        fixture=fixture, side=side, scoring_category=goal, minute=20 + minute * 15
                    )
            fixture.status = Fixture.Status.COMPLETED
            fixture.completed_at = timezone.now()
            fixture.save()
            fixture.recalculate_scores()
            return fixture

        play(1, "RSA", "KEN", 2, 1, "Semi-final 1")
        play(1, "BRA", "JPN", 3, 2, "Semi-final 2")
        bronze = play(None, "KEN", "JPN", 1, 0, "Bronze medal match")
        event.bronze_fixture = bronze
        event.save(update_fields=["bronze_fixture", "updated_at"])
        play(2, "RSA", "BRA", 1, 0, "Final")
        services.sync_medals(
            event, actor=delegate, reason="Medals awarded from the confirmed final"
        )

    def _sprint(self, games, nocs, delegate) -> None:
        event = games.events.filter(sport_key="athletics", name="Men's 100 m").first()
        if event is None:
            return
        from apps.results import services as results

        rows = []
        for code, (name, seconds) in SPRINTERS.items():
            athlete = Athlete.objects.create(games=games, noc=nocs[code], name=name)
            rows.append((services.add_entry(event, nocs[code], athlete), seconds))
        fixture = results.create_event(
            event.competition,
            label="Final",
            participant_ids=[entry.participant_id for entry, _ in rows],
            actor=delegate,
        )
        sides = {side.participant_id: side for side in fixture.sides.all()}
        results.save_results(
            fixture,
            [
                {"side": str(sides[entry.participant_id].id), "data": {"time": seconds}}
                for entry, seconds in rows
            ],
            delegate,
        )
        results.finalise(fixture, delegate, reason="Photo finish reviewed")
        services.sync_medals(
            event, actor=delegate, reason="Medals awarded from the confirmed final"
        )
        GamesEvent.objects.filter(pk=event.pk).update(venue="Stadium")

    def _experience(self, games, delegate) -> str:
        """Qualification, personal bests and a Games record; only what is missing."""

        from apps.games.experience import add_record

        added = []
        sprint = games.events.filter(sport_key="athletics", name="Men's 100 m").first()
        if sprint is None:
            return ""
        if not sprint.qualification_rule:
            sprint.qualification_rule = "First 3 in each heat (Q) and the next 2 fastest (q)"
            sprint.qualification_mark = "10.05"
            sprint.save(update_fields=["qualification_rule", "qualification_mark", "updated_at"])
            added.append("the 100 m qualification rule")
        bests = {"Thabo Nkosi": "9.89", "Daniel Kiprop": "9.94", "Lucas Silva": "10.00"}
        for athlete in Athlete.objects.filter(games=games, name__in=bests, personal_bests=[]):
            athlete.personal_bests = [
                {"event": "100 m", "mark": bests[athlete.name], "date": "2026-05-16"}
            ]
            athlete.save(update_fields=["personal_bests", "updated_at"])
            added.append(f"{athlete.name}'s personal best")
        winner = sprint.medals.filter(medal="gold").select_related("entry__athlete").first()
        if winner and winner.entry.athlete and not sprint.records.exists():
            add_record(
                sprint,
                {
                    "scope": "games",
                    "mark": "9.91",
                    "previous_mark": "9.95",
                    "athlete": str(winner.entry.athlete_id),
                },
                delegate,
            )
            added.append("a Games record")
        return ", ".join(added)
