"""Service functions related to cache policy and staleness checks for Taxon records."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from api.models.taxon import Taxon


def is_stale(taxon: "Taxon") -> bool:
    """Determines if a given Taxon instance is stale based on its cached_at timestamp and the configured TTL.

    Args:
        taxon: The Taxon instance to check for staleness

    Returns:
        bool: True if the taxon is considered stale and should be refreshed from WoRMS, False otherwise
    """
    ttl = getattr(settings, "WORMS_CACHE_TTL_DAYS", 30)
    return taxon.cached_at < timezone.now() - timedelta(days=ttl)
