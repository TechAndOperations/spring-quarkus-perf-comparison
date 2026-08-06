# nodejs

NestJS 11 + TypeORM implementation of the Fruit Store Benchmark API, ported from
[`quarkus3-virtual`](../quarkus3-virtual). It adds **Node.js as a runtime category** to the
comparison suite alongside the Quarkus and Spring Boot modules.

It implements the same contract as every other module ([`openapi.yml`](../openapi.yml)) against the
same Postgres schema ([`scripts/dbdata/db.sql`](../scripts/dbdata/db.sql)):

| Method | Path            | Response                                  |
|--------|-----------------|-------------------------------------------|
| GET    | `/fruits`       | `FruitDTO[]`, 200                         |
| GET    | `/fruits/{name}`| `FruitDTO` 200, or 404 with an empty body |
| POST   | `/fruits`       | the created `FruitDTO`, 200 (not 201)     |

The source layout deliberately mirrors the Java packages (`domain`, `dto`, `mapping`,
`repository`, `rest`, `service`) so the two implementations can be diffed side by side.

## Two query implementations, selectable at runtime

This module ships **two first-class benchmark runtimes** built from the same compiled output,
selected by the `QUERY_MODE` environment variable:

- **`nodejs-orm`** (`QUERY_MODE=orm`, the **default**) - TypeORM `find({ relations })`, the
  idiomatic implementation. See `src/repository/fruit.repository.ts`.
- **`nodejs-sql`** (`QUERY_MODE=sql`) - a single hand-written join, no entity hydration. See
  `src/repository/fruit-rows.ts`. Roughly 1.7x the throughput of `nodejs-orm` when this was first
  measured.

Both are registered as separate entries in `scripts/perf-lab/main.yml` rather than one runtime
toggled by an env var, and `test/fruit.e2e-spec.ts` runs every assertion against both modes on
every `npm test`/`npm run test:e2e` invocation - the same approach later adopted for the `rust/`
and `go/` modules (`rust-orm`/`rust-sql`, `go-sql`/`go-orm`). This module is where the
comparison was first done, and it was originally checked only by hand, with one-off manual runs
on different occasions rather than a controlled same-session A/B - that produced an initially
wrong read of the speedup (a factor first reported by comparing two measurements taken in
different sessions, only corrected once both modes were re-measured back-to-back in the same
session; see `rust/README.md`, "Why `orm` (SeaORM) is the default", for the fuller account). Two
first-class runtimes benchmarked by the same pipeline invocation avoid that failure mode entirely.

## Running locally

Requires Node.js 22+ and the shared infrastructure containers.

```sh
cd ../scripts && ./infra.sh -s     # Postgres on :5432 (+ Grafana LGTM on :4317)
cd ../nodejs
npm install                        # first time only, to generate package-lock.json
npm run build
npm start                          # listens on :8080
```

> [!IMPORTANT]
> `package-lock.json` must be committed. Benchmark runs use `npm ci`, which requires it, and
> reproducible dependency versions are what make results comparable between runs. The pipeline
> aborts with an explicit message if the lockfile is missing. After the first `npm install`, use
> `npm ci` locally too so you exercise the same install path as the benchmark.

```sh
curl -s http://localhost:8080/fruits | jq '.[0]'
curl -s http://localhost:8080/fruits/Apple
npm test                           # mapper unit tests
npm run test:e2e                   # endpoint tests against the seeded database, both query modes
```

Set `QUERY_MODE=sql` before `npm start` to run the raw-SQL path instead of the TypeORM default.

Configuration is environment-driven; the defaults match the `%prod` profile of the Quarkus
modules: `DB_HOST` (`localhost`), `DB_PORT` (`5432`), `DB_USER`/`DB_PASSWORD`/`DB_NAME`
(`fruits`), `DB_POOL_MAX` (`20`, matching Agroal's default), `PORT` (`8080`).
Set `OTEL_SDK_DISABLED=true` to run without instrumentation.

## Benchmarking

Registered as the `nodejs-orm` and `nodejs-sql` runtimes. Both are **opt-in** — neither is in the
default runtime set, so they must be requested explicitly:

```sh
cd ../scripts/perf-lab
./run-benchmarks.sh --runtimes nodejs-orm,nodejs-sql --tests run-load-test --iterations 3
```

`npm run build` compiles with `tsc` and then assembles a self-contained `build/` directory
containing `dist/`, `package.json` and `node_modules/`, which the pipeline caches as the build
artifact (`buildOutputDir: build`). Copying `node_modules` is the direct analogue of
`./mvnw package` copying every dependency jar into `target/quarkus-app/lib/`, so it belongs
inside the measured build time. `npm ci` runs beforehand in the `update-node-version` step and is
therefore excluded, mirroring how `./mvnw dependency:go-offline` is excluded for the JVM runtimes.
Both runtimes build the identical output and only differ in the `QUERY_MODE` environment variable
set in their `runCmd` - expect their build-time measurements to be near-identical; only
startup/RSS/throughput should meaningfully differ between them.

Use `--node-args` for runtime flags; the default `--max-old-space-size=512` is the analogue of the
JVM runtimes' `-Xmx512m`.

## Notes on comparability

Read these before drawing conclusions from a head-to-head run.

- **A single Node.js process saturates one core.** The pipeline pins the app to `--cpus-app`
  (2+ cores by default), which the JVM runtimes use in full. Throughput here is therefore *not*
  core-normalised against them, while RSS and throughput density remain directly comparable.
  This reflects Node's concurrency model rather than a measurement artifact. Clustering was
  considered and rejected: `pmap -x $APP_PID` in
  [`main.yml`](../scripts/perf-lab/main.yml) reads a single PID and would under-report worker
  memory, and `kill -15` could orphan workers.
- **Query shapes differ even though responses are identical.** In `orm` mode, `FruitRepository`
  joins `storePrices` → `store` in one statement via TypeORM's `find({ relations })`. The Java
  module instead relies on a lazy `@OneToMany`, an EAGER `@ManyToOne` with `FetchMode.SELECT`, and
  Hibernate's second-level cache on `Store` — several statements per request in exchange for
  cache hits. `sql` mode (`fruit-rows.ts`) uses the same single hand-written join as `rust-sql`
  and `go-sql`. Each shape is its own module's idiomatic default, not a bug.
- **Sequence-generated ids are explicit.** `fruits.id` has no `DEFAULT`, so the repository draws
  from `fruits_seq` before inserting, exactly as Hibernate's `GenerationType.SEQUENCE` with
  `allocationSize = 1` does.
- **`bigint` and `numeric` are coerced to JS numbers** in
  [`numeric.transformer.ts`](src/domain/numeric.transformer.ts) because node-postgres returns them
  as strings, which would otherwise emit `{"id":"1","price":"1.29"}` instead of
  `{"id":1,"price":1.29}`.
- **Empty and null fields are omitted by the mappers** to replicate the Java module's
  `quarkus.jackson.serialization-inclusion: non-empty`.
- **JSON key order differs from `quarkus3-virtual`, harmlessly.** This module emits keys in DTO
  declaration order (`id, name, description, storePrices`). The Quarkus modules set
  `quarkus.rest.jackson.optimization.enable-reflection-free-serializers: true`, and those generated
  serializers sort properties alphabetically (`description, id, name, storePrices`). Key order is
  not part of [`openapi.yml`](../openapi.yml) — JSON object member order carries no meaning — and
  the serialised byte *length* is identical either way, so throughput and RSS are unaffected. A raw
  `diff` of a response against `quarkus3-virtual` will therefore always differ; normalise first:

  ```sh
  diff <(curl -s localhost:8080/fruits | jq -S 'sort_by(.id)') /tmp/expected.json
  ```

### Known limitation

The pipeline detects build failures by grepping the build log for the literal string
`BUILD FAILURE` ([`main.yml`](../scripts/perf-lab/main.yml), `measure-build-times`), which is
Maven-specific — npm and `tsc` never print it. A failing build here will not abort the run at that
point; it surfaces later as a startup timeout in `watch-log`. Making that check toolchain-aware is
a worthwhile follow-up.
