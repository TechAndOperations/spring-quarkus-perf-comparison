# rust

Rust (Axum + SeaORM/sqlx) implementation of the Fruit Store Benchmark API, ported from
[`quarkus3-virtual`](../quarkus3-virtual). It adds **Rust as a runtime category** alongside the
Node.js/NestJS and Go modules.

It implements the same contract as every other module ([`openapi.yml`](../openapi.yml)) against the
same Postgres schema ([`scripts/dbdata/db.sql`](../scripts/dbdata/db.sql)):

| Method | Path             | Response                                  |
|--------|------------------|--------------------------------------------|
| GET    | `/fruits`        | `FruitDTO[]`, 200                         |
| GET    | `/fruits/{name}` | `FruitDTO` 200, or 404 with an empty body |
| POST   | `/fruits`        | the created `FruitDTO`, 200 (not 201)     |

Source layout mirrors the other modules' spirit as closely as idiomatic Rust allows: `dto.rs`
(DTOs), `repository.rs` (the shared trait), `repository_orm.rs`/`entities/` (SeaORM),
`repository_sql.rs` (raw sqlx), `service.rs` (thin orchestration + tracing spans), `rest.rs`
(Axum routes).

## Two query implementations, selectable at runtime

This module ships **two first-class benchmark runtimes** built from the same binary, selected by
the `QUERY_MODE` environment variable:

- **`rust-orm`** (`QUERY_MODE=orm`, the **default**, [`repository_orm.rs`](src/repository_orm.rs),
  [`entities/`](src/entities)) - SeaORM entities + relation loading, the structural analogue of
  quarkus3-virtual's Hibernate relations, the Node.js module's TypeORM path, and `go-orm`.
- **`rust-sql`** (`QUERY_MODE=sql`, [`repository_sql.rs`](src/repository_sql.rs)) - a single
  hand-written join, manual row mapping, no entity hydration. The same shape as the Node.js
  module's faster "sql" mode and `go-sql`.

Both implementations are wired behind one `FruitRepository` trait ([`repository.rs`](src/repository.rs))
via `async-trait` (native async-fn-in-traits is not yet dyn-compatible, and `main.rs` selects an
implementation at runtime behind `Arc<dyn FruitRepository>`). Both share the *same* `sqlx::PgPool`
- the ORM path wraps it via `SqlxPostgresConnector` rather than opening a second pool - so
`DB_POOL_MAX` and connection-level resource usage are identical between modes; only the query
shape differs.

Both are registered as separate entries in `scripts/perf-lab/main.yml` rather than one runtime
toggled by an env var, and [`tests/fruit_test.rs`](tests/fruit_test.rs) runs every assertion
against both modes on every `cargo test` invocation - the same approach taken in `go/` for
`go-sql`/`go-orm`, adopted here for the same reason: the Node.js module's ORM-vs-raw-SQL
comparison was first done by hand, with one-off manual runs on different occasions rather than a
controlled same-session A/B, and that produced an initially wrong read of the speedup. Two
first-class runtimes benchmarked by the same pipeline invocation, with the same iteration count,
avoid that failure mode, and the dual-mode test suite catches an ORM/raw-SQL divergence
immediately instead of relying on someone remembering to check it later.

### Why `orm` (SeaORM) is the default

Unlike the raw-SQL path, which was already proven faster in both the Node.js and Go modules, there
was no equivalent question already answered for Rust when this module was first written - it
shipped with only the raw-SQL path, since sqlx has no ORM layer of its own. SeaORM was added
afterwards specifically to let this module ask the same question the other two already had an
answer for. Defaulting to `orm` (rather than defaulting to the already-known-fast `sql`) means a
plain `cargo run`/`./target/release/rust` with no environment variable set exercises the same
"idiomatic ORM path" every other module defaults to for local development - `rust-sql` remains
one environment variable away, and both are equally first-class in the benchmark pipeline
regardless of which the binary defaults to.

## Running locally

Requires a recent stable Rust toolchain (built and tested with cargo/rustc 1.93.1) and the shared
infrastructure containers.

```sh
cd ../scripts && ./infra.sh -s     # Postgres on :5432 (+ Grafana LGTM on :4317)
cd ../rust
cargo build --release
QUERY_MODE=orm ./target/release/rust     # or QUERY_MODE=sql; defaults to orm
```

```sh
curl -s http://localhost:8080/fruits | jq '.[0]'
curl -s http://localhost:8080/fruits/Apple
cargo test     # unit tests + integration tests against the seeded database, both query modes
```

Configuration is environment-driven; defaults match the `%prod` profile of the Quarkus modules and
the Node.js/Go modules' env var names: `DB_HOST` (`localhost`), `DB_PORT` (`5432`), `DB_USER`/
`DB_PASSWORD`/`DB_NAME` (`fruits`), `DB_POOL_MAX` (`20`, matching Agroal's default), `PORT` (`8080`).
Set `OTEL_SDK_DISABLED=true` to run without instrumentation.

## Benchmarking

Registered as the `rust-orm` and `rust-sql` runtimes. Both are **opt-in** — neither is in the
default runtime set:

```sh
cd ../scripts/perf-lab
./run-benchmarks.sh --runtimes rust-orm,rust-sql --tests run-load-test --iterations 3
```

`cargo clean && cargo build --release` is timed directly as the build step (`buildCmd`) for both
runtimes - no separate "assemble the build output" step is needed, because Cargo's own output
directory is already named `target/`, the same default `buildOutputDir` the pipeline already uses
for the Maven runtimes. `cargo fetch --locked` runs beforehand in the `update-rust-version` step
and is therefore excluded from the measured build time, mirroring how `./mvnw dependency:go-offline`
/ `npm ci` are excluded for the other runtimes. Both runtimes compile the identical binary and only
differ in the `QUERY_MODE` environment variable set in their `runCmd` - expect their build-time
measurements to be near-identical; only startup/RSS/throughput should meaningfully differ between
them.

**The `cargo clean` is deliberate and costs real time.** `clone-repo` copies this module to a
fresh absolute path once per pipeline run, but every iteration after the first reuses that same
copy's `target/` - without an explicit clean, Cargo's incremental cache turns iterations 2+ into
near-instant relinks instead of real builds (measured on one 3-iteration run: 216.37s, then 3.04s,
then 0.16s). That is not comparable to the JVM runtimes, which always run `mvnw clean package` and
are therefore cold on every iteration already, nor to `go`, whose builds are fast enough that
the effect is negligible. `cargo clean` deletes the *entire* `target/` directory, including every
already-compiled dependency (LTO recompiles the whole ~270-crate dependency graph from scratch),
so expect each iteration's build step to take the full cold-build time (several minutes with LTO
enabled) rather than the few seconds an incremental rebuild would take - `--iterations 3` on
`rust-orm`+`rust-sql` together therefore adds a meaningful amount of wall-clock time to a run that
includes them, by design.

The release profile ([`Cargo.toml`](Cargo.toml)) enables `lto = true`, `codegen-units = 1`, and
`panic = "abort"` - all trade build time for runtime speed and a smaller binary, appropriate for a
benchmark artifact that is compiled once and measured many times.

## Notes on comparability

- **`numeric`/`bigint` handled by casting in SQL**, not by a decimal crate: `price::float8` in the
  raw-SQL query text casts Postgres `numeric` to `f64` at the database, matching Java's
  `BigDecimal` -> JSON number and the Node.js module's `bigint`/`numeric` string coercion (see
  `nodejs/src/domain/numeric.transformer.ts`) with less code and no extra dependency. SeaORM's
  entities (`entities/*.rs`) map the same columns straight to `i64`/`f64` fields with no casting
  needed on that side either.
- **SeaORM has no embedded-value-object concept.** Unlike JPA's `@Embeddable`/TypeORM's
  `{ prefix: false }`/GORM's `embedded` tag, there is no separate `Address` entity in
  `entities/store.rs` - `address`/`city`/`country` are flat fields directly on `store::Model`. The
  DTO layer (`dto.rs`) is what reassembles them into a nested `AddressDto` on the way out, exactly
  as `go`'s GORM entities do.
- **SeaORM's eager loading is two queries, not one JOIN for the full two-level relation.**
  `find_also_related` (used in `repository_orm.rs` to join `store_fruit_prices` to `stores`) *does*
  emit a single JOIN for that pair - matching the TypeORM module's `find({ relations })` - but
  loading `fruit -> store_fruit_price -> store` still takes two queries total (one for fruits, one
  for the price/store join), with the grouping-by-`fruit_id` done in application code afterwards.
  This is a different shape from GORM's `Preload`, which issues a separate query per relation
  level, and from the raw-SQL path's single three-way join - each represents its own
  library's idiomatic default, not a bug.
- **Fields are omitted with `#[serde(skip_serializing_if = ...)]`** on `description` and
  `storePrices` to replicate the Java module's `quarkus.jackson.serialization-inclusion: non-empty`
  - the same rule implemented by hand in the Node.js module's mappers and via `json:"...,omitempty"`
  in the Go module.
- **JSON key order differs from `quarkus3-virtual`, harmlessly** - same situation as the Node.js
  and Go modules (see `nodejs/README.md` for the full explanation). `serde` serialises struct
  fields in declaration order; Quarkus's reflection-free serializers sort keys alphabetically. Key
  order is not part of [`openapi.yml`](../openapi.yml) and does not affect response size.
- **A missing `name` field on POST returns 422, not 400, in both modes.** `CreateFruitRequest.name`
  is a required (non-`Option`) `String`, so Axum's `Json` extractor rejects a request that omits
  the field entirely during deserialization, before this module's own "blank name" check
  (`rest.rs::add_fruit`) ever runs - Axum's built-in behaviour for a missing struct field is 422
  Unprocessable Entity. A present-but-empty `name` (`{"name":""}`) *does* reach the check and
  correctly returns 400, matching the other modules. Not fixed, since the write path is not
  load-tested and unifying the two cases would need extra validation middleware for no
  benchmark-relevant benefit; see `tests/fruit_test.rs` for both cases asserted explicitly, and
  `go/README.md` for why the Go module does not have this asymmetry.
- **`nextval('fruits_seq')` is a manual call in both implementations.** Neither SeaORM nor sqlx has
  an equivalent of Hibernate's `@SequenceGenerator`; `fruits.id` has no `DEFAULT` in
  `scripts/dbdata/db.sql`, so both `repository_orm.rs::persist` and `repository_sql.rs::persist`
  fetch the next sequence value explicitly before inserting - same requirement as `go`'s two
  repositories.
- **OpenTelemetry - version-sensitive, least-verified part of this module.** `src/tracing_setup.rs`
  wires `opentelemetry`/`opentelemetry_sdk`/`opentelemetry-otlp`/`tracing-opentelemetry` for parity
  with `quarkus3-virtual`'s traces (sampled at `traceidratio` 0.1) and the Node.js/Go modules' OTel
  setup. These four crates must stay on matching major versions - if `cargo build` ever fails
  there after a `cargo update`, bump all four together rather than one at a time.
