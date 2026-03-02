"""URL configuration for the Rank API endpoints."""

from rest_framework.routers import DefaultRouter

from api.views.rank import RankViewSet

router_rank = DefaultRouter()
router_rank.register(r"", RankViewSet, basename="ranks")
