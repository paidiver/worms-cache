"""API URL configuration module."""

from django.urls import include, path

from ..views import HealthView
from .name_index import router_name_index
from .rank import router_rank
from .taxon import router_taxon
from .vernacular import router_vernacular

urlpatterns = [
    path("health/", HealthView.as_view(), name="Health"),
    path("taxa/", include(router_taxon.urls)),
    path("vernaculars/", include(router_vernacular.urls)),
    path("ranks/", include(router_rank.urls)),
    path("name_indexes/", include(router_name_index.urls)),
]
