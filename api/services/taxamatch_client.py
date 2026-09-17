"""Client for the Taxamatch service, which provides fuzzy matching of taxonomic names."""

from typing import Any

import requests
from rest_framework import status

from config import settings


class TaxamatchError(RuntimeError):
    """Custom exception for errors related to the Taxamatch service."""

    def __init__(self, message="Taxamatch service is unavailable.", status_code=502):
        super().__init__(message)
        self.status_code = status_code


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
    if not queries:
        return []
    url = f"{settings.TAXAMATCH_URL}/match"
    try:
        response = requests.post(url, json={"queries": queries}, timeout=timeout)
        if response.status_code != status.HTTP_200_OK:
            raise TaxamatchError(f"Taxamatch service error {response.status_code}.")
        data = response.json()
    except requests.Timeout as exc:
        raise TaxamatchError("Taxamatch service did not respond in time.", status_code=504) from exc
    except requests.RequestException as exc:
        raise TaxamatchError() from exc
    except ValueError as exc:
        raise TaxamatchError("Taxamatch service returned invalid JSON.") from exc
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list) or len(results) != len(queries):
        raise TaxamatchError("Taxamatch service returned an invalid batch response.")
    for query, result in zip(queries, results, strict=True):
        candidate_ids = {candidate["id"] for candidate in query["candidates"]}
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("matched_ids"), list)
            or result.get("errors")
            or any(type(value) is not int or value not in candidate_ids for value in result["matched_ids"])
        ):
            raise TaxamatchError("Taxamatch service returned invalid matching results.")
    return results
