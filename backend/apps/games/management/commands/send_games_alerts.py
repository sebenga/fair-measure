"""Send start-time alerts to followers of every session starting soon.

    python manage.py send_games_alerts --minutes 30

Run it every few minutes (cron or a scheduler). Each follower is alerted once per
session; result alerts go out by themselves when medals are confirmed.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.games.experience import send_start_alerts


class Command(BaseCommand):
    help = "Alert followers of Games sessions that start within the next N minutes."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=30)

    def handle(self, *args, **options):
        sent = send_start_alerts(minutes=options["minutes"])
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} start-time alert(s)."))
