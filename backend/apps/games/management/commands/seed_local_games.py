"""A local games demo: a school sports day with four houses and points per placing.

    python manage.py seed_local_games

Houses are the "NOCs"; events come from ordinary presets; 1st earns 5 points, 2nd 3
and 3rd 1, feeding a points table alongside the medal table. Safe to re-run.
"""

from __future__ import annotations

from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.games import services
from apps.games.models import NOC, Athlete, Games, GamesOfficial
from apps.results import services as results

User = get_user_model()
NAME = "Fair Measure Primary Sports Day"
HOUSES = [
    ("RED", "Red House", "#dc2626"),
    ("BLU", "Blue House", "#2563eb"),
    ("GRN", "Green House", "#16a34a"),
    ("YLW", "Yellow House", "#ca8a04"),
]
# (event, preset, finishing positions by house; equal numbers are a dead heat)
RACES = [
    ("Egg and spoon race", "athletics_road", {"RED": 1, "BLU": 2, "GRN": 3, "YLW": 4}),
    ("Sack race", "athletics_road", {"BLU": 1, "GRN": 1, "RED": 3, "YLW": 4}),
]


class Command(BaseCommand):
    help = "Seed a school sports day: houses, points per placing and two decided races."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        owner = User.objects.filter(email="owner@example.com").first()
        judge = User.objects.filter(email="delegate@example.com").first()
        if owner is None or judge is None:
            self.stderr.write(
                "Run seed_demo and seed_games first (owner@ and delegate@ are needed)."
            )
            return
        if Games.objects.filter(name=NAME).exists():
            self.stdout.write("The sports day already exists; nothing changed.")
            return
        today = date.today()
        games = Games.objects.create(
            name=NAME,
            kind=Games.Kind.CUSTOM,
            host="Fair Measure Primary",
            starts_on=today,
            ends_on=today,
            owner=owner,
            team_label="House",
            placing_points=[5, 3, 1],
        )
        GamesOfficial.objects.create(games=games, user=judge)
        houses = {
            code: NOC.objects.create(games=games, code=code, name=name, colour=colour)
            for code, name, colour in HOUSES
        }
        for index, (name, preset, places) in enumerate(RACES):
            event = services.add_custom_event(
                games, sport_label="Sports day", name=name, preset_key=preset
            )
            event.venue = "School field"
            event.scheduled_at = timezone.make_aware(datetime.combine(today, time(9 + index, 0)))
            event.save(update_fields=["venue", "scheduled_at", "updated_at"])
            entries = {}
            for code in places:
                athlete = Athlete.objects.create(
                    games=games, noc=houses[code], name=f"{houses[code].name} runner {index + 1}"
                )
                entries[code] = services.add_entry(event, houses[code], athlete)
            fixture = results.create_event(event.competition, label="Final", actor=owner)
            sides = {side.participant_id: side for side in fixture.sides.all()}
            results.save_results(
                fixture,
                [
                    {
                        "side": str(sides[entries[code].participant_id].id),
                        "data": {"position": place},
                    }
                    for code, place in places.items()
                ],
                owner,
            )
            results.finalise(fixture, judge, reason="Finish judged by the teachers")
        later = services.add_custom_event(
            games, sport_label="Sports day", name="Relay", preset_key="athletics_road"
        )
        later.venue = "School field"
        later.scheduled_at = timezone.make_aware(datetime.combine(today, time(14, 0)))
        later.save(update_fields=["venue", "scheduled_at", "updated_at"])
        self.stdout.write(
            self.style.SUCCESS(
                "Sports day ready: 4 houses, 3 events (2 decided), points 5/3/1. "
                "Organiser owner@example.com; judge delegate@example.com."
            )
        )
