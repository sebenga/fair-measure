from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("competitions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="kind",
            field=models.CharField(
                choices=[("individual", "Player"), ("team", "Team")],
                default="individual",
                max_length=16,
            ),
        ),
    ]
