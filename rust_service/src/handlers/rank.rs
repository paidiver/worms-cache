use axum::{extract::Path, extract::State, Json};

use crate::errors::AppError;
use crate::models::rank::RankRow;
use crate::state::AppState;

#[utoipa::path(
    get,
    path = "/ranks/",
    tag = "Ranks",
    responses(
        (status = 200, description = "All taxonomic ranks ordered by rank_id", body = Vec<RankRow>),
    )
)]
pub async fn list_ranks(State(state): State<AppState>) -> Result<Json<Vec<RankRow>>, AppError> {
    let rows = sqlx::query_as::<_, RankRow>(
        "SELECT name, rank_id FROM ranks ORDER BY rank_id",
    )
    .fetch_all(&state.db)
    .await?;
    Ok(Json(rows))
}

#[utoipa::path(
    get,
    path = "/ranks/{name}/",
    tag = "Ranks",
    params(
        ("name" = String, Path, description = "Rank name (e.g. Species, Genus, Family)"),
    ),
    responses(
        (status = 200, description = "Rank record", body = RankRow),
        (status = 404, description = "Rank not found"),
    )
)]
pub async fn get_rank(
    State(state): State<AppState>,
    Path(name): Path<String>,
) -> Result<Json<RankRow>, AppError> {
    let row = sqlx::query_as::<_, RankRow>(
        "SELECT name, rank_id FROM ranks WHERE name = $1",
    )
    .bind(&name)
    .fetch_optional(&state.db)
    .await?
    .ok_or(AppError::NotFound)?;
    Ok(Json(row))
}
