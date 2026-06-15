use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use utoipa::ToSchema;

// ---------------------------------------------------------------------------
// DB row types
// ---------------------------------------------------------------------------

/// Raw taxon row from the `taxa` table, with joined `valid_taxon` data.
///
/// The SQL query uses LEFT JOIN and COALESCE to populate `valid_aphia_id` and
/// `valid_name` so the serialiser does not need a second query.
#[derive(Debug, Clone, FromRow)]
pub struct TaxonRow {
    pub aphia_id: i32,
    pub scientific_name: String,
    pub rank: String,
    pub status: String,
    pub valid_taxon_id: Option<i32>,
    /// `COALESCE(valid_taxon.aphia_id, taxa.aphia_id)`
    pub valid_aphia_id: i32,
    /// `COALESCE(valid_taxon.scientific_name, taxa.scientific_name)`
    pub valid_name: String,
    pub parent_id: Option<i32>,
    pub worms_modified: Option<DateTime<Utc>>,
    pub source_url: Option<String>,
    pub cached_at: DateTime<Utc>,
}

/// Lightweight row used when building parent/classification chains.
#[derive(Debug, Clone, FromRow)]
pub struct ClassificationRow {
    pub aphia_id: i32,
    pub scientific_name: String,
    pub rank: String,
    #[allow(dead_code)]
    pub parent_id: Option<i32>,
    #[allow(dead_code)]
    pub depth: i32,
}

// ---------------------------------------------------------------------------
// API response types
// ---------------------------------------------------------------------------

/// WoRMS-compatible taxon representation.
///
/// Field names use `PascalCase` / `camelCase` to match the WoRMS REST API
/// convention (`AphiaID`, `scientificname`, `valid_AphiaID`, …).
#[derive(Debug, Clone, Serialize, ToSchema)]
#[allow(non_snake_case)]
pub struct TaxonResponse {
    pub AphiaID: i32,
    pub scientificname: String,
    pub url: Option<String>,
    pub rank: String,
    pub status: String,
    pub valid_AphiaID: i32,
    pub valid_name: String,
    pub modified: Option<DateTime<Utc>>,
    pub cached_at: DateTime<Utc>,
    pub parent_AphiaID: Option<i32>,
}

impl From<TaxonRow> for TaxonResponse {
    fn from(row: TaxonRow) -> Self {
        TaxonResponse {
            AphiaID: row.aphia_id,
            scientificname: row.scientific_name,
            url: row.source_url,
            rank: row.rank,
            status: row.status,
            valid_AphiaID: row.valid_aphia_id,
            valid_name: row.valid_name,
            modified: row.worms_modified,
            cached_at: row.cached_at,
            parent_AphiaID: row.parent_id,
        }
    }
}

/// WoRMS-style nested classification node.
#[derive(Debug, Clone, Serialize, ToSchema)]
#[allow(non_snake_case)]
pub struct ClassificationNode {
    pub AphiaID: i32,
    pub rank: String,
    pub scientificname: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub child: Option<Box<ClassificationNode>>,
}

/// Request body for the ingest endpoint.
#[derive(Debug, Deserialize, ToSchema)]
pub struct IngestRequest {
    #[allow(dead_code)]
    pub aphia_id: i32,
}

/// Response wrapper used by `GET /taxa/:aphia_id/`.
#[derive(Debug, Serialize, ToSchema)]
pub struct TaxonWithContextResponse {
    pub taxon: TaxonResponse,
    pub parents: Vec<TaxonResponse>,
    pub descendants: Vec<TaxonResponse>,
}
