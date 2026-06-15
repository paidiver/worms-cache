use axum::{
    extract::{Path, State},
    Json,
};
use serde::Deserialize;
use utoipa::IntoParams;

use crate::errors::AppError;
use crate::extractors::QsQuery;
use crate::models::name_index::NameIndexRow;
use crate::state::AppState;

const NAME_INDEX_SELECT: &str = r#"
    SELECT id, taxon_id, name_type, name_raw, canonical_norm,
           genus_norm, epithet_norm, genus_prefix2, genus_prefix3, canon_prefix3
    FROM name_index
"#;

#[derive(Debug, Deserialize, Default, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct NameIndexListQuery {
    /// Filter by taxon ID.
    pub taxon_id: Option<i32>,
    /// Filter by name type (e.g. `scientific`, `vernacular`).
    pub name_type: Option<String>,
    /// Case-insensitive substring match on `canonical_norm`.
    pub canonical_norm: Option<String>,
    /// Page size (default 50, max 200).
    pub limit: Option<i64>,
}

#[utoipa::path(
    get,
    path = "/name_indexes/",
    tag = "Name Index",
    params(NameIndexListQuery),
    responses(
        (status = 200, description = "List of name index records", body = Vec<NameIndexRow>),
    )
)]
pub async fn list_name_indexes(
    State(state): State<AppState>,
    QsQuery(params): QsQuery<NameIndexListQuery>,
) -> Result<Json<Vec<NameIndexRow>>, AppError> {
    let limit = params.limit.unwrap_or(50).clamp(1, 200);

    let rows = sqlx::query_as::<_, NameIndexRow>(&format!(
        r#"
        {NAME_INDEX_SELECT}
        WHERE ($1::integer IS NULL OR taxon_id = $1)
          AND ($2::text IS NULL OR name_type = $2)
          AND ($3::text IS NULL OR canonical_norm ILIKE '%' || $3 || '%')
        ORDER BY id
        LIMIT $4
        "#
    ))
    .bind(params.taxon_id)
    .bind(params.name_type.as_deref())
    .bind(params.canonical_norm.as_deref())
    .bind(limit)
    .fetch_all(&state.db)
    .await?;

    Ok(Json(rows))
}

#[utoipa::path(
    get,
    path = "/name_indexes/{id}/",
    tag = "Name Index",
    params(
        ("id" = i64, Path, description = "Name index record ID"),
    ),
    responses(
        (status = 200, description = "Name index record", body = NameIndexRow),
        (status = 404, description = "Record not found"),
    )
)]
pub async fn get_name_index(
    State(state): State<AppState>,
    Path(id): Path<i64>,
) -> Result<Json<NameIndexRow>, AppError> {
    let row = sqlx::query_as::<_, NameIndexRow>(&format!(
        "{NAME_INDEX_SELECT} WHERE id = $1"
    ))
    .bind(id)
    .fetch_optional(&state.db)
    .await?
    .ok_or(AppError::NotFound)?;

    Ok(Json(row))
}
