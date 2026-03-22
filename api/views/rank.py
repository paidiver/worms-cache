"""ViewSet for the Rank model (WoRMS-style)."""

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from api.models import Rank
from api.serializers.rank import RankSerializer


@extend_schema(tags=["Ranks"])
class RankViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving Rank names for a given taxon AphiaID."""

    serializer_class = RankSerializer
    queryset = Rank.objects.all()
