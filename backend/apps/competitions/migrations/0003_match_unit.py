from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("competitions", "0002_participant_kind"),
    ]

    operations = [
        migrations.CreateModel(
            name="MatchUnit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("unit", models.CharField(max_length=40)),
                ("count", models.PositiveIntegerField(default=1)),
                ("minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("best_of", models.PositiveIntegerField(blank=True, null=True)),
                ("first_to", models.PositiveIntegerField(blank=True, null=True)),
                ("win_by", models.PositiveIntegerField(blank=True, null=True)),
                ("tiebreak_at", models.PositiveIntegerField(blank=True, null=True)),
                ("affects_total", models.BooleanField(default=True)),
                ("resolves_draw", models.BooleanField(default=False)),
                (
                    "competition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="match_units",
                        to="competitions.competition",
                    ),
                ),
            ],
            options={"ordering": ["display_order", "created_at"]},
        ),
    ]
