"""Add the stat-only score types to competitions created before they existed.

    python manage.py add_player_stat_types

Each competition gets the stat types its preset now records (assists, tackles,
rebounds and so on). They never change a score, so locked competitions are safe.
Safe to re-run.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.competitions.models import Competition, ScoringCategory
from apps.competitions.stat_types import STAT_SCORE_TYPES


class Command(BaseCommand):
    help = "Add stat-only score types (assists, tackles, ...) to existing competitions."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        updated = added = 0
        for competition in Competition.objects.all():
            settings = dict(competition.settings_json or {})
            rows = STAT_SCORE_TYPES.get(settings.get("preset") or "")
            if not rows:
                continue
            have = set(competition.scoring_categories.values_list("code", flat=True))
            types = list(settings.get("score_types") or [])
            typed = {item.get("key") for item in types}
            order = competition.scoring_categories.count()
            changed = False
            for row in rows:
                if row["key"] not in have:
                    order += 1
                    ScoringCategory.objects.create(
                        competition=competition,
                        code=row["key"],
                        name=row["label"],
                        points=row["value"],
                        affects_score=False,
                        description=row.get("description", ""),
                        display_order=order,
                    )
                    added += 1
                    changed = True
                if row["key"] not in typed:
                    types.append(row)
                    changed = True
            if changed:
                settings["score_types"] = types
                competition.settings_json = settings
                competition.save(update_fields=["settings_json", "updated_at"])
                updated += 1
        self.stdout.write(
            self.style.SUCCESS(f"Added {added} stat type(s) across {updated} competition(s).")
        )
