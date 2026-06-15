use utoipa::{
    openapi::security::{ApiKey, ApiKeyValue, HttpAuthScheme, HttpBuilder, SecurityScheme},
    Modify, OpenApi,
};

use crate::handlers::{health, name_index, rank, taxon, vernacular};
use crate::models::{
    name_index::NameIndexRow,
    rank::RankRow,
    taxon::{ClassificationNode, TaxonResponse, TaxonWithContextResponse, IngestRequest},
    vernacular::{VernacularMiniResponse, VernacularResponse},
};

/// Adds the bearer-token security scheme used by the ingest endpoint.
struct SecurityAddon;

impl Modify for SecurityAddon {
    fn modify(&self, openapi: &mut utoipa::openapi::OpenApi) {
        let components = openapi.components.get_or_insert_with(Default::default);
        components.add_security_scheme(
            "bearer_token",
            SecurityScheme::Http(
                HttpBuilder::new()
                    .scheme(HttpAuthScheme::Bearer)
                    .bearer_format("token")
                    .build(),
            ),
        );
    }
}

#[derive(OpenApi)]
#[openapi(
    info(
        title = "WoRMS Cache API — Rust/Axum",
        version = "0.1.0",
        description = "Read-only REST API for WoRMS taxonomic data, implemented in Rust with Axum. \
            All write operations (ingestion) are handled exclusively by the Django service.",
        contact(
            name = "paidiver",
            url = "https://github.com/paidiver/worms-cache",
        ),
    ),
    paths(
        // Health
        health::health,
        // Taxa
        taxon::list_taxa,
        taxon::get_taxon,
        taxon::get_ids_with_descendants,
        taxon::get_classification,
        taxon::get_synonyms,
        taxon::ajax_by_name_part,
        taxon::ajax_by_name_part_only_ids,
        taxon::match_names,
        taxon::match_names_pair,
        taxon::ingest,
        // Vernaculars
        vernacular::list_vernaculars,
        vernacular::get_vernaculars_by_aphia_id,
        // Ranks
        rank::list_ranks,
        rank::get_rank,
        // Name index
        name_index::list_name_indexes,
        name_index::get_name_index,
    ),
    components(
        schemas(
            TaxonResponse,
            TaxonWithContextResponse,
            ClassificationNode,
            IngestRequest,
            VernacularResponse,
            VernacularMiniResponse,
            RankRow,
            NameIndexRow,
            health::HealthResponse,
        )
    ),
    tags(
        (name = "Health",      description = "Service health check"),
        (name = "Taxa",        description = "Taxon lookup, autocomplete, and fuzzy matching"),
        (name = "Vernaculars", description = "Common / vernacular names"),
        (name = "Ranks",       description = "Taxonomic rank definitions"),
        (name = "Name Index",  description = "Internal name-index records"),
    ),
    modifiers(&SecurityAddon),
)]
pub struct ApiDoc;
