"""Unit tests for the IngestAphiaId service, which ingests WoRMS records by AphiaID."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from api.models import Taxon, Vernacular
from api.models.rank import Rank
from api.services.ingest_aphia_id import IngestAphiaId

LEAF_ID = 10
ROOT_ID = 1
PHYLUM_ID = 2
RECORD_BY_ID = {
    ROOT_ID: {
        "AphiaID": ROOT_ID,
        "scientificname": "Animalia",
        "rank": "Kingdom",
        "status": "accepted",
        "modified": None,
        "url": "https://worms.test/root",
    },
    PHYLUM_ID: {
        "AphiaID": PHYLUM_ID,
        "scientificname": "Chordata",
        "rank": "Phylum",
        "status": "accepted",
        "modified": None,
        "url": "https://worms.test/phylum",
    },
    LEAF_ID: {
        "AphiaID": LEAF_ID,
        "scientificname": "Gadus morhua",
        "rank": "Species",
        "status": "accepted",
        "modified": "2020-01-01T00:00:00Z",
        "url": "https://worms.test/leaf",
    },
}


CLASSIFICATION_RETURN_VALUE = {
    "AphiaID": ROOT_ID,
    "rank": "Kingdom",
    "scientificname": "Animalia",
    "child": {
        "AphiaID": PHYLUM_ID,
        "rank": "Phylum",
        "scientificname": "Chordata",
        "child": {
            "AphiaID": LEAF_ID,
            "rank": "Species",
            "scientificname": "Gadus morhua",
            "child": None,
        },
    },
}

VERNACULARS_RETURN_VALUE = [
    {"vernacular": "cod", "language_code": "eng"},
    {"vernacular": " bacalhau ", "language_code": "por"},
    {"vernacular": "", "language_code": "eng"},
    {"vernacular": "no-lang", "language_code": ""},
]

SYNONYMS_RETURN_VALUE = [
    {
        "AphiaID": 999,
        "scientificname": "Gadus morhua (syn)",
        "rank": "Species",
        "status": "unaccepted",
        "valid_AphiaID": LEAF_ID,
        "valid_name": "Gadus morhua",
        "modified": None,
        "url": "https://worms.test/syn",
    }
]


class IngestAphiaIdTests(TestCase):
    """Unit tests for the IngestAphiaId service using a mocked WoRMS client."""

    @patch("api.services.ingest_aphia_id.WoRMSClient")
    def test_ingest_accepted_taxon_creates_chain_vernaculars_and_synonyms(self, MockClient: MagicMock):
        """Tests that ingesting an accepted AphiaID creates/updates the taxon record, classification chain, vernacular.

        Args:
            MockClient: The mocked WoRMSClient class, injected by the @patch decorator.
        """
        client = MockClient.return_value

        leaf_id = LEAF_ID
        root_id = ROOT_ID
        phylum_id = PHYLUM_ID

        record_by_id = RECORD_BY_ID

        def record_side_effect(aid: int) -> dict:
            """Side effect function for client.record() that returns the corresponding record from record_by_id.

            Args:
                aid: The AphiaID for which to return the record

            Returns:
                The record dictionary corresponding to the input AphiaID, or None if not found
            """
            return record_by_id.get(int(aid))

        client.record.side_effect = record_side_effect

        client.classification.return_value = CLASSIFICATION_RETURN_VALUE

        client.vernaculars.return_value = VERNACULARS_RETURN_VALUE

        client.synonyms.return_value = SYNONYMS_RETURN_VALUE

        Taxon.objects.create(aphia_id=leaf_id, scientific_name="OLD", rank="Species", status="accepted")
        old_leaf = Taxon.objects.get(aphia_id=leaf_id)
        Vernacular.objects.create(taxon=old_leaf, name="old", language_code="eng")

        svc = IngestAphiaId({leaf_id})
        leafs = svc.ingest_aphia_id(leaf_id)

        self.assertTrue(Taxon.objects.filter(aphia_id=root_id).exists())
        self.assertTrue(Taxon.objects.filter(aphia_id=phylum_id).exists())
        self.assertTrue(Taxon.objects.filter(aphia_id=leaf_id).exists())
        self.assertTrue(Taxon.objects.filter(aphia_id=999).exists())

        root = Taxon.objects.get(aphia_id=root_id)
        phylum = Taxon.objects.get(aphia_id=phylum_id)
        leaf = Taxon.objects.get(aphia_id=leaf_id)

        self.assertEqual(phylum.parent_id, root.aphia_id)
        self.assertEqual(leaf.parent_id, phylum.aphia_id)

        self.assertEqual(leaf.scientific_name, "Gadus morhua")
        self.assertEqual(leaf.rank, "Species")
        self.assertEqual(leaf.status, "accepted")

        vern = Vernacular.objects.filter(taxon=leaf).order_by("language_code")
        self.assertEqual(vern.count(), 2)
        self.assertEqual([(v.name, v.language_code) for v in vern], [("cod", "eng"), ("bacalhau", "por")])
        self.assertFalse(Vernacular.objects.filter(taxon=leaf, name="old").exists())

        self.assertTrue(any(t.aphia_id == leaf_id for t in leafs))

        client.record.assert_any_call(leaf_id)
        client.classification.assert_called_with(leaf_id)
        client.vernaculars.assert_called_with(leaf_id)
        client.synonyms.assert_called()

    @patch("api.services.ingest_aphia_id.WoRMSClient")
    def test_ingest_rank(self, MockClient: MagicMock):
        """Tests that ingesting rank.

        Args:
            MockClient: The mocked WoRMSClient class, injected by the @patch decorator.
        """
        client = MockClient.return_value

        client.classification.return_value = CLASSIFICATION_RETURN_VALUE

        client.vernaculars.return_value = VERNACULARS_RETURN_VALUE

        client.synonyms.return_value = SYNONYMS_RETURN_VALUE

        client.ranks.return_value = [
            {"taxonRankID": 1, "taxonRank": "Kingdom"},
            {"taxonRankID": 2, "taxonRank": "Phylum"},
            {"taxonRankID": 3, "taxonRank": "Class"},
            {"taxonRankID": 3, "taxonRank": "Class"},
        ]

        svc = IngestAphiaId({LEAF_ID})
        svc.ingest(add_ranks=True)

        client.ranks.assert_called()
        self.assertTrue(Rank.objects.filter(rank_id=1).exists())
        self.assertTrue(Rank.objects.filter(rank_id=2).exists())
        self.assertTrue(Rank.objects.filter(rank_id=3).exists())
        self.assertEqual(Rank.objects.get(rank_id=1).name, "Kingdom")
        self.assertEqual(len(Rank.objects.all()), 3)

    @patch("api.services.ingest_aphia_id.WoRMSClient")
    def test_ingest_rank_empty_ranks_response(self, MockClient: MagicMock):
        """Tests that ingesting rank with an empty response from the client raises a ValueError.

        Args:
            MockClient: The mocked WoRMSClient class, injected by the @patch decorator.
        """
        client = MockClient.return_value
        client.ranks.return_value = None

        svc = IngestAphiaId({LEAF_ID})

        with self.assertRaises(ValueError):
            svc.ingest(add_ranks=True)

    @patch("api.services.ingest_aphia_id.WoRMSClient")
    def test_ingest_unaccepted_taxon_also_ingests_valid_taxon(self, MockClient: MagicMock):
        """Tests that ingesting an unaccepted AphiaID also ingests the valid taxon it points to.

        And that the unaccepted taxon record correctly references the valid taxon.

        Args:
            MockClient: The mocked WoRMSClient class, injected by the @patch decorator. MockClient.return_value is the
        instance used by the service.
        """
        client = MockClient.return_value

        invalid_id = 200
        valid_id = 201

        invalid_record = {
            "AphiaID": invalid_id,
            "scientificname": "Bad name",
            "rank": "Species",
            "status": "unaccepted",
            "valid_AphiaID": valid_id,
            "valid_name": "Good name",
            "modified": None,
            "url": "https://worms.test/invalid",
        }
        valid_record = {
            "AphiaID": valid_id,
            "scientificname": "Good name",
            "rank": "Species",
            "status": "accepted",
            "modified": None,
            "url": "https://worms.test/valid",
        }

        def record_side_effect(aid: int) -> dict:
            """Side effect function for client.record() that returns the corresponding record based on input AphiaID.

            Args:
                aid: The AphiaID for which to return the record

            Returns:
                The record dictionary corresponding to the input AphiaID, or None if not found
            """
            if int(aid) == invalid_id:
                return invalid_record
            if int(aid) == valid_id:
                return valid_record
            return None

        client.record.side_effect = record_side_effect
        client.classification.return_value = None
        client.vernaculars.return_value = []
        client.synonyms.return_value = []

        svc = IngestAphiaId({invalid_id})
        leafs = svc.ingest_aphia_id(invalid_id)

        self.assertTrue(Taxon.objects.filter(aphia_id=invalid_id).exists())
        self.assertTrue(Taxon.objects.filter(aphia_id=valid_id).exists())

        invalid = Taxon.objects.get(aphia_id=invalid_id)
        valid = Taxon.objects.get(aphia_id=valid_id)

        self.assertIsNotNone(invalid.valid_taxon)
        self.assertEqual(invalid.valid_taxon_id, valid.aphia_id)

        client.classification.assert_called_with(valid_id)
        client.vernaculars.assert_called_with(valid_id)

        self.assertTrue(any(t.aphia_id == invalid_id for t in leafs))
        self.assertTrue(any(t.aphia_id == valid_id for t in leafs))

    @patch("api.services.ingest_aphia_id.WoRMSClient")
    def test_ingest_aphia_id_raises_if_no_record(self, MockClient: MagicMock):
        """Tests that ingesting an AphiaID for which the WoRMS client returns no record raises a ValueError.

        Args:
            MockClient: The mocked WoRMSClient class, injected by the @patch decorator.
        """
        client = MockClient.return_value
        client.record.return_value = None

        svc = IngestAphiaId({123})
        with self.assertRaises(ValueError):
            svc.ingest_aphia_id(123)

        svc.ingest()
        self.assertFalse(Taxon.objects.exists())

    @patch("api.services.ingest_aphia_id.WoRMSClient")
    def test_atomic_rolls_back_on_error(self, MockClient: MagicMock):
        """Tests that if an error occurs during ingestion of an AphiaID.

        Args:
            MockClient: The mocked WoRMSClient class, injected by the @patch decorator.
        """
        client = MockClient.return_value
        client.record.return_value = {
            "AphiaID": 10,
            "scientificname": "Gadus morhua",
            "rank": "Species",
            "status": "accepted",
            "modified": None,
            "url": "https://worms.test/leaf",
        }

        client.classification.side_effect = RuntimeError("boom")

        svc = IngestAphiaId({10})
        with self.assertRaises(RuntimeError):
            svc.ingest_aphia_id(10)

        self.assertFalse(Taxon.objects.filter(aphia_id=10).exists())
