use serde_json::{json, Value};

/// Mirrors quarkus3-virtual's `FruitControllerEndToEndTest` and the Node.js module's
/// `test/fruit.e2e-spec.ts`: hits the real endpoints against the real database, seeded by
/// `scripts/dbdata/db.sql`.
///
/// Requires the shared Postgres container to be up (`cd scripts && ./infra.sh -s`). OpenTelemetry
/// is disabled here so the suite does not need the LGTM collector.
async fn spawn_app() -> String {
    std::env::set_var("OTEL_SDK_DISABLED", "true");
    std::env::set_var("PORT", "0");

    let pool = axum08::connect().await.expect("failed to connect to the database");
    let router = axum08::app(pool);

    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();

    tokio::spawn(async move {
        axum::serve(listener, router).await.unwrap();
    });

    format!("http://{addr}")
}

#[tokio::test]
async fn get_fruits_returns_seeded_fruits_with_nested_store_prices() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();

    let body: Value = client.get(format!("{base}/fruits")).send().await.unwrap().json().await.unwrap();
    let fruits = body.as_array().unwrap();

    assert!(fruits.len() >= 10);

    let apple = fruits.iter().find(|f| f["name"] == "Apple").expect("Apple should be seeded");

    assert_eq!(apple["id"], 1);
    assert_eq!(apple["description"], "Hearty fruit");

    let prices = apple["storePrices"].as_array().unwrap();
    assert!(!prices.is_empty());

    let store_1_price = prices.iter().find(|p| p["store"]["name"] == "Store 1").unwrap();

    assert_eq!(store_1_price["price"], 1.29);
    assert!(store_1_price["price"].is_number());
    assert_eq!(store_1_price["store"]["currency"], "USD");
    assert_eq!(
        store_1_price["store"]["address"],
        json!({ "address": "123 Main St", "city": "Anytown", "country": "USA" })
    );
}

#[tokio::test]
async fn get_fruit_by_name_returns_the_fruit() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();

    let response = client.get(format!("{base}/fruits/Apple")).send().await.unwrap();

    assert_eq!(response.status(), 200);

    let body: Value = response.json().await.unwrap();

    assert_eq!(body["name"], "Apple");
    assert_eq!(body["description"], "Hearty fruit");
}

#[tokio::test]
async fn get_fruit_by_name_returns_404_with_empty_body_when_not_found() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();

    let response = client.get(format!("{base}/fruits/NotAFruit")).send().await.unwrap();

    assert_eq!(response.status(), 404);
    // A NestJS/JAX-RS-style JSON error body ({"statusCode":404,...}) would fail this assertion.
    assert_eq!(response.text().await.unwrap(), "");
}

#[tokio::test]
async fn post_fruits_creates_a_fruit_and_returns_200() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();

    let name = format!("Grapefruit-{}", std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos());

    let response = client
        .post(format!("{base}/fruits"))
        .json(&json!({ "name": name, "description": "Summer fruit" }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 200);

    let body: Value = response.json().await.unwrap();

    assert_eq!(body["name"], name);
    assert_eq!(body["description"], "Summer fruit");
    assert!(body["id"].as_i64().unwrap() > 10);
    // storePrices is unset on create (see FruitRepository::persist) and omitted when empty.
    assert!(body.get("storePrices").is_none());

    let follow_up = client.get(format!("{base}/fruits/{name}")).send().await.unwrap();
    assert_eq!(follow_up.status(), 200);
}

#[tokio::test]
async fn post_fruits_rejects_a_blank_name() {
    let base = spawn_app().await;
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

    assert_eq!(response.status(), 400);
}

#[tokio::test]
async fn post_fruits_rejects_a_missing_name_field() {
    let base = spawn_app().await;
    let client = reqwest::Client::new();

    let response = client
        .post(format!("{base}/fruits"))
        .json(&json!({ "description": "No name" }))
        .send()
        .await
        .unwrap();

    assert_eq!(response.status(), 422);
}
