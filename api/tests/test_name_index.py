"""Integration tests for NameIndexViewSet endpoints."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import NameIndex
from api.models.taxon import Taxon


class NameIndexViewSetTests(APITestCase):
    """Integration tests for NameIndexViewSet list/retrieve endpoints."""

    BASENAME = "name_indexes"

    def setUp(self):
        """Set up test data for NameIndexViewSet tests."""
        self.taxon1 = Taxon.objects.create(
            aphia_id=100,
            scientific_name="Animalia",
            rank="Kingdom",
            parent=None,
        )
        self.taxon2 = Taxon.objects.create(
            aphia_id=101,
            scientific_name="Animalia",
            rank="Kingdom",
            parent=None,
        )
        self.n1 = NameIndex.objects.create(name_raw="Gadus morhua", taxon_id=self.taxon1.aphia_id)
        self.n2 = NameIndex.objects.create(name_raw="Pleuronectes platessa", taxon_id=self.taxon2.aphia_id)

    def list_url(self) -> str:
        """Helper method to construct the list URL for the NameIndexViewSet.

        Returns:
            The URL for the list endpoint of the NameIndexViewSet
        """
        return reverse(f"{self.BASENAME}-list")

    def detail_url(self, pk: int) -> str:
        """Helper method to construct the detail URL for a given PK.

        Args:
            pk: The primary key of the NameIndex entry to construct the URL for

        Returns:
            The URL for the detail endpoint of the NameIndexViewSet for the given PK
        """
        return reverse(f"{self.BASENAME}-detail", kwargs={"pk": pk})

    def test_list_name_index(self):
        """Test that the list endpoint returns all name index entries."""
        resp = self.client.get(self.list_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertGreaterEqual(len(data), 2)

    def test_retrieve_name_index(self):
        """Test that the retrieve endpoint returns the correct name index entry for a given PK."""
        resp = self.client.get(self.detail_url(self.n1.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.assertIn("name_raw", resp.data)
        self.assertEqual(resp.data["name_raw"], "Gadus morhua")

    def test_retrieve_name_index_not_found(self):
        """Test that the retrieve endpoint returns 404 for a non-existent PK."""
        resp = self.client.get(self.detail_url(99999999))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
