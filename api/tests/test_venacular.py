"""Integration tests for VernacularViewSet endpoints."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models.taxon import Taxon
from api.models.vernacular import Vernacular


class VernacularViewSetTests(APITestCase):
    """Integration tests for VernacularViewSet retrieve endpoint."""

    BASENAME = "vernaculars"

    def setUp(self):
        """Set up test data for VernacularViewSet tests."""
        self.valid = Taxon.objects.create(
            aphia_id=100,
            scientific_name="Gadus morhua",
            rank="Species",
        )

        self.invalid = Taxon.objects.create(
            aphia_id=200,
            scientific_name="Gadus morhua (invalid)",
            rank="Species",
            valid_taxon=self.valid,
        )

        Vernacular.objects.create(taxon=self.valid, name="cod", language_code="eng")
        Vernacular.objects.create(taxon=self.valid, name="bacalhau", language_code="por")
        Vernacular.objects.create(taxon=self.invalid, name="should_not_be_seen_if_follow_valid", language_code="eng")

    def detail_url(self, aphia_id: int) -> str:
        """Helper method to construct the detail URL for a given AphiaID.

        Args:
            aphia_id: The AphiaID to construct the URL for
        """
        return reverse(f"{self.BASENAME}-detail", kwargs={"aphia_id": aphia_id})

    def test_retrieve_returns_all_vernaculars_for_taxon(self):
        """Test that the retrieve endpoint returns all vernaculars for a given taxon."""
        resp = self.client.get(self.detail_url(self.valid.aphia_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.assertTrue(all(set(item.keys()) == {"name", "language_code"} for item in resp.data))

        names = sorted([item["name"] for item in resp.data])
        self.assertEqual(names, ["bacalhau", "cod"])

    def test_retrieve_filters_by_language_code(self):
        """Test that the retrieve endpoint filters vernaculars by language_code query parameter."""
        resp = self.client.get(self.detail_url(self.valid.aphia_id), {"language_code": "por"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["name"], "bacalhau")
        self.assertEqual(resp.data[0]["language_code"], "por")

    def test_retrieve_follow_valid_true_resolves_invalid_to_valid(self):
        """Test that the retrieve endpoint for invalid AphiaID to valid_id when follow_valid query parameter is true."""
        resp = self.client.get(self.detail_url(self.invalid.aphia_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        names = sorted([item["name"] for item in resp.data])
        self.assertEqual(names, ["bacalhau", "cod"])

    def test_retrieve_follow_valid_false_does_not_resolve(self):
        """Retrieve endpoint for invalid AphiaID doesn't resolve to valid_id follow_valid query parameter is false."""
        resp = self.client.get(self.detail_url(self.invalid.aphia_id), {"follow_valid": "false"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["name"], "should_not_be_seen_if_follow_valid")
        self.assertEqual(resp.data[0]["language_code"], "eng")

    def test_retrieve_invalid_aphia_id_returns_400(self):
        """Test that the retrieve endpoint returns 400 Bad Request for an invalid AphiaID."""
        resp = self.client.get(self.detail_url("abc"))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("aphia_id", resp.data)
