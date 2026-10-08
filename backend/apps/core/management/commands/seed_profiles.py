"""Create dummy people so a team can be assembled from real profiles."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

PROFILES = [
    ("lina.mensah@example.com", "Lina Mensah"),
    ("jules.okonkwo@example.com", "Jules Okonkwo"),
    ("priya.shah@example.com", "Priya Shah"),
    ("marco.bianchi@example.com", "Marco Bianchi"),
    ("sofia.alvarez@example.com", "Sofia Alvarez"),
    ("kenji.mori@example.com", "Kenji Mori"),
]


class Command(BaseCommand):
    help = "Create dummy profiles that can be picked when forming a team."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--password",
            default="fairmeasure",
            help="Password for every dummy profile this command creates.",
        )

    def handle(self, *args, **options) -> None:
        password = options["password"]
        created = 0
        for email, display_name in PROFILES:
            user, was_created = User.objects.get_or_create(
                email=email,
                defaults={"display_name": display_name, "email_verified": True},
            )
            if was_created:
                user.set_password(password)
                user.save(update_fields=["password"])
                created += 1
                self.stdout.write(f"  created {display_name} <{email}>")
            elif user.display_name != display_name:
                user.display_name = display_name
                user.save(update_fields=["display_name"])
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{created} new profiles. Sign in as any of them with {password}.\n"
            )
        )
