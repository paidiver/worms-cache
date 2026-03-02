"""WoRMS API client for fetching taxonomic data from the World Register of Marine Species (WoRMS)."""

from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import settings

HTTP_NO_CONTENT = 204


@dataclass(frozen=True)
class WoRMSClient:
    """Client for interacting with the WoRMS API."""

    base_url: str = settings.WORMS_API_BASE_URL

    def __post_init__(self):
        """Post-initialization to validate the base URL."""
        pass

    def _session(self) -> requests.Session:
        """Create a requests Session with retry logic for transient errors.

        Returns:
            A configured requests Session object with retry logic.
        """
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session

    def _get(self, path: str) -> dict | list[dict] | None:
        """Helper method to perform a GET request to the WoRMS API.

        Args:
            path: The API endpoint path to append to the base URL.

        Returns:
            The JSON response from the API as a dictionary or list of dictionaries, or None if no content.
        """
        url = f"{self.base_url}{path}"
        with self._session() as session:
            response = session.get(url, timeout=20)
            if response.status_code == HTTP_NO_CONTENT:
                return None
            response.raise_for_status()
            return response.json()

    def record(self, aphia_id: int) -> dict | None:
        """Fetch the AphiaRecord for a given AphiaID.

        Args:
            aphia_id: The AphiaID for which to fetch the record.

        Returns:
            A dictionary representing the AphiaRecord, or None if not found.
        """
        return self._get(f"/AphiaRecordByAphiaID/{aphia_id}")

    def classification(self, aphia_id: int) -> dict | None:
        """Fetch the classification chain for a given AphiaID.

        Args:
            aphia_id: The AphiaID for which to fetch the classification chain.

        Returns:
            A nested dictionary representing the classification chain, or None if not found.
        """
        return self._get(f"/AphiaClassificationByAphiaID/{aphia_id}")

    def ranks(self, rank_id: int = -1) -> list[dict] | None:
        """Fetch the rank information.

        Returns:
            A list of dictionaries representing the rank information, or None if not found.
        """
        return self._get(f"/AphiaTaxonRanksByID/{rank_id}")

    def vernaculars(self, aphia_id: int) -> list[dict]:
        """Fetch the vernacular names for a given AphiaID.

        Args:
            aphia_id: The AphiaID for which to fetch the vernacular names.

        Returns:
            A list of dictionaries representing the vernacular names, or an empty list if not found.
        """
        return self._get(f"/AphiaVernacularsByAphiaID/{aphia_id}") or []

    def synonyms(self, aphia_id: int) -> list[dict]:
        """Fetch the synonyms for a given AphiaID.

        Args:
            aphia_id: The AphiaID for which to fetch the synonyms.

        Returns:
            A list of dictionaries representing the synonyms, or an empty list if not found.
        """
        return self._get(f"/AphiaSynonymsByAphiaID/{aphia_id}") or []
