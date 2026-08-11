package main

import (
	"context"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/exaring/otelpgx"
	"github.com/jackc/pgx/v5/pgxpool"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	gormlogger "gorm.io/gorm/logger"
	"gorm.io/plugin/opentelemetry/tracing"
)

func main() {
	// Captured as the very first statement so it covers the whole startup cost: DB connection,
	// router construction, and the listener bind - the same span the Node.js and Rust modules
	// measure (see nodejs/src/main.ts, rust/src/main.rs).
	start := time.Now()

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM)
	defer stop()

	shutdownTelemetry, err := initTelemetry(ctx)
	if err != nil {
		slog.Error("failed to init telemetry", "error", err)
		os.Exit(1)
	}

	// Which read implementation to use: `sql` (default) - a single hand-written join, no
	// hydration; or `orm` - GORM entities + Preload, the structural analogue of quarkus3-virtual's
	// Hibernate relations and the Node.js module's TypeORM path. See repository.go.
	queryMode := envOrDefault("QUERY_MODE", "sql")

	repository, closeDB, err := connect(ctx, queryMode)
	if err != nil {
		slog.Error("failed to connect to the database", "error", err)
		os.Exit(1)
	}

	service := newFruitService(repository)
	mux := newMux(service)

	port := envOrDefault("PORT", "8080")

	listener, err := net.Listen("tcp", ":"+port)
	if err != nil {
		slog.Error("failed to bind listener", "error", err)
		os.Exit(1)
	}

	// The HTTP server span and the http.server.* metrics that quarkus3-virtual gets from its REST
	// layer. Without this the module reported a single service-level span per request against
	// Quarkus's two to three, which understated its observability cost in the benchmark. Skipped
	// when telemetry is off so that path keeps costing nothing.
	var handler http.Handler = mux
	if otelEnabled() {
		handler = otelhttp.NewHandler(mux, "http.server")
	}

	server := &http.Server{Handler: handler}

	go func() {
		<-ctx.Done()

		// The benchmark pipeline stops the app with `kill -15` (main.yml `kill -15 $APP_PID`);
		// graceful shutdown lets in-flight requests finish instead of dropping them.
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		_ = server.Shutdown(shutdownCtx)
	}()

	// Wording mirrors Quarkus/Spring/NestJS/Axum so the pipeline's logFileStartedRegex
	// (".*go.+started in.*") can detect readiness - see scripts/perf-lab/main.yml watch-log.
	fmt.Printf(
		"go 1.0 (net/http, query mode=%s) started in %.3fs. Listening on: http://0.0.0.0:%s\n",
		queryMode, time.Since(start).Seconds(), port,
	)
	// Through slog, not fmt: it is the module's only log record on a clean run, and without it the
	// OTLP log pipeline carries nothing and the service never appears in Loki - every other slog
	// call here is an Error that only fires on failure. quarkus3-virtual populates Loki the same
	// way, from its own startup lines. The readiness line above stays on fmt so the pipeline's
	// logFileStartedRegex keeps matching a bare, unprefixed line.
	slog.Info("go configuration", "queryMode", queryMode, "otel", otelStatus())

	if err := server.Serve(listener); err != nil && err != http.ErrServerClosed {
		slog.Error("server error", "error", err)
	}

	closeDB()
	_ = shutdownTelemetry(context.Background())
}

// Same defaults as the Node.js and Rust modules - every sibling module hardcodes localhost:5432
// for the %prod profile because infra.sh publishes the container port on the benchmark host.
func connect(ctx context.Context, queryMode string) (FruitRepository, func(), error) {
	dsn := fmt.Sprintf(
		"postgres://%s:%s@%s:%s/%s",
		envOrDefault("DB_USER", "fruits"), envOrDefault("DB_PASSWORD", "fruits"),
		envOrDefault("DB_HOST", "localhost"), envOrDefault("DB_PORT", "5432"),
		envOrDefault("DB_NAME", "fruits"),
	)

	if queryMode == "orm" {
		db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{Logger: gormlogger.Default.LogMode(gormlogger.Silent)})
		if err != nil {
			return nil, nil, err
		}

		// The SQL spans Hibernate emits in the Quarkus modules; otelpgx does the same job on the
		// raw-SQL path below.
		if otelEnabled() {
			if err := db.Use(tracing.NewPlugin()); err != nil {
				return nil, nil, err
			}
		}

		sqlDB, err := db.DB()
		if err != nil {
			return nil, nil, err
		}

		// Agroal's default maximum pool size in the Quarkus modules is 20.
		sqlDB.SetMaxOpenConns(poolMax())

		return newGormFruitRepository(db), func() { _ = sqlDB.Close() }, nil
	}

	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, nil, err
	}

	cfg.MaxConns = int32(poolMax())

	if otelEnabled() {
		cfg.ConnConfig.Tracer = otelpgx.NewTracer()
	}

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, nil, err
	}

	if err := pool.Ping(ctx); err != nil {
		return nil, nil, err
	}

	return newPgxFruitRepository(pool), pool.Close, nil
}

func poolMax() int {
	n, err := strconv.Atoi(envOrDefault("DB_POOL_MAX", "20"))
	if err != nil {
		return 20
	}

	return n
}

func envOrDefault(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}

	return fallback
}

func otelEnabled() bool {
	return os.Getenv("OTEL_SDK_DISABLED") != "true"
}

func otelStatus() string {
	if !otelEnabled() {
		return "off"
	}

	return "on"
}
