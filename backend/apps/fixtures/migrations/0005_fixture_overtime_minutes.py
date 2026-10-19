from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("fixtures", "0004_fixturereferee"),
    ]

    operations = [
        migrations.AddField(
            model_name="fixture",
            name="overtime_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
