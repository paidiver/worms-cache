use axum::Json;
use serde::Serialize;
use serde_json::{json, Value};
use utoipa::ToSchema;

#[derive(Serialize, ToSchema)]
pub struct HealthResponse {
    pub status: String,
}

#[utoipa::path(
    get,
    path = "/health/",
    tag = "Health",
    responses(
        (status = 200, description = "Service is healthy", body = HealthResponse),
    )
)]
pub async fn health() -> Json<Value> {
    Json(json!({ "status": "ok" }))
}
