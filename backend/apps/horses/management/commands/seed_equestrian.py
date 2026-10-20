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
from apps.competitions.presets import apply_preset
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

    def _jumping(self, owner, judge, horses) -> int:
        """A jump-off class: one finalised show with a jump-off and an elimination."""

        competition, created = Competition.objects.get_or_create(
            name="Highveld Jumping Series",
            owner=owner,
            defaults={"status": Competition.Status.ACTIVE, "sport": "show jumping"},
        )
        if not created and competition.fixtures.exists():
            return 0
        apply_preset(competition, "show_jumping")
        competition.status = Competition.Status.ACTIVE
        competition.save(update_fields=["status", "updated_at"])
        Membership.objects.get_or_create(
            competition=competition, user=owner, defaults={"role": Role.OWNER}
        )
        CompetitionOfficial.objects.get_or_create(
            competition=competition, user=judge, title="ground_jury", defaults={"appointed_by": owner}
        )
        for index, horse in enumerate(horses[:5]):
            participant, _ = competition.participants.get_or_create(
                name=f"{horse.name} / {RIDERS[index]}", defaults={"kind": "individual"}
            )
            Combination.objects.get_or_create(
                participant=participant,
                defaults={"horse": horse, "rider_name": RIDERS[index], "trainer_name": TRAINERS[index]},
            )
        fixture = services.create_event(competition, label="Show 1 · 1.30 m", actor=judge)
        sheets = [
            {"round": {"time": "68.4"}, "jump_off": {"time": "39.1"}},
            {"round": {"time": "70.9"}, "jump_off": {"knockdown": 1, "time": "37.6"}},
            {"round": {"knockdown": 1, "time": "64.2"}},
            {"round": {"refusal": 1, "time": "75.3"}},
            {"round": {"refusal": 2, "time": "58.0"}},
        ]
        rows = [
            {"side": str(side.id), "data": {"rounds": sheets[index]}}
            for index, side in enumerate(fixture.sides.order_by("position"))
        ]
        services.save_results(
            fixture, rows, judge, config={"time_allowed": {"round": 72, "jump_off": 45}}
        )
        services.finalise(fixture, judge, reason="Ground jury confirmed the class")
        return 1

    def _dressage(self, owner, judge, horses) -> int:
        """A Prix St-Georges class with five judges, one error of course and a vet elimination."""

        competition, created = Competition.objects.get_or_create(
            name="Cape Dressage Championship",
            owner=owner,
            defaults={"status": Competition.Status.ACTIVE, "sport": "dressage"},
        )
        if not created and competition.fixtures.exists():
            return 0
        apply_preset(competition, "dressage")
        competition.status = Competition.Status.ACTIVE
        competition.save(update_fields=["status", "updated_at"])
        Membership.objects.get_or_create(
            competition=competition, user=owner, defaults={"role": Role.OWNER}
        )
        CompetitionOfficial.objects.get_or_create(
            competition=competition, user=judge, title="ground_jury", defaults={"appointed_by": owner}
        )
        for index, horse in enumerate(horses[:4]):
            participant, _ = competition.participants.get_or_create(
                name=f"{horse.name} / {RIDERS[index]}", defaults={"kind": "individual"}
            )
            Combination.objects.get_or_create(
                participant=participant,
                defaults={"horse": horse, "rider_name": RIDERS[index], "trainer_name": TRAINERS[index]},
            )
        fixture = services.create_event(competition, label="Prix St-Georges", actor=judge)
        services.save_results(fixture, [], judge, config={"test": "prix_st_georges"})
        config = services.sheet_config(fixture)
        sides = list(fixture.sides.order_by("position"))
        rows = []
        for index, side in enumerate(sides[:3]):
            marks = {}
            for shift, position in enumerate(config["judges"]):
                base = 7.5 - index * 0.5 + (0.5 if shift % 2 else 0)
                marks[position] = {item["key"]: base for item in config["sheet"]}
            data = {"marks": marks}
            if index == 1:
                data["errors"] = 1
            rows.append({"side": str(side.id), "data": data})
        services.save_results(fixture, rows, judge)
        services.set_status(
            fixture, sides[3].id, "EL", judge, reason="Lameness before the final halt", welfare=True
        )
        services.finalise(fixture, judge, reason="Ground jury confirmed the class")
        return 1

    def _eventing(self, owner, judge, horses) -> int:
        """A horse trial: three phases, a refusal, a failed inspection and a cross-country fall."""

        competition, created = Competition.objects.get_or_create(
            name="Midlands Horse Trials",
            owner=owner,
            defaults={"status": Competition.Status.ACTIVE, "sport": "eventing"},
        )
        if not created and competition.fixtures.exists():
            return 0
        apply_preset(competition, "eventing")
        competition.status = Competition.Status.ACTIVE
        competition.save(update_fields=["status", "updated_at"])
        Membership.objects.get_or_create(
            competition=competition, user=owner, defaults={"role": Role.OWNER}
        )
        CompetitionOfficial.objects.get_or_create(
            competition=competition, user=judge, title="ground_jury", defaults={"appointed_by": owner}
        )
        for index, horse in enumerate(horses[:5]):
            participant, _ = competition.participants.get_or_create(
                name=f"{horse.name} / {RIDERS[index]}", defaults={"kind": "individual"}
            )
            Combination.objects.get_or_create(
                participant=participant,
                defaults={"horse": horse, "rider_name": RIDERS[index], "trainer_name": TRAINERS[index]},
            )
        fixture = services.create_event(competition, label="CCI2*-S", actor=judge)
        passed = {"before_cross_country": "pass", "before_jumping": "pass"}
        runs = [
            {"inspections": passed, "phases": {"dressage": {"percentage": "71.2"}, "cross_country": {"time": 352}, "jumping": {"time": 79}}},
            {"inspections": passed, "phases": {"dressage": {"percentage": "74.6"}, "cross_country": {"time": 371}, "jumping": {"knockdown": 1, "time": 80}}},
            {"inspections": passed, "phases": {"dressage": {"percentage": "69.0"}, "cross_country": {"refusals": {"8": 1}, "time": 349}, "jumping": {"time": 77}}},
            {"inspections": {"before_cross_country": "pass", "before_jumping": "fail"}, "phases": {"dressage": {"percentage": "72.4"}, "cross_country": {"time": 358}}},
            {"inspections": {"before_cross_country": "pass"}, "phases": {"dressage": {"percentage": "66.8"}, "cross_country": {"horse_fall": 1, "time": 210}}},
        ]
        rows = [
            {"side": str(side.id), "data": runs[index]}
            for index, side in enumerate(fixture.sides.order_by("position"))
        ]
        services.save_results(
            fixture, rows, judge, config={"time_allowed": {"cross_country": 360, "jumping": 80}}
        )
        services.finalise(fixture, judge, reason="Ground jury confirmed the results")
        return 1

    def _endurance(self, owner, judge, horses) -> int:
        """An 80 km ride: three finishers with Best Condition marks, an FTQ and a late presentation."""

        competition, created = Competition.objects.get_or_create(
            name="Karoo Endurance Ride",
            owner=owner,
            defaults={"status": Competition.Status.ACTIVE, "sport": "endurance"},
        )
        if not created and competition.fixtures.exists():
            return 0
        apply_preset(competition, "endurance")
        competition.status = Competition.Status.ACTIVE
        competition.save(update_fields=["status", "updated_at"])
        Membership.objects.get_or_create(
            competition=competition, user=owner, defaults={"role": Role.OWNER}
        )
        CompetitionOfficial.objects.get_or_create(
            competition=competition, user=judge, title="vet", defaults={"appointed_by": owner}
        )
        for index, horse in enumerate(horses[:5]):
            participant, _ = competition.participants.get_or_create(
                name=f"{horse.name} / {RIDERS[index]}", defaults={"kind": "individual"}
            )
            Combination.objects.get_or_create(
                participant=participant,
                defaults={"horse": horse, "rider_name": RIDERS[index], "trainer_name": TRAINERS[index]},
            )
        fixture = services.create_event(competition, label="80 km CEI 1*", actor=judge)

        def gate(seconds, heart_rate=58, present=420, **extra):
            return {
                "ride_seconds": seconds,
                "hold_seconds": 2400,
                "heart_rate": heart_rate,
                "sound": True,
                "presentation_seconds": present,
                **extra,
            }

        bc = {"recovery": 8, "hydration": 9, "lesions": 10, "soundness": 9, "movement": 8}
        rides = [
            {"loops": [gate(4200), gate(4300), gate(3000)], "final_inspection": {"result": "pass"},
             "best_condition": {"marks": {**bc, "recovery": 7}, "weight_kg": 68}},
            {"loops": [gate(4300), gate(4350), gate(3100)], "final_inspection": {"result": "pass"},
             "best_condition": {"marks": bc, "weight_kg": 82}},
            {"loops": [gate(4500), gate(4600), gate(3300)], "final_inspection": {"result": "pass"},
             "best_condition": {"marks": {**bc, "hydration": 7}, "weight_kg": 75}},
            {"loops": [gate(4100), gate(4200, ftq_code="GA")]},
            {"loops": [gate(4400, present=1020)]},
        ]
        rows = [
            {"side": str(side.id), "data": rides[index]}
            for index, side in enumerate(fixture.sides.order_by("position"))
        ]
        services.save_results(fixture, rows, judge, config={"test": "cei1_80"})
        services.finalise(fixture, judge, reason="Vet commission confirmed")
        return 1

    def _horseball(self, owner, referee) -> int:
        """A horseball league with one match played and one to come."""

        from apps.competitions.models import Participant, RosterMember
        from apps.fixtures.models import Fixture, FixtureReferee, FixtureSide, ScoreEvent

        competition, created = Competition.objects.get_or_create(
            name="Gauteng Horseball League",
            owner=owner,
            defaults={"status": Competition.Status.ACTIVE, "sport": "horseball"},
        )
        if not created and competition.fixtures.exists():
            return 0
        apply_preset(competition, "horseball")
        competition.status = Competition.Status.ACTIVE
        competition.save(update_fields=["status", "updated_at"])
        Membership.objects.get_or_create(
            competition=competition, user=owner, defaults={"role": Role.OWNER}
        )
        CompetitionOfficial.objects.get_or_create(
            competition=competition, user=referee, title="umpire", defaults={"appointed_by": owner}
        )
        teams = []
        for name, players in (
            ("Highveld Riders", ["Ava Mokoena", "Ben Pretorius", "Cara Naidoo", "Dan Botha"]),
            ("Coastal Chargers", ["Esi Dlamini", "Finn Jacobs", "Gia Steyn", "Hugo Khumalo"]),
        ):
            team, _ = Participant.objects.get_or_create(
                competition=competition, name=name, defaults={"kind": Participant.Kind.TEAM}
            )
            for number, player in enumerate(players, start=1):
                RosterMember.objects.get_or_create(participant=team, name=player, defaults={"number": number})
            teams.append(team)
        goal = competition.scoring_categories.get(code="goal")
        played = Fixture.objects.create(competition=competition, label="Round 1", status=Fixture.Status.LIVE)
        home = FixtureSide.objects.create(fixture=played, participant=teams[0], position=0, is_home=True)
        away = FixtureSide.objects.create(fixture=played, participant=teams[1], position=1)
        FixtureReferee.objects.create(fixture=played, user=referee)
        for unit, side, team, number in ((0, home, teams[0], 1), (0, away, teams[1], 2), (1, home, teams[0], 3), (1, home, teams[0], 1)):
            player = team.roster.get(number=number)
            ScoreEvent.objects.create(
                fixture=played, side=side, scoring_category=goal, unit_index=unit,
                player=player, player_name=player.name, recorded_by=referee,
            )
        played.recalculate_scores()
        played.status = Fixture.Status.COMPLETED
        played.save(update_fields=["status", "updated_at"])
        upcoming = Fixture.objects.create(competition=competition, label="Round 2")
        FixtureSide.objects.create(fixture=upcoming, participant=teams[1], position=0, is_home=True)
        FixtureSide.objects.create(fixture=upcoming, participant=teams[0], position=1)
        FixtureReferee.objects.create(fixture=upcoming, user=referee)
        from apps.standings.services import refresh_standings

        refresh_standings(competition)
        return 1

    def _tent_pegging(self, owner, judge, horses) -> int:
        """A lance event decided by a run-off between two riders level on points."""

        competition, created = Competition.objects.get_or_create(
            name="Tent Pegging Nationals",
            owner=owner,
            defaults={"status": Competition.Status.ACTIVE, "sport": "tent pegging"},
        )
        if not created and competition.fixtures.exists():
            return 0
        apply_preset(competition, "tent_pegging")
        competition.status = Competition.Status.ACTIVE
        competition.save(update_fields=["status", "updated_at"])
        Membership.objects.get_or_create(
            competition=competition, user=owner, defaults={"role": Role.OWNER}
        )
        CompetitionOfficial.objects.get_or_create(
            competition=competition, user=judge, title="judge", defaults={"appointed_by": owner}
        )
        for index, horse in enumerate(horses[:4]):
            participant, _ = competition.participants.get_or_create(
                name=f"{horse.name} / {RIDERS[index]}", defaults={"kind": "individual"}
            )
            Combination.objects.get_or_create(
                participant=participant,
                defaults={"horse": horse, "rider_name": RIDERS[index], "trainer_name": TRAINERS[index]},
            )
        fixture = services.create_event(competition, label="Individual lance", actor=judge)

        def runs(*pairs):
            return [{"outcome": outcome, "time": time} for outcome, time in pairs]

        sheets = [
            {"runs": runs(("carried", 6.1), ("carried", 6.3), ("drawn", 6.0)), "run_off": runs(("carried", 6.2))},
            {"runs": runs(("carried", 6.0), ("drawn", 6.2), ("carried", 6.3)), "run_off": runs(("strike", 6.1))},
            {"runs": runs(("carried", 6.6), ("carried", 6.2), ("strike", 6.0))},
            {"runs": runs(("miss", 6.0), ("drawn", 6.1), ("strike", 6.3))},
        ]
        rows = [
            {"side": str(side.id), "data": sheets[index]}
            for index, side in enumerate(fixture.sides.order_by("position"))
        ]
        services.save_results(fixture, rows, judge, config={"test": "lance"})
        services.finalise(fixture, judge, reason="Judges confirmed the event")
        return 1

    def _polo(self, owner, umpire) -> int:
        """A handicap polo league: two rostered teams, one played match, one to play."""

        from apps.competitions.models import Participant, RosterMember
        from apps.fixtures.models import Fixture, FixtureAward, FixtureReferee, FixtureSide, ScoreEvent

        competition, created = Competition.objects.get_or_create(
            name="Plettenberg Bay Polo Cup",
            owner=owner,
            defaults={"status": Competition.Status.ACTIVE, "sport": "polo"},
        )
        if not created and competition.fixtures.exists():
            return 0
        apply_preset(competition, "polo_handicap", unit_count=4)
        competition.status = Competition.Status.ACTIVE
        competition.save(update_fields=["status", "updated_at"])
        Membership.objects.get_or_create(
            competition=competition, user=owner, defaults={"role": Role.OWNER}
        )
        CompetitionOfficial.objects.get_or_create(
            competition=competition, user=umpire, title="umpire", defaults={"appointed_by": owner}
        )
        teams = []
        for name, players in (
            ("Kurland", [("Ava Mokoena", 4), ("Ben Pretorius", 3), ("Cara Naidoo", 2), ("Dan Botha", 1)]),
            ("Inanda", [("Esi Dlamini", 2), ("Finn Jacobs", 1), ("Gia Steyn", 1), ("Hugo Khumalo", 0)]),
        ):
            team, _ = Participant.objects.get_or_create(
                competition=competition, name=name, defaults={"kind": Participant.Kind.TEAM}
            )
            for number, (player, handicap) in enumerate(players, start=1):
                RosterMember.objects.get_or_create(
                    participant=team,
                    name=player,
                    defaults={"number": number, "handicap": handicap},
                )
            teams.append(team)

        goal = competition.scoring_categories.get(code="goal")
        penalty_one = competition.scoring_categories.get(code="penalty-1")
        played = Fixture.objects.create(
            competition=competition, label="Round 1", status=Fixture.Status.LIVE
        )
        home = FixtureSide.objects.create(fixture=played, participant=teams[0], position=0, is_home=True)
        away = FixtureSide.objects.create(fixture=played, participant=teams[1], position=1)
        FixtureReferee.objects.create(fixture=played, user=umpire)
        star = teams[0].roster.get(number=1)
        for unit, side, category, player in (
            (0, home, goal, star),
            (1, away, goal, teams[1].roster.get(number=1)),
            (2, home, goal, star),
            (3, away, penalty_one, None),
            (3, home, goal, teams[0].roster.get(number=2)),
        ):
            ScoreEvent.objects.create(
                fixture=played,
                side=side,
                scoring_category=category,
                unit_index=unit,
                player=player,
                player_name=player.name if player else "",
                recorded_by=umpire,
            )
        played.recalculate_scores()
        played.status = Fixture.Status.COMPLETED
        played.save(update_fields=["status", "updated_at"])
        FixtureAward.objects.create(fixture=played, key="mvp", player=star, name=star.name, awarded_by=umpire)
        FixtureAward.objects.create(
            fixture=played, key="best_playing_pony", player=star, name="Cuartetera", awarded_by=umpire
        )
        upcoming = Fixture.objects.create(competition=competition, label="Final")
        FixtureSide.objects.create(fixture=upcoming, participant=teams[1], position=0, is_home=True)
        FixtureSide.objects.create(fixture=upcoming, participant=teams[0], position=1)
        FixtureReferee.objects.create(fixture=upcoming, user=umpire)
        from apps.standings.services import refresh_standings

        refresh_standings(competition)
        return 1

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

        for key, name in (
            ("horse_racing_flat", "Kenilworth flat series"),
            ("horse_racing_jumps", "Greyville jumps series"),
        ):
            competition, created = Competition.objects.get_or_create(
                name=name,
                owner=owner,
                defaults={"status": Competition.Status.ACTIVE, "sport": "horse racing"},
            )
            if not created and competition.fixtures.exists():
                continue
            apply_preset(competition, key)
            competition.status = Competition.Status.ACTIVE
            competition.save(update_fields=["status", "updated_at"])
            Membership.objects.get_or_create(
                competition=competition, user=owner, defaults={"role": Role.OWNER}
            )
            CompetitionOfficial.objects.get_or_create(
                competition=competition,
                user=steward,
                title="steward",
                defaults={"appointed_by": owner},
            )
            for index, horse in enumerate(horses[:4]):
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
            fixture = services.create_event(competition, label="Race 1", actor=steward)
            services.save_results(
                fixture,
                [
                    {"side": str(side.id), "data": {"position": index + 1, "margin": "neck"}}
                    for index, side in enumerate(fixture.sides.order_by("position"))
                ],
                steward,
                config={
                    "card": {
                        "grade": "Listed",
                        "distance_m": 1600 if key == "horse_racing_flat" else 3200,
                        "surface": "Turf" if key == "horse_racing_flat" else "Hurdle",
                        "going": "Good",
                    }
                },
            )
            made += 1

        made += self._polo(owner, steward)
        made += self._jumping(owner, judge, horses)
        made += self._dressage(owner, judge, horses)
        made += self._eventing(owner, judge, horses)
        made += self._endurance(owner, judge, horses)
        made += self._horseball(owner, steward)
        made += self._tent_pegging(owner, judge, horses)

        self.stdout.write(
            self.style.SUCCESS(
                f"Equestrian engine demo ready: {len(horses)} horses, "
                f"{made} new demo competitions. Officials: steward@example.com and "
                f"judge@example.com (password '{self.password}'). Each demo has a "
                "provisional event for an official to finalise."
            )
        )
