//! Scientific-name normalisation utilities, mirroring `api/utils/names.py`.
//!
//! * `normalize_scientific_name` – ASCII-fold, lowercase, strip punctuation, collapse whitespace.
//! * `parse_genus_epithet`       – Split into genus / epithet and compute prefix indices.
//! * `handle_scientific_name_input` – Capitalise genus for Taxamatch input.

use regex::Regex;
use std::sync::OnceLock;
use unicode_normalization::UnicodeNormalization;

// ---------------------------------------------------------------------------
// Static regex cache
// ---------------------------------------------------------------------------

static WS_RE: OnceLock<Regex> = OnceLock::new();
static PUNCT_RE: OnceLock<Regex> = OnceLock::new();

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct ParsedName {
    pub canonical_norm: String,
    pub genus_norm: Option<String>,
    #[allow(dead_code)]
    pub epithet_norm: Option<String>,
    pub genus_prefix2: Option<String>,
    pub genus_prefix3: Option<String>,
    #[allow(dead_code)]
    pub canon_prefix3: Option<String>,
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Remove Unicode combining diacritical marks after NFKD decomposition.
///
/// After NFKD, a character like 'é' is split into 'e' (U+0065) and a combining
/// acute accent (U+0301).  We drop all code-points in the standard combining
/// ranges so only base characters remain.
fn strip_combining_marks(s: &str) -> String {
    s.nfkd()
        .filter(|c| {
            let cp = *c as u32;
            // Combining Diacritical Marks              0300–036F
            // Combining Diacritical Marks Supplement   1DC0–1DFF
            // Combining Diacritical Marks for Symbols  20D0–20FF
            // Combining Half Marks                     FE20–FE2F
            !(0x0300..=0x036F).contains(&cp)
                && !(0x1DC0..=0x1DFF).contains(&cp)
                && !(0x20D0..=0x20FF).contains(&cp)
                && !(0xFE20..=0xFE2F).contains(&cp)
        })
        .collect()
}

// ---------------------------------------------------------------------------
// Public functions
// ---------------------------------------------------------------------------

/// Normalise a scientific name for indexing / searching.
///
/// Steps (mirrors the Python implementation):
/// 1. Strip combining diacritical marks (NFKD + filter).
/// 2. Lowercase.
/// 3. Replace punctuation characters (keeping `\w`, spaces, hyphens) with a space.
/// 4. Collapse runs of whitespace and trim.
pub fn normalize_scientific_name(raw: &str) -> String {
    let raw = raw.trim();
    let folded = strip_combining_marks(raw);
    let lower = folded.to_lowercase();

    let punct_re = PUNCT_RE.get_or_init(|| Regex::new(r"[^\w\s\-]+").unwrap());
    let no_punct = punct_re.replace_all(&lower, " ");

    let ws_re = WS_RE.get_or_init(|| Regex::new(r"\s+").unwrap());
    ws_re.replace_all(&no_punct, " ").trim().to_string()
}

/// Parse a scientific name into its normalised components.
pub fn parse_genus_epithet(raw: &str) -> ParsedName {
    let canonical_norm = normalize_scientific_name(raw);
    let tokens: Vec<&str> = canonical_norm.split_whitespace().collect();

    let genus_norm = tokens.first().map(|s| s.to_string());
    let epithet_norm = if tokens.len() >= 2 {
        Some(tokens[1].to_string())
    } else {
        None
    };

    let genus_prefix2 = genus_norm.as_ref().and_then(|g| {
        if g.len() >= 2 {
            Some(g[..2].to_string())
        } else {
            None
        }
    });

    let genus_prefix3 = genus_norm.as_ref().and_then(|g| {
        if g.len() >= 3 {
            Some(g[..3].to_string())
        } else {
            None
        }
    });

    let canon_prefix3 = if canonical_norm.len() >= 3 {
        Some(canonical_norm[..3].to_string())
    } else {
        None
    };

    ParsedName {
        canonical_norm,
        genus_norm,
        epithet_norm,
        genus_prefix2,
        genus_prefix3,
        canon_prefix3,
    }
}

/// Capitalise the first character and lowercase the rest (Python `str.capitalize()`).
fn capitalize_str(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => first.to_uppercase().to_string() + &chars.as_str().to_lowercase(),
    }
}

/// Prepare a name for Taxamatch input.
///
/// When the name has ≥ 2 tokens the genus (first token) is capitalised.
/// This mirrors `_handle_scientific_name_input` in the Django view.
pub fn handle_scientific_name_input(name: &str) -> String {
    let name = name.trim();
    let tokens: Vec<&str> = name.split_whitespace().collect();
    if tokens.len() >= 2 {
        format!("{} {}", capitalize_str(tokens[0]), tokens[1..].join(" "))
    } else {
        name.to_string()
    }
}
