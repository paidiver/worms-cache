"""URL configuration for the Name Index API endpoints."""

from rest_framework.routers import DefaultRouter

from api.views.name_index import NameIndexViewSet

router_name_index = DefaultRouter()
router_name_index.register(r"", NameIndexViewSet, basename="name_indexes")
