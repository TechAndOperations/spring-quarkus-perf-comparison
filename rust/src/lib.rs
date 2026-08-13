//! Split out from main.rs so integration tests (tests/fruit_test.rs) can build a router against
//! the real database without spawning a whole binary.

pub mod dto;
pub mod entities;
pub mod health;
pub mod repository;
pub mod repository_orm;
pub mod repository_sql;
pub mod rest;
pub mod service;
pub mod tracing_setup;

use std::sync::Arc;

use sea_orm::SqlxPostgresConnector;
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;

use repository::FruitRepository;

/// Which read/write implementation to use, selected by the QUERY_MODE environment variable.
///
///  - `orm` (default) - SeaORM entities + relation loading (`repository_orm.rs`).
///  - `sql`            - one hand-written join, no entity hydration (`repository_sql.rs`).
///
/// Both produce identical JSON; only the persistence path differs. See repository.rs for why two
/// implementations exist.
pub fn query_mode() -> String {
    let mode = std::env::var("QUERY_MODE").unwrap_or_default();

    if mode.trim().to_lowercase() == "sql" {
        "sql".to_string()
    } else {
        "orm".to_string()
    }
}

/// Same defaults as the Node.js and Go modules - every sibling module hardcodes localhost:5432
/// for the `%prod` profile because `infra.sh` publishes the container port on the benchmark host.
///
/// Always creates a single sqlx `PgPool`, regardless of `QUERY_MODE`: the ORM path wraps this
/// same pool via `SqlxPostgresConnector` rather than opening a second one, so `DB_POOL_MAX`
/// applies identically to both modes and the two are measuring the same connection-level
/// resource usage.
pub async fn connect_pool() -> Result<PgPool, sqlx::Error> {
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

/// Builds the repository implementation selected by `query_mode()` from a shared pool.
pub fn build_repository(pool: PgPool, mode: &str) -> Arc<dyn FruitRepository> {
    if mode == "sql" {
        Arc::new(repository_sql::SqlFruitRepository::new(pool))
    } else {
        let db = SqlxPostgresConnector::from_sqlx_postgres_pool(pool);

        Arc::new(repository_orm::OrmFruitRepository::new(db))
    }
}

pub fn app(repository: Arc<dyn FruitRepository>) -> axum::Router {
    let service = service::FruitService::new(repository);

    // Route/method/status/duration spans around every request, the same depth the other
    // modules get from their own framework's built-in middleware (Quarkus/Spring's server
    // filters, NestJS's Express middleware, Go's otelhttp) - the #[instrument] in service.rs
    // only covers the application layer below this. OtelInResponseLayer must be outermost
    // (applied last / listed first) so the trace header it adds is not itself traced.
    rest::router(service)
        .merge(health::router())
        .layer(axum_tracing_opentelemetry::middleware::OtelInResponseLayer::default())
        .layer(axum_tracing_opentelemetry::middleware::OtelAxumLayer::default())
}
