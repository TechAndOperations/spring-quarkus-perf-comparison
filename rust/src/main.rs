use std::time::Instant;

use rust::{app, build_repository, connect_pool, query_mode, tracing_setup};

#[tokio::main]
async fn main() {
    // Captured as the very first statement so it covers the whole startup cost: DB pool
    // creation, router construction, and the listener bind - the same span the Node.js and Go
    // modules measure (see nodejs/src/main.ts, go/main.go).
    let start = Instant::now();

    let provider = tracing_setup::init();

    let mode = query_mode();

    let pool = connect_pool().await.expect("failed to connect to the database");
    let repository = build_repository(pool, &mode);
    let router = app(repository);

    let port: u16 = std::env::var("PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(8080);
    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port))
        .await
        .expect("failed to bind listener");

    // Wording mirrors Quarkus/Spring/NestJS/Go so the pipeline's logFileStartedRegex
    // (".*rust.+started in.*") can detect readiness - see scripts/perf-lab/main.yml watch-log.
    println!(
        "rust 1.0 (powered by Axum, query mode={mode}) started in {:.3}s. Listening on: http://0.0.0.0:{port}",
        start.elapsed().as_secs_f64()
    );
    println!(
        "rust configuration: otel={}",
        if std::env::var("OTEL_SDK_DISABLED").as_deref() == Ok("true") { "off" } else { "on" }
    );

    axum::serve(listener, router)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .expect("server error");

    // The benchmark pipeline stops the app with `kill -15` (main.yml `kill -15 $APP_PID`);
    // graceful shutdown above lets this run before the process exits, flushing the final batch
    // of spans instead of dropping them.
    if let Some(provider) = provider {
        let _ = provider.shutdown();
    }
}

async fn shutdown_signal() {
    tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        .expect("failed to install SIGTERM handler")
        .recv()
        .await;
}
