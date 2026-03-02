"""Serializers for the WoRMS cache API."""

from rest_framework import serializers

from api.models.vernacular import Vernacular


class VernacularSerializer(serializers.ModelSerializer):
    """Serializer for the Vernacular model, representing a vernacular name for a taxon."""

    class Meta:
        """Meta information for the VernacularSerializer."""

        model = Vernacular
        fields = ["taxon_id", "name", "language_code"]


class VernacularMiniSerializer(serializers.ModelSerializer):
    """Serializer for the Vernacular model, representing a vernacular name for a taxon."""

    class Meta:
        """Meta information for the VernacularSerializer."""

        model = Vernacular
        fields = ["name", "language_code"]
