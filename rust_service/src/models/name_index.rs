use serde::Serialize;
use sqlx::FromRow;
use utoipa::ToSchema;

/// Corresponds to the `name_index` table.
#[derive(Debug, Clone, FromRow, Serialize, ToSchema)]
pub struct NameIndexRow {
    pub id: i64,
    pub taxon_id: i32,
    pub name_type: String,
    pub name_raw: String,
    pub canonical_norm: String,
    pub genus_norm: Option<String>,
    pub epithet_norm: Option<String>,
    pub genus_prefix2: Option<String>,
    pub genus_prefix3: Option<String>,
    pub canon_prefix3: Option<String>,
}
