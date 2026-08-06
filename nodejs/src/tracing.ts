import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-grpc';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { NodeSDK } from '@opentelemetry/sdk-node';
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { TraceIdRatioBasedSampler } from '@opentelemetry/sdk-trace-base';
import { ATTR_SERVICE_NAME, ATTR_SERVICE_VERSION } from '@opentelemetry/semantic-conventions';

/**
 * Observability parity with `quarkus3-virtual`, which runs `quarkus-micrometer-opentelemetry`
 * with traces sampled at `traceidratio` 0.1, metrics and logs enabled, and JDBC telemetry on.
 * Benchmarking this module without comparable instrumentation would measure a materially
 * lighter application than the JVM modules it is being compared against.
 *
 * Imported first in main.ts so the auto-instrumentations can patch http/pg/nestjs-core before
 * those modules are required. Exports OTLP/gRPC to localhost:4317 by default, which is where
 * scripts/infra.sh publishes the Grafana LGTM container.
 *
 * Set OTEL_SDK_DISABLED=true to measure without instrumentation.
 */
if (process.env.OTEL_SDK_DISABLED !== 'true') {
  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME || 'nodejs',
      [ATTR_SERVICE_VERSION]: '1.0'
    }),
    sampler: new TraceIdRatioBasedSampler(Number(process.env.OTEL_TRACES_SAMPLER_ARG || 0.1)),
    traceExporter: new OTLPTraceExporter(),
    metricReader: new PeriodicExportingMetricReader({ exporter: new OTLPMetricExporter() }),
    instrumentations: [
      getNodeAutoInstrumentations({
        // Extremely chatty and has no analogue in the Quarkus module's instrumentation.
        '@opentelemetry/instrumentation-fs': { enabled: false }
      })
    ]
  });

  sdk.start();

  // The benchmark pipeline stops the app with `kill -15` (main.yml `kill -15 $APP_PID`).
  process.once('SIGTERM', () => {
    sdk.shutdown().finally(() => process.exit(0));
  });
}
