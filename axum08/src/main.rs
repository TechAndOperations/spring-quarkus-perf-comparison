use std::time::Instant;

use axum08::{app, connect, tracing_setup};

#[tokio::main]
async fn main() {
    // Captured as the very first statement so it covers the whole startup cost: DB pool creation,
    // router construction, and the listener bind - the same span the Node.js module measures via
    // `performance.now()` (see nestjs11/src/main.ts).
    let start = Instant::now();

    let provider = tracing_setup::init();

    let pool = connect().await.expect("failed to connect to the database");
    let router = app(pool);

    let port: u16 = std::env::var("PORT").ok().and_then(|v| v.parse().ok()).unwrap_or(8080);
    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port))
        .await
        .expect("failed to bind listener");

    // Wording mirrors Quarkus/Spring/NestJS so the pipeline's logFileStartedRegex
    // (".*axum08.+started in.*") can detect readiness - see scripts/perf-lab/main.yml watch-log.
    println!(
        "axum08 1.0 (powered by Axum) started in {:.3}s. Listening on: http://0.0.0.0:{port}",
        start.elapsed().as_secs_f64()
    );
    println!(
        "axum08 configuration: otel={}",
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
