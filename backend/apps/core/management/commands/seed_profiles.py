"""Create dummy people so a team can be assembled from real profiles."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()

NAMED = [
    ("lina.mensah@example.com", "Lina", "Mensah"),
    ("jules.okonkwo@example.com", "Jules", "Okonkwo"),
    ("priya.shah@example.com", "Priya", "Shah"),
    ("marco.bianchi@example.com", "Marco", "Bianchi"),
    ("sofia.alvarez@example.com", "Sofia", "Alvarez"),
    ("kenji.mori@example.com", "Kenji", "Mori"),
]

GIVEN = [
    "Amina", "Boitumelo", "Chidi", "Dineo", "Elias", "Fatima", "Gustavo", "Hana",
    "Ibrahim", "Jade", "Kofi", "Lerato", "Mateo", "Naledi", "Omar", "Palesa",
    "Quinn", "Rudo", "Sibusiso", "Thandi", "Uma", "Vuyo", "Wanjiku", "Xavier",
    "Yara", "Zanele", "Andre", "Bongi", "Carmen", "David", "Elena", "Farai",
    "Grace", "Hugo", "Ines", "Jabu", "Karabo", "Liam", "Mpho", "Noor",
]

FAMILY = [
    "Adams", "Botha", "Chauke", "Dlamini", "Eze", "Ferreira", "Gumede", "Hassan",
    "Iversen", "Jacobs", "Khumalo", "Lopez", "Mokoena", "Ndlovu", "Owusu", "Patel",
    "Qureshi", "Rossouw", "Sithole", "Tshabalala", "Uys", "Van Wyk", "Williams",
    "Xhaba", "Yilmaz", "Zulu",
]


def generated_profiles(count: int = 200) -> list[tuple[str, str, str]]:
    """Stable fictional people. Re-running the command finds the same emails."""

    rows = list(NAMED)
    index = 0
    while len(rows) < count:
        given = GIVEN[index % len(GIVEN)]
        family = FAMILY[(index // len(GIVEN)) % len(FAMILY)]
        index += 1
        email = f"{given}.{family}.{index}@example.com".lower().replace(" ", "")
        rows.append((email, given, family))
    return rows[:count]


class Command(BaseCommand):
    help = "Create dummy profiles that can be picked when forming a team."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--password",
            default="fairmeasure",
            help="Password for every dummy profile this command creates.",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=200,
            help="How many profiles to ensure exist.",
        )

    def handle(self, *args, **options) -> None:
        password = options["password"]
        count = max(int(options["count"]), 1)
        created = 0
        with transaction.atomic():
            for email, given, family in generated_profiles(count):
                display_name = f"{given} {family}"
                user, was_created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "display_name": display_name,
                        "given_name": given,
                        "family_name": family,
                        "email_verified": True,
                    },
                )
                if was_created:
                    user.set_password(password)
                    user.save(update_fields=["password"])
                    created += 1
                else:
                    changed = []
                    if user.display_name != display_name:
                        user.display_name = display_name
                        changed.append("display_name")
                    if not user.given_name:
                        user.given_name = given
                        changed.append("given_name")
                    if not user.family_name:
                        user.family_name = family
                        changed.append("family_name")
                    if changed:
                        user.save(update_fields=changed)
        total = User.objects.filter(email__in=[row[0] for row in generated_profiles(count)]).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{created} new profiles. {total} test profiles are ready. "
                f"Sign in as any of them with {password}.\n"
            )
        )
