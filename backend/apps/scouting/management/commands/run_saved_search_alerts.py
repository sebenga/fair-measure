"""Notify scouts of players newly matching their saved searches.

    python manage.py run_saved_search_alerts

The BullMQ worker runs this every 15 minutes (``saved-search-alerts`` on the
``scouting`` queue); the command is for running it by hand.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.scouting.discovery_views import run_saved_search_alerts


class Command(BaseCommand):
    help = "Alert scouts about new matches for their saved searches."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(f"Sent {run_saved_search_alerts()} saved-search alert(s).")
        )
