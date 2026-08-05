# axum08

Rust (Axum + sqlx) implementation of the Fruit Store Benchmark API, ported from
[`quarkus3-virtual`](../quarkus3-virtual). It adds **Rust as a runtime category** alongside the
Node.js/NestJS module, the Quarkus modules, and the Spring Boot modules.

It implements the same contract as every other module ([`openapi.yml`](../openapi.yml)) against the
same Postgres schema ([`scripts/dbdata/db.sql`](../scripts/dbdata/db.sql)):

| Method | Path             | Response                                  |
|--------|------------------|--------------------------------------------|
| GET    | `/fruits`        | `FruitDTO[]`, 200                         |
| GET    | `/fruits/{name}` | `FruitDTO` 200, or 404 with an empty body |
| POST   | `/fruits`        | the created `FruitDTO`, 200 (not 201)     |

Source layout mirrors the other modules' spirit as closely as idiomatic Rust allows: `dto.rs`
(DTOs), `repository.rs` (SQL + row mapping), `service.rs` (thin orchestration + tracing spans),
`rest.rs` (Axum routes). There is no `domain`/`mapping` split - see "Single query implementation"
below for why.

## Running locally

Requires a recent stable Rust toolchain (built and tested with cargo/rustc 1.93.1) and the shared infrastructure containers.

```sh
cd ../scripts && ./infra.sh -s     # Postgres on :5432 (+ Grafana LGTM on :4317)
cd ../axum08
cargo build --release
./target/release/axum08            # listens on :8080
```

```sh
curl -s http://localhost:8080/fruits | jq '.[0]'
curl -s http://localhost:8080/fruits/Apple
cargo test                         # unit tests + integration tests against the seeded database
```

Configuration is environment-driven; defaults match the `%prod` profile of the Quarkus modules and
the Node.js module's env var names: `DB_HOST` (`localhost`), `DB_PORT` (`5432`), `DB_USER`/
`DB_PASSWORD`/`DB_NAME` (`fruits`), `DB_POOL_MAX` (`20`, matching Agroal's default), `PORT` (`8080`).
Set `OTEL_SDK_DISABLED=true` to run without instrumentation.

## Benchmarking

Registered as the `axum08-rust` runtime. It is **opt-in** — not in the default runtime set:

```sh
cd ../scripts/perf-lab
./run-benchmarks.sh --runtimes axum08-rust --tests run-load-test --iterations 1
```

`cargo build --release` is timed directly as the build step (`buildCmd`) - unlike the Node.js
module, no separate "assemble the build output" step is needed, because Cargo's own output
directory is already named `target/`, the same default `buildOutputDir` the pipeline already uses
for the Maven runtimes. `cargo fetch --locked` runs beforehand in the `update-rust-version` step
and is therefore excluded from the measured build time, mirroring how `./mvnw dependency:go-offline`
/ `npm ci` are excluded for the other runtimes.

The release profile ([`Cargo.toml`](Cargo.toml)) enables `lto = true`, `codegen-units = 1`, and
`panic = "abort"` - all trade build time for runtime speed and a smaller binary, appropriate for a
benchmark artifact that is compiled once and measured many times.

## Notes on comparability

- **Single query implementation, no ORM.** Rust does not have an entity-hydration ORM in the
  Hibernate/TypeORM sense, so there is no "idiomatic ORM path vs a faster raw-SQL path" choice to
  make the way there was for the Node.js module (see nestjs11/README.md, "Two query
  implementations", where the raw-SQL path measured roughly 1.7x the throughput of TypeORM). This
  module's single implementation - one hand-written join in `repository.rs`, no entity classes -
  *is* that faster shape from the outset.
- **`numeric`/`bigint` handled by casting in SQL**, not by a decimal crate: `price::float8` in the
  query text casts Postgres `numeric` to `f64` at the database, matching Java's `BigDecimal` ->
  JSON number and the Node.js module's `bigint`/`numeric` string coercion (see
  nestjs11/src/domain/numeric.transformer.ts) with less code and no extra dependency.
- **Fields are omitted with `#[serde(skip_serializing_if = ...)]`** on `description` and
  `storePrices` to replicate the Java module's `quarkus.jackson.serialization-inclusion: non-empty`
  - the same rule implemented by hand in the Node.js module's mappers.
- **JSON key order differs from `quarkus3-virtual`, harmlessly** - same situation as the Node.js
  module (see nestjs11/README.md for the full explanation). `serde` serialises struct fields in
  declaration order; Quarkus's reflection-free serializers sort keys alphabetically. Key order is
  not part of [`openapi.yml`](../openapi.yml) and does not affect response size.
- **A missing `name` field on POST returns 422, not 400.** `CreateFruitRequest.name` is a required
  (non-`Option`) `String`, so Axum's `Json` extractor rejects a request that omits the field
  entirely during deserialization, before this module's own "blank name" check
  (`rest.rs::add_fruit`) ever runs - Axum's built-in behaviour for a missing struct field is 422
  Unprocessable Entity. A present-but-empty `name` (`{"name":""}`) *does* reach the check and
  correctly returns 400, matching the other modules. Not fixed, since the write path is not
  load-tested and unifying the two cases would need extra validation middleware for no
  benchmark-relevant benefit; see `tests/fruit_test.rs` for both cases asserted explicitly.
- **OpenTelemetry - version-sensitive, least-verified part of this module.** `src/tracing_setup.rs`
  wires `opentelemetry`/`opentelemetry_sdk`/`opentelemetry-otlp`/`tracing-opentelemetry` for parity
  with `quarkus3-virtual`'s traces (sampled at `traceidratio` 0.1) and the Node.js module's OTel
  setup. These four crates must stay on matching major versions - if `cargo build` ever fails
  there after a `cargo update`, bump all four together rather than one at a time.
