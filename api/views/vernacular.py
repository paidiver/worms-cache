"""ViewSet for the Vernacular model (WoRMS-style)."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from api.models.taxon import Taxon
from api.models.vernacular import Vernacular
from api.serializers.vernacular import VernacularMiniSerializer, VernacularSerializer


@extend_schema(tags=["Vernaculars"])
class VernacularViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving Vernacular names for a given taxon AphiaID."""

    serializer_class = VernacularSerializer
    queryset = Vernacular.objects.select_related("taxon").all()

    lookup_url_kwarg = "aphia_id"

    def _parse_aphia_id(self) -> int:
        """Parse the AphiaID from the URL kwargs and return it as an integer.

        Returns:
            The AphiaID parsed from the URL kwargs as an integer.
        """
        raw = self.kwargs.get(self.lookup_url_kwarg) or self.kwargs.get("pk")
        try:
            return int(raw)
        except (TypeError, ValueError) as e:
            raise ValidationError({"aphia_id": "Must be an integer AphiaID."}) from e

    def _resolve_valid_aphia_id(self, aphia_id: int) -> int:
        """Check if the given AphiaID corresponds to a valid taxon or synonym, and return AphiaID of the valid taxon.

        Args:
            aphia_id: The AphiaID to check

        Returns:
            The AphiaID of the valid taxon if the given AphiaID is a synonym
        """
        taxon = Taxon.objects.only("aphia_id", "valid_taxon_id").filter(aphia_id=aphia_id).first()
        if taxon and taxon.valid_taxon_id and taxon.valid_taxon_id != aphia_id:
            return taxon.valid_taxon_id
        return aphia_id

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="language_code",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Optional ISO 639-3 language code (e.g. eng, por).",
            ),
            OpenApiParameter(
                name="follow_valid",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                default=True,
                description="If true, redirect invalid AphiaID to its valid_taxon_id when available.",
            ),
        ],
        responses={200: VernacularMiniSerializer(many=True)},
    )
    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        """Retrieve vernacular names for a given taxon AphiaID, optionally filtered by language code.

        Args:
            request: The HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments, expected to include "aphia_id" for the taxon.
        """
        aphia_id = self._parse_aphia_id()

        follow_valid = request.query_params.get("follow_valid", "true").strip().lower() not in {"0", "false", "no"}
        if follow_valid:
            aphia_id = self._resolve_valid_aphia_id(aphia_id)

        language_code = (request.query_params.get("language_code") or "").strip() or None

        qs = Vernacular.objects.filter(taxon_id=aphia_id)
        if language_code:
            qs = qs.filter(language_code=language_code)

        serializer = VernacularMiniSerializer(qs, many=True)
        return Response(serializer.data)
