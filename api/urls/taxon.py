"""URL configuration for the Taxon API endpoints."""

from rest_framework.routers import DefaultRouter

from api.views.taxon import TaxonViewSet

router_taxon = DefaultRouter()
router_taxon.register(r"", TaxonViewSet, basename="taxa")
