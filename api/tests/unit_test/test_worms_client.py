"""Unit tests for WoRMSClient (worms_client)."""

from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase
from requests.exceptions import HTTPError
from requests.sessions import HTTPAdapter

from api.services.worms_client import HTTP_NO_CONTENT, WoRMSClient


class WoRMSClientTests(SimpleTestCase):
    """Tests for WoRMSClient using mocked requests.Session."""

    def _mock_session_cm(self, response: MagicMock) -> tuple[MagicMock, MagicMock]:
        """Helper function to create a mocked for requests.

        Args:
            response: The MagicMock response object that the session's get() method should return.

        Returns:
            A tuple containing the mocked context manager and the mocked session.
        """
        session = MagicMock(name="session")
        session.get.return_value = response

        cm = MagicMock(name="session_cm")
        cm.__enter__.return_value = session
        cm.__exit__.return_value = None
        return cm, session

    def test_session_creates_session_with_retries(self):
        """Test that _session() creates a requests Session with the expected retry configuration."""
        client = WoRMSClient(base_url="https://worms.example")
        session = client._session()

        self.assertIsInstance(session, requests.Session)
        adapter = session.get_adapter("https://")
        self.assertIsInstance(adapter, HTTPAdapter)
        self.assertIsNotNone(adapter.max_retries)
        self.assertEqual(adapter.max_retries.total, 5)
        self.assertEqual(adapter.max_retries.backoff_factor, 0.5)
        self.assertEqual(adapter.max_retries.status_forcelist, (429, 500, 502, 503, 504))
        self.assertEqual(adapter.max_retries.allowed_methods, ("GET",))

    def test_get_returns_json_for_200(self):
        """Test that _get() returns the JSON-decoded response for a successful 200 response from the WoRMS API."""
        client = WoRMSClient(base_url="https://worms.example")

        response = MagicMock(name="response")
        response.status_code = 200
        response.json.return_value = {"ok": True}
        response.raise_for_status.return_value = None

        cm, session = self._mock_session_cm(response)

        with patch.object(WoRMSClient, "_session", return_value=cm):
            out = client._get("/AphiaRecordByAphiaID/10")

        self.assertEqual(out, {"ok": True})
        session.get.assert_called_once_with("https://worms.example/AphiaRecordByAphiaID/10", timeout=20)
        response.raise_for_status.assert_called_once()

    def test_get_returns_none_for_204(self):
        """Test that _get() returns None for a 204 No Content response from the WoRMS API."""
        client = WoRMSClient(base_url="https://worms.example")

        response = MagicMock(name="response")
        response.status_code = HTTP_NO_CONTENT
        cm, session = self._mock_session_cm(response)

        with patch.object(WoRMSClient, "_session", return_value=cm):
            out = client._get("/AphiaRecordByAphiaID/10")

        self.assertIsNone(out)
        session.get.assert_called_once()
        response.raise_for_status.assert_not_called()
        response.json.assert_not_called()

    def test_get_raises_for_non_204_http_error(self):
        """Test that _get() raises an HTTPError for a non-204 with an HTTP error status code from the WoRMS API."""
        client = WoRMSClient(base_url="https://worms.example")

        response = MagicMock(name="response")
        response.status_code = 500
        response.raise_for_status.side_effect = HTTPError("boom")

        cm, session = self._mock_session_cm(response)

        with patch.object(WoRMSClient, "_session", return_value=cm), self.assertRaises(HTTPError):
            client._get("/AphiaRecordByAphiaID/10")

        session.get.assert_called_once()
        response.raise_for_status.assert_called_once()

    def test_record_builds_correct_path(self):
        """Test that record() builds the correct API path and returns the expected result."""
        client = WoRMSClient(base_url="https://worms.example")
        with patch.object(WoRMSClient, "_get", return_value={"AphiaID": 10}) as mock_get:
            out = client.record(10)

        self.assertEqual(out, {"AphiaID": 10})
        mock_get.assert_called_once_with("/AphiaRecordByAphiaID/10")

    def test_classification_builds_correct_path(self):
        """Test that classification() builds the correct API path and returns the expected result."""
        client = WoRMSClient(base_url="https://worms.example")
        with patch.object(WoRMSClient, "_get", return_value={"AphiaID": 10, "child": None}) as mock_get:
            out = client.classification(10)

        self.assertEqual(out["AphiaID"], 10)
        mock_get.assert_called_once_with("/AphiaClassificationByAphiaID/10")

    def test_vernaculars_returns_list_or_empty(self):
        """Test that vernaculars() returns a list of vernacular names or an empty list if the API returns None."""
        client = WoRMSClient(base_url="https://worms.example")

        with patch.object(WoRMSClient, "_get", return_value=[{"vernacular": "cod"}]) as mock_get:
            out = client.vernaculars(10)
        self.assertEqual(out, [{"vernacular": "cod"}])
        mock_get.assert_called_once_with("/AphiaVernacularsByAphiaID/10")

        with patch.object(WoRMSClient, "_get", return_value=None) as mock_get2:
            out2 = client.vernaculars(10)
        self.assertEqual(out2, [])
        mock_get2.assert_called_once_with("/AphiaVernacularsByAphiaID/10")

    def test_ranks_returns_list_or_empty(self):
        """Test that ranks() returns a list of rank names or an empty list if the API returns None."""
        client = WoRMSClient(base_url="https://worms.example")

        with patch.object(WoRMSClient, "_get", return_value=[{"rankName": "cod"}]) as mock_get:
            out = client.ranks(10)
        self.assertEqual(out, [{"rankName": "cod"}])
        mock_get.assert_called_once_with("/AphiaTaxonRanksByID/10")

        with patch.object(WoRMSClient, "_get", return_value=None) as mock_get2:
            out2 = client.ranks(10)
        self.assertEqual(out2, None)
        mock_get2.assert_called_once_with("/AphiaTaxonRanksByID/10")

    def test_synonyms_returns_list_or_empty(self):
        """Test that synonyms() returns a list of synonyms or an empty list if the API returns None."""
        client = WoRMSClient(base_url="https://worms.example")

        with patch.object(WoRMSClient, "_get", return_value=[{"AphiaID": 999}]) as mock_get:
            out = client.synonyms(10)
        self.assertEqual(out, [{"AphiaID": 999}])
        mock_get.assert_called_once_with("/AphiaSynonymsByAphiaID/10")

        with patch.object(WoRMSClient, "_get", return_value=None) as mock_get2:
            out2 = client.synonyms(10)
        self.assertEqual(out2, [])
        mock_get2.assert_called_once_with("/AphiaSynonymsByAphiaID/10")
