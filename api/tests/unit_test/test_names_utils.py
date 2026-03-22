"""Unit tests for name parsing/normalization utilities."""

from django.test import SimpleTestCase

from api.utils.names import ParsedName, _ascii_fold, normalize_scientific_name, parse_genus_epithet


class NameUtilsTests(SimpleTestCase):
    """Tests for name parsing and normalization utilities in api.utils.names."""

    def test_ascii_fold_removes_diacritics(self):
        """Test that _ascii_fold() removes diacritics and non-ASCII characters from a string."""
        self.assertEqual(_ascii_fold("Gádùs"), "Gadus")
        self.assertEqual(_ascii_fold("São Tomé"), "Sao Tome")

    def test_normalize_scientific_name_basic(self):
        """Test that normalize_scientific_name() lowercases and trims whitespace."""
        self.assertEqual(normalize_scientific_name("Gadus morhua"), "gadus morhua")
        self.assertEqual(normalize_scientific_name("  Gadus   morhua  "), "gadus morhua")

    def test_normalize_scientific_name_punctuation_removed(self):
        """Test that normalize_scientific_name() removes punctuation."""
        self.assertEqual(normalize_scientific_name("Gadus, morhua."), "gadus morhua")
        self.assertEqual(normalize_scientific_name("Gadus (morhua)"), "gadus morhua")

    def test_normalize_scientific_name_keeps_hyphen(self):
        """Test that normalize_scientific_name() keeps hyphens in the normalized name."""
        self.assertEqual(normalize_scientific_name("Acantho-pecten"), "acantho-pecten")

    def test_normalize_scientific_name_ascii_folding_and_lower(self):
        """Test that normalize_scientific_name() applies ASCII folding and lowercasing together."""
        self.assertEqual(normalize_scientific_name("GÁDÙS MÖRHÛA"), "gadus morhua")

    def test_normalize_scientific_name_empty_or_none(self):
        """Test that normalize_scientific_name() handles empty or None input."""
        self.assertEqual(normalize_scientific_name(""), "")
        self.assertEqual(normalize_scientific_name(None), "")

    def test_parse_genus_epithet_two_tokens(self):
        """Test that parse_genus_epithet() correctly parses a scientific name with two tokens into genus and epithet."""
        parsed = parse_genus_epithet("Gadus morhua")
        self.assertIsInstance(parsed, ParsedName)
        self.assertEqual(parsed.canonical_norm, "gadus morhua")
        self.assertEqual(parsed.genus_norm, "gadus")
        self.assertEqual(parsed.epithet_norm, "morhua")
        self.assertEqual(parsed.genus_prefix2, "ga")
        self.assertEqual(parsed.genus_prefix3, "gad")
        self.assertEqual(parsed.canon_prefix3, "gad")

    def test_parse_genus_epithet_one_token(self):
        """Test that parse_genus_epithet() parses a scientific name with one token into genus and no epithet."""
        parsed = parse_genus_epithet("Gadus")
        self.assertEqual(parsed.canonical_norm, "gadus")
        self.assertEqual(parsed.genus_norm, "gadus")
        self.assertIsNone(parsed.epithet_norm)
        self.assertEqual(parsed.genus_prefix2, "ga")
        self.assertEqual(parsed.genus_prefix3, "gad")
        self.assertEqual(parsed.canon_prefix3, "gad")

    def test_parse_genus_epithet_short_genus_prefixes(self):
        """Test that parse_genus_epithet handles short genus names without enough char for 2 or 3 letter prefixes."""
        parsed = parse_genus_epithet("Ox")
        self.assertEqual(parsed.canonical_norm, "ox")
        self.assertEqual(parsed.genus_norm, "ox")
        self.assertIsNone(parsed.genus_prefix3)
        self.assertEqual(parsed.genus_prefix2, "ox")
        self.assertIsNone(parsed.canon_prefix3)

    def test_parse_genus_epithet_no_tokens(self):
        """Test that parse_genus_epithet() handles an input string with no tokens."""
        parsed = parse_genus_epithet("   ")
        self.assertEqual(parsed.canonical_norm, "")
        self.assertIsNone(parsed.genus_norm)
        self.assertIsNone(parsed.epithet_norm)
        self.assertIsNone(parsed.genus_prefix2)
        self.assertIsNone(parsed.genus_prefix3)
        self.assertIsNone(parsed.canon_prefix3)
