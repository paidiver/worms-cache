"""Tests for TaxonViewSet endpoints and related logic."""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.models import Taxon
from api.models.name_index import NameIndex
from api.models.rank import Rank
from api.models.vernacular import Vernacular
from api.services.taxamatch_client import TaxamatchError
from api.views.taxon import _handle_scientific_name_input


class Row:
    """Helper class to represent a row of candidate name data for testing purposes."""

    def __init__(self, _id, taxon_id, name_raw):
        self.id = _id
        self.taxon_id = taxon_id
        self.name_raw = name_raw


class TaxonViewSetTests(APITestCase):
    """Integration tests for TaxonViewSet endpoints."""

    def setUp(self):
        """Set up test data for TaxonViewSet tests."""
        self.root = Taxon.objects.create(
            aphia_id=1,
            scientific_name="Animalia",
            rank="Kingdom",
            parent=None,
        )
        self.phylum = Taxon.objects.create(
            aphia_id=2,
            scientific_name="Chordata",
            rank="Phylum",
            parent=self.root,
        )
        self.leaf = Taxon.objects.create(
            aphia_id=3,
            scientific_name="Gadus morhua",
            rank="Species",
            parent=self.phylum,
        )

        self.invalid = Taxon.objects.create(
            aphia_id=999,
            scientific_name="Gadus morhua (syn)",
            rank="Species",
            parent=self.phylum,
            valid_taxon=self.leaf,
        )
        Rank.objects.create(rank_id=10, name="Species")
        Rank.objects.create(rank_id=20, name="Genus")
        Rank.objects.create(rank_id=30, name="Family")

        NameIndex.objects.create(
            id=10,
            taxon=self.leaf,
            name_raw="Gadus morhua",
            canonical_norm="gadus morhua",
            genus_norm="gadus",
            genus_prefix3="gad",
            genus_prefix2="ga",
        )
        NameIndex.objects.create(
            id=11,
            taxon=self.invalid,
            name_raw="Gadus morhua (syn)",
            canonical_norm="gadus morhua syn",
            genus_norm="gadus",
            genus_prefix3="gad",
            genus_prefix2="ga",
        )

        Vernacular.objects.create(taxon=self.leaf, name="cod", language_code="eng")
        Vernacular.objects.create(taxon=self.leaf, name="bacalhau", language_code="por")

    def list_url(self) -> str:
        """Return the URL for the TaxonViewSet list endpoint.

        Returns:
            str: The URL for the TaxonViewSet list endpoint.
        """
        return reverse("taxa-list")

    def detail_url(self, aphia_id: int) -> str:
        """Return the URL for the TaxonViewSet detail endpoint for a given AphiaID.

        Args:
            aphia_id: The AphiaID of the taxon to retrieve.

        Returns:
            str: The URL for the TaxonViewSet detail endpoint for the given AphiaID
        """
        return reverse("taxa-detail", kwargs={"aphia_id": aphia_id})

    def classification_url(self, aphia_id: int) -> str:
        """Return the URL for the classification endpoint for a given AphiaID.

        Args:
            aphia_id: The AphiaID of the taxon to retrieve the classification for.

        Returns:
            str: The URL for the classification endpoint for the given AphiaID
        """
        return reverse("taxa-classification", kwargs={"aphia_id": aphia_id})

    def synonyms_url(self, aphia_id: int) -> str:
        """Return the URL for the synonyms endpoint for a given AphiaID.

        Args:
            aphia_id: The AphiaID of the taxon to retrieve synonyms for.

        Returns:
            str: The URL for the synonyms endpoint for the given AphiaID
        """
        return reverse("taxa-synonyms", kwargs={"aphia_id": aphia_id})

    def match_names_url(self) -> str:
        """Return the URL for the match names endpoint.

        Returns:
            str: The URL for the match names endpoint
        """
        return reverse("taxa-match-names")

    def match_names_pair_url(self) -> str:
        """Return the URL for the match names pair endpoint.

        Returns:
            str: The URL for the match names pair endpoint
        """
        return reverse("taxa-match-names-pair")

    def ajax_by_name_part_url(self, name_part: str) -> str:
        """Return the URL for the AJAX by name part endpoint.

        Args:
            name_part: The part of the scientific name to search for.

        Returns:
            str: The URL for the AJAX by name part endpoint with the given name part.
        """
        return reverse("taxa-ajax-by-name-part", kwargs={"NamePart": name_part})

    def test_list_taxa(self):
        """Test that the list endpoint returns taxa with expected fields and ordering."""
        resp = self.client.get(self.list_url())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        names = [t["scientificname"] if "scientificname" in t else t.get("scientific_name") for t in resp.data]
        self.assertTrue(any("Animalia" in (n or "") for n in names))

    def test_list_taxa_filters_scientific_name(self):
        """Test that the list endpoint can filter taxa by scientific name."""
        resp = self.client.get(self.list_url(), {"scientific_name": "gadus"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any("Gadus morhua" in (item.get("scientificname") or item.get("scientific_name", "")) for item in resp.data)
        )

    def test_list_taxa_filters_rank(self):
        """Test that the list endpoint can filter taxa by rank."""
        resp = self.client.get(self.list_url(), {"rank": "species"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for item in resp.data:
            self.assertEqual((item.get("rank") or "").lower(), "species")

    def test_retrieve_taxon_by_aphia_id(self):
        """Test that the detail endpoint returns the correct taxon for a given AphiaID."""
        resp = self.client.get(self.detail_url(self.leaf.aphia_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["AphiaID"], self.leaf.aphia_id)

    def test_retrieve_taxon_resolves_valid_taxon_field(self):
        """Test that the detail endpoint returns the valid taxon information when the taxon is a synonym."""
        resp = self.client.get(self.detail_url(self.invalid.aphia_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotEqual(resp.data["AphiaID"], self.leaf.aphia_id)
        self.assertEqual(resp.data["valid_AphiaID"], self.leaf.aphia_id)

    def test_retrieve_taxon_not_found(self):
        """Test that the detail endpoint returns 404 for a non-existent taxon."""
        resp = self.client.get(self.detail_url(123456789))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_taxon_invalid_id_returns_400(self):
        """Test that the detail endpoint returns 400 for an invalid AphiaID format."""
        resp = self.client.get(reverse("taxa-detail", kwargs={"aphia_id": "abc"}))
        self.assertIn(resp.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND))

    def test_classification_returns_nested_tree(self):
        """Test that the classification endpoint returns the correct nested classification tree for a given AphiaID."""
        resp = self.client.get(self.classification_url(self.leaf.aphia_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        data = resp.data
        self.assertEqual(data["AphiaID"], self.root.aphia_id)
        self.assertEqual(data["child"]["AphiaID"], self.phylum.aphia_id)
        self.assertEqual(data["child"]["child"]["AphiaID"], self.leaf.aphia_id)
        self.assertIsNone(data["child"]["child"]["child"])

    def test_classification_resolves_synonym(self):
        """Test that the classification endpoint resolves to the valid taxon when given an invalid/synonym AphiaID."""
        resp = self.client.get(self.classification_url(self.invalid.aphia_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        leaf = resp.data["child"]["child"]
        self.assertEqual(leaf["AphiaID"], self.invalid.aphia_id)

    def test_synonyms_returns_synonym_taxa(self):
        """Test that the synonyms endpoint returns taxa that are synonyms of the given AphiaID."""
        resp = self.client.get(self.synonyms_url(self.leaf.aphia_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        returned_ids = [item["AphiaID"] for item in resp.data]
        self.assertIn(self.invalid.aphia_id, returned_ids)

    def test_synonyms_returns_synonym_taxa_for_valid_taxon(self):
        """Test that the synonyms endpoint returns taxa that are synonyms of the given valid taxon."""
        resp = self.client.get(self.synonyms_url(self.invalid.aphia_id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        returned_ids = [item["AphiaID"] for item in resp.data]
        returned_valid_ids = [item["valid_AphiaID"] for item in resp.data]
        self.assertIn(self.invalid.aphia_id, returned_ids)
        self.assertTrue(all(vid == self.invalid.valid_taxon_id for vid in returned_valid_ids))

    @patch("api.views.taxon.candidate_name_rows")
    @patch("api.views.taxon.match_batch")
    def test_match_names_returns_200_with_results_when_taxamatch_matches(
        self, mock_match_batch: MagicMock, mock_candidate_name_rows: MagicMock
    ):
        """Match_names endpoint returns 200 with expected results when Taxamatch returns matched ID for candidate names.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
            mock_candidate_name_rows: The mocked candidate_name_rows function to control its behavior in the test.
        """
        mock_candidate_name_rows.return_value = [
            Row(10, self.leaf.aphia_id, "Gadus morhua"),
            Row(11, self.leaf.aphia_id, "Gadus morhua"),
        ]
        mock_match_batch.return_value = [{"matched_ids": [10]}]

        resp = self.client.get(self.match_names_url(), {"scientificnames[]": ["gadus morhua"], "max_results": 3})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.assertEqual(len(resp.data), 1)
        self.assertGreaterEqual(len(resp.data[0]), 1)
        self.assertEqual(resp.data[0][0]["AphiaID"], self.leaf.aphia_id)

        called_payload = mock_match_batch.call_args[0][0]
        self.assertEqual(called_payload[0]["input"], "Gadus morhua")

    @patch("api.views.taxon.candidate_name_rows")
    @patch("api.views.taxon.match_batch")
    def test_match_names_returns_204_when_taxamatch_returns_no_matched_ids(
        self, mock_match_batch: MagicMock, mock_candidate_name_rows: MagicMock
    ):
        """Match_names endpoint returns 204 when Taxamatch returns no matched IDs for candidate names.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
            mock_candidate_name_rows: The mocked candidate_name_rows function to control its behavior in the test.
        """
        mock_candidate_name_rows.return_value = [Row(10, self.leaf.aphia_id, "Gadus morhua")]
        mock_match_batch.return_value = [{"matched_ids": []}]

        resp = self.client.get(self.match_names_url(), {"scientificnames[]": ["gadus morhua"], "max_results": 3})
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    @patch("api.views.taxon.candidate_name_rows")
    @patch("api.views.taxon.match_batch")
    def test_match_names_returns_204_when_taxamatch_raises_error(
        self, mock_match_batch: MagicMock, mock_candidate_name_rows: MagicMock
    ):
        """Match_names endpoint returns 204 when Taxamatch raises an error.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
            mock_candidate_name_rows: The mocked candidate_name_rows function to control its behavior in the test.
        """
        mock_candidate_name_rows.return_value = [Row(10, self.leaf.aphia_id, "Gadus morhua")]
        mock_match_batch.side_effect = TaxamatchError("boom")

        resp = self.client.get(self.match_names_url(), {"scientificnames[]": ["gadus morhua"], "max_results": 3})
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    @patch("api.views.taxon.candidate_name_rows")
    @patch("api.views.taxon.match_batch")
    def test_match_names_returns_204_when_all_empty(
        self, mock_match_batch: MagicMock, mock_candidate_name_rows: MagicMock
    ):
        """Match_names endpoint returns 204 when all candidate_name_rows return empty lists.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
            mock_candidate_name_rows: The mocked candidate_name_rows function to control its behavior in the test.
        """
        mock_candidate_name_rows.return_value = []
        mock_match_batch.return_value = []

        resp = self.client.get(self.match_names_url(), {"scientificnames[]": ["doesnotexist"]})
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_match_names_rejects_more_than_limit(self):
        """Match_names endpoint returns 400 when more than the allowed number of names are submitted."""
        too_many = ["a b"] * 51
        resp = self.client.get(self.match_names_url(), [("scientificnames[]", n) for n in too_many])
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("names", resp.data)

    def test_ajax_by_name_part_returns_204_on_blank_namepart(self):
        """Ajax_by_name_part endpoint returns 204 when the name part is blank.

        This test ensures that the endpoint correctly handles cases where the
        name part is blank (e.g., spaces) and returns a 204 No Content response.
        """
        resp = self.client.get(self.ajax_by_name_part_url("   "))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    @patch("api.views.taxon.match_batch")
    def test_ajax_by_name_part_scientific_only_uses_candidate_name_rows_and_combines(self, mock_match_batch: MagicMock):
        """Test that the ajax_by_name_part endpoint with combine_vernaculars=false uses candidate_name_rows results.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
        """
        mock_match_batch.return_value = [{"matched_ids": []}]

        resp = self.client.get(
            self.ajax_by_name_part_url("gadus"),
            {
                "combine_vernaculars": "false",
                "max_matches": 20,
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        returned_ids = [t["AphiaID"] for t in resp.data]
        self.assertEqual(returned_ids, [self.leaf.aphia_id])

        self.assertEqual(mock_match_batch.call_count, 1)
        payload = mock_match_batch.call_args[0][0]
        self.assertEqual(payload[0]["input"], "gadus")
        self.assertTrue(len(payload[0]["candidates"]) >= 1)

    @patch("api.views.taxon.match_batch")
    def test_ajax_by_name_part_scientific_restrict_response(self, mock_match_batch: MagicMock):
        """Test that the ajax_by_name_part endpoint with combine_vernaculars=false and max_matches=1 restricts response.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
        """
        Taxon.objects.create(
            aphia_id=55,
            scientific_name="Gadus mora",
            rank="Species",
            parent=self.phylum,
        )
        mock_match_batch.return_value = [{"matched_ids": []}]

        resp = self.client.get(
            self.ajax_by_name_part_url("gadus"),
            {
                "combine_vernaculars": "false",
                "max_matches": 1,
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        returned_ids = [t["AphiaID"] for t in resp.data]
        self.assertEqual(returned_ids, [self.leaf.aphia_id])

        self.assertEqual(mock_match_batch.call_count, 1)
        payload = mock_match_batch.call_args[0][0]
        self.assertEqual(payload[0]["input"], "gadus")
        self.assertTrue(len(payload[0]["candidates"]) >= 1)

    @patch("api.views.taxon.match_batch")
    def test_ajax_by_name_part_includes_vernacular_when_enabled_and_language_filtered(
        self, mock_match_batch: MagicMock
    ):
        """Test that the ajax_by_name_part endpoint with combine_vernaculars=true includes vern filtered by language.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
        """
        mock_match_batch.return_value = [{"matched_ids": []}]

        resp = self.client.get(
            self.ajax_by_name_part_url("cod"),
            {
                "combine_vernaculars": "true",
                "languages[]": ["eng"],
                "max_matches": 20,
                "rank_min": 10,
                "rank_max": 10,
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        returned_ids = [t["AphiaID"] for t in resp.data]
        self.assertEqual(returned_ids, [self.leaf.aphia_id])

    @patch("api.views.taxon.match_batch")
    def test_ajax_by_name_part_excluded_ids_removes_results(self, mock_match_batch: MagicMock):
        """If the only combined result is excluded -> 204.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
        """
        mock_match_batch.return_value = [{"matched_ids": []}]

        resp = self.client.get(
            self.ajax_by_name_part_url("gadus"),
            {
                "combine_vernaculars": "false",
                "excluded_ids[]": [str(self.leaf.aphia_id)],
                "max_matches": 20,
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    @patch("api.views.taxon.match_batch")
    def test_ajax_by_name_part_with_wrong_excluded_ids(self, mock_match_batch: MagicMock):
        """If the only combined result is excluded -> 204.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
        """
        mock_match_batch.return_value = [{"matched_ids": []}]

        resp = self.client.get(
            self.ajax_by_name_part_url("gadus"),
            {
                "combine_vernaculars": "false",
                "excluded_ids[]": ["wrong_format"],
                "max_matches": 20,
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @patch("api.views.taxon.match_batch")
    def test_ajax_by_name_part_when_taxamatch_raises_error(
        self,
        mock_match_batch: MagicMock,
    ):
        """match_names catches TaxamatchError and treats as no results."""
        mock_match_batch.side_effect = TaxamatchError("boom")
        resp = self.client.get(
            self.ajax_by_name_part_url("gadus"),
            {
                "combine_vernaculars": "false",
                "excluded_ids[]": ["wrong_format"],
                "max_matches": 20,
            },
        )
        resp = self.client.get(self.match_names_url(), {"scientificnames[]": ["gadus morhua"], "max_results": 3})
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    @patch("api.views.taxon.match_batch")
    def test_match_names_pair(self, mock_match_batch: MagicMock):
        """Test that the match_names_pair endpoint returns correct match result for two scientific names.

        Args:
            mock_match_batch: The mocked match_batch function to control its behavior in the test.
        """
        mock_match_batch.return_value = [{"matched_ids": [1]}]

        resp = self.client.get(
            self.match_names_pair_url(),
            {"scientificname1": "gadus morhua", "scientificname2": "Gadus morhua"},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, {"match": True})

    def test_handle_scientific_name_input_capitalizes_genus_when_two_tokens(self):
        """Test that the function capitalizes the genus part of a scientific name when there are two tokens."""
        self.assertEqual(_handle_scientific_name_input("gadus morhua"), "Gadus morhua")

    def test_handle_scientific_name_input_does_not_change_one_token(self):
        """Test that the function does not change a scientific name with only one token."""
        self.assertEqual(_handle_scientific_name_input("gadus"), "gadus")

    def test_handle_scientific_name_input_strips(self):
        """Test that the function strips leading and trailing whitespace from the input name."""
        self.assertEqual(_handle_scientific_name_input("  gadus morhua  "), "Gadus morhua")


class IngestAphiaIdViewTests(APITestCase):
    """Tests for the ingest AphiaID endpoint."""

    def setUp(self):
        """Set up test data and a test user for authentication."""
        self.user = User.objects.create_user(username="testuser", password="testpassword")

    def ingest_url(self) -> str:
        """Return the URL for the ingest endpoint.

        Returns:
            str: The URL for the ingest endpoint.
        """
        return reverse("taxa-ingest")

    @patch("api.views.taxon.IngestAphiaId")
    def test_ingest_returns_202_when_authenticated(self, mock_ingest_class: MagicMock):
        """Test that authenticated POST to ingest endpoint returns 202 with ingested taxa.

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

        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.ingest_url(), {"aphia_id": 12345}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        mock_ingest_class.assert_called_once_with(aphia_ids={12345})
        mock_instance.ingest_aphia_id.assert_called_once_with(12345)

    def test_ingest_returns_401_when_unauthenticated(self):
        """Test that unauthenticated POST to ingest endpoint returns 401."""
        resp = self.client.post(self.ingest_url(), {"aphia_id": 12345}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ingest_returns_400_for_invalid_aphia_id(self):
        """Test that POST to ingest endpoint with invalid aphia_id returns 400."""
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.ingest_url(), {"aphia_id": -1}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ingest_returns_400_when_aphia_id_missing(self):
        """Test that POST to ingest endpoint without aphia_id returns 400."""
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.ingest_url(), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
