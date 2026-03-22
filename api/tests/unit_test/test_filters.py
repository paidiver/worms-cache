"""Unit tests for candidate_name_rows service (filters)."""

from unittest.mock import MagicMock, call, patch

from django.test import TestCase

from api.services.filters import candidate_name_rows, rank_names_for_range
from api.utils.names import ParsedName


def _make_qs(return_rows: list[MagicMock]) -> MagicMock:
    """Helper function to create a mocked QuerySet that returns the specified rows when sliced or iterated over.

    Args:
        return_rows: The list of rows that the mocked QuerySet should return when sliced or iterated over.

    Returns:
        A MagicMock object that simulates a Django QuerySet with the specified behavior.
    """
    qs = MagicMock(name="QuerySetMock")

    qs.filter.return_value = qs
    qs.annotate.return_value = qs
    qs.order_by.return_value = qs
    qs.select_related.return_value = qs

    sliced = MagicMock(name="SlicedQuerySetMock")

    sliced.__iter__.side_effect = lambda: iter(return_rows)
    qs.__iter__.side_effect = lambda: iter(return_rows)

    qs.__getitem__.return_value = sliced

    return qs


class FiltersTests(TestCase):
    """Tests for candidate_name_rows branching logic using mocks."""

    def test_rank_names_for_range_returns_none_when_no_filtering_needed(self):
        """Rank_min=0 and rank_max=0 means no filtering => None."""
        out = rank_names_for_range(0, 0)
        self.assertIsNone(out)

    def test_rank_names_for_range_raises_when_min_greater_than_max(self):
        """If both >0 and rank_min > rank_max => ValueError."""
        with self.assertRaises(ValueError):
            rank_names_for_range(5, 3)

    @patch("api.services.filters.Rank")
    def test_rank_names_for_range_filters_min_only(self, mock_rank: MagicMock):
        """If only rank_min>0 => filter rank_id__gte then values_list."""
        qs = MagicMock(name="RankQS")
        qs.filter.return_value = qs
        qs.values_list.return_value = ["Species", "Genus"]
        mock_rank.objects.all.return_value = qs

        out = rank_names_for_range(10, 0)

        mock_rank.objects.all.assert_called_once()
        qs.filter.assert_called_once_with(rank_id__gte=10)
        qs.values_list.assert_called_once_with("name", flat=True)
        self.assertEqual(out, {"Species", "Genus"})

    @patch("api.services.filters.Rank")
    def test_rank_names_for_range_filters_max_only(self, mock_rank: MagicMock):
        """If only rank_max>0 => filter rank_id__lte then values_list."""
        qs = MagicMock(name="RankQS")
        qs.filter.return_value = qs
        qs.values_list.return_value = ["Family"]
        mock_rank.objects.all.return_value = qs

        out = rank_names_for_range(0, 7)

        mock_rank.objects.all.assert_called_once()
        qs.filter.assert_called_once_with(rank_id__lte=7)
        qs.values_list.assert_called_once_with("name", flat=True)
        self.assertEqual(out, {"Family"})

    @patch("api.services.filters.Rank")
    def test_rank_names_for_range_filters_min_and_max(self, mock_rank: MagicMock):
        """If both >0 and min<=max => apply both filters then values_list."""
        qs0 = MagicMock(name="RankQS0")
        qs1 = MagicMock(name="RankQS1")
        qs2 = MagicMock(name="RankQS2")

        mock_rank.objects.all.return_value = qs0
        qs0.filter.return_value = qs1
        qs1.filter.return_value = qs2
        qs2.values_list.return_value = ["Order", "Family"]

        out = rank_names_for_range(3, 10)

        mock_rank.objects.all.assert_called_once()
        qs0.filter.assert_called_once_with(rank_id__gte=3)
        qs1.filter.assert_called_once_with(rank_id__lte=10)
        qs2.values_list.assert_called_once_with("name", flat=True)
        self.assertEqual(out, {"Order", "Family"})

    @patch("api.services.filters.TrigramSimilarity")
    @patch("api.services.filters.NameIndex")
    @patch("api.services.filters.parse_genus_epithet")
    def test_one_token_uses_prefix2_when_prefix3_missing(
        self, mock_parse: MagicMock, mock_nameindex: MagicMock, mock_trigram: MagicMock
    ):
        """Test single token with genus_prefix3 missing but genus_prefix2 present.

        Args:
            mock_parse: Mock for the parse_genus_epithet function to control the parsed name output.
            mock_nameindex: Mock for the NameIndex model to control the QuerySet behavior.
            mock_trigram: Mock for the TrigramSimilarity function to verify it is called with expected arguments.
        """
        mock_parse.return_value = ParsedName(
            canonical_norm="gadus",
            genus_norm="gadus",
            genus_prefix3=None,
            genus_prefix2="ga",
            epithet_norm=None,
            canon_prefix3=None,
        )

        rows = [MagicMock(id=21)]
        base = _make_qs(return_rows=rows)
        mock_nameindex.objects.all.return_value = base

        out = candidate_name_rows("Gadus", limit=10)
        self.assertEqual(out, rows)

        base.select_related.assert_called_with("taxon")
        base.filter.assert_any_call(genus_prefix2="ga")
        mock_trigram.assert_any_call("genus_norm", "gadus")

    @patch("api.services.filters.TrigramSimilarity")
    @patch("api.services.filters.NameIndex")
    @patch("api.services.filters.parse_genus_epithet")
    def test_one_token_uses_base_queryset_when_no_prefixes(
        self, mock_parse: MagicMock, mock_nameindex: MagicMock, mock_trigram: MagicMock
    ):
        """Test single token with no genus prefixes.

        Args:
            mock_parse: Mock for the parse_genus_epithet function to control the parsed name output.
            mock_nameindex: Mock for the NameIndex model to control the QuerySet behavior.
            mock_trigram: Mock for the TrigramSimilarity function to verify it is called with expected arguments.
        """
        mock_parse.return_value = ParsedName(
            canonical_norm="gadus",
            genus_norm="gadus",
            genus_prefix3=None,
            genus_prefix2=None,
            epithet_norm=None,
            canon_prefix3=None,
        )

        rows = [MagicMock(id=31)]
        base = _make_qs(return_rows=rows)
        mock_nameindex.objects.all.return_value = base

        out = candidate_name_rows("Gadus", limit=10)
        self.assertEqual(out, rows)

        base.select_related.assert_called_with("taxon")

        self.assertNotIn(call(genus_prefix3="gad"), base.filter.call_args_list)
        self.assertNotIn(call(genus_prefix2="ga"), base.filter.call_args_list)

        self.assertIn(call(sim__gt=0.2), base.filter.call_args_list)

        mock_trigram.assert_any_call("genus_norm", "gadus")

    @patch("api.services.filters.TrigramSimilarity")
    @patch("api.services.filters.NameIndex")
    @patch("api.services.filters.parse_genus_epithet")
    def test_one_token_returns_prefix3_results_early(
        self, mock_parse: MagicMock, mock_nameindex: MagicMock, mock_trigram: MagicMock
    ):
        """Test single token with prefix3 present.

        Args:
            mock_parse: Mock for the parse_genus_epithet function to control the parsed name output.
            mock_nameindex: Mock for the NameIndex model to control the QuerySet behavior.
            mock_trigram: Mock for the TrigramSimilarity function to verify it is called with expected arguments.
        """
        mock_parse.return_value = ParsedName(
            canonical_norm="gadus",
            genus_norm="gadus",
            genus_prefix3="gad",
            genus_prefix2="ga",
            epithet_norm=None,
            canon_prefix3=None,
        )

        rows = [MagicMock(id=1), MagicMock(id=2)]
        base = _make_qs(return_rows=rows)
        mock_nameindex.objects.all.return_value = base

        out = candidate_name_rows("Gadus", limit=10)
        self.assertEqual(out, rows)

        base.select_related.assert_called_with("taxon")
        base.filter.assert_any_call(genus_prefix3="gad")

        mock_trigram.assert_any_call("genus_norm", "gadus")
        base.filter.assert_any_call(sim__gt=0.2)
        base.order_by.assert_called_with("-sim")

    @patch("api.services.filters.TrigramSimilarity")
    @patch("api.services.filters.NameIndex")
    @patch("api.services.filters.parse_genus_epithet")
    def test_one_token_falls_back_to_canonical_similarity_when_prefix_query_empty(
        self, mock_parse: MagicMock, mock_nameindex: MagicMock, mock_trigram: MagicMock
    ):
        """Test single token with prefix3 present and fallback to canonical similarity.

        Args:
            mock_parse: Mock for the parse_genus_epithet function to control the parsed name output.
            mock_nameindex: Mock for the NameIndex model to control the QuerySet behavior.
            mock_trigram: Mock for the TrigramSimilarity function to verify it is called with expected arguments.
        """
        mock_parse.return_value = ParsedName(
            canonical_norm="gadus",
            genus_norm="gadus",
            genus_prefix3="gad",
            genus_prefix2="ga",
            epithet_norm=None,
            canon_prefix3=None,
        )

        qs_prefix_empty = _make_qs(return_rows=[])
        qs_canon = _make_qs(return_rows=[MagicMock(id=7)])

        base = MagicMock(name="BaseQS")
        base.select_related.return_value = base

        base.filter.return_value = qs_prefix_empty
        base.annotate.return_value = qs_canon

        mock_nameindex.objects.all.return_value = base

        out = candidate_name_rows("Gadus", limit=10)
        self.assertEqual(len(out), 1)

        base.select_related.assert_called_with("taxon")
        base.filter.assert_any_call(genus_prefix3="gad")

        mock_trigram.assert_any_call("genus_norm", "gadus")
        mock_trigram.assert_any_call("canonical_norm", "gadus")

        self.assertGreaterEqual(mock_trigram.call_count, 2)

    @patch("api.services.filters.TrigramSimilarity")
    @patch("api.services.filters.NameIndex")
    @patch("api.services.filters.parse_genus_epithet")
    def test_two_tokens_prefers_exact_genus_norm_then_similarity(
        self, mock_parse: MagicMock, mock_nameindex: MagicMock, mock_trigram: MagicMock
    ):
        """Test two tokens with exact genus norm and fallback to canonical similarity.

        Args:
            mock_parse: Mock for the parse_genus_epithet function to control the parsed name output.
            mock_nameindex: Mock for the NameIndex model to control the QuerySet behavior.
            mock_trigram: Mock for the TrigramSimilarity function to verify it is called with expected arguments.
        """
        mock_parse.return_value = ParsedName(
            canonical_norm="gadus morhua",
            genus_norm="gadus",
            genus_prefix3="gad",
            genus_prefix2="ga",
            epithet_norm="morhua",
            canon_prefix3=None,
        )

        rows = [MagicMock(id=3)]
        qs = _make_qs(return_rows=rows)

        base = MagicMock(name="BaseQS")
        base.select_related.return_value = base
        base.filter.return_value = qs
        mock_nameindex.objects.all.return_value = base

        out = candidate_name_rows("gadus morhua", limit=5)
        self.assertEqual(out, rows)

        base.select_related.assert_called_with("taxon")
        base.filter.assert_called_with(genus_norm="gadus")
        mock_trigram.assert_any_call("canonical_norm", "gadus morhua")
        qs.filter.assert_any_call(sim__gt=0.2)
        qs.order_by.assert_called_with("-sim")

    @patch("api.services.filters.TrigramSimilarity")
    @patch("api.services.filters.NameIndex")
    @patch("api.services.filters.parse_genus_epithet")
    def test_two_tokens_falls_back_to_prefix3_when_genus_norm_returns_no_rows(
        self, mock_parse: MagicMock, mock_nameindex: MagicMock, mock_trigram: MagicMock
    ):
        """Test two tokens with empty genus_norm and fallback to genus_prefix3.

        Args:
            mock_parse: Mock for the parse_genus_epithet function to control the parsed name output.
            mock_nameindex: Mock for the NameIndex model to control the QuerySet behavior.
            mock_trigram: Mock for the TrigramSimilarity function to verify it is called with expected arguments.
        """
        mock_parse.return_value = ParsedName(
            canonical_norm="gadus morhua",
            genus_norm="gadus",
            genus_prefix3="gad",
            genus_prefix2="ga",
            epithet_norm="morhua",
            canon_prefix3=None,
        )

        qs_genus_empty = _make_qs(return_rows=[])
        qs_prefix = _make_qs(return_rows=[MagicMock(id=9)])

        base = MagicMock(name="BaseQS")
        base.select_related.return_value = base
        mock_nameindex.objects.all.return_value = base

        def filter_side_effect(**kwargs):
            if kwargs == {"genus_norm": "gadus"}:
                return qs_genus_empty
            if kwargs == {"genus_prefix3": "gad"}:
                return qs_prefix
            raise AssertionError(f"Unexpected filter kwargs: {kwargs}")

        base.filter.side_effect = filter_side_effect

        out = candidate_name_rows("gadus morhua", limit=10)
        self.assertEqual(len(out), 1)

        base.select_related.assert_called_with("taxon")
        base.filter.assert_any_call(genus_norm="gadus")
        base.filter.assert_any_call(genus_prefix3="gad")

        mock_trigram.assert_any_call("canonical_norm", "gadus morhua")
        self.assertGreaterEqual(mock_trigram.call_count, 1)

    @patch("api.services.filters.TrigramSimilarity")
    @patch("api.services.filters.NameIndex")
    @patch("api.services.filters.parse_genus_epithet")
    def test_final_fallback_is_canonical_similarity(
        self, mock_parse: MagicMock, mock_nameindex: MagicMock, mock_trigram: MagicMock
    ):
        """Test final fallback to canonical similarity when genus_norm and genus_prefix3 are missing.

        Args:
            mock_parse: Mock for the parse_genus_epithet function to control the parsed name output.
            mock_nameindex: Mock for the NameIndex model to control the QuerySet behavior.
            mock_trigram: Mock for the TrigramSimilarity function to verify it is called with expected arguments.
        """
        mock_parse.return_value = ParsedName(
            canonical_norm="unknown taxon",
            genus_norm=None,
            genus_prefix3=None,
            genus_prefix2=None,
            epithet_norm="taxon",
            canon_prefix3=None,
        )

        rows = [MagicMock(id=11), MagicMock(id=12)]
        base = MagicMock(name="BaseQS")
        base.select_related.return_value = base

        qs = _make_qs(return_rows=rows)
        base.annotate.return_value = qs

        mock_nameindex.objects.all.return_value = base

        out = candidate_name_rows("unknown taxon", limit=2)
        self.assertEqual(out, rows)

        base.select_related.assert_called_with("taxon")
        mock_trigram.assert_any_call("canonical_norm", "unknown taxon")
        qs.filter.assert_any_call(sim__gt=0.2)
        qs.order_by.assert_called_with("-sim")
        qs.__getitem__.assert_called()
