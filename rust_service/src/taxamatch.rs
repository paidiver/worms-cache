//! HTTP client wrapper for the Taxamatch fuzzy-matching service.
//!
//! The protocol is identical to the Python `taxamatch_client.py`:
//!   POST <TAXAMATCH_URL>/match
//!   Body:  { "queries": [ { "input": "...", "candidates": [{"id":1,"name":"..."}] } ] }
//!   Reply: { "results": [ { "matched_ids": [1,2] } ] }

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Request / response types
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize)]
pub struct TaxamatchQuery {
    pub input: String,
    pub candidates: Vec<TaxamatchCandidate>,
}

#[derive(Debug, Clone, Serialize)]
pub struct TaxamatchCandidate {
    /// NameIndex primary key (i64 – BigAutoField in Django).
    pub id: i64,
    pub name: String,
}

#[derive(Debug, Deserialize)]
pub struct TaxamatchResult {
    pub matched_ids: Option<Vec<i64>>,
}

#[derive(Serialize)]
struct TaxamatchRequest {
    queries: Vec<TaxamatchQuery>,
}

#[derive(Deserialize)]
struct TaxamatchResponse {
    results: Vec<TaxamatchResult>,
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Send a batch of name-matching queries to the Taxamatch service.
///
/// Returns an `Err(String)` if the HTTP request fails or the service returns
/// a non-2xx status code; in that case callers should fall back gracefully.
pub async fn match_batch(
    client: &reqwest::Client,
    taxamatch_url: &str,
    queries: Vec<TaxamatchQuery>,
    timeout_secs: f64,
) -> Result<Vec<TaxamatchResult>, String> {
    let url = format!("{taxamatch_url}/match");
    let body = TaxamatchRequest { queries };

    let response = client
        .post(&url)
        .json(&body)
        .timeout(std::time::Duration::from_secs_f64(timeout_secs))
        .send()
        .await
        .map_err(|e| format!("Taxamatch request failed: {e}"))?;

    if !response.status().is_success() {
        return Err(format!(
            "Taxamatch service returned {}",
            response.status()
        ));
    }

    let data: TaxamatchResponse = response
        .json()
        .await
        .map_err(|e| format!("Failed to parse taxamatch response: {e}"))?;

    Ok(data.results)
}
