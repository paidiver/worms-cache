"""WoRMS API client for fetching taxonomic data from the World Register of Marine Species (WoRMS)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from rest_framework import status
from urllib3.util.retry import Retry

from config import settings

CHANGE_PAGE_SIZE = 50


class WoRMSError(RuntimeError):
    """An unavailable or malformed upstream response, safe to expose to clients."""

    def __init__(self, message="WoRMS service is unavailable.", status_code=502):
        super().__init__(message)
        self.status_code = status_code


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
        try:
            with self._session() as session:
                response = session.get(url, timeout=20)
                if response.status_code == status.HTTP_204_NO_CONTENT:
                    return None
                response.raise_for_status()
                return response.json()
        except requests.Timeout as exc:
            raise WoRMSError("WoRMS service did not respond in time.", status_code=504) from exc
        except requests.RequestException as exc:
            raise WoRMSError() from exc
        except ValueError as exc:
            raise WoRMSError("WoRMS service returned invalid JSON.") from exc

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

    def records_by_date(self, start_date: str, end_date: str | None = None) -> list[dict]:
        """Fetch every change page in a fixed window, including nonmarine and extinct taxa."""
        end_date = end_date or datetime.now(UTC).isoformat()
        records = []
        offset = 1
        previous_page = None
        while True:
            query = urlencode(
                {
                    "startdate": start_date,
                    "enddate": end_date,
                    "marine_only": "false",
                    "extant_only": "false",
                    "offset": offset,
                }
            )
            page = self._get(f"/AphiaRecordsByDate?{query}") or []
            if not isinstance(page, list) or any(not isinstance(item, dict) or "AphiaID" not in item for item in page):
                raise WoRMSError("WoRMS service returned an invalid change page.")
            if page and page == previous_page:
                raise WoRMSError("WoRMS service repeated a change page.")
            records.extend(page)
            if len(page) < CHANGE_PAGE_SIZE:
                return records
            offset += len(page)
            previous_page = page
