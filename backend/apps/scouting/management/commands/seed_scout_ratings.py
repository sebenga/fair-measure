"""Scouting Phase 4 demo: dated scout ratings of the stats-league strikers.

    python manage.py seed_scout_ratings

Lions Academy scouts (scout@ and scoutadmin@example.com) rate five strikers over
three months in quick and full mode with different confidence; Cape Coastal
(scout.cape@) rates two of the same players, which Lions scouts never see.
Needs seed_scouting and seed_scouting_stats. Safe to re-run.
"""

from __future__ import annotations

import random
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.scouting import catalog
from apps.scouting.models import PlayerProfile, ScoutingRole, ScoutRating

User = get_user_model()
NOTES = [
    "Sharp movement in the box; finishes early.",
    "Good first touch, needs to press from the front more.",
    "Strong in the air. Faded after the hour.",
    "Quick over 10 m, decision making under pressure still raw.",
    "Leads the line well; vocal with teammates.",
]


class Command(BaseCommand):
    help = "Seed dated scout ratings for the stats-league strikers."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        strikers = list(
            PlayerProfile.objects.filter(user__email__startswith="striker").order_by("user__email")[
                :5
            ]
        )
        if not strikers:
            self.stderr.write("Run seed_scouting_stats first.")
            return
        if ScoutRating.objects.filter(profile__in=strikers).exists():
            self.stdout.write("Scout ratings already exist; nothing changed.")
            return
        rng = random.Random(11)  # noqa: S311 - repeatable demo data, not security
        raters = []
        for email in ("scout@example.com", "scoutadmin@example.com", "scout.cape@example.com"):
            user = User.objects.filter(email=email).first()
            role = (
                ScoutingRole.objects.filter(user=user, organisation__isnull=False)
                .select_related("organisation")
                .first()
                if user
                else None
            )
            if role:
                raters.append((user, role.organisation))
        attributes = [
            row["key"]
            for row in catalog.attributes_for("soccer")
            if not row.get("applies_to_positions")
        ]
        created = 0
        now = timezone.now()
        for index, profile in enumerate(strikers):
            talent = 5 + index % 4
            for rater_index, (user, organisation) in enumerate(raters):
                if rater_index == 2 and index > 1:
                    continue  # the rival club only looked at two players
                for visit, days_ago in enumerate((90, 30)):
                    growth = visit  # players improve between visits
                    full = (index + rater_index + visit) % 2 == 1
                    area_scores = {}
                    attribute_scores = {}
                    if full:
                        for key in rng.sample(attributes, 9):  # scouts skip what they did not see
                            attribute_scores[key] = max(
                                1, min(10, talent + growth + rng.randint(-2, 2))
                            )
                    else:
                        for area in ("physical", "technical", "tactical", "mental", "context"):
                            area_scores[area] = max(
                                1, min(10, talent + growth + rng.randint(-1, 2))
                            )
                    ScoutRating.objects.create(
                        client_id=uuid.uuid4(),
                        profile=profile,
                        scout=user,
                        organisation=organisation,
                        sport="soccer",
                        position="striker",
                        mode="full" if full else "quick",
                        watched="live" if visit else "video",
                        confidence=("low", "medium", "high")[(index + visit + rater_index) % 3],
                        area_scores=area_scores,
                        attribute_scores=attribute_scores,
                        current_ability=max(1, min(10, talent + growth)),
                        potential=max(1, min(10, talent + 2)),
                        recommendation=("monitor", "trial", "sign", "trial")[(index + visit) % 4],
                        notes=NOTES[(index + rater_index + visit) % len(NOTES)],
                        observed_at=now - timedelta(days=days_ago, hours=rater_index),
                    )
                    created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created} scout ratings of {len(strikers)} strikers. Sign in as "
                "scout@example.com and open a striker's Ratings tab, or Rate a player."
            )
        )
