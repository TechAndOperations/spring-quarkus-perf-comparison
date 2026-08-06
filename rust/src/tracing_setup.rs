use opentelemetry::trace::TracerProvider as _;
use opentelemetry::KeyValue;
use opentelemetry_sdk::runtime::Tokio;
use opentelemetry_sdk::trace::{Sampler, TracerProvider};
use opentelemetry_sdk::Resource;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::EnvFilter;

/// Observability parity with `quarkus3-virtual`, which runs `quarkus-micrometer-opentelemetry`
/// with traces sampled at `traceidratio` 0.1. Mirrors the Node.js module's `src/tracing.ts`.
///
/// Exports OTLP/gRPC to localhost:4317 by default, matching where `scripts/infra.sh` publishes
/// the Grafana LGTM container's collector. Set OTEL_SDK_DISABLED=true to run without it.
///
/// Returns the tracer provider so main.rs can shut it down on SIGTERM (the benchmark pipeline
/// stops the app with `kill -15`); dropping it without an explicit shutdown can lose the final
/// batch of spans.
pub fn init() -> Option<TracerProvider> {
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

    let exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .build()
        .expect("failed to build OTLP span exporter");

    let provider = TracerProvider::builder()
        .with_sampler(Sampler::TraceIdRatioBased(sampler_arg))
        .with_resource(Resource::new(vec![KeyValue::new("service.name", service_name)]))
        .with_batch_exporter(exporter, Tokio)
        .build();

    let tracer = provider.tracer("rust");

    tracing_subscriber::registry()
        .with(EnvFilter::from_default_env())
        .with(tracing_subscriber::fmt::layer())
        .with(tracing_opentelemetry::layer().with_tracer(tracer))
        .init();

    Some(provider)
}
