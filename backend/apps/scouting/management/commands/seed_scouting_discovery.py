"""Scouting Phase 5 demo: competition levels, a shortlist, a saved search and contact requests.

    python manage.py seed_scouting_discovery

Needs seed_scouting, seed_scouting_stats and seed_scout_ratings. Safe to re-run.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.competitions.models import Competition
from apps.scouting import search
from apps.scouting.models import (
    ContactRequest,
    PlayerProfile,
    SavedSearch,
    ScoutingRole,
    Shortlist,
    ShortlistComment,
    ShortlistEntry,
    ShortlistLog,
)
from apps.scouting.services import access_level, is_minor

User = get_user_model()
LEVELS = {"Fair Measure Stats League": "provincial", "Sunday Soccer": "club"}
FAST_STRIKERS = {"sport": "soccer", "tests": [{"key": "sprint_40m", "op": "lt", "value": 5.3}]}


class Command(BaseCommand):
    help = "Seed competition levels, a Lions shortlist, a saved search and contact requests."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        for name, level in LEVELS.items():
            for competition in Competition.objects.filter(name=name):
                settings = dict(competition.settings_json or {})
                if settings.get("level") != level:
                    settings["level"] = level
                    competition.settings_json = settings
                    competition.save(update_fields=["settings_json", "updated_at"])
        scout = User.objects.filter(email="scout@example.com").first()
        admin = User.objects.filter(email="scoutadmin@example.com").first()
        role = (
            ScoutingRole.objects.filter(user=scout, organisation__isnull=False)
            .select_related("organisation")
            .first()
        )
        if scout is None or role is None:
            self.stderr.write(
                "Run seed_scouting first (scout@example.com with an organisation is needed)."
            )
            return
        lions = role.organisation
        strikers = list(
            PlayerProfile.objects.filter(user__email__startswith="striker").order_by("user__email")[
                :4
            ]
        )
        if not strikers:
            self.stderr.write("Run seed_scouting_stats first.")
            return

        shortlist, created = Shortlist.objects.get_or_create(
            organisation=lions,
            name="Stats league strikers",
            defaults={
                "description": "Provincial-level strikers to watch this season",
                "created_by": admin or scout,
            },
        )
        if created:
            plan = [
                ("watching", scout),
                ("trial_booked", admin or scout),
                ("watching", None),
                ("signed", admin or scout),
            ]
            for profile, (status, assignee) in zip(strikers, plan, strict=False):
                entry = ShortlistEntry.objects.create(
                    shortlist=shortlist, profile=profile, status="watching", added_by=scout
                )
                ShortlistLog.objects.create(
                    shortlist=shortlist,
                    profile=profile,
                    actor=scout,
                    action="added",
                    after={"status": "watching"},
                )
                if status != "watching":
                    entry.status = status
                    ShortlistLog.objects.create(
                        shortlist=shortlist,
                        profile=profile,
                        actor=admin or scout,
                        action="status",
                        before={"status": "watching"},
                        after={"status": status},
                    )
                if assignee:
                    entry.assigned_to = assignee
                    ShortlistLog.objects.create(
                        shortlist=shortlist,
                        profile=profile,
                        actor=admin or scout,
                        action="assigned",
                        after={
                            "assigned_to": {"id": str(assignee.id), "name": assignee.display_name}
                        },
                    )
                entry.save()
            comment = ShortlistComment.objects.create(
                entry=shortlist.entries.get(profile=strikers[1]),
                author=admin or scout,
                body="Trial booked for the March camp; bring the video analyst.",
            )
            ShortlistLog.objects.create(
                shortlist=shortlist,
                profile=strikers[1],
                actor=admin or scout,
                action="commented",
                after={"comment": comment.body},
            )

        if not SavedSearch.objects.filter(user=scout, name="Fast strikers").exists():
            SavedSearch.objects.create(
                user=scout,
                organisation=lions,
                name="Fast strikers",
                filters=search.clean(FAST_STRIKERS),
                alerts=True,
                matched_ids=[str(item["profile"].id) for item in search.run(scout, FAST_STRIKERS)],
            )

        target = strikers[2] if len(strikers) > 2 else strikers[0]
        if not ContactRequest.objects.filter(profile=target, organisation=lions).exists():
            ContactRequest.objects.create(
                profile=target,
                organisation=lions,
                requested_by=scout,
                message=(
                    "Highveld Lions Academy would like to invite you to an open trial in "
                    "Johannesburg."
                ),
            )
        junior = PlayerProfile.objects.filter(user__email="junior@example.com").first()
        if (
            junior is not None
            and is_minor(junior)
            and access_level(junior, scout) == "scout"
            and not ContactRequest.objects.filter(profile=junior, organisation=lions).exists()
        ):
            ContactRequest.objects.create(
                profile=junior,
                organisation=lions,
                requested_by=scout,
                message="We would like to invite Ayanda to our U17 development day.",
                to_guardian=True,
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Discovery demo ready: levels set, Lions shortlist, a saved search with alerts and "
                "contact requests. Sign in as scout@example.com (Talent search, Shortlists) or "
                "as a striker or guardian@example.com (Contact requests)."
            )
        )
