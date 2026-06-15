use std::net::SocketAddr;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod db;
mod errors;
mod extractors;
mod handlers;
mod models;
mod names;
mod openapi;
mod routes;
mod state;
mod taxamatch;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Load .env if present (ignored when the file does not exist)
    let _ = dotenvy::dotenv();

    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "worms_cache_rust=debug,tower_http=debug,info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let cfg = config::Config::from_env()?;
    let pool = db::create_pool(&cfg.database_url).await?;

    let app = routes::create_router(pool, cfg.taxamatch_url.clone(), cfg.ingest_token.clone());

    let addr: SocketAddr = format!("0.0.0.0:{}", cfg.port).parse()?;
    tracing::info!("worms-cache-rust listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
