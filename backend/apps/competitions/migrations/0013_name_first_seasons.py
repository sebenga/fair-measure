"""Leagues that already started a second season keep their first one as "Season 1"."""

from django.db import migrations
from django.db.models import F, Max, Min


def name_first_seasons(apps, schema_editor):
    Stage = apps.get_model("competitions", "Stage")
    Fixture = apps.get_model("fixtures", "Fixture")
    FixtureSide = apps.get_model("fixtures", "FixtureSide")

    rolled_over = (
        Stage.objects.filter(kind="league", name__startswith="Season ")
        .values_list("competition_id", flat=True)
        .distinct()
    )
    for competition_id in rolled_over:
        if Stage.objects.filter(competition_id=competition_id, name="Season 1").exists():
            continue
        loose = Fixture.objects.filter(competition_id=competition_id, stage__isnull=True).exclude(
            status="cancelled"
        )
        if not loose.exists():
            continue
        dates = loose.aggregate(first=Min("scheduled_at"), last=Max("scheduled_at"))
        Stage.objects.filter(competition_id=competition_id).update(display_order=F("display_order") + 1)
        stage = Stage.objects.create(
            competition_id=competition_id,
            name="Season 1",
            kind="league",
            display_order=0,
            starts_on=dates["first"].date() if dates["first"] else None,
            ends_on=dates["last"].date() if dates["last"] else None,
        )
        loose.update(stage=stage)
        entrants = (
            FixtureSide.objects.filter(fixture__stage=stage, participant__isnull=False)
            .values_list("participant_id", flat=True)
            .distinct()
        )
        stage.participants.add(*entrants)


class Migration(migrations.Migration):
    dependencies = [
        ("competitions", "0012_competition_invites"),
        ("fixtures", "0011_fixture_phase_shootout"),
    ]

    operations = [migrations.RunPython(name_first_seasons, migrations.RunPython.noop)]
