//! Split out from main.rs so integration tests (tests/fruit_test.rs) can build a router against
//! the real database without spawning a whole binary.

pub mod dto;
pub mod health;
pub mod repository;
pub mod rest;
pub mod service;
pub mod tracing_setup;

use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;

/// Same defaults as the Node.js module's `AppModule` (see nestjs11/src/app.module.ts) - every
/// sibling module hardcodes localhost:5432 for the `%prod` profile because `infra.sh` publishes
/// the container port on the benchmark host.
pub async fn connect() -> Result<PgPool, sqlx::Error> {
    let host = std::env::var("DB_HOST").unwrap_or_else(|_| "localhost".to_string());
    let port = std::env::var("DB_PORT").unwrap_or_else(|_| "5432".to_string());
    let user = std::env::var("DB_USER").unwrap_or_else(|_| "fruits".to_string());
    let password = std::env::var("DB_PASSWORD").unwrap_or_else(|_| "fruits".to_string());
    let database = std::env::var("DB_NAME").unwrap_or_else(|_| "fruits".to_string());
    // Agroal's default maximum pool size in the Quarkus modules is 20.
    let pool_max: u32 = std::env::var("DB_POOL_MAX").ok().and_then(|v| v.parse().ok()).unwrap_or(20);

    let url = format!("postgres://{user}:{password}@{host}:{port}/{database}");

    PgPoolOptions::new().max_connections(pool_max).connect(&url).await
}

pub fn app(pool: PgPool) -> axum::Router {
    let service = service::FruitService::new(repository::FruitRepository::new(pool));

    rest::router(service).merge(health::router())
}
