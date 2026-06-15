use axum::{
    routing::{get, post},
    Router,
};
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;
use utoipa::OpenApi;
use utoipa_swagger_ui::SwaggerUi;

use crate::handlers::{health, name_index, rank, taxon, vernacular};
use crate::openapi::ApiDoc;
use crate::state::AppState;

pub fn create_router(
    db: sqlx::PgPool,
    taxamatch_url: String,
    ingest_token: Option<String>,
) -> Router {
    let state = AppState::new(db, taxamatch_url, ingest_token);

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    Router::new()
        // Health
        .route("/health/", get(health::health))

        // ── Taxa ──────────────────────────────────────────────────────────
        // Static sub-paths must come before the `:aphia_id` wildcard so that
        // Axum's trie router can distinguish them.
        .route("/taxa/", get(taxon::list_taxa))
        .route(
            "/taxa/ids_with_descendants/",
            get(taxon::get_ids_with_descendants),
        )
        .route("/taxa/match_names/", get(taxon::match_names))
        .route("/taxa/match_names_pair/", get(taxon::match_names_pair))
        .route(
            "/taxa/classification/:aphia_id/",
            get(taxon::get_classification),
        )
        .route("/taxa/synonyms/:aphia_id/", get(taxon::get_synonyms))
        // Note: `only_ids` sub-path must precede the bare `:name_part` route
        .route(
            "/taxa/ajax_by_name_part/only_ids/:name_part",
            get(taxon::ajax_by_name_part_only_ids),
        )
        .route(
            "/taxa/ajax_by_name_part/:name_part",
            get(taxon::ajax_by_name_part),
        )
        .route("/taxa/ingest/", post(taxon::ingest))
        .route("/taxa/:aphia_id/", get(taxon::get_taxon))

        // ── Vernaculars ───────────────────────────────────────────────────
        .route("/vernaculars/", get(vernacular::list_vernaculars))
        .route(
            "/vernaculars/:aphia_id/",
            get(vernacular::get_vernaculars_by_aphia_id),
        )

        // ── Ranks ─────────────────────────────────────────────────────────
        .route("/ranks/", get(rank::list_ranks))
        .route("/ranks/:name/", get(rank::get_rank))

        // ── Name indexes ──────────────────────────────────────────────────
        .route("/name_indexes/", get(name_index::list_name_indexes))
        .route("/name_indexes/:id/", get(name_index::get_name_index))

        // Middleware
        .layer(cors)
        .layer(TraceLayer::new_for_http())
        .with_state(state)
        // ── OpenAPI / Swagger UI ──────────────────────────────────────────
        // Served without AppState so it is merged *after* with_state.
        .merge(
            SwaggerUi::new("/swagger-ui")
                .url("/api-docs/openapi.json", ApiDoc::openapi()),
        )
}
