"""Demo competitions for the Olympic-style result types, one per type.

Each has a provisional event for an official (steward@ or judge@example.com) to
confirm. The settings are inline because the locked sport presets arrive later.

    python manage.py seed_result_demos
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.competitions.models import Competition, Membership, PointsPolicy
from apps.core.permissions import Role
from apps.results import services
from apps.results.models import CompetitionOfficial

User = get_user_model()
NAMES = ["Amara Okafor", "Ben Carter", "Chen Wei", "Dana Novak", "Elif Kaya", "Felipe Ruiz"]
STATUSES = [
    {"code": "DQ", "label": "Disqualified"},
    {"code": "DNS", "label": "Did not start"},
    {"code": "DNF", "label": "Did not finish"},
    {"code": "NM", "label": "No mark"},
]

DEMOS = {
    "timed_lowest": {
        "config": {"decimals": 2, "reaction_limit": "0.100"},
        "data": [
            {"time": "9.87", "reaction_time": "0.142"},
            {"time": "9.912", "reaction_time": "0.155"},
            {"time": "9.905", "reaction_time": "0.149"},
            {"time": "10.04"},
            {"time": "10.11"},
            {"time": "9.70", "reaction_time": "0.088"},
        ],
    },
    "measured_highest": {
        "config": {"max_attempts": 6},
        "data": [
            {"attempts": ["8.21", "x", "8.05"]},
            {"attempts": ["8.21", "8.10", "x"]},
            {"attempts": ["7.98", "8.02", "x"]},
            {"attempts": ["x", "7.80", "7.91"]},
            {"attempts": ["7.65"]},
            {"attempts": ["x", "x", "x"]},
        ],
    },
    "judged_score": {
        "config": {
            "judges": 7,
            "drop_high": 2,
            "drop_low": 2,
            "multiply_by_difficulty": True,
            "max_score": 10,
            "score_step": "0.5",
            "attempts": 2,
        },
        "data": "dives",
    },
    "points_lowest": {
        "config": {"discard_worst": 1, "double_last": True, "tie_break": "last_round", "rounds": 5},
        "data": [
            {"rounds": [1, 3, 2, 6, 2]},
            {"rounds": [2, 1, 4, 3, 1]},
            {"rounds": [3, 2, 1, 5, 3]},
            {"rounds": [4, 5, 3, 1, 4]},
            {"rounds": [5, 4, 6, 2, 5]},
            {"rounds": [6, 6, 5, 4, 6]},
        ],
    },
    "points_highest": {
        "config": {"tie_break": "none", "rounds": 2},
        "data": [
            {"rounds": [340, 335], "tiebreak": [30, 12]},
            {"rounds": [338, 337], "tiebreak": [30, 14]},
            {"rounds": [333, 330], "tiebreak": [24, 9]},
            {"rounds": [329, 331], "tiebreak": [22, 8]},
            {"rounds": [320, 326], "tiebreak": [18, 6]},
            {"rounds": [318, 319], "tiebreak": [15, 5]},
        ],
    },
    "multi_run_aggregate": {
        "config": {"runs": 2, "decimals": 2},
        "data": [
            {"runs": ["52.10", "51.95"]},
            {"runs": ["52.00", "52.05"]},
            {"runs": ["52.40", "52.31"]},
            {"runs": ["53.02", "52.88"]},
            {"runs": ["52.75"]},
            {"status": "DNF"},
        ],
    },
    "combined_events": {
        "config": {"table": "decathlon"},
        "data": "decathlon",
    },
    "combat_decision": {
        "config": {
            "decide_by": "cards",
            "methods": [
                {"code": "DEC", "label": "Judges' decision"},
                {"code": "KO", "label": "Knockout"},
                {"code": "RSC", "label": "Referee stops contest"},
                {"code": "DQ", "label": "Disqualification"},
            ],
        },
        "entrants": 2,
        "data": [
            {"cards": [29, 28, 29, 27, 28]},
            {"cards": [28, 29, 28, 30, 29]},
        ],
    },
}


def _dives(index: int) -> dict:
    base = 8.5 - index * 0.5
    scores = [max(0, min(10, base + shift)) for shift in (-1, -0.5, 0, 0, 0, 0.5, 1)]
    return {
        "attempts": [
            {"scores": scores, "difficulty": "3.2"},
            {"scores": scores, "difficulty": "3.0"},
        ]
    }


def _decathlon(index: int) -> dict:
    return {
        "marks": {
            "100m": f"{10.40 + index * 0.08:.2f}",
            "long_jump": f"{7.70 - index * 0.06:.2f}",
            "shot_put": f"{15.5 - index * 0.3:.2f}",
            "high_jump": f"{2.08 - index * 0.03:.2f}",
            "400m": f"{47.5 + index * 0.4:.2f}",
            "110m_hurdles": f"{14.0 + index * 0.1:.2f}",
            "discus": f"{48.0 - index * 1.2:.2f}",
            "pole_vault": f"{5.10 - index * 0.1:.2f}",
            "javelin": f"{65.0 - index * 1.5:.2f}",
            "1500m": f"{270 + index * 4:.2f}",
        }
    }


class Command(BaseCommand):
    help = "Seed one demo competition per Olympic-style result type."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        owner = User.objects.filter(email="owner@example.com").first()
        officials = list(
            User.objects.filter(email__in=["steward@example.com", "judge@example.com"])
        )
        if owner is None:
            self.stderr.write("Run seed_demo first: owner@example.com is missing.")
            return
        made = 0
        for result_type, demo in DEMOS.items():
            name = f"Engine demo · {result_type.replace('_', ' ').capitalize()}"
            competition, created = Competition.objects.get_or_create(
                name=name, owner=owner, defaults={"status": Competition.Status.ACTIVE}
            )
            competition.settings_json = {
                **(competition.settings_json or {}),
                "result_type": result_type,
                "result_config": demo["config"],
                "statuses": STATUSES,
                "official_results": True,
                "participant_type": "individual",
                "contest_type": "accumulation",
                "placing_points": [10, 8, 6, 5, 4, 3],
                "governing_body": "Engine demo: each locked preset names its own federation",
                "rulebook": "Demo settings, not a real rulebook",
                "description": "A demo of the results engine. Not a sport preset.",
                "locked": True,
                "scoring_locked": True,
            }
            competition.save()
            Membership.objects.get_or_create(
                competition=competition, user=owner, defaults={"role": Role.OWNER}
            )
            policy, _ = PointsPolicy.objects.get_or_create(competition=competition)
            policy.tiebreakers = ["points", "placings", "name"]
            policy.save()
            for person in officials:
                CompetitionOfficial.objects.get_or_create(
                    competition=competition,
                    user=person,
                    title="judge",
                    defaults={"appointed_by": owner},
                )
            if not created and competition.fixtures.exists():
                continue
            count = demo.get("entrants", len(NAMES))
            for person in NAMES[:count]:
                competition.participants.get_or_create(name=person, defaults={"kind": "individual"})
            fixture = services.create_event(competition, label="Final", actor=owner)
            rows = []
            for index, side in enumerate(fixture.sides.order_by("position")):
                if demo["data"] == "dives":
                    data = _dives(index)
                elif demo["data"] == "decathlon":
                    data = _decathlon(index)
                else:
                    data = demo["data"][index]
                rows.append({"side": str(side.id), "data": data})
            services.save_results(fixture, rows, owner)
            made += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Result-type demos ready: {made} new. Confirm them as steward@example.com "
                "or judge@example.com (password 'fairmeasure')."
            )
        )
