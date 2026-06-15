use anyhow::Context;

#[derive(Debug, Clone)]
pub struct Config {
    pub database_url: String,
    pub port: u16,
    pub taxamatch_url: String,
    /// Optional Bearer token that guards the (read-only stub) ingest endpoint.
    pub ingest_token: Option<String>,
}

impl Config {
    pub fn from_env() -> anyhow::Result<Self> {
        let database_url = std::env::var("DATABASE_URL")
            .or_else(|_| build_database_url_from_parts())
            .context("DATABASE_URL or POSTGRES_* env vars must be set")?;

        let port = std::env::var("RUST_API_PORT")
            .unwrap_or_else(|_| "8002".to_string())
            .parse::<u16>()
            .context("RUST_API_PORT must be a valid port number")?;

        let taxamatch_url = std::env::var("TAXAMATCH_URL")
            .unwrap_or_else(|_| "http://taxamatch:8080".to_string())
            .trim_end_matches('/')
            .to_string();

        let ingest_token = std::env::var("INGEST_API_TOKEN")
            .ok()
            .filter(|t| !t.is_empty());

        Ok(Self {
            database_url,
            port,
            taxamatch_url,
            ingest_token,
        })
    }
}

fn build_database_url_from_parts() -> Result<String, std::env::VarError> {
    let user = std::env::var("POSTGRES_USER").unwrap_or_else(|_| "myuser".to_string());
    let password =
        std::env::var("POSTGRES_PASSWORD").unwrap_or_else(|_| "mypassword".to_string());
    let host = std::env::var("POSTGRES_HOST").unwrap_or_else(|_| "localhost".to_string());
    let port = std::env::var("POSTGRES_PORT").unwrap_or_else(|_| "5432".to_string());
    let db = std::env::var("POSTGRES_DB").unwrap_or_else(|_| "worms-cachedb".to_string());
    Ok(format!(
        "postgres://{}:{}@{}:{}/{}",
        user, password, host, port, db
    ))
}
