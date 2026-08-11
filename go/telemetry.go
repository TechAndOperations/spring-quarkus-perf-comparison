package main

import (
	"context"
	"errors"
	"log/slog"
	"os"
	"strconv"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/contrib/instrumentation/runtime"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	logglobal "go.opentelemetry.io/otel/log/global"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

// Observability parity with quarkus3-virtual, which runs quarkus-micrometer-opentelemetry with all
// three signals on (otel.logs.enabled, otel.metrics.enabled) and traces sampled at traceidratio
// 0.1. Mirrors the Node.js module's src/tracing.ts and the Rust module's src/tracing_setup.rs.
//
// Exports OTLP/gRPC to localhost:4317 by default (each exporter's own default), matching where
// scripts/infra.sh publishes the Grafana LGTM container's collector. That collector speaks
// plaintext, so WithInsecure is required on every exporter: the otlp*grpc packages all default to
// TLS and their default endpoint carries no scheme to opt out of it. Set OTEL_SDK_DISABLED=true to
// run without any of it.
//
// Returns a shutdown function so main.go can flush the final batches on SIGTERM (the benchmark
// pipeline stops the app with `kill -15`); a no-op function is returned when disabled so the caller
// does not need an extra branch.
func initTelemetry(ctx context.Context) (func(context.Context) error, error) {
	noop := func(context.Context) error { return nil }

	if !otelEnabled() {
		return noop, nil
	}

	res, err := resource.Merge(
		resource.Default(),
		resource.NewSchemaless(attribute.String("service.name", otelServiceName())),
	)
	if err != nil {
		return noop, err
	}

	// Shut providers down in reverse order of construction, and keep going past a failing one so a
	// single stuck exporter cannot strand the batches held by the others.
	var shutdowns []func(context.Context) error

	shutdown := func(ctx context.Context) error {
		var errs []error

		for i := len(shutdowns) - 1; i >= 0; i-- {
			if err := shutdowns[i](ctx); err != nil {
				errs = append(errs, err)
			}
		}

		return errors.Join(errs...)
	}

	traceExporter, err := otlptracegrpc.New(ctx, otlptracegrpc.WithInsecure())
	if err != nil {
		return shutdown, err
	}

	tracerProvider := sdktrace.NewTracerProvider(
		sdktrace.WithSampler(sdktrace.TraceIDRatioBased(otelSamplerArg())),
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tracerProvider)
	shutdowns = append(shutdowns, tracerProvider.Shutdown)

	metricExporter, err := otlpmetricgrpc.New(ctx, otlpmetricgrpc.WithInsecure())
	if err != nil {
		return shutdown, err
	}

	meterProvider := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter)),
		sdkmetric.WithResource(res),
	)
	otel.SetMeterProvider(meterProvider)
	shutdowns = append(shutdowns, meterProvider.Shutdown)

	// Go runtime metrics (GC, goroutines, memory) - the closest analogue to the JVM metrics
	// Micrometer publishes automatically in the Quarkus and Spring modules.
	if err := runtime.Start(runtime.WithMeterProvider(meterProvider)); err != nil {
		return shutdown, err
	}

	logExporter, err := otlploggrpc.New(ctx, otlploggrpc.WithInsecure())
	if err != nil {
		return shutdown, err
	}

	loggerProvider := sdklog.NewLoggerProvider(
		sdklog.WithProcessor(sdklog.NewBatchProcessor(logExporter)),
		sdklog.WithResource(res),
	)
	logglobal.SetLoggerProvider(loggerProvider)
	shutdowns = append(shutdowns, loggerProvider.Shutdown)

	// Fan out rather than replace: Quarkus keeps logging to the console while shipping to the
	// collector, and the pipeline's app log is the only place a failing exporter can be seen at all
	// (an OTLP error cannot report itself over OTLP).
	//
	// The console side must be a fresh handler, never slog.Default().Handler(): the built-in
	// default writes through the log package, and SetDefault re-points that package at the new slog
	// default. Reusing it here would send every record log -> slog -> log and deadlock on the log
	// package's non-reentrant mutex, hanging the first caller before the server ever starts.
	slog.SetDefault(slog.New(fanoutHandler{handlers: []slog.Handler{
		slog.NewTextHandler(os.Stderr, nil),
		otelslog.NewHandler("go", otelslog.WithLoggerProvider(loggerProvider)),
	}}))

	return shutdown, nil
}

// fanoutHandler duplicates every record to each wrapped handler. slog ships no such combinator.
type fanoutHandler struct {
	handlers []slog.Handler
}

func (h fanoutHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, sub := range h.handlers {
		if sub.Enabled(ctx, level) {
			return true
		}
	}

	return false
}

func (h fanoutHandler) Handle(ctx context.Context, record slog.Record) error {
	var errs []error

	for _, sub := range h.handlers {
		if !sub.Enabled(ctx, record.Level) {
			continue
		}

		// Clone: handlers may retain the record, and Record holds shared attribute storage.
		if err := sub.Handle(ctx, record.Clone()); err != nil {
			errs = append(errs, err)
		}
	}

	return errors.Join(errs...)
}

func (h fanoutHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	subs := make([]slog.Handler, len(h.handlers))
	for i, sub := range h.handlers {
		subs[i] = sub.WithAttrs(attrs)
	}

	return fanoutHandler{handlers: subs}
}

func (h fanoutHandler) WithGroup(name string) slog.Handler {
	subs := make([]slog.Handler, len(h.handlers))
	for i, sub := range h.handlers {
		subs[i] = sub.WithGroup(name)
	}

	return fanoutHandler{handlers: subs}
}

func otelServiceName() string {
	if v := os.Getenv("OTEL_SERVICE_NAME"); v != "" {
		return v
	}

	return "go"
}

func otelSamplerArg() float64 {
	if v := os.Getenv("OTEL_TRACES_SAMPLER_ARG"); v != "" {
		if f, err := strconv.ParseFloat(v, 64); err == nil {
			return f
		}
	}

	return 0.1
}
