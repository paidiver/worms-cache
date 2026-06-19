use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use serde::{Deserialize, Deserializer};
use sqlx::PgPool;
use std::collections::{HashMap, HashSet};
use utoipa::IntoParams;

use crate::errors::AppError;
use crate::extractors::QsQuery;
use crate::models::name_index::NameIndexRow;
use crate::models::taxon::{
    ClassificationNode, ClassificationRow, IngestRequest, TaxonResponse, TaxonRow,
    TaxonWithContextResponse,
};
use crate::names::{handle_scientific_name_input, parse_genus_epithet};
use crate::state::AppState;
use crate::taxamatch::{match_batch, TaxamatchCandidate, TaxamatchQuery};

fn deserialize_aphia_ids<'de, D>(deserializer: D) -> Result<Option<Vec<i32>>, D::Error>
where
    D: Deserializer<'de>,
{
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum OneOrMany {
        One(String),
        Many(Vec<String>),
    }

    let value = Option::<OneOrMany>::deserialize(deserializer)?;

    let Some(value) = value else {
        return Ok(None);
    };

    let raw_values = match value {
        OneOrMany::One(s) => vec![s],
        OneOrMany::Many(v) => v,
    };

    let mut ids = Vec::new();

    for raw in raw_values {
        for part in raw.split(',') {
            let part = part.trim();

            if part.is_empty() {
                continue;
            }

            let id = part.parse::<i32>().map_err(serde::de::Error::custom)?;
            ids.push(id);
        }
    }

    Ok(Some(ids))
}

// ---------------------------------------------------------------------------
// Shared SQL fragment
// ---------------------------------------------------------------------------

/// Core SELECT … FROM … LEFT JOIN fragment reused in every taxa query.
///
/// Always produces the column aliases that `TaxonRow` expects:
///   aphia_id, scientific_name, rank, status, valid_taxon_id,
///   valid_aphia_id, valid_name, parent_id, worms_modified, source_url, cached_at
const TAXON_SELECT: &str = r#"
    SELECT
        t.aphia_id,
        t.scientific_name,
        t.rank,
        t.status,
        t.valid_taxon_id,
        COALESCE(v.aphia_id, t.aphia_id)              AS valid_aphia_id,
        COALESCE(v.scientific_name, t.scientific_name) AS valid_name,
        t.parent_id,
        t.worms_modified,
        t.source_url,
        t.cached_at
    FROM taxa t
    LEFT JOIN taxa v ON t.valid_taxon_id = v.aphia_id
"#;

// ---------------------------------------------------------------------------
// Query-parameter structs
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize, Default, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct TaxonListQuery {
    /// Substring match against scientific name (case-insensitive).
    pub scientific_name: Option<String>,

    /// Exact rank filter, e.g. `Species`, `Genus` (case-insensitive).
    pub rank: Option<String>,

    /// AphiaIDs from `aphia_ids=123,456`.
    #[serde(
        default,
        rename = "aphia_ids",
        deserialize_with = "deserialize_aphia_ids"
    )]
    pub aphia_ids_csv: Option<Vec<i32>>,

    /// AphiaIDs from `aphia_ids[]=123&aphia_ids[]=456`.
    #[param(rename = "aphia_ids[]", style = Form, explode = true)]
    #[serde(
        default,
        rename = "aphia_ids[]",
        deserialize_with = "deserialize_aphia_ids"
    )]
    pub aphia_ids_brackets: Option<Vec<i32>>,
}

impl TaxonListQuery {
    pub fn aphia_ids(&self) -> Vec<i32> {
        self.aphia_ids_csv
            .clone()
            .unwrap_or_default()
            .into_iter()
            .chain(self.aphia_ids_brackets.clone().unwrap_or_default())
            .collect()
    }
}

#[derive(Debug, Deserialize, Default, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct TaxonRetrieveQuery {
    /// Resolve synonyms to their valid taxon.
    pub only_valid: Option<bool>,
    /// Include all descendant taxa.
    pub include_descendants: Option<bool>,
    /// Include the full parent chain.
    pub include_parents: Option<bool>,
}

#[derive(Debug, Deserialize, Default, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct AphiaIdsQuery {
    /// AphiaIDs from `aphia_ids=123,456`.
    #[serde(
        default,
        rename = "aphia_ids",
        deserialize_with = "deserialize_aphia_ids"
    )]
    pub aphia_ids_csv: Option<Vec<i32>>,

    /// AphiaIDs from `aphia_ids[]=123&aphia_ids[]=456`.
    #[param(rename = "aphia_ids[]", style = Form, explode = true)]
    #[serde(
        default,
        rename = "aphia_ids[]",
        deserialize_with = "deserialize_aphia_ids"
    )]
    pub aphia_ids_brackets: Option<Vec<i32>>,
}

impl AphiaIdsQuery {
    pub fn aphia_ids(&self) -> Vec<i32> {
        self.aphia_ids_csv
            .clone()
            .unwrap_or_default()
            .into_iter()
            .chain(self.aphia_ids_brackets.clone().unwrap_or_default())
            .collect()
    }
}

#[derive(Debug, Deserialize, Default, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct AjaxByNamePartQuery {
    /// Minimum rank_id (WoRMS integer scale).
    pub rank_min: Option<i32>,
    /// Maximum rank_id (WoRMS integer scale).
    pub rank_max: Option<i32>,
    /// Maximum number of results (default 20, max 50).
    pub max_matches: Option<i32>,
    /// AphiaIDs to exclude from results.
    #[param(rename = "excluded_ids[]", style = Form, explode = true)]
    #[serde(rename = "excluded_ids[]")]
    pub excluded_ids: Option<Vec<i32>>,
    /// Also search vernacular names.
    pub combine_vernaculars: Option<bool>,
    /// Restrict vernacular search to these language codes.
    #[param(rename = "languages[]", style = Form, explode = true)]
    #[serde(rename = "languages[]")]
    pub languages: Option<Vec<String>>,
}

#[derive(Debug, Deserialize, Default, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct MatchNamesQuery {
    /// Scientific names to match (up to 50).
    #[param(rename = "scientificnames[]", style = Form, explode = true)]
    #[serde(rename = "scientificnames[]")]
    pub scientificnames: Option<Vec<String>>,
    /// Maximum matches per input name (default 3).
    pub max_results: Option<i32>,
}

#[derive(Debug, Deserialize, Default, IntoParams)]
#[into_params(parameter_in = Query)]
pub struct MatchNamesPairQuery {
    /// First scientific name.
    pub scientificname1: Option<String>,
    /// Second scientific name.
    pub scientificname2: Option<String>,
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

/// `GET /taxa/`
///
/// List taxa.  When `aphia_ids[]` is supplied the exact set is returned;
/// otherwise the list is filtered by `scientific_name` (substring) and/or
/// `rank` (case-insensitive exact), capped at 50 records.
#[utoipa::path(
    get,
    path = "/taxa/",
    tag = "Taxa",
    params(TaxonListQuery),
    responses(
        (status = 200, description = "List of taxa", body = Vec<TaxonResponse>),
    )
)]
pub async fn list_taxa(
    State(state): State<AppState>,
    QsQuery(params): QsQuery<TaxonListQuery>,
) -> Result<Json<Vec<TaxonResponse>>, AppError> {
    let aphia_ids = params.aphia_ids();

    let rows = if !aphia_ids.is_empty() {
        sqlx::query_as::<_, TaxonRow>(&format!(
            "{TAXON_SELECT} WHERE t.aphia_id = ANY($1::integer[]) ORDER BY t.scientific_name"
        ))
        .bind(&aphia_ids[..])
        .fetch_all(&state.db)
        .await?
    } else {
        sqlx::query_as::<_, TaxonRow>(&format!(
            r#"
            {TAXON_SELECT}
            WHERE ($1::text IS NULL OR t.scientific_name ILIKE '%' || $1 || '%')
              AND ($2::text IS NULL OR LOWER(t.rank) = LOWER($2))
            ORDER BY t.scientific_name
            LIMIT 50
            "#
        ))
        .bind(params.scientific_name.as_deref())
        .bind(params.rank.as_deref())
        .fetch_all(&state.db)
        .await?
    };

    Ok(Json(rows.into_iter().map(TaxonResponse::from).collect()))
}

/// `GET /taxa/:aphia_id/`
///
/// Retrieve a single taxon.  Optional query parameters:
/// * `only_valid`          – resolve synonyms to their valid taxon.
/// * `include_parents`     – include the full parent chain.
/// * `include_descendants` – include all descendant taxa.
#[utoipa::path(
    get,
    path = "/taxa/{aphia_id}/",
    tag = "Taxa",
    params(
        ("aphia_id" = i32, Path, description = "WoRMS AphiaID"),
        TaxonRetrieveQuery,
    ),
    responses(
        (status = 200, description = "Taxon with optional parents and descendants", body = TaxonWithContextResponse),
        (status = 404, description = "Taxon not found"),
    )
)]
pub async fn get_taxon(
    State(state): State<AppState>,
    Path(aphia_id): Path<i32>,
    QsQuery(params): QsQuery<TaxonRetrieveQuery>,
) -> Result<Json<TaxonWithContextResponse>, AppError> {
    let only_valid = params.only_valid.unwrap_or(false);
    let include_parents = params.include_parents.unwrap_or(false);
    let include_descendants = params.include_descendants.unwrap_or(false);

    let row = fetch_taxon_by_id(&state.db, aphia_id).await?;

    // Optionally redirect synonym → valid taxon
    let row = if only_valid {
        match row.valid_taxon_id {
            Some(valid_id) if valid_id != row.aphia_id => {
                fetch_taxon_by_id(&state.db, valid_id).await?
            }
            _ => row,
        }
    } else {
        row
    };

    let actual_id = row.aphia_id;
    let taxon_resp = TaxonResponse::from(row);

    let parents = if include_parents {
        fetch_parents(&state.db, actual_id).await?
    } else {
        vec![]
    };

    let descendants = if include_descendants {
        fetch_descendants(&state.db, actual_id).await?
    } else {
        vec![]
    };

    Ok(Json(TaxonWithContextResponse {
        taxon: taxon_resp,
        parents,
        descendants,
    }))
}

/// `GET /taxa/ids_with_descendants/`
///
/// Return the given AphiaIDs plus every descendant AphiaID, deduplicated in
/// traversal order (breadth-first via recursive CTE).
#[utoipa::path(
    get,
    path = "/taxa/ids_with_descendants/",
    tag = "Taxa",
    params(AphiaIdsQuery),
    responses(
        (status = 200, description = "Flat list of AphiaIDs including all descendants", body = Vec<i32>),
        (status = 400, description = "aphia_ids[] is required"),
    )
)]
pub async fn get_ids_with_descendants(
    State(state): State<AppState>,
    QsQuery(params): QsQuery<AphiaIdsQuery>,
) -> Result<Json<Vec<i32>>, AppError> {
    let aphia_ids = params.aphia_ids();

    if aphia_ids.is_empty() {
        return Err(AppError::BadRequest(
            "aphia_ids or aphia_ids[] must contain at least one integer.".to_string(),
        ));
    }

    let ids = sqlx::query_scalar::<_, i32>(
        r#"
        WITH RECURSIVE descendants AS (
            SELECT aphia_id FROM taxa WHERE aphia_id = ANY($1::integer[])
            UNION ALL
            SELECT t.aphia_id
            FROM taxa t
            INNER JOIN descendants d ON t.parent_id = d.aphia_id
        )
        SELECT aphia_id FROM descendants
        "#,
    )
    .bind(&aphia_ids[..])
    .fetch_all(&state.db)
    .await?;

    // Deduplicate while preserving traversal order
    let mut seen: HashSet<i32> = HashSet::new();
    let result: Vec<i32> = ids.into_iter().filter(|id| seen.insert(*id)).collect();

    Ok(Json(result))
}

/// `GET /taxa/classification/:aphia_id/`
///
/// Return a WoRMS-style nested classification object: root → … → leaf, each
/// node carrying `AphiaID`, `rank`, `scientificname`, and an optional `child`.
#[utoipa::path(
    get,
    path = "/taxa/classification/{aphia_id}/",
    tag = "Taxa",
    params(
        ("aphia_id" = i32, Path, description = "WoRMS AphiaID"),
    ),
    responses(
        (status = 200, description = "Nested classification chain from root to leaf", body = ClassificationNode),
        (status = 404, description = "Taxon not found"),
    )
)]
pub async fn get_classification(
    State(state): State<AppState>,
    Path(aphia_id): Path<i32>,
) -> Result<Json<Option<ClassificationNode>>, AppError> {
    // Verify the taxon exists before doing the CTE walk
    let _ = fetch_taxon_by_id(&state.db, aphia_id).await?;

    let chain = sqlx::query_as::<_, ClassificationRow>(
        r#"
        WITH RECURSIVE parent_chain AS (
            SELECT aphia_id, scientific_name, rank, parent_id, 0::integer AS depth
            FROM taxa
            WHERE aphia_id = $1
            UNION ALL
            SELECT t.aphia_id, t.scientific_name, t.rank, t.parent_id, pc.depth + 1
            FROM taxa t
            INNER JOIN parent_chain pc ON t.aphia_id = pc.parent_id
        )
        SELECT aphia_id, scientific_name, rank, parent_id, depth
        FROM parent_chain
        ORDER BY depth DESC
        "#,
    )
    .bind(aphia_id)
    .fetch_all(&state.db)
    .await?;

    Ok(Json(build_classification_tree(chain)))
}

/// `GET /taxa/synonyms/:aphia_id/`
///
/// Return all synonyms of the resolved valid taxon.
#[utoipa::path(
    get,
    path = "/taxa/synonyms/{aphia_id}/",
    tag = "Taxa",
    params(
        ("aphia_id" = i32, Path, description = "WoRMS AphiaID"),
    ),
    responses(
        (status = 200, description = "Synonyms of the valid taxon", body = Vec<TaxonResponse>),
        (status = 404, description = "Taxon not found"),
    )
)]
pub async fn get_synonyms(
    State(state): State<AppState>,
    Path(aphia_id): Path<i32>,
) -> Result<Json<Vec<TaxonResponse>>, AppError> {
    let row = fetch_taxon_by_id(&state.db, aphia_id).await?;
    let valid_id = row
        .valid_taxon_id
        .filter(|&id| id != row.aphia_id)
        .unwrap_or(row.aphia_id);

    let rows = sqlx::query_as::<_, TaxonRow>(&format!(
        "{TAXON_SELECT} WHERE t.valid_taxon_id = $1 AND t.aphia_id != $1 ORDER BY t.scientific_name"
    ))
    .bind(valid_id)
    .fetch_all(&state.db)
    .await?;

    Ok(Json(rows.into_iter().map(TaxonResponse::from).collect()))
}

/// `GET /taxa/ajax_by_name_part/:name_part`
///
/// Fuzzy autocomplete using trigram similarity + Taxamatch.  Returns matched
/// taxa resolved to their valid taxon, or HTTP 204 when nothing matches.
#[utoipa::path(
    get,
    path = "/taxa/ajax_by_name_part/{name_part}",
    tag = "Taxa",
    params(
        ("name_part" = String, Path, description = "Partial scientific or vernacular name"),
        AjaxByNamePartQuery,
    ),
    responses(
        (status = 200, description = "Matched taxa resolved to their valid taxon", body = Vec<TaxonResponse>),
        (status = 204, description = "No matches found"),
    )
)]
pub async fn ajax_by_name_part(
    State(state): State<AppState>,
    Path(name_part): Path<String>,
    QsQuery(params): QsQuery<AjaxByNamePartQuery>,
) -> Result<Response, AppError> {
    let taxa = get_ajax_results(&state, &name_part, &params).await?;
    if taxa.is_empty() {
        return Ok(StatusCode::NO_CONTENT.into_response());
    }
    Ok(Json(taxa).into_response())
}

/// `GET /taxa/ajax_by_name_part/only_ids/:name_part`
///
/// Same as `ajax_by_name_part` but returns only AphiaIDs.
#[utoipa::path(
    get,
    path = "/taxa/ajax_by_name_part/only_ids/{name_part}",
    tag = "Taxa",
    params(
        ("name_part" = String, Path, description = "Partial scientific or vernacular name"),
        AjaxByNamePartQuery,
    ),
    responses(
        (status = 200, description = "List of matched AphiaIDs", body = Vec<i32>),
        (status = 204, description = "No matches found"),
    )
)]
pub async fn ajax_by_name_part_only_ids(
    State(state): State<AppState>,
    Path(name_part): Path<String>,
    QsQuery(params): QsQuery<AjaxByNamePartQuery>,
) -> Result<Response, AppError> {
    let taxa = get_ajax_results(&state, &name_part, &params).await?;
    if taxa.is_empty() {
        return Ok(StatusCode::NO_CONTENT.into_response());
    }
    let ids: Vec<i32> = taxa.iter().map(|t| t.AphiaID).collect();
    Ok(Json(ids).into_response())
}

/// `GET /taxa/match_names/`
///
/// Match up to 50 scientific names using trigram candidate retrieval followed
/// by the Taxamatch fuzzy algorithm.  Returns a list-of-lists (one inner list
/// per input name, capped by `max_results`).
#[utoipa::path(
    get,
    path = "/taxa/match_names/",
    tag = "Taxa",
    params(MatchNamesQuery),
    responses(
        (status = 200, description = "List of match lists, one per input name", body = Vec<TaxonResponse>),
        (status = 204, description = "No matches found for any input name"),
        (status = 400, description = "Too many names (max 50)"),
    )
)]
pub async fn match_names(
    State(state): State<AppState>,
    QsQuery(params): QsQuery<MatchNamesQuery>,
) -> Result<Response, AppError> {
    let names = params.scientificnames.unwrap_or_default();
    if names.len() > 50 {
        return Err(AppError::BadRequest(
            "Maximum 50 names per call.".to_string(),
        ));
    }
    let max_results = params.max_results.unwrap_or(3).clamp(1, 50) as usize;

    // Gather candidates for every input name
    let mut per_input: Vec<(String, Vec<NameIndexRow>)> = Vec::with_capacity(names.len());
    for raw in &names {
        let qname = raw.trim();
        if qname.is_empty() {
            per_input.push((String::new(), vec![]));
            continue;
        }
        let candidates = candidate_name_rows(&state.db, qname, 300, None).await?;
        let normalized = handle_scientific_name_input(qname);
        per_input.push((normalized, candidates));
    }

    // Build batch for Taxamatch
    let mut batch_queries: Vec<TaxamatchQuery> = Vec::new();
    let mut batch_to_input: Vec<usize> = Vec::new();
    for (i, (input, candidates)) in per_input.iter().enumerate() {
        if !candidates.is_empty() {
            batch_queries.push(TaxamatchQuery {
                input: input.clone(),
                candidates: candidates
                    .iter()
                    .map(|c| TaxamatchCandidate {
                        id: c.id,
                        name: c.name_raw.clone(),
                    })
                    .collect(),
            });
            batch_to_input.push(i);
        }
    }

    // Call Taxamatch; on failure fall through without matches
    let mut matched_ids_by_input: HashMap<usize, HashSet<i64>> = HashMap::new();
    if !batch_queries.is_empty() {
        if let Ok(results) =
            match_batch(&state.http_client, &state.taxamatch_url, batch_queries, 3.0).await
        {
            for (j, br) in results.iter().enumerate() {
                let idx = batch_to_input[j];
                let ids: HashSet<i64> = br
                    .matched_ids
                    .clone()
                    .unwrap_or_default()
                    .into_iter()
                    .collect();
                matched_ids_by_input.insert(idx, ids);
            }
        }
    }

    // Resolve each input to an ordered list of TaxonResponses
    let mut results: Vec<Vec<TaxonResponse>> = Vec::with_capacity(per_input.len());
    for (i, (_, candidates)) in per_input.iter().enumerate() {
        if candidates.is_empty() {
            results.push(vec![]);
            continue;
        }
        let matched = matched_ids_by_input.get(&i);
        let matched_rows: Vec<&NameIndexRow> = if let Some(ids) = matched {
            candidates.iter().filter(|c| ids.contains(&c.id)).collect()
        } else {
            vec![]
        };
        if matched_rows.is_empty() {
            results.push(vec![]);
            continue;
        }

        let taxon_ids = dedupe_keep_order(matched_rows.iter().map(|r| r.taxon_id));
        let taxa = fetch_taxa_by_ids_ordered(&state.db, &taxon_ids).await?;
        results.push(resolve_to_valid_taxa(taxa, max_results));
    }

    if results.iter().all(|r| r.is_empty()) {
        return Ok(StatusCode::NO_CONTENT.into_response());
    }
    Ok(Json(results).into_response())
}

/// `GET /taxa/match_names_pair/`
///
/// Check whether two scientific names refer to the same taxon according to
/// Taxamatch.  Returns `{ "match": true/false }`.
#[utoipa::path(
    get,
    path = "/taxa/match_names_pair/",
    tag = "Taxa",
    params(MatchNamesPairQuery),
    responses(
        (status = 200, description = "Match result — `{ \"match\": true/false }`",
            body = serde_json::Value,
        ),
        (status = 400, description = "Both names are required"),
    )
)]
pub async fn match_names_pair(
    State(state): State<AppState>,
    QsQuery(params): QsQuery<MatchNamesPairQuery>,
) -> Result<Json<serde_json::Value>, AppError> {
    let name1 = handle_scientific_name_input(
        params.scientificname1.as_deref().unwrap_or("").trim(),
    );
    let name2 = handle_scientific_name_input(
        params.scientificname2.as_deref().unwrap_or("").trim(),
    );

    if name1.is_empty() || name2.is_empty() {
        return Err(AppError::BadRequest(
            "Both scientificname1 and scientificname2 are required.".to_string(),
        ));
    }

    let batch = vec![TaxamatchQuery {
        input: name1,
        candidates: vec![TaxamatchCandidate { id: 1, name: name2 }],
    }];

    let results = match_batch(&state.http_client, &state.taxamatch_url, batch, 3.0)
        .await
        .map_err(AppError::Taxamatch)?;

    let matched = results
        .first()
        .and_then(|r| r.matched_ids.as_ref())
        .map(|ids| !ids.is_empty())
        .unwrap_or(false);

    Ok(Json(serde_json::json!({ "match": matched })))
}

/// `POST /taxa/ingest/`
///
/// This endpoint is intentionally **not implemented** in the Rust service.
/// WoRMS ingestion (external API calls + name-index rebuild) remains the
/// responsibility of the Django service.  A 501 response is returned so that
/// clients fail clearly instead of silently.
#[utoipa::path(
    post,
    path = "/taxa/ingest/",
    tag = "Taxa",
    request_body = IngestRequest,
    security(
        ("bearer_token" = [])
    ),
    responses(
        (status = 501, description = "Not implemented in the Rust service — use the Django service"),
        (status = 401, description = "Unauthorized"),
    )
)]
pub async fn ingest(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(_body): Json<IngestRequest>,
) -> Result<Response, AppError> {
    // Verify token even for the stub, so authentication is still enforced
    let token = extract_bearer_token(&headers);
    match (token, &state.ingest_token) {
        (Some(provided), Some(expected)) if provided == expected.as_str() => {}
        (_, None) => {
            // No token configured → any caller can reach this (intentional for dev)
        }
        _ => return Err(AppError::Unauthorized),
    }

    Ok((
        StatusCode::NOT_IMPLEMENTED,
        Json(serde_json::json!({
            "detail": "Ingest is handled exclusively by the Django service."
        })),
    )
        .into_response())
}

// ---------------------------------------------------------------------------
// Internal DB helpers
// ---------------------------------------------------------------------------

/// Fetch a single taxon by AphiaID; returns `AppError::NotFound` when absent.
async fn fetch_taxon_by_id(db: &PgPool, aphia_id: i32) -> Result<TaxonRow, AppError> {
    sqlx::query_as::<_, TaxonRow>(&format!("{TAXON_SELECT} WHERE t.aphia_id = $1"))
        .bind(aphia_id)
        .fetch_optional(db)
        .await?
        .ok_or(AppError::NotFound)
}

/// Fetch multiple taxa by a list of AphiaIDs and return them in the same order.
async fn fetch_taxa_by_ids_ordered(
    db: &PgPool,
    aphia_ids: &[i32],
) -> Result<Vec<TaxonResponse>, AppError> {
    if aphia_ids.is_empty() {
        return Ok(vec![]);
    }
    let rows = sqlx::query_as::<_, TaxonRow>(&format!(
        "{TAXON_SELECT} WHERE t.aphia_id = ANY($1::integer[])"
    ))
    .bind(aphia_ids)
    .fetch_all(db)
    .await?;

    let map: HashMap<i32, TaxonResponse> = rows
        .into_iter()
        .map(|r| (r.aphia_id, TaxonResponse::from(r)))
        .collect();

    Ok(aphia_ids
        .iter()
        .filter_map(|id| map.get(id).cloned())
        .collect())
}

/// Return all parent taxa from root down to (but not including) the given taxon.
async fn fetch_parents(db: &PgPool, aphia_id: i32) -> Result<Vec<TaxonResponse>, AppError> {
    let chain = sqlx::query_as::<_, ClassificationRow>(
        r#"
        WITH RECURSIVE parent_chain AS (
            SELECT aphia_id, scientific_name, rank, parent_id, 0::integer AS depth
            FROM taxa WHERE aphia_id = $1
            UNION ALL
            SELECT t.aphia_id, t.scientific_name, t.rank, t.parent_id, pc.depth + 1
            FROM taxa t
            INNER JOIN parent_chain pc ON t.aphia_id = pc.parent_id
        )
        SELECT aphia_id, scientific_name, rank, parent_id, depth
        FROM parent_chain
        WHERE aphia_id != $1
        ORDER BY depth DESC
        "#,
    )
    .bind(aphia_id)
    .fetch_all(db)
    .await?;

    if chain.is_empty() {
        return Ok(vec![]);
    }
    let parent_ids: Vec<i32> = chain.iter().map(|r| r.aphia_id).collect();
    fetch_taxa_by_ids_ordered(db, &parent_ids).await
}

/// Return all descendant taxa via recursive CTE, ordered by scientific name.
async fn fetch_descendants(db: &PgPool, aphia_id: i32) -> Result<Vec<TaxonResponse>, AppError> {
    let rows = sqlx::query_as::<_, TaxonRow>(&format!(
        r#"
        WITH RECURSIVE desc_ids AS (
            SELECT aphia_id FROM taxa WHERE parent_id = $1
            UNION ALL
            SELECT t.aphia_id FROM taxa t
            INNER JOIN desc_ids d ON t.parent_id = d.aphia_id
        )
        {TAXON_SELECT}
        WHERE t.aphia_id IN (SELECT aphia_id FROM desc_ids)
        ORDER BY t.scientific_name
        "#
    ))
    .bind(aphia_id)
    .fetch_all(db)
    .await?;

    Ok(rows.into_iter().map(TaxonResponse::from).collect())
}

/// Build a WoRMS-style nested `ClassificationNode` tree.
///
/// `chain` must be ordered by `depth DESC` (root first, leaf last), as
/// produced by the `ORDER BY depth DESC` CTE above.  We reverse-iterate to
/// build child → parent → … → root nesting.
fn build_classification_tree(chain: Vec<ClassificationRow>) -> Option<ClassificationNode> {
    let mut node: Option<ClassificationNode> = None;
    // chain[0] = root (deepest depth), chain.last() = the requested taxon
    for row in chain.iter().rev() {
        node = Some(ClassificationNode {
            AphiaID: row.aphia_id,
            rank: row.rank.clone(),
            scientificname: row.scientific_name.clone(),
            child: node.map(Box::new),
        });
    }
    node
}

/// Resolve an optional rank range to a `Vec<String>` of matching rank names.
///
/// Returns `None` (no filter) when both `rank_min` and `rank_max` are 0.
async fn get_rank_names_for_range(
    db: &PgPool,
    rank_min: i32,
    rank_max: i32,
) -> Result<Option<Vec<String>>, AppError> {
    if rank_min == 0 && rank_max == 0 {
        return Ok(None);
    }
    if rank_min > 0 && rank_max > 0 && rank_min > rank_max {
        return Err(AppError::BadRequest(
            "rank_min cannot be greater than rank_max.".to_string(),
        ));
    }
    let names = sqlx::query_scalar::<_, String>(
        r#"
        SELECT name FROM ranks
        WHERE ($1::integer IS NULL OR rank_id >= $1)
          AND ($2::integer IS NULL OR rank_id <= $2)
        "#,
    )
    .bind(if rank_min > 0 { Some(rank_min) } else { None })
    .bind(if rank_max > 0 { Some(rank_max) } else { None })
    .fetch_all(db)
    .await?;

    Ok(Some(names))
}

// ---------------------------------------------------------------------------
// Candidate name-index retrieval (mirrors `api/services/filters.py`)
// ---------------------------------------------------------------------------

/// Return candidate `NameIndexRow`s for a query name using trigram similarity.
///
/// Logic mirrors `candidate_name_rows` in the Python service:
/// * 1 token  → filter by `genus_prefix3` / `genus_prefix2`, order by
///              `similarity(genus_norm, …)`.  Falls back to canonical trigram.
/// * 2+ tokens → exact `genus_norm` match + canonical trigram.  Falls back to
///               `genus_prefix3` + canonical trigram.
async fn candidate_name_rows(
    db: &PgPool,
    query_name: &str,
    limit: i64,
    rank_names: Option<Vec<String>>,
) -> Result<Vec<NameIndexRow>, AppError> {
    let parsed = parse_genus_epithet(query_name);
    let tokens: Vec<&str> = parsed.canonical_norm.split_whitespace().collect();

    if tokens.len() == 1 {
        let genus = match parsed.genus_norm.as_deref() {
            Some(g) => g.to_string(),
            None => return Ok(vec![]),
        };

        // Try genus_prefix3
        if let Some(ref p3) = parsed.genus_prefix3 {
            let rows = query_by_genus_trigram(
                db,
                &genus,
                Some(p3.as_str()),
                None,
                rank_names.clone(),
                limit,
            )
            .await?;
            if !rows.is_empty() {
                return Ok(rows);
            }
        }
        // Try genus_prefix2
        if let Some(ref p2) = parsed.genus_prefix2 {
            let rows = query_by_genus_trigram(
                db,
                &genus,
                None,
                Some(p2.as_str()),
                rank_names.clone(),
                limit,
            )
            .await?;
            if !rows.is_empty() {
                return Ok(rows);
            }
        }
        // Fallback: canonical trigram
        return query_by_canonical_trigram(db, &parsed.canonical_norm, rank_names, limit).await;
    }

    // 2+ tokens — exact genus match first
    if let Some(ref genus) = parsed.genus_norm {
        let rows = query_by_genus_exact_canonical(
            db,
            &parsed.canonical_norm,
            genus,
            rank_names.clone(),
            limit,
        )
        .await?;
        if !rows.is_empty() {
            return Ok(rows);
        }
    }

    // Fallback: genus_prefix3 + canonical trigram
    if let Some(ref p3) = parsed.genus_prefix3 {
        let rows = query_by_prefix3_canonical(
            db,
            &parsed.canonical_norm,
            p3,
            rank_names.clone(),
            limit,
        )
        .await?;
        if !rows.is_empty() {
            return Ok(rows);
        }
    }

    Ok(vec![])
}

const NAME_IDX_COLS: &str = r#"
    ni.id, ni.taxon_id, ni.name_type, ni.name_raw, ni.canonical_norm,
    ni.genus_norm, ni.epithet_norm, ni.genus_prefix2, ni.genus_prefix3, ni.canon_prefix3
"#;

/// 1-token path: filter by prefix, rank; order by trigram on `genus_norm`.
async fn query_by_genus_trigram(
    db: &PgPool,
    genus: &str,
    prefix3: Option<&str>,
    prefix2: Option<&str>,
    rank_names: Option<Vec<String>>,
    limit: i64,
) -> Result<Vec<NameIndexRow>, AppError> {
    sqlx::query_as::<_, NameIndexRow>(&format!(
        r#"
        SELECT {NAME_IDX_COLS}
        FROM name_index ni
        JOIN taxa t ON ni.taxon_id = t.aphia_id
        WHERE ($1::text IS NULL OR ni.genus_prefix3 = $1)
          AND ($2::text IS NULL OR ni.genus_prefix2 = $2)
          AND ($3::text[] IS NULL OR t.rank = ANY($3))
          AND ni.genus_norm IS NOT NULL
          AND similarity(ni.genus_norm, $4) > 0.2
        ORDER BY similarity(ni.genus_norm, $4) DESC
        LIMIT $5
        "#
    ))
    .bind(prefix3)
    .bind(prefix2)
    .bind(rank_names)
    .bind(genus)
    .bind(limit)
    .fetch_all(db)
    .await
    .map_err(AppError::from)
}

/// Fallback 1-token path: trigram on `canonical_norm` with no prefix filter.
async fn query_by_canonical_trigram(
    db: &PgPool,
    canonical_norm: &str,
    rank_names: Option<Vec<String>>,
    limit: i64,
) -> Result<Vec<NameIndexRow>, AppError> {
    sqlx::query_as::<_, NameIndexRow>(&format!(
        r#"
        SELECT {NAME_IDX_COLS}
        FROM name_index ni
        JOIN taxa t ON ni.taxon_id = t.aphia_id
        WHERE ($1::text[] IS NULL OR t.rank = ANY($1))
          AND similarity(ni.canonical_norm, $2) > 0.2
        ORDER BY similarity(ni.canonical_norm, $2) DESC
        LIMIT $3
        "#
    ))
    .bind(rank_names)
    .bind(canonical_norm)
    .bind(limit)
    .fetch_all(db)
    .await
    .map_err(AppError::from)
}

/// 2+-token primary path: exact genus match, trigram on `canonical_norm`.
async fn query_by_genus_exact_canonical(
    db: &PgPool,
    canonical_norm: &str,
    genus: &str,
    rank_names: Option<Vec<String>>,
    limit: i64,
) -> Result<Vec<NameIndexRow>, AppError> {
    sqlx::query_as::<_, NameIndexRow>(&format!(
        r#"
        SELECT {NAME_IDX_COLS}
        FROM name_index ni
        JOIN taxa t ON ni.taxon_id = t.aphia_id
        WHERE ni.genus_norm = $1
          AND ($2::text[] IS NULL OR t.rank = ANY($2))
          AND similarity(ni.canonical_norm, $3) > 0.2
        ORDER BY similarity(ni.canonical_norm, $3) DESC
        LIMIT $4
        "#
    ))
    .bind(genus)
    .bind(rank_names)
    .bind(canonical_norm)
    .bind(limit)
    .fetch_all(db)
    .await
    .map_err(AppError::from)
}

/// 2+-token fallback path: `genus_prefix3` filter + trigram on `canonical_norm`.
async fn query_by_prefix3_canonical(
    db: &PgPool,
    canonical_norm: &str,
    prefix3: &str,
    rank_names: Option<Vec<String>>,
    limit: i64,
) -> Result<Vec<NameIndexRow>, AppError> {
    sqlx::query_as::<_, NameIndexRow>(&format!(
        r#"
        SELECT {NAME_IDX_COLS}
        FROM name_index ni
        JOIN taxa t ON ni.taxon_id = t.aphia_id
        WHERE ni.genus_prefix3 = $1
          AND ($2::text[] IS NULL OR t.rank = ANY($2))
          AND similarity(ni.canonical_norm, $3) > 0.2
        ORDER BY similarity(ni.canonical_norm, $3) DESC
        LIMIT $4
        "#
    ))
    .bind(prefix3)
    .bind(rank_names)
    .bind(canonical_norm)
    .bind(limit)
    .fetch_all(db)
    .await
    .map_err(AppError::from)
}

// ---------------------------------------------------------------------------
// Ajax-by-name-part core logic
// ---------------------------------------------------------------------------

async fn get_ajax_results(
    state: &AppState,
    name_part: &str,
    params: &AjaxByNamePartQuery,
) -> Result<Vec<TaxonResponse>, AppError> {
    let name_part = name_part.trim();
    if name_part.is_empty() {
        return Ok(vec![]);
    }

    let max_matches = params.max_matches.unwrap_or(20).clamp(1, 50) as usize;
    let rank_min = params.rank_min.unwrap_or(0);
    let rank_max = params.rank_max.unwrap_or(0);
    let excluded: HashSet<i32> = params
        .excluded_ids
        .clone()
        .unwrap_or_default()
        .into_iter()
        .collect();
    let combine_vernaculars = params.combine_vernaculars.unwrap_or(false);
    let languages: Vec<String> = params
        .languages
        .clone()
        .unwrap_or_default()
        .into_iter()
        .map(|l| l.trim().to_lowercase())
        .collect();

    let rank_names = get_rank_names_for_range(&state.db, rank_min, rank_max).await?;

    // --- Scientific-name candidates + Taxamatch ---
    let candidates =
        candidate_name_rows(&state.db, name_part, 300, rank_names.clone()).await?;

    let mut scientific_ids: Vec<i32> = Vec::new();
    if !candidates.is_empty() {
        let normalized = handle_scientific_name_input(name_part);
        let query = TaxamatchQuery {
            input: normalized,
            candidates: candidates
                .iter()
                .map(|c| TaxamatchCandidate {
                    id: c.id,
                    name: c.name_raw.clone(),
                })
                .collect(),
        };

        match match_batch(&state.http_client, &state.taxamatch_url, vec![query], 3.0).await {
            Ok(results) => {
                let matched: HashSet<i64> = results
                    .first()
                    .and_then(|r| r.matched_ids.as_ref())
                    .map(|ids| ids.iter().cloned().collect())
                    .unwrap_or_default();

                if !matched.is_empty() {
                    scientific_ids =
                        dedupe_keep_order(candidates.iter().filter_map(|c| {
                            if matched.contains(&c.id) {
                                Some(c.taxon_id)
                            } else {
                                None
                            }
                        }));
                } else {
                    scientific_ids = dedupe_keep_order(candidates.iter().map(|c| c.taxon_id));
                }
            }
            Err(_) => {
                // Taxamatch unavailable — fall back to all candidates
                scientific_ids = dedupe_keep_order(candidates.iter().map(|c| c.taxon_id));
            }
        }
    }

    // --- Optional vernacular matches ---
    let mut vern_ids: Vec<i32> = Vec::new();
    if combine_vernaculars {
        vern_ids = fetch_vernacular_taxon_ids(
            &state.db,
            name_part,
            rank_names.clone(),
            if languages.is_empty() {
                None
            } else {
                Some(languages.clone())
            },
            max_matches as i64,
        )
        .await?;
    }

    // Combine, filter excluded, resolve valid taxa
    let seen_sci: HashSet<i32> = scientific_ids.iter().cloned().collect();
    let mut all_ids = scientific_ids;
    for id in vern_ids {
        if !seen_sci.contains(&id) {
            all_ids.push(id);
        }
    }
    all_ids.retain(|id| !excluded.contains(id));

    if all_ids.is_empty() {
        return Ok(vec![]);
    }

    let taxa = fetch_taxa_by_ids_ordered(&state.db, &all_ids).await?;
    Ok(resolve_to_valid_taxa(taxa, max_matches))
}

/// Return taxon IDs matched via trigram similarity on vernacular names.
async fn fetch_vernacular_taxon_ids(
    db: &PgPool,
    name_part: &str,
    rank_names: Option<Vec<String>>,
    languages: Option<Vec<String>>,
    limit: i64,
) -> Result<Vec<i32>, AppError> {
    sqlx::query_scalar::<_, i32>(
        r#"
        SELECT taxon_id FROM (
            SELECT v.taxon_id, MAX(similarity(v.name, $1)) AS max_sim
            FROM vernaculars v
            JOIN taxa t ON v.taxon_id = t.aphia_id
            WHERE similarity(v.name, $1) > 0.2
              AND ($2::text[] IS NULL OR v.language_code = ANY($2))
              AND ($3::text[] IS NULL OR t.rank = ANY($3))
            GROUP BY v.taxon_id
        ) sub
        ORDER BY max_sim DESC
        LIMIT $4
        "#,
    )
    .bind(name_part)
    .bind(languages)
    .bind(rank_names)
    .bind(limit)
    .fetch_all(db)
    .await
    .map_err(AppError::from)
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

/// Deduplicate an iterator while preserving first-occurrence order.
fn dedupe_keep_order(iter: impl Iterator<Item = i32>) -> Vec<i32> {
    let mut seen = HashSet::new();
    iter.filter(|id| seen.insert(*id)).collect()
}

/// Resolve a list of taxa to their valid taxa, deduplicating by valid AphiaID
/// and capping the result at `max_results`.
fn resolve_to_valid_taxa(taxa: Vec<TaxonResponse>, max_results: usize) -> Vec<TaxonResponse> {
    let mut seen: HashSet<i32> = HashSet::new();
    let mut result = Vec::new();
    for t in taxa {
        let valid_id = t.valid_AphiaID;
        if seen.insert(valid_id) {
            result.push(t);
        }
        if result.len() >= max_results {
            break;
        }
    }
    result
}

/// Extract a Bearer token from the `Authorization` header.
fn extract_bearer_token(headers: &HeaderMap) -> Option<&str> {
    headers
        .get("Authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|s| s.strip_prefix("Bearer "))
        .map(str::trim)
}
