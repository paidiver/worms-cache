"""Serializers for the WoRMS cache API."""

from rest_framework import serializers

from api.models import NameIndex


class NameIndexSerializer(serializers.ModelSerializer):
    """Serializer for the NameIndex model."""

    class Meta:
        """Meta information for the NameIndexSerializer."""

        model = NameIndex
        fields = "__all__"
