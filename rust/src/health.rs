use axum::routing::get;
use axum::Router;
use serde_json::{json, Value};

/// Minimal stand-in for the `quarkus-smallrye-health` endpoints the other modules expose at
/// `/q/health`. Nothing in the benchmark pipeline calls these (time-to-first-request polls
/// `TARGET_URL` instead); they exist for parity when poking at a running app by hand.
pub fn router() -> Router {
    Router::new()
        .route("/q/health", get(up))
        .route("/q/health/live", get(up))
        .route("/q/health/ready", get(up))
}

async fn up() -> axum::Json<Value> {
    axum::Json(json!({ "status": "UP", "checks": [] }))
}
