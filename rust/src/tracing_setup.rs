use opentelemetry::trace::TracerProvider as _;
use opentelemetry_appender_tracing::layer::OpenTelemetryTracingBridge;
use opentelemetry_sdk::logs::SdkLoggerProvider;
use opentelemetry_sdk::metrics::SdkMeterProvider;
use opentelemetry_sdk::trace::{Sampler, SdkTracerProvider};
use opentelemetry_sdk::Resource;
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::util::SubscriberInitExt;
use tracing_subscriber::EnvFilter;
use tracing_subscriber::Layer;

/// Traces, logs and metrics, held together so main.rs can flush all three on SIGTERM (the
/// benchmark pipeline stops the app with `kill -15`); dropping a provider without an explicit
/// shutdown can lose its final batch.
pub struct Telemetry {
    tracer_provider: SdkTracerProvider,
    logger_provider: SdkLoggerProvider,
    meter_provider: SdkMeterProvider,
}

impl Telemetry {
    pub fn shutdown(&self) {
        let _ = self.tracer_provider.shutdown();
        let _ = self.logger_provider.shutdown();
        let _ = self.meter_provider.shutdown();
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
    let resource = Resource::builder().with_service_name(service_name).build();

    let span_exporter = opentelemetry_otlp::SpanExporter::builder()
        .with_tonic()
        .build()
        .expect("failed to build OTLP span exporter");

    let tracer_provider = SdkTracerProvider::builder()
        .with_sampler(Sampler::TraceIdRatioBased(sampler_arg))
        .with_resource(resource.clone())
        .with_batch_exporter(span_exporter)
        .build();

    let log_exporter = opentelemetry_otlp::LogExporter::builder()
        .with_tonic()
        .build()
        .expect("failed to build OTLP log exporter");

    let logger_provider = SdkLoggerProvider::builder()
        .with_resource(resource.clone())
        .with_batch_exporter(log_exporter)
        .build();

    // Periodic export, not a batch processor: metrics are pulled on a timer
    // (OTEL_METRIC_EXPORT_INTERVAL, default 60s) rather than pushed per-event like spans and
    // logs, since Tokio's runtime gauges (worker count, queue depth) are cheap to sample and
    // don't need per-change delivery.
    let metric_exporter = opentelemetry_otlp::MetricExporter::builder()
        .with_tonic()
        .build()
        .expect("failed to build OTLP metric exporter");

    let meter_provider = SdkMeterProvider::builder()
        .with_resource(resource)
        .with_periodic_exporter(metric_exporter)
        .build();

    opentelemetry::global::set_meter_provider(meter_provider.clone());
    // Registers the observable instruments against the current Tokio runtime - must run inside
    // it, which init() does since main.rs calls it from within #[tokio::main]. See
    // rust/README.md for the metric names this exposes.
    opentelemetry_instrumentation_tokio::observe_current_runtime();

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

    Some(Telemetry { tracer_provider, logger_provider, meter_provider })
}
