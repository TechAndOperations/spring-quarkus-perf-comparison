use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Json, Response};
use axum::routing::get;
use axum::Router;

use crate::dto::{CreateFruitRequest, FruitDto};
use crate::service::FruitService;

/// Mirrors `org.acme.rest.FruitController`. Contract is the repo-wide `openapi.yml`.
///
/// Unlike the NestJS module (see nestjs11/src/rest/fruit.controller.ts), axum needs no explicit
/// override for either JAX-RS-matching behaviour: a handler returning `Json<T>` already answers
/// 200 for any method including POST (NestJS defaults POST to 201), and returning `StatusCode`
/// directly, with no body, already produces an empty 404 (no JSON error object).
pub fn router(service: FruitService) -> Router {
    Router::new()
        .route("/fruits", get(get_all).post(add_fruit))
        .route("/fruits/{name}", get(get_fruit))
        .with_state(service)
}

async fn get_all(State(service): State<FruitService>) -> Result<Json<Vec<FruitDto>>, ApiError> {
    Ok(Json(service.get_all_fruits().await?))
}

async fn get_fruit(State(service): State<FruitService>, Path(name): Path<String>) -> Result<Response, ApiError> {
    match service.get_fruit_by_name(&name).await? {
        Some(fruit) => Ok(Json(fruit).into_response()),
        None => Ok(StatusCode::NOT_FOUND.into_response()),
    }
}

async fn add_fruit(
    State(service): State<FruitService>,
    Json(body): Json<CreateFruitRequest>,
) -> Result<Response, ApiError> {
    // Mirrors class-validator's @IsNotEmpty on FruitDTO.name in the Node.js module and Hibernate
    // Validator's @NotBlank in the Java module.
    if body.name.trim().is_empty() {
        return Ok((StatusCode::BAD_REQUEST, "Name is mandatory").into_response());
    }

    Ok(Json(service.create_fruit(body).await?).into_response())
}

/// Maps any repository failure to a 500. The load test never exercises the write path and the
/// read paths only fail on infrastructure problems (pool exhaustion, DB unreachable), so this
/// stays a single catch-all rather than a per-error-kind mapping.
struct ApiError(sqlx::Error);

impl From<sqlx::Error> for ApiError {
    fn from(err: sqlx::Error) -> Self {
        Self(err)
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        tracing::error!(error = %self.0, "request failed");
        StatusCode::INTERNAL_SERVER_ERROR.into_response()
    }
}
