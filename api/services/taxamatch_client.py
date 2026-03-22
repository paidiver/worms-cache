"""Client for the Taxamatch service, which provides fuzzy matching of taxonomic names."""

from typing import Any

import requests
from rest_framework import status

from config import settings


class TaxamatchError(RuntimeError):
    """Custom exception for errors related to the Taxamatch service."""

    pass


def match_batch(queries: list[dict[str, Any]], timeout: float = 3.0) -> list[dict[str, Any]]:
    """Match a batch of taxonomic name queries against the Taxamatch service.

    Args:
        queries: A list of query dictionaries, each containing at least a "name" key with the taxonomic name to match.
        timeout: The timeout in seconds for the HTTP request to the Taxamatch service.

    Example:
        queries = [
            {"q": "name", "candidates": [{"id": 123, "name": "candidate"}, ...]},
            ...
        ]
        returns: list entries like {"q": "...", "matched_ids": [...], "errors": [...]}

    Returns:
        A list of result dictionaries, each containing the original query and the matched IDs or errors.
    """
    url = f"{settings.TAXAMATCH_URL}/match"
    response = requests.post(url, json={"queries": queries}, timeout=timeout)
    if response.status_code != status.HTTP_200_OK:
        raise TaxamatchError(f"Taxamatch service error {response.status_code}: {response.text[:500]}")
    data = response.json()
    return data.get("results", [])
