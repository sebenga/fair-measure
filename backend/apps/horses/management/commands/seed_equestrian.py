"""Demo data for the performance-results engine: horses, officials, and one demo
competition per result type, each with a provisional event ready to finalise.

The demo settings are written inline because the locked sport presets arrive
later; they exercise the same engine those presets will use. Safe to re-run.

    python manage.py seed_equestrian
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.competitions.models import Competition, Membership, PointsPolicy
from apps.core.permissions import Role
from apps.horses.models import Combination, Horse
from apps.results import services
from apps.results.models import CompetitionOfficial

User = get_user_model()

HORSES = [
    ("Bold Venture", "Thoroughbred", "gelding", "Bay"),
    ("Copper Sky", "Thoroughbred", "mare", "Chestnut"),
    ("Dune Runner", "Arabian", "gelding", "Grey"),
    ("Echo Point", "Warmblood", "stallion", "Black"),
    ("Fynbos Flyer", "Boerperd", "mare", "Bay"),
    ("Karoo Mist", "Arabian", "mare", "Grey"),
]
RIDERS = ["Ava Mokoena", "Ben Pretorius", "Cara Naidoo", "Dan Botha", "Esi Dlamini", "Finn Jacobs"]
TRAINERS = ["Pat Steyn", "Pat Steyn", "Lee Khumalo", "Lee Khumalo", "Sam Fourie", "Sam Fourie"]

STATUSES = [
    {"code": "EL", "label": "Eliminated"},
    {"code": "RT", "label": "Retired"},
    {"code": "WD", "label": "Withdrawn"},
    {"code": "DNF", "label": "Did not finish"},
    {"code": "DQ", "label": "Disqualified"},
]

DEMOS = {
    "finishing_order": {
        "name": "Engine demo · Finishing order",
        "config": {"record_fields": ["margin", "time"]},
        "statuses": [
            {"code": "PU", "label": "Pulled up"},
            {"code": "F", "label": "Fell"},
            {"code": "UR", "label": "Unseated rider"},
            *STATUSES,
        ],
        "data": [
            {"position": 1, "margin": "", "time": "71.42"},
            {"position": 2, "margin": "1¼"},
            {"position": 2, "margin": "dead heat"},
            {"position": 4, "margin": "neck"},
            {"position": 5, "margin": "3"},
            {"status": "PU"},
        ],
    },
    "faults_then_time": {
        "name": "Engine demo · Faults then time",
        "config": {
            "rounds": [
                {"key": "round", "label": "Round 1"},
                {"key": "jump_off", "label": "Jump-off", "decides": "first"},
            ],
            "penalties": [
                {"key": "knockdown", "label": "Knock-down", "faults": 4},
                {"key": "refusal", "label": "Refusal", "faults": 4, "eliminate_at": 2},
                {"key": "fall", "label": "Fall", "eliminate_at": 1},
            ],
            "time": {"penalty": 1, "per_seconds": 4, "commenced": True, "limit_factor": 2},
            "time_allowed": {"round": 72, "jump_off": 46},
        },
        "data": [
            {"rounds": {"round": {"time": "70.2"}, "jump_off": {"time": "41.8"}}},
            {"rounds": {"round": {"time": "68.9"}, "jump_off": {"knockdown": 1, "time": "39.5"}}},
            {"rounds": {"round": {"knockdown": 1, "time": "66.0"}}},
            {"rounds": {"round": {"time": "75.3"}}},
            {"rounds": {"round": {"refusal": 2, "time": "80"}}},
            {"rounds": {"round": {"knockdown": 2, "time": "69.4"}}},
        ],
    },
    "penalty_total_lowest": {
        "name": "Engine demo · Penalty total",
        "config": {
            "phases": [
                {"key": "test", "label": "Test", "input": "percentage", "from_percentage": 100},
                {
                    "key": "course",
                    "label": "Course",
                    "penalties": [
                        {
                            "key": "refusals",
                            "label": "Refusals",
                            "per_obstacle": True,
                            "scale": [20, 40],
                            "eliminate_at": 3,
                        },
                        {"key": "fall", "label": "Fall", "eliminate_at": 1},
                    ],
                    "time": {"penalty": "0.4", "per_seconds": 1},
                },
                {
                    "key": "final",
                    "label": "Final round",
                    "penalties": [{"key": "knockdown", "label": "Knock-down", "faults": 4}],
                    "time": {"penalty": "0.4", "per_seconds": 1},
                },
            ],
            "inspections": [
                {"key": "first", "label": "First inspection"},
                {"key": "second", "label": "Second inspection"},
            ],
            "time_allowed": {"course": 360, "final": 82},
            "tiebreakers": ["phase:course", "phase_time:course", "phase:final", "phase:test"],
        },
        "data": [
            {
                "phases": {
                    "test": {"percentage": "72.5"},
                    "course": {"time": 355},
                    "final": {"time": 80},
                }
            },
            {
                "phases": {
                    "test": {"percentage": "70.1"},
                    "course": {"time": 362},
                    "final": {"knockdown": 1, "time": 81},
                }
            },
            {
                "phases": {
                    "test": {"percentage": "68.0"},
                    "course": {"refusals": {"6": 1}, "time": 350},
                    "final": {"time": 79},
                }
            },
            {
                "phases": {
                    "test": {"percentage": "74.0"},
                    "course": {"time": 370},
                    "final": {"time": 84},
                }
            },
            {"inspections": {"first": "fail"}},
            {
                "phases": {
                    "test": {"percentage": "66.5"},
                    "course": {"refusals": {"9": 3}, "time": 380},
                    "final": {"time": 80},
                }
            },
        ],
    },
    "judged_percentage": {
        "name": "Engine demo · Judged percentage",
        "config": {
            "sheet": [
                {"key": "m1", "label": "Entry and halt", "coefficient": 1},
                {"key": "m2", "label": "Working trot", "coefficient": 1},
                {"key": "m3", "label": "Half-pass", "coefficient": 2},
                {"key": "m4", "label": "Extended canter", "coefficient": 1},
                {"key": "c1", "label": "Rider position", "coefficient": 2, "collective": True},
            ],
            "max_mark": 10,
            "mark_step": "0.5",
            "decimals": 3,
            "errors": {"deduct_points": [2], "eliminate_at": 2},
            "judges": ["C", "E", "B"],
        },
        "data": "marks",
    },
    "timed_with_vet_gates": {
        "name": "Engine demo · Timed with vet gates",
        "statuses": [{"code": "FTQ", "label": "Failed to qualify"}, *STATUSES],
        "config": {
            "loops": [
                {"key": "l1", "label": "Gate 1", "distance_km": 32},
                {"key": "l2", "label": "Gate 2", "distance_km": 28},
                {"key": "l3", "label": "Finish", "distance_km": 20},
            ],
            "heart_rate_max": 64,
        },
        "data": "loops",
    },
    "points_per_run": {
        "name": "Engine demo · Points per run",
        "config": {
            "outcomes": [
                {"key": "carried", "label": "Carried", "points": 6},
                {"key": "drawn", "label": "Drawn", "points": 4},
                {"key": "strike", "label": "Strike", "points": 2},
                {"key": "miss", "label": "Miss", "points": 0},
            ],
            "time_limit_seconds": "6.4",
            "runs": 3,
        },
        "data": [
            {
                "runs": [
                    {"outcome": "carried", "time": 6.1},
                    {"outcome": "carried", "time": 6.2},
                    {"outcome": "drawn", "time": 6.0},
                ]
            },
            {
                "runs": [
                    {"outcome": "carried", "time": 6.3},
                    {"outcome": "drawn", "time": 6.0},
                    {"outcome": "carried", "time": 6.1},
                ]
            },
            {
                "runs": [
                    {"outcome": "strike", "time": 6.0},
                    {"outcome": "carried", "time": 6.9},
                    {"outcome": "drawn", "time": 6.2},
                ]
            },
            {
                "runs": [
                    {"outcome": "miss", "time": 6.0},
                    {"outcome": "strike", "time": 6.1},
                    {"outcome": "strike", "time": 6.3},
                ]
            },
            {
                "runs": [
                    {"outcome": "drawn", "time": 6.2},
                    {"outcome": "drawn", "time": 6.2},
                    {"outcome": "drawn", "time": 6.3},
                ]
            },
            {"status": "WD"},
        ],
    },
}


def _marks(index: int) -> dict:
    base = 7.5 - index * 0.5
    marks = {}
    for judge, shift in (("C", 0), ("E", 0.5), ("B", -0.5)):
        value = max(0, min(10, base + shift))
        marks[judge] = dict.fromkeys(("m1", "m2", "m3", "m4", "c1"), value)
    data = {"marks": marks}
    if index == 4:
        data["errors"] = 1
    if index == 5:
        return {"errors": 2}
    return data


def _loops(index: int) -> dict:
    if index == 4:
        return {"loops": [{"ride_seconds": 5900, "heart_rate": 71, "sound": True}]}
    if index == 5:
        return {
            "loops": [
                {"ride_seconds": 6000, "heart_rate": 58, "sound": True},
                {"ride_seconds": 5600, "heart_rate": 60, "sound": False},
            ]
        }
    return {
        "loops": [
            {
                "ride_seconds": 5800 + index * 60,
                "hold_seconds": 2400,
                "heart_rate": 58,
                "sound": True,
            },
            {
                "ride_seconds": 5100 + index * 45,
                "hold_seconds": 2400,
                "heart_rate": 60,
                "sound": True,
            },
            {"ride_seconds": 3600 + index * 30, "heart_rate": 55, "sound": True},
        ],
        "final_inspection": {"result": "pass"},
    }


class Command(BaseCommand):
    help = "Seed horses, officials and one demo competition per performance result type."

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
        steward = self._person("steward@example.com", "Sipho", "Steward")
        judge = self._person("judge@example.com", "Jana", "Judge")

        horses = []
        for index, (name, breed, sex, colour) in enumerate(HORSES):
            horse, _ = Horse.objects.get_or_create(
                registration_number=f"DEMO-{index + 1:03d}",
                defaults={
                    "name": name,
                    "breed": breed,
                    "sex": sex,
                    "colour": colour,
                    "trainer_name": TRAINERS[index],
                    "owner_names": "Demo Stables",
                    "created_by": owner,
                },
            )
            horse.owners.add(owner)
            horses.append(horse)

        made = 0
        for result_type, demo in DEMOS.items():
            competition, created = Competition.objects.get_or_create(
                name=demo["name"],
                owner=owner,
                defaults={"status": Competition.Status.ACTIVE},
            )
            competition.settings_json = {
                **(competition.settings_json or {}),
                "result_type": result_type,
                "result_config": demo["config"],
                "statuses": demo.get("statuses") or STATUSES,
                "official_results": True,
                "participant_type": "combination",
                "contest_type": "accumulation",
                "placing_points": [10, 8, 6, 5, 4, 3],
                "governing_body": "Engine demo: each locked preset names its own governing body",
                "rulebook": "Demo settings, not a real rulebook",
                "description": "A demo of the results engine. Not a sport preset.",
                "locked": True,
                "scoring_locked": True,
            }
            competition.status = Competition.Status.ACTIVE
            competition.save()
            Membership.objects.get_or_create(
                competition=competition, user=owner, defaults={"role": Role.OWNER}
            )
            policy, _ = PointsPolicy.objects.get_or_create(competition=competition)
            policy.tiebreakers = ["points", "placings", "name"]
            policy.save()
            for person, title in ((steward, "steward"), (judge, "judge")):
                CompetitionOfficial.objects.get_or_create(
                    competition=competition,
                    user=person,
                    title=title,
                    defaults={"appointed_by": owner},
                )
            if not created and competition.fixtures.exists():
                continue
            for index, horse in enumerate(horses):
                participant, _ = competition.participants.get_or_create(
                    name=f"{horse.name} / {RIDERS[index]}", defaults={"kind": "individual"}
                )
                Combination.objects.get_or_create(
                    participant=participant,
                    defaults={
                        "horse": horse,
                        "rider_name": RIDERS[index],
                        "trainer_name": TRAINERS[index],
                    },
                )
            fixture = services.create_event(competition, label="Event 1", actor=owner)
            sides = list(fixture.sides.select_related("participant").order_by("position"))
            rows = []
            for index, side in enumerate(sides):
                if demo["data"] == "marks":
                    data = _marks(index)
                elif demo["data"] == "loops":
                    data = _loops(index)
                else:
                    data = demo["data"][index]
                rows.append({"side": str(side.id), "data": data})
            services.save_results(fixture, rows, owner)
            made += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Equestrian engine demo ready: {len(horses)} horses, "
                f"{made} new demo competitions. Officials: steward@example.com and "
                f"judge@example.com (password '{self.password}'). Each demo has a "
                "provisional event for an official to finalise."
            )
        )
