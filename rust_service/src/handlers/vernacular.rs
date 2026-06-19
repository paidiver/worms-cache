use axum::{
    extract::{Path, State},
    Json,
};
use serde::Deserialize;
use sqlx::PgPool;
use utoipa::IntoParams;

use crate::errors::AppError;
use crate::extractors::QsQuery;
use crate::models::vernacular::{VernacularMiniResponse, VernacularResponse, VernacularRow};
use crate::state::AppState;

// ---------------------------------------------------------------------------
// Query parameter structs
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize, Default, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct VernacularListQuery {
    /// Filter by taxon ID (AphiaID).
    pub taxon_id: Option<i32>,
    /// Filter by ISO 639-1 language code (e.g. `eng`, `fra`).
    pub language_code: Option<String>,
}

#[derive(Debug, Deserialize, Default, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct VernacularRetrieveQuery {
    /// Filter by ISO 639-1 language code.
    pub language_code: Option<String>,
    /// When `true` (default) an invalid AphiaID is silently redirected to its
    /// valid taxon before looking up vernacular names.
    pub follow_valid: Option<bool>,
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

/// `GET /vernaculars/`
///
/// List all vernacular names, optionally filtered by `taxon_id` and/or
/// `language_code`.
#[utoipa::path(
    get,
    path = "/vernaculars/",
    tag = "Vernaculars",
    params(VernacularListQuery),
    responses(
        (status = 200, description = "List of vernacular names", body = Vec<VernacularResponse>),
    )
)]
pub async fn list_vernaculars(
    State(state): State<AppState>,
    QsQuery(params): QsQuery<VernacularListQuery>,
) -> Result<Json<Vec<VernacularResponse>>, AppError> {
    let rows = sqlx::query_as::<_, VernacularRow>(
        r#"
        SELECT id, taxon_id, name, language_code
        FROM vernaculars
        WHERE ($1::integer IS NULL OR taxon_id = $1)
          AND ($2::text IS NULL OR language_code = $2)
        ORDER BY taxon_id, language_code, name
        LIMIT 1000
        "#,
    )
    .bind(params.taxon_id)
    .bind(params.language_code.as_deref())
    .fetch_all(&state.db)
    .await?;

    Ok(Json(rows.into_iter().map(VernacularResponse::from).collect()))
}

/// `GET /vernaculars/:aphia_id/`
///
/// Return vernacular names for a given AphiaID, with optional language filter.
/// When `follow_valid=true` (default) synonyms are automatically resolved to
/// the valid taxon before the lookup.
#[utoipa::path(
    get,
    path = "/vernaculars/{aphia_id}/",
    tag = "Vernaculars",
    params(
        ("aphia_id" = i32, Path, description = "WoRMS AphiaID"),
        VernacularRetrieveQuery,
    ),
    responses(
        (status = 200, description = "Vernacular names for the taxon", body = Vec<VernacularMiniResponse>),
        (status = 404, description = "Taxon not found"),
    )
)]
pub async fn get_vernaculars_by_aphia_id(
    State(state): State<AppState>,
    Path(aphia_id): Path<i32>,
    QsQuery(params): QsQuery<VernacularRetrieveQuery>,
) -> Result<Json<Vec<VernacularMiniResponse>>, AppError> {
    let follow_valid = params.follow_valid.unwrap_or(true);

    let resolved_id = if follow_valid {
        resolve_valid_aphia_id(&state.db, aphia_id).await?
    } else {
        aphia_id
    };

    let rows = sqlx::query_as::<_, VernacularRow>(
        r#"
        SELECT id, taxon_id, name, language_code
        FROM vernaculars
        WHERE taxon_id = $1
          AND ($2::text IS NULL OR language_code = $2)
        ORDER BY language_code, name
        "#,
    )
    .bind(resolved_id)
    .bind(params.language_code.as_deref())
    .fetch_all(&state.db)
    .await?;

    Ok(Json(
        rows.into_iter().map(VernacularMiniResponse::from).collect(),
    ))
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Resolve `aphia_id` to the AphiaID of its valid taxon when it is a synonym.
async fn resolve_valid_aphia_id(db: &PgPool, aphia_id: i32) -> Result<i32, AppError> {
    #[derive(sqlx::FromRow)]
    struct Row {
        valid_taxon_id: Option<i32>,
    }

    let row = sqlx::query_as::<_, Row>(
        "SELECT valid_taxon_id FROM taxa WHERE aphia_id = $1",
    )
    .bind(aphia_id)
    .fetch_optional(db)
    .await?;

    if let Some(Row {
        valid_taxon_id: Some(valid_id),
    }) = row
    {
        if valid_id != aphia_id {
            return Ok(valid_id);
        }
    }
    Ok(aphia_id)
}
