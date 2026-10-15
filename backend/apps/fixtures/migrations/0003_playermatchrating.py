import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("competitions", "0003_match_unit"),
        ("fixtures", "0002_scoreevent_unit_index"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlayerMatchRating",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("rating", models.DecimalField(decimal_places=1, max_digits=3)),
                (
                    "fixture",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ratings",
                        to="fixtures.fixture",
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="match_ratings",
                        to="competitions.rostermember",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="playermatchrating",
            constraint=models.UniqueConstraint(
                fields=("fixture", "player"), name="unique_player_match_rating"
            ),
        ),
    ]
