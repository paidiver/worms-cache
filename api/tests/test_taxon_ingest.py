"""Tests for TaxonViewSet ingest endpoint."""

from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models.taxon import Taxon


@override_settings(INGEST_API_TOKEN="test-token")
class IngestAphiaIdViewTests(APITestCase):
    """Tests for the ingest AphiaID endpoint."""

    def setUp(self) -> None:
        """Set up the test case with a test client and any necessary data."""
        Taxon.objects.create(
            aphia_id=12348,
            scientific_name="Animalia",
            rank="Kingdom",
            parent=None,
        )

    def ingest_url(self) -> str:
        """Return the URL for the ingest endpoint.

        Returns:
            str: The URL for the ingest endpoint.
        """
        return reverse("taxa-ingest")

    @patch("api.views.taxon.IngestAphiaId")
    def test_ingest_returns_202_when_authenticated_with_valid_token(self, mock_ingest_class: MagicMock):
        """Test that POST to ingest endpoint with valid token returns 202 with ingested taxa.

        Args:
            mock_ingest_class: The mocked IngestAphiaId class to control its behavior in the test.
        """
        mock_taxon = MagicMock()
        mock_taxon.aphia_id = 12345
        mock_taxon.scientific_name = "Gadus morhua"
        mock_taxon.rank = "Species"
        mock_taxon.status = "accepted"
        mock_taxon.source_url = None
        mock_taxon.worms_modified = None
        mock_taxon.cached_at = None
        mock_taxon.valid_taxon = None
        mock_taxon.parent = None

        mock_instance = MagicMock()
        mock_instance.ingest_aphia_id.return_value = [mock_taxon]
        mock_ingest_class.return_value = mock_instance

        resp = self.client.post(
            self.ingest_url(),
            {"aphia_id": 12345},
            format="json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        mock_ingest_class.assert_called_once_with(aphia_ids={12345})
        mock_instance.ingest_aphia_id.assert_called_once_with(12345)

    @patch("api.views.taxon.IngestAphiaId")
    def test_ingest_returns_error_when_aphiaid_is_wrong(self, mock_ingest_class: MagicMock):
        """Test that POST to ingest endpoint with valid token returns 202 with ingested taxa.

        Args:
            mock_ingest_class: The mocked IngestAphiaId class to control its behavior in the test.
        """
        mock_instance = MagicMock()
        mock_instance.ingest_aphia_id.side_effect = Exception("Ingestion error")
        mock_ingest_class.return_value = mock_instance

        resp = self.client.post(
            self.ingest_url(),
            {"aphia_id": 11111},
            format="json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        mock_ingest_class.assert_called_once_with(aphia_ids={11111})
        mock_instance.ingest_aphia_id.assert_called_once_with(11111)

    def test_ingest_returns_existing_data_with_aphia_id_already_in_db(self):
        """Test that POST to ingest endpoint with aphia_id already in DB returns 200 with existing data."""
        resp = self.client.post(
            self.ingest_url(),
            {"aphia_id": 12348},
            format="json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["AphiaID"], 12348)

    def test_ingest_returns_403_when_unauthenticated(self):
        """Test that POST to ingest endpoint without token is rejected."""
        resp = self.client.post(self.ingest_url(), {"aphia_id": 12345}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_ingest_returns_403_when_token_is_invalid(self):
        """Test that POST to ingest endpoint with invalid token is rejected."""
        resp = self.client.post(
            self.ingest_url(),
            {"aphia_id": 12345},
            format="json",
            HTTP_AUTHORIZATION="Bearer wrong-token",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_ingest_returns_400_for_invalid_aphia_id(self):
        """Test that POST to ingest endpoint with invalid aphia_id returns 400."""
        resp = self.client.post(
            self.ingest_url(),
            {"aphia_id": -1},
            format="json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ingest_returns_400_when_aphia_id_missing(self):
        """Test that POST to ingest endpoint without aphia_id returns 400."""
        resp = self.client.post(
            self.ingest_url(),
            {},
            format="json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
