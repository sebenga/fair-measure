# Generated manually for limited vote budgets.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("competitions", "0015_soccer_match_card_and_player_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="vote",
            name="quantity",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RemoveConstraint(
            model_name="vote",
            name="uniq_vote_per_round_voter",
        ),
        migrations.AddConstraint(
            model_name="vote",
            constraint=models.UniqueConstraint(
                fields=("round", "voter", "participant"),
                name="uniq_vote_per_round_voter_participant",
            ),
        ),
    ]
