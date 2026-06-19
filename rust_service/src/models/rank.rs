use serde::Serialize;
use sqlx::FromRow;
use utoipa::ToSchema;

/// Corresponds to the `ranks` table.
#[derive(Debug, Clone, FromRow, Serialize, ToSchema)]
pub struct RankRow {
    pub name: String,
    pub rank_id: i32,
}
