from decimal import Decimal

from django.db import migrations


def reset_prices(apps, schema_editor):
    """Squads bought at the old pound prices restart at R0, like every player's value."""

    apps.get_model("fantasy", "FantasyPick").objects.update(price=Decimal("0"))


class Migration(migrations.Migration):
    dependencies = [
        ("fantasy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(reset_prices, migrations.RunPython.noop),
    ]
