use serde::Serialize;
use sqlx::FromRow;
use utoipa::ToSchema;

#[derive(Debug, Clone, FromRow)]
pub struct VernacularRow {
    #[allow(dead_code)]
    pub id: i64,
    pub taxon_id: i32,
    pub name: String,
    pub language_code: String,
}

/// Full vernacular record (used by `GET /vernaculars/`).
#[derive(Debug, Clone, Serialize, ToSchema)]
pub struct VernacularResponse {
    pub taxon_id: i32,
    pub name: String,
    pub language_code: String,
}

/// Minimal vernacular record (used by `GET /vernaculars/:aphia_id/`).
#[derive(Debug, Clone, Serialize, ToSchema)]
pub struct VernacularMiniResponse {
    pub name: String,
    pub language_code: String,
}

impl From<VernacularRow> for VernacularResponse {
    fn from(row: VernacularRow) -> Self {
        VernacularResponse {
            taxon_id: row.taxon_id,
            name: row.name,
            language_code: row.language_code,
        }
    }
}

impl From<VernacularRow> for VernacularMiniResponse {
    fn from(row: VernacularRow) -> Self {
        VernacularMiniResponse {
            name: row.name,
            language_code: row.language_code,
        }
    }
}
