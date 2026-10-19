from rest_framework import serializers

from apps.fixtures.serializers import ParticipantRefSerializer

from .models import StandingRow


class StandingRowSerializer(serializers.ModelSerializer):
    participant = ParticipantRefSerializer(read_only=True)

    class Meta:
        model = StandingRow
        fields = [
            "position",
            "participant",
            "played",
            "wins",
            "draws",
            "losses",
            "score_for",
            "score_against",
            "score_difference",
            "points",
            "bonus_points",
            "form",
            "detail",
            "computed_at",
        ]
