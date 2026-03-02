"""ViewSet for the NameIndex model (WoRMS-style)."""

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from api.models import NameIndex
from api.serializers.name_index import NameIndexSerializer


@extend_schema(tags=["Search Index"])
class NameIndexViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving NameIndex names for a given taxon AphiaID."""

    serializer_class = NameIndexSerializer
    queryset = NameIndex.objects.all()
