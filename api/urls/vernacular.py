"""URL configuration for the Vernacular API endpoints."""

from rest_framework.routers import DefaultRouter

from api.views.vernacular import VernacularViewSet

router_vernacular = DefaultRouter()
router_vernacular.register(r"", VernacularViewSet, basename="vernaculars")
