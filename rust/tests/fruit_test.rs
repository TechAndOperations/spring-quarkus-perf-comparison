use serde_json::{json, Value};

/// Mirrors quarkus3-virtual's `FruitControllerEndToEndTest`, the Node.js module's
/// `test/fruit.e2e-spec.ts`, and the Go module's `integration_test.go`: hits the real endpoints
/// against the real database, seeded by `scripts/dbdata/db.sql`.
///
/// Requires the shared Postgres container to be up (`cd scripts && ./infra.sh -s`). OpenTelemetry
/// is disabled here so the suite does not need the LGTM collector.
///
/// Every test in this file runs against both QUERY_MODE values ("orm" and "sql") - the same
/// approach as the Go module's `forEachQueryMode`, which catches an ORM/raw-SQL divergence
/// immediately instead of relying on a manual curl/diff after the fact (see the Node.js module's
/// history for what happens when that check is only done by hand).
async fn spawn_app(mode: &str) -> String {
    std::env::set_var("OTEL_SDK_DISABLED", "true");

    let pool = rust::connect_pool().await.expect("failed to connect to the database");
    let repository = rust::build_repository(pool, mode);
    let router = rust::app(repository);

    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();

    tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });

    format!("http://{addr}")
}

const QUERY_MODES: [&str; 2] = ["orm", "sql"];

#[tokio::test]
async fn get_fruits_returns_seeded_fruits_with_nested_store_prices() {
    for mode in QUERY_MODES {
        let base = spawn_app(mode).await;
        let client = reqwest::Client::new();

        let body: Value = client.get(format!("{base}/fruits")).send().await.unwrap().json().await.unwrap();
        let fruits = body.as_array().unwrap();

        assert!(fruits.len() >= 10, "mode={mode}");

        let apple = fruits.iter().find(|f| f["name"] == "Apple").unwrap_or_else(|| panic!("mode={mode}: Apple should be seeded"));

        assert_eq!(apple["id"], 1, "mode={mode}");
        assert_eq!(apple["description"], "Hearty fruit", "mode={mode}");

        let prices = apple["storePrices"].as_array().unwrap();
        assert!(!prices.is_empty(), "mode={mode}");

        let store_1_price = prices.iter().find(|p| p["store"]["name"] == "Store 1").unwrap();

        assert_eq!(store_1_price["price"], 1.29, "mode={mode}");
        assert!(store_1_price["price"].is_number(), "mode={mode}");
        assert_eq!(store_1_price["store"]["currency"], "USD", "mode={mode}");
        assert_eq!(
            store_1_price["store"]["address"],
            json!({ "address": "123 Main St", "city": "Anytown", "country": "USA" }),
            "mode={mode}"
        );
    }
}

#[tokio::test]
async fn get_fruit_by_name_returns_the_fruit() {
    for mode in QUERY_MODES {
        let base = spawn_app(mode).await;
        let client = reqwest::Client::new();

        let response = client.get(format!("{base}/fruits/Apple")).send().await.unwrap();

        assert_eq!(response.status(), 200, "mode={mode}");

        let body: Value = response.json().await.unwrap();

        assert_eq!(body["name"], "Apple", "mode={mode}");
        assert_eq!(body["description"], "Hearty fruit", "mode={mode}");
    }
}

#[tokio::test]
async fn get_fruit_by_name_returns_404_with_empty_body_when_not_found() {
    for mode in QUERY_MODES {
        let base = spawn_app(mode).await;
        let client = reqwest::Client::new();

        let response = client.get(format!("{base}/fruits/NotAFruit")).send().await.unwrap();

        assert_eq!(response.status(), 404, "mode={mode}");
        // A NestJS/JAX-RS-style JSON error body ({"statusCode":404,...}) would fail this assertion.
        assert_eq!(response.text().await.unwrap(), "", "mode={mode}");
    }
}

#[tokio::test]
async fn post_fruits_creates_a_fruit_and_returns_200() {
    for mode in QUERY_MODES {
        let base = spawn_app(mode).await;
        let client = reqwest::Client::new();

        let name = format!(
            "Grapefruit-{mode}-{}",
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        );

        let response = client
            .post(format!("{base}/fruits"))
            .json(&json!({ "name": name, "description": "Summer fruit" }))
            .send()
            .await
            .unwrap();

        assert_eq!(response.status(), 200, "mode={mode}");

        let body: Value = response.json().await.unwrap();

        assert_eq!(body["name"], name, "mode={mode}");
        assert_eq!(body["description"], "Summer fruit", "mode={mode}");
        assert!(body["id"].as_i64().unwrap() > 10, "mode={mode}");
        // storePrices is unset on create (see repository_orm.rs/repository_sql.rs::persist) and
        // omitted when empty.
        assert!(body.get("storePrices").is_none(), "mode={mode}");

        let follow_up = client.get(format!("{base}/fruits/{name}")).send().await.unwrap();
        assert_eq!(follow_up.status(), 200, "mode={mode}");
    }
}

#[tokio::test]
async fn post_fruits_rejects_a_blank_name() {
    for mode in QUERY_MODES {
        let base = spawn_app(mode).await;
        let client = reqwest::Client::new();

        // An empty string, not an absent field: `name` is a required (non-Option) String, so an
        // absent field is rejected by serde during JSON deserialization with 422 before this
        // handler's own validation ever runs - a distinct case from the blank-string check below.
        let response = client
            .post(format!("{base}/fruits"))
            .json(&json!({ "name": "", "description": "No name" }))
            .send()
            .await
            .unwrap();

        assert_eq!(response.status(), 400, "mode={mode}");
    }
}

#[tokio::test]
async fn post_fruits_rejects_a_missing_name_field() {
    for mode in QUERY_MODES {
        let base = spawn_app(mode).await;
        let client = reqwest::Client::new();

        let response = client
            .post(format!("{base}/fruits"))
            .json(&json!({ "description": "No name" }))
            .send()
            .await
            .unwrap();

        assert_eq!(response.status(), 422, "mode={mode}");
    }
}
