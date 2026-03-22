"""Serializers for the WoRMS cache API."""

from rest_framework import serializers

from api.models import Rank


class RankSerializer(serializers.ModelSerializer):
    """Serializer for the Rank model, representing a rank for a taxon."""

    class Meta:
        """Meta information for the RankSerializer."""

        model = Rank
        fields = ["rank_id", "name"]
