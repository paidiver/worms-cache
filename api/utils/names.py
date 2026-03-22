"""Utility functions for normalizing and parsing scientific names for the WoRMS cache API."""

import re
import unicodedata
from dataclasses import dataclass

_ws = re.compile(r"\s+")
_punct = re.compile(r"[^\w\s-]+", re.UNICODE)

PREFIX_LEN_2 = 2
PREFIX_LEN_3 = 3


@dataclass
class ParsedName:
    """Structured representation of a parsed scientific name, normalized forms and genus/epithet components."""

    canonical_norm: str
    genus_norm: str | None
    epithet_norm: str | None
    genus_prefix2: str | None
    genus_prefix3: str | None
    canon_prefix3: str | None


def _ascii_fold(string: str) -> str:
    """Convert a Unicode string to ASCII by removing diacritics and other non-ASCII characters.

    Args:
        string: The input string to be ASCII-folded.

    Returns:
        A new string with diacritics removed and non-ASCII characters stripped out.
    """
    normalized_string = unicodedata.normalize("NFKD", string)
    return "".join(ch for ch in normalized_string if not unicodedata.combining(ch))


def normalize_scientific_name(raw: str) -> str:
    """Normalize a scientific name string for consistent indexing and searching.

    Args:
        raw: The raw scientific name string to be normalized.

    Returns:
        A normalized version of the scientific name, with ASCII folding, lowercasing, and punctuation removed.
    """
    raw = (raw or "").strip()
    normalized_string = _ascii_fold(raw)
    normalized_string = normalized_string.lower()
    normalized_string = _punct.sub(" ", normalized_string)
    normalized_string = _ws.sub(" ", normalized_string).strip()
    return normalized_string


def parse_genus_epithet(raw: str) -> ParsedName:
    """Parse a scientific name into its genus and epithet components.

    Args:
        raw: The raw scientific name string to be parsed.

    Returns:
        A ParsedName object containing the normalized scientific name, genus, epithet, and their prefixes.
    """
    norm = normalize_scientific_name(raw)

    tokens = norm.split()
    genus = tokens[0] if tokens else None
    epithet = tokens[1] if len(tokens) > 1 else None

    genus_prefix2 = genus[:PREFIX_LEN_2] if genus and len(genus) >= PREFIX_LEN_2 else None
    genus_prefix3 = genus[:PREFIX_LEN_3] if genus and len(genus) >= PREFIX_LEN_3 else None
    canon_prefix3 = norm[:PREFIX_LEN_3] if len(norm) >= PREFIX_LEN_3 else None

    return ParsedName(
        canonical_norm=norm,
        genus_norm=genus,
        epithet_norm=epithet,
        genus_prefix2=genus_prefix2,
        genus_prefix3=genus_prefix3,
        canon_prefix3=canon_prefix3,
    )
