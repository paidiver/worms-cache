"""Validated query parameters for WoRMS-compatible endpoints."""

from rest_framework import serializers


class TaxonQuerySerializer(serializers.Serializer):
    """Validate optional filters without changing successful response shapes."""

    max_matches = serializers.IntegerField(min_value=1, max_value=50, default=20)
    max_results = serializers.IntegerField(min_value=1, max_value=50, default=3)
    rank_min = serializers.IntegerField(min_value=0, default=0)
    rank_max = serializers.IntegerField(min_value=0, default=0)
    offset = serializers.IntegerField(min_value=1, default=1)
    limit = serializers.IntegerField(min_value=1, max_value=50, default=50)
    combine_vernaculars = serializers.BooleanField(default=False)
    id_only = serializers.BooleanField(default=True)
    only_valid = serializers.BooleanField(default=False)
    include_descendants = serializers.BooleanField(default=False)
    include_parents = serializers.BooleanField(default=False)
    aphia_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=2147483647), required=False, allow_empty=False
    )
    excluded_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=2147483647), default=list
    )
    languages = serializers.ListField(child=serializers.CharField(max_length=3, min_length=3), default=list)
    scientificnames = serializers.ListField(
        child=serializers.CharField(max_length=512), min_length=1, max_length=50, required=False
    )
    scientificname1 = serializers.CharField(max_length=512, required=False)
    scientificname2 = serializers.CharField(max_length=512, required=False)

    def validate(self, attrs):
        """Check rank ranges, where zero means an open bound."""
        if attrs["rank_min"] and attrs["rank_max"] and attrs["rank_min"] > attrs["rank_max"]:
            raise serializers.ValidationError({"rank_max": "Must be greater than or equal to rank_min."})
        return attrs


def validate_query(params):
    """Normalize repeated bracket-style parameters before serializer validation."""
    data = params.dict()
    for name in ("aphia_ids", "excluded_ids", "languages", "scientificnames"):
        if f"{name}[]" in params:
            data[name] = params.getlist(f"{name}[]")
    serializer = TaxonQuerySerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data
