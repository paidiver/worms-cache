"""Unit tests for rebuild_name_index service."""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from api.models import Taxon
from api.models.name_index import NameIndex, NameType
from api.services.rebuild_name_index import rebuild_name_index


class RebuildNameIndexTests(TestCase):
    """Tests for rebuild_name_index()."""

    def setUp(self):
        """Set up test data for rebuild_name_index tests."""
        self.valid = Taxon.objects.create(
            aphia_id=1,
            scientific_name="Gadus morhua",
            rank="Species",
            parent=None,
        )

        self.syn = Taxon.objects.create(
            aphia_id=2,
            scientific_name="Gadus morhua (syn)",
            rank="Species",
            parent=None,
            valid_taxon=self.valid,
        )

        self.other = Taxon.objects.create(
            aphia_id=3,
            scientific_name="Animalia",
            rank="Kingdom",
            parent=None,
        )

        NameIndex.objects.create(
            taxon_id=999,
            name_type=NameType.ACCEPTED,
            name_raw="Old row",
            canonical_norm="old",
            genus_norm="old",
            epithet_norm=None,
            genus_prefix2=None,
            genus_prefix3=None,
            canon_prefix3=None,
        )

    @patch("api.services.rebuild_name_index.parse_genus_epithet")
    def test_rebuild_clears_table_and_creates_expected_rows(self, mock_parse: MagicMock):
        """Test that rebuild_name_index() clears the NameIndex table and creates expected rows based on Taxon data.

        Args:
            mock_parse: The mocked parse_genus_epithet function.
        """

        def parse_side_effect(name: str):
            return MagicMock(
                canonical_norm=f"canon::{name.lower()}",
                genus_norm="gadus" if "gadus" in name.lower() else "animalia",
                epithet_norm="morhua" if "morhua" in name.lower() else None,
                genus_prefix2="ga" if "gadus" in name.lower() else "an",
                genus_prefix3="gad" if "gadus" in name.lower() else "ani",
                canon_prefix3="can",
            )

        mock_parse.side_effect = parse_side_effect

        rebuild_name_index()

        self.assertFalse(NameIndex.objects.filter(taxon_id=999).exists())

        accepted = NameIndex.objects.filter(name_type=NameType.ACCEPTED).order_by("taxon_id")
        self.assertEqual(accepted.count(), 3)
        self.assertEqual(list(accepted.values_list("taxon_id", flat=True)), [1, 2, 3])

        syn_rows = NameIndex.objects.filter(name_type=NameType.SYNONYM)
        self.assertEqual(syn_rows.count(), 1)
        self.assertEqual(syn_rows.first().taxon_id, self.valid.aphia_id)
        self.assertEqual(syn_rows.first().name_raw, self.syn.scientific_name)

        row = NameIndex.objects.get(taxon_id=self.valid.aphia_id, name_type=NameType.ACCEPTED)
        self.assertEqual(row.name_raw, self.valid.scientific_name)
        self.assertTrue(row.canonical_norm.startswith("canon::"))
        self.assertEqual(row.genus_prefix3, "gad")

        self.assertEqual(mock_parse.call_count, 3)

    @patch("api.services.rebuild_name_index.NameIndex.objects.bulk_create")
    @patch("api.services.rebuild_name_index.parse_genus_epithet")
    def test_rebuild_uses_bulk_create_with_ignore_conflicts(self, mock_parse: MagicMock, mock_bulk_create: MagicMock):
        """Test that rebuild_name_index() uses bulk_create with ignore_conflicts=True when creating NameIndex rows.

        Args:
            mock_parse: The mocked parse_genus_epithet function.
            mock_bulk_create: The mocked NameIndex.objects.bulk_create method.
        """
        mock_parse.return_value = MagicMock(
            canonical_norm="canon",
            genus_norm="g",
            epithet_norm=None,
            genus_prefix2="g1",
            genus_prefix3="g12",
            canon_prefix3="can",
        )

        rebuild_name_index()

        self.assertGreaterEqual(mock_bulk_create.call_count, 1)
        for _, kwargs in mock_bulk_create.call_args_list:
            self.assertIn("ignore_conflicts", kwargs)
            self.assertTrue(kwargs["ignore_conflicts"])

    @patch("api.services.rebuild_name_index.parse_genus_epithet")
    def test_rebuild_creates_synonym_only_when_valid_taxon_differs(self, mock_parse: MagicMock):
        """rebuild_name_index() creates a SYNONYM row only when the valid_taxon_id differs from the taxon own aphia_id.

        Args:
            mock_parse: The mocked parse_genus_epithet function.
        """
        mock_parse.return_value = MagicMock(
            canonical_norm="canon",
            genus_norm="x",
            epithet_norm=None,
            genus_prefix2="xx",
            genus_prefix3="xxx",
            canon_prefix3="can",
        )

        rebuild_name_index()

        self.assertEqual(NameIndex.objects.filter(name_type=NameType.SYNONYM).count(), 1)
        self.assertEqual(NameIndex.objects.filter(name_type=NameType.ACCEPTED).count(), 3)

    @patch("api.services.rebuild_name_index.CHUNK_SIZE", 1)
    @patch("api.services.rebuild_name_index.parse_genus_epithet")
    def test_rebuild_change_chunk_size(self, mock_parse: MagicMock):
        """Test that rebuild_name_index() processes Taxon entries in chunks when CHUNK_SIZE is set to a low value.

        Args:
            mock_parse: The mocked parse_genus_epithet function.
        """
        mock_parse.return_value = MagicMock(
            canonical_norm="canon",
            genus_norm="x",
            epithet_norm=None,
            genus_prefix2="xx",
            genus_prefix3="xxx",
            canon_prefix3="can",
        )
        rebuild_name_index()

        self.assertEqual(NameIndex.objects.filter(name_type=NameType.SYNONYM).count(), 1)
        self.assertEqual(NameIndex.objects.filter(name_type=NameType.ACCEPTED).count(), 3)
