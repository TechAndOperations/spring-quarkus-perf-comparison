use opentelemetry::trace::TracerProvider as _;
use opentelemetry::KeyValue;
use opentelemetry_appender_tracing::layer::OpenTelemetryTracingBridge;
use opentelemetry_sdk::logs::LoggerProvider;
use opentelemetry_sdk::runtime::Tokio;
use opentelemetry_sdk::trace::{Sampler, TracerProvider};
use opentelemetry_sdk::Resource;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::EnvFilter;
use tracing_subscriber::Layer;

/// Traces and logs, held together so main.rs can flush both on SIGTERM (the benchmark pipeline
/// stops the app with `kill -15`); dropping a provider without an explicit shutdown can lose its
/// final batch.
///
/// No metrics: `opentelemetry-instrumentation-tokio` has no release compatible with the 0.27 line
/// this module is pinned to, and hand-rolled instruments would not match what Micrometer publishes
/// automatically in the Quarkus modules. Tracked in rust/README.md.
pub struct Telemetry {
    tracer_provider: TracerProvider,
    logger_provider: LoggerProvider,
}

impl Telemetry {
    pub fn shutdown(&self) {
        let _ = self.tracer_provider.shutdown();
        let _ = self.logger_provider.shutdown();
    }
}

/// Observability parity with `quarkus3-virtual`, which runs `quarkus-micrometer-opentelemetry`
/// with traces sampled at `traceidratio` 0.1 and logs enabled. Mirrors the Node.js module's
/// `src/tracing.ts` and the Go module's `telemetry.go`.
///
/// Exports OTLP/gRPC to localhost:4317 by default, matching where `scripts/infra.sh` publishes
/// the Grafana LGTM container's collector. Set OTEL_SDK_DISABLED=true to run without it.
pub fn init() -> Option<Telemetry> {
    if std::env::var("OTEL_SDK_DISABLED").as_deref() == Ok("true") {
        tracing_subscriber::registry()
            .with(EnvFilter::from_default_env())
            .with(tracing_subscriber::fmt::layer())
            .init();

        return None;
    }

    let sampler_arg: f64 = std::env::var("OTEL_TRACES_SAMPLER_ARG")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(0.1);

    let service_name = std::env::var("OTEL_SERVICE_NAME").unwrap_or_else(|_| "rust".to_string());
    let resource = Resource::new(vec![KeyValue::new("service.name", service_name)]);

    let span_exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .build()
        .expect("failed to build OTLP span exporter");

    let tracer_provider = TracerProvider::builder()
        .with_sampler(Sampler::TraceIdRatioBased(sampler_arg))
        .with_resource(resource.clone())
        .with_batch_exporter(span_exporter, Tokio)
        .build();

    let log_exporter = opentelemetry_otlp::LogExporter::builder()
        .with_tonic()
        .build()
        .expect("failed to build OTLP log exporter");

    let logger_provider = LoggerProvider::builder()
        .with_resource(resource)
        .with_batch_exporter(log_exporter, Tokio)
        .build();

    let tracer = tracer_provider.tracer("rust");

    // Per-layer filters, not a global one: the `#[instrument]` spans in service.rs are INFO, but
    // EnvFilter::from_default_env() falls back to ERROR when RUST_LOG is unset (the benchmark
    // pipeline never sets it), which would silently starve the exporters. Filtering per layer feeds
    // those records to OpenTelemetry while leaving console output on RUST_LOG, so the fmt layer does
    // not log a line per request under load.
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer().with_filter(EnvFilter::from_default_env()))
        .with(
            tracing_opentelemetry::layer()
                .with_tracer(tracer)
                .with_filter(EnvFilter::new("info")),
        )
        .with(OpenTelemetryTracingBridge::new(&logger_provider).with_filter(EnvFilter::new("info")))
        .init();

    Some(Telemetry { tracer_provider, logger_provider })
}
