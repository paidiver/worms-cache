"""Integration tests for RankViewSet endpoints."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Rank


class RankViewSetTests(APITestCase):
    """Integration tests for RankViewSet list/retrieve endpoints."""

    BASENAME = "ranks"

    def setUp(self):
        """Set up test data for RankViewSet tests."""
        self.rank1 = Rank.objects.create(rank_id=1, name="Kingdom")
        self.rank2 = Rank.objects.create(rank_id=2, name="Phylum")

    def list_url(self) -> str:
        """Helper method to construct the list URL for the RankViewSet.

        Returns:
            The URL for the list endpoint of the RankViewSet
        """
        return reverse(f"{self.BASENAME}-list")

    def detail_url(self, pk: int) -> str:
        """Helper method to construct the detail URL for a given PK.

        Args:
            pk: The primary key of the Rank entry to construct the URL for

        Returns:
            The URL for the detail endpoint of the RankViewSet for the given PK
        """
        return reverse(f"{self.BASENAME}-detail", kwargs={"pk": pk})

    def test_list_ranks(self):
        """Test that the list endpoint returns all rank entries."""
        resp = self.client.get(self.list_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertGreaterEqual(len(data), 2)

    def test_retrieve_rank(self):
        """Test that the retrieve endpoint returns the correct rank entry for a given PK."""
        resp = self.client.get(self.detail_url(self.rank1.pk))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.assertIn("name", resp.data)
        self.assertEqual(resp.data["name"], "Kingdom")

    def test_retrieve_rank_not_found(self):
        """Test that the retrieve endpoint returns 404 for a non-existent PK."""
        resp = self.client.get(self.detail_url(99999999))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
