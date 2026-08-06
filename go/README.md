# go

Go (net/http + pgx/GORM) implementation of the Fruit Store Benchmark API, ported from
[`quarkus3-virtual`](../quarkus3-virtual). It adds **Go as a runtime category** alongside the
Node.js/NestJS and Rust/Axum modules.

It implements the same contract as every other module ([`openapi.yml`](../openapi.yml)) against the
same Postgres schema ([`scripts/dbdata/db.sql`](../scripts/dbdata/db.sql)):

| Method | Path             | Response                                  |
|--------|------------------|--------------------------------------------|
| GET    | `/fruits`        | `FruitDTO[]`, 200                         |
| GET    | `/fruits/{name}` | `FruitDTO` 200, or 404 with an empty body |
| POST   | `/fruits`        | the created `FruitDTO`, 200 (not 201)     |

There is no web framework dependency: `net/http`'s pattern-based `ServeMux` (Go 1.22+) is enough
for three routes, and Go's standard library culture leans toward not adding a router dependency
for a case this small.

## Two query implementations, selectable at runtime

Unlike the Rust module (which has no ORM at all) or the Node.js module (whose two modes are two
code paths behind an env var, tested manually), this module ships **two first-class benchmark
runtimes** built from the same binary:

- **`go-sql`** (`QUERY_MODE=sql`, [`repository_pgx.go`](repository_pgx.go)) - a single
  hand-written join, manual row mapping, no entity hydration. The same shape as the Rust module
  and the Node.js module's faster "sql" mode.
- **`go-orm`** (`QUERY_MODE=orm`, [`repository_gorm.go`](repository_gorm.go),
  [`entities_gorm.go`](entities_gorm.go)) - GORM entities + `Preload`, the structural analogue of
  quarkus3-virtual's Hibernate relations and the Node.js module's TypeORM path.

Both are registered as separate entries in `scripts/perf-lab/main.yml` rather than one runtime
toggled by an env var, and [`integration_test.go`](integration_test.go) runs every assertion
against both modes on every `go test` invocation. This is deliberately stricter than how the
Node.js module's ORM-vs-raw-SQL comparison was first done: by hand, with one-off manual runs on
different occasions rather than a controlled same-session A/B. That produced an initially wrong
read of the speedup - a factor was first reported by comparing two measurements taken in different
sessions (and therefore different machine states), and only corrected once both modes were
re-measured back-to-back in the same session. Two first-class runtimes benchmarked by the same
pipeline invocation, with the same iteration count, avoid that failure mode entirely, and the
dual-mode test suite catches a pgx/GORM divergence immediately instead of relying on someone
remembering to check it later.

## Running locally

Requires a Go toolchain (built and tested with `go1.26.0`) and the shared infrastructure
containers.

```sh
cd ../scripts && ./infra.sh -s     # Postgres on :5432 (+ Grafana LGTM on :4317)
cd ../go
go build -ldflags="-s -w" -o target/release/go .
QUERY_MODE=sql ./target/release/go     # or QUERY_MODE=orm; defaults to sql
```

```sh
curl -s http://localhost:8080/fruits | jq '.[0]'
curl -s http://localhost:8080/fruits/Apple
go test ./...     # unit tests + integration tests against the seeded database, both query modes
```

Configuration is environment-driven; defaults match the `%prod` profile of the Quarkus modules and
the Node.js/Rust modules' env var names: `DB_HOST` (`localhost`), `DB_PORT` (`5432`), `DB_USER`/
`DB_PASSWORD`/`DB_NAME` (`fruits`), `DB_POOL_MAX` (`20`, matching Agroal's default), `PORT` (`8080`).
Set `OTEL_SDK_DISABLED=true` to run without instrumentation.

## Benchmarking

Registered as the `go-sql` and `go-orm` runtimes. Both are **opt-in** — neither is in the
default runtime set:

```sh
cd ../scripts/perf-lab
./run-benchmarks.sh --runtimes go-sql,go-orm --tests run-load-test --iterations 3
```

`go build -a -ldflags="-s -w" -o target/release/go .` is timed directly as the build step
(`buildCmd`); `-s -w` strips the symbol table and DWARF debug info, shrinking the binary, the
closest Go equivalent of the Rust module's `[profile.release]` tuning (LTO, `codegen-units = 1`,
`panic = "abort"`). `go mod download` runs beforehand in the `update-go-version` step and is
therefore excluded from the measured build time, mirroring how `cargo fetch`/`npm ci` are excluded
for the other runtimes. Both runtimes compile the identical binary and only differ in the
`QUERY_MODE` environment variable set in their `runCmd` - expect their build-time measurements to
be near-identical; only startup/RSS/throughput should meaningfully differ between them.

**The `-a` flag is deliberate and costs real time.** `clone-repo` copies this module to a fresh
absolute path once per pipeline run, but every iteration after the first reuses that same copy's
build - without forcing a full rebuild, Go's build cache would turn iterations 2+ into
near-instant no-op relinks instead of real builds, the same problem `rust-orm`/`rust-sql` hit
(see `rust/README.md`). Unlike Cargo's `target/`, which is per-project, Go's build cache
(`$GOCACHE`) is global across every Go project on the host, so `go clean -cache` was rejected as
the fix here - it would invalidate unrelated projects' cached builds too. `go build -a` instead
forces this invocation to recompile every package from source without touching the shared cache,
achieving the same per-iteration cold build without the collateral damage.

Go's runtime auto-sizes `GOMAXPROCS` from the visible CPU affinity mask (`sched_getaffinity` on
Linux), so `taskset --cpu-list` pinning works transparently with no extra runtime flag - unlike
Node.js, there is no equivalent of `--max-old-space-size`/`-Xmx` to set.

## Notes on comparability

- **`bigint`/`numeric` need no coercion.** `pgx` already returns Postgres `bigint`/`numeric` as
  Go's native `int64`/`float64` (`price::float8` in the SQL just avoids pulling in a
  bignum/decimal dependency for exact-decimal semantics no test here relies on). This is unlike
  node-postgres, which returns both as strings and required an explicit transformer (see
  `nodejs/src/domain/numeric.transformer.ts`).
- **Fields are omitted with `json:"...,omitempty"`** on `Description` and `StorePrices` to
  replicate the Java module's `quarkus.jackson.serialization-inclusion: non-empty` - the same rule
  implemented by hand in the Node.js module's mappers and via `#[serde(skip_serializing_if)]` in
  the Rust module. Go's `omitempty` already treats an empty string and a nil/zero-length slice as
  empty, so (unlike the other two modules) no manual per-field emptiness checks are needed.
- **JSON key order differs from `quarkus3-virtual`, harmlessly** - same situation as the Node.js
  and Rust modules (see `nodejs/README.md` for the full explanation). `encoding/json` marshals
  struct fields in declaration order; Quarkus's reflection-free serializers sort keys
  alphabetically. Key order is not part of [`openapi.yml`](../openapi.yml) and does not affect
  response size.
- **A missing `name` field and a blank `name` behave identically here - a small parity win over
  the Rust module.** `CreateFruitRequest.Description` is a `*string` specifically so an absent
  JSON field and an explicit empty string are distinguishable when persisting (nil -> SQL `NULL`,
  matching Java's `Fruit.setDescription(fruitDTO.description())` when the DTO's description is
  null); but `Name` is a plain `string`, and `encoding/json` silently leaves an absent field at its
  zero value (`""`) rather than erroring, so both an absent and a blank `name` reach the same
  `strings.TrimSpace(...) == ""` check and return 400. The Rust module cannot make this two fields
  behave the same way: its `name` field being a non-`Option` `String` means a *missing* field is
  rejected by `serde` with 422 before the module's own validation ever runs, while a
  *present-but-empty* string reaches the check and correctly returns 400 (see
  `rust/README.md`). Go's zero-value semantics happen to close that gap for free.
- **GORM's eager loading issues multiple queries, not one JOIN.** `Preload("StorePrices.Store")`
  is GORM's idiomatic default: one query for `fruits`, then a second batched query for
  `store_fruit_prices` + `stores`. This is a genuine difference from the TypeORM module's
  `find({ relations })`, which does emit a single JOIN, and from `go-sql`'s single
  hand-written join - each represents its own ecosystem's idiomatic default, not a bug.

### Known limitation

The pipeline detects build failures by grepping the build log for the literal string
`BUILD FAILURE` (`scripts/perf-lab/main.yml`, `measure-build-times`), which is Maven-specific -
`go build` never prints it. A failing build here will not abort the run at that point; it surfaces
later as a startup timeout in `watch-log`. Same accepted limitation as the Node.js and Rust
modules.
