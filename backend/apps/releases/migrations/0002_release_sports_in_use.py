"""Keep every sport that already has a competition open, plus football.

Everything else starts hidden and is released from the platform admin page.
"""

from django.db import migrations

FIRST_RELEASE = {"soccer"}


def release_sports_in_use(apps, schema_editor):
    Competition = apps.get_model("competitions", "Competition")
    Release = apps.get_model("releases", "Release")

    keys = set(FIRST_RELEASE)
    for settings_json in Competition.objects.values_list("settings_json", flat=True).iterator():
        preset = (settings_json or {}).get("preset") if isinstance(settings_json, dict) else None
        if preset:
            keys.add(str(preset)[:80])
    for key in sorted(keys):
        Release.objects.get_or_create(kind="sport", key=key, defaults={"live": True})


class Migration(migrations.Migration):
    dependencies = [
        ("releases", "0001_initial"),
        ("competitions", "0010_competition_platform_hidden"),
    ]

    operations = [migrations.RunPython(release_sports_in_use, migrations.RunPython.noop)]
