"""Serializers for the WoRMS cache API."""

from rest_framework import serializers

from api.models.taxon import Taxon


class TaxonWormsLikeSerializer(serializers.ModelSerializer):
    """Serializer for the Taxon model, providing a minimal representation of a taxon."""

    AphiaID = serializers.IntegerField(source="aphia_id", read_only=True)
    url = serializers.CharField(source="source_url", read_only=True)
    scientificname = serializers.CharField(source="scientific_name", read_only=True)
    valid_AphiaID = serializers.SerializerMethodField()
    valid_name = serializers.SerializerMethodField()

    modified = serializers.DateTimeField(source="worms_modified", read_only=True)
    parent_AphiaID = serializers.IntegerField(source="parent.aphia_id", read_only=True)

    def get_valid_AphiaID(self, obj: Taxon):
        """Return the AphiaID of the valid taxon if this taxon is a synonym, otherwise return its own AphiaID.

        Args:
            obj: The Taxon instance being serialized.

        Returns:
            int: The AphiaID of the valid taxon if this taxon is a synonym, or the taxon's own AphiaID if it is valid.
        """
        return obj.valid_taxon.aphia_id if obj.valid_taxon else obj.aphia_id

    def get_valid_name(self, obj: Taxon):
        """Return the scientific name of the valid taxon if this taxon is a synonym, otherwise return its name.

        Args:
            obj: The Taxon instance being serialized.

        Returns:
            str: The scientific name of the valid taxon if this taxon is a synonym, or the taxon's own name if it is
        valid.
        """
        return obj.valid_taxon.scientific_name if obj.valid_taxon else obj.scientific_name

    class Meta:
        """Meta information for the TaxonWormsLikeSerializer."""

        model = Taxon
        fields = [
            "AphiaID",
            "scientificname",
            "url",
            "rank",
            "status",
            "valid_AphiaID",
            "valid_name",
            "modified",
            "cached_at",
            "parent_AphiaID",
        ]


class TaxonMiniSerializer(serializers.ModelSerializer):
    """Serializer for the Taxon model, providing a minimal representation of a taxon."""

    valid_aphia_id = serializers.IntegerField(source="valid_taxon.aphia_id", read_only=True)
    valid_name = serializers.CharField(source="valid_taxon.scientific_name", read_only=True)
    parent_aphia_id = serializers.IntegerField(source="parent.aphia_id", read_only=True)

    class Meta:
        """Meta information for the TaxonMiniSerializer."""

        model = Taxon
        fields = [
            "aphia_id",
            "scientific_name",
            "rank",
            "status",
            "valid_aphia_id",
            "valid_name",
            "parent_aphia_id",
            "worms_modified",
            "cached_at",
            "source_url",
        ]


class ClassificationNodeSerializer(serializers.Serializer):
    """Serializer for representing a taxon in a classification tree structure."""

    AphiaID = serializers.IntegerField()
    rank = serializers.CharField()
    scientificname = serializers.CharField()
    child = serializers.DictField(allow_null=True)


class IngestAphiaIdSerializer(serializers.Serializer):
    """Serializer for the ingest AphiaID endpoint request body."""

    aphia_id = serializers.IntegerField(min_value=1, help_text="The AphiaID to ingest from WoRMS.")
