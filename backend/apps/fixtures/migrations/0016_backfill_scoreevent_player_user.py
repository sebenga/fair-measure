"""Backfill ScoreEvent.player_user and team_name from roster / side."""

from __future__ import annotations

from django.db import migrations


def forwards(apps, schema_editor):
    ScoreEvent = apps.get_model("fixtures", "ScoreEvent")
    RosterMember = apps.get_model("competitions", "RosterMember")
    Side = apps.get_model("fixtures", "FixtureSide")
    Participant = apps.get_model("competitions", "Participant")

    participants = {row.id: row.name for row in Participant.objects.all().only("id", "name")}

    for event in ScoreEvent.objects.all().iterator(chunk_size=500):
        updates = {}
        side = Side.objects.filter(pk=event.side_id).first() if event.side_id else None
        team_name = event.team_name
        if not team_name and side is not None:
            team_name = participants.get(side.participant_id, "")
            if team_name:
                updates["team_name"] = team_name

        if event.player_user_id is None and event.player_id:
            member = RosterMember.objects.filter(pk=event.player_id).only("user_id").first()
            if member is not None and member.user_id:
                updates["player_user_id"] = member.user_id

        if event.player_user_id is None and event.player_name and side is not None:
            member = (
                RosterMember.objects.filter(
                    participant_id=side.participant_id,
                    name=event.player_name,
                )
                .exclude(user_id=None)
                .only("user_id")
                .first()
            )
            if member is not None:
                updates["player_user_id"] = member.user_id

        if updates:
            ScoreEvent.objects.filter(pk=event.pk).update(**updates)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("fixtures", "0015_soccer_match_card_and_player_history"),
        ("competitions", "0015_soccer_match_card_and_player_history"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
