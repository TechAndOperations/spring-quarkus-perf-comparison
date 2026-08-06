package main

import (
	"context"
	"os"
	"strconv"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

// Observability parity with quarkus3-virtual, which runs quarkus-micrometer-opentelemetry with
// traces sampled at traceidratio 0.1. Mirrors the Node.js module's src/tracing.ts and the Rust
// module's src/tracing_setup.rs.
//
// Exports OTLP/gRPC to localhost:4317 by default (otlptracegrpc's own default), matching where
// scripts/infra.sh publishes the Grafana LGTM container's collector. Set OTEL_SDK_DISABLED=true
// to run without it.
//
// Returns a shutdown function so main.go can flush the final batch of spans on SIGTERM (the
// benchmark pipeline stops the app with `kill -15`); a no-op function is returned when disabled so
// the caller does not need an extra branch.
func initTracing(ctx context.Context) (func(context.Context) error, error) {
	noop := func(context.Context) error { return nil }

	if os.Getenv("OTEL_SDK_DISABLED") == "true" {
		return noop, nil
	}

	samplerArg := 0.1
	if v := os.Getenv("OTEL_TRACES_SAMPLER_ARG"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			samplerArg = f
		}
	}

	serviceName := os.Getenv("OTEL_SERVICE_NAME")
	if serviceName == "" {
		serviceName = "go"
	}

	exporter, err := otlptracegrpc.New(ctx)
	if err != nil {
		return noop, err
	}

	res, err := resource.Merge(resource.Default(), resource.NewSchemaless(attribute.String("service.name", serviceName)))
	if err != nil {
		return noop, err
	}

	provider := sdktrace.NewTracerProvider(
		sdktrace.WithSampler(sdktrace.TraceIDRatioBased(samplerArg)),
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
	)

	otel.SetTracerProvider(provider)

	return provider.Shutdown, nil
}
