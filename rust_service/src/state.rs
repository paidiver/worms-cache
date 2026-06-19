use sqlx::PgPool;

/// Shared application state threaded through every Axum handler via `State<AppState>`.
#[derive(Debug, Clone)]
pub struct AppState {
    pub db: PgPool,
    pub http_client: reqwest::Client,
    pub taxamatch_url: String,
    /// Bearer token required for the `/taxa/ingest` write endpoint.
    pub ingest_token: Option<String>,
}

impl AppState {
    pub fn new(db: PgPool, taxamatch_url: String, ingest_token: Option<String>) -> Self {
        let http_client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .build()
            .expect("Failed to build HTTP client");

        Self {
            db,
            http_client,
            taxamatch_url,
            ingest_token,
        }
    }
}
