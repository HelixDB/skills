# HelixDB Skills

Hosted `skills.sh` repository for HelixDB agent skills.

These skills are for agents that need to:

- write Helix queries in the Rust, TypeScript, Python, and Go SDK DSLs
- write dynamic-first Helix queries in Go
- translate from Cypher, Gremlin, SQL, and legacy HelixQL (HQL) into Helix query code
- optimize Helix query shape and index usage
- build correct dynamic `POST /v1/query` payloads
- design and operate an agent memory system on Helix's hybrid graph + vector + full-text engine

## Status

Available now:

- `helix-cli`
- `helix-query-authoring`
- `helix-query-from-cypher`
- `helix-query-from-gremlin`
- `helix-query-from-hql`
- `helix-query-json-dynamic`
- `helix-query-optimize`
- `helix-query-rust`
- `helix-query-typescript`
- `helix-query-go`
- `helix-query-python`
- `helix-memory-system`

Planned next:

- `helix-query-from-sql`

## Install

```bash
npx skills add HelixDB/skills
```

## Running queries (prerequisites)

These skills cover **authoring** Helix queries; they assume you already have a Helix instance to run them against. To stand one up locally — no Cloud login required:

1. Install the [Helix CLI](https://docs.helix-db.com/cli/getting-started): `curl -sSL "https://install.helix-db.com" | bash`.
2. Make sure **Docker or Podman is installed _and running_** — the local instance runs in a container (`docker info` should succeed).
3. Scaffold and start a local instance:
   ```bash
   helix init local
   helix start dev          # `helix run` is kept as an alias
   ```
4. Run queries: send the DSL output through the SDK client (`Client` / `client.Exec`) or with `helix query dev --file <request.json>`.

The skills are SDK- and instance-agnostic: they produce query code and `POST /v1/query` payloads for a running instance reachable at a gateway URL (plus an API key for Helix Cloud). There is no `helix compile`/`helix check` step — queries are validated server-side when sent. See the [HelixDB docs](https://docs.helix-db.com) for the full setup and the non-interactive/agent path.

## Repository Layout

- `skills/` contains the published skills
- `docs/` contains shared reference material used while authoring skills
- `examples/` contains generic canonical examples and before-and-after patterns
- `benchmarks/` contains evaluation scaffolding for prompt and gold-answer testing
- `helix-skills-repo-plan.md` is the working implementation plan and checklist

## Current Skills

### `helix-cli`

Use this skill when an agent needs to drive the `helix` CLI itself — run, query, and deploy Helix instances — rather than author the query bodies.

It teaches agents to:

- use the v3 mental model: a runtime orchestrator, not a compiler (no `helix compile`/`helix check`, no `.hx` workflow)
- run the local dev loop (`helix init local` → `start` → `query` → `stop`) with Docker/Podman, including in-memory vs `--disk` persistence
- send dynamic queries to `POST /v1/query` via `helix query` (`--file`/`--json`/`-e` TypeScript DSL/`--ts-file`)
- operate on Helix Cloud (`helix auth`, `push`, `sync`, `workspace`/`project`/`cluster`)
- read and edit `helix.toml` and the `~/.helix/*` state files

It points to the `helix-query-*` skills for the query bodies themselves; see its `REFERENCE.md` for the full command catalog and `EXAMPLES.md` for end-to-end sessions.

### `helix-query-authoring`

Use this skill when an agent needs to write or revise Helix Rust DSL queries from scratch.

It teaches agents to:

- inspect local query patterns before inventing new ones
- choose `read_batch()` versus `write_batch()` correctly
- anchor on the narrowest indexed node or edge set first
- preserve tenant scope for text and vector search
- shape outputs intentionally with `project`, `value_map`, `limit`, `range`, and `dedup`

### `helix-query-json-dynamic`

Use this skill when an agent needs to build or debug dynamic inline-query requests for `POST /v1/query`.

It teaches agents to:

- use the correct request envelope
- target the dynamic route (`POST /v1/query`) with an inline `query` object
- add `parameter_types` when typed coercion matters
- send `DateTime` values correctly
- avoid malformed bundle-shaped payloads

### `helix-query-go`

Use this skill when an agent needs to write or revise HelixDB queries with the Go SDK.

It teaches agents to:

- write normal Go functions returning `helix.Request`
- set query names with `helix.ReadQuery` and `helix.WriteQuery`
- declare runtime params inline with `q.ParamString`, `q.ParamI64`, `q.ParamDateTime`, and related helpers
- avoid accidentally inlining request-specific literals in predicates and source predicates
- execute dynamic requests with `client.Exec(ctx, request, &out)`
- handle HTTP 409 conflicts explicitly with caller-owned retries
- avoid `.With(...)`, `WithQueryName(...)`, and stored-query bundle workflows for Go v1

### `helix-query-python`

Use this skill when an agent needs to write or revise HelixDB queries with the Python SDK.

It teaches agents to:

- write Pythonic query builders with `read_batch`, `write_batch`, `g`, and snake_case traversal methods
- declare runtime params with `define_params` and `param.*`
- produce dynamic requests with `to_dynamic_request` / `to_dynamic_json`
- execute requests with `Client(...).query().dynamic(request).send()` or `.stored(name)`
- generate `queries.json` bundles with `define_queries`, `register_read`, and `register_write`
- keep Python queries structurally identical to the Rust/TypeScript/Go JSON AST

### `helix-query-from-cypher`

Use this skill when an agent needs to port Neo4j or Cypher queries into Helix Rust DSL.

It teaches agents to:

- translate `MATCH` into explicit anchors and traversals
- map `WHERE` to `Predicate` logic
- map `RETURN`, `DISTINCT`, ordering, and limits into explicit output shaping
- handle `OPTIONAL MATCH`, `MERGE`, `CASE`, `UNWIND`, `FOREACH`, multi-hop traversal, null checks, and timestamps as Helix-native translations rather than literal rewrites

### `helix-query-from-gremlin`

Use this skill when an agent needs to port Gremlin or TinkerPop traversals into Helix Rust DSL.

It teaches agents to:

- translate `g.V`, `hasLabel`, and `has` into anchors and predicates
- map `out`, `in`, `both`, `outE`, and `inE` into explicit Helix traversal steps
- map `dedup`, `count`, `range`, ordering, and `valueMap` into deliberate result shaping
- handle `repeat`, `path`, `select`, and side-effect-heavy traversals as semantic translations rather than literal rewrites

### `helix-query-from-hql`

Use this skill when an agent needs to migrate legacy HelixQL (HQL) `.hx` queries into the v2 Rust or TypeScript DSL.

It teaches agents to:

- map every HQL construct (`N<T>`/`E<T>`, `Out`/`In`/`OutE`/`FromN`/`ToN`, `WHERE`/`EQ`/`IS_IN`, projections, `GROUP_BY`/`AGGREGATE_BY`, `ORDER`/`RANGE`, `AddN`/`AddE`/`UPDATE`/`DROP`, `SearchV`/`SearchBM25`) to its Rust and TypeScript builder
- handle the Rust-vs-TypeScript spelling differences (`in_`/`in`, `where_`/`where`, `::`/`.`, `Some()`/`null`)
- flag HQL features with no DSL equivalent (`Upsert`, `RerankRRF`/`RerankMMR`, shortest-path, `Embed`, advanced math, `EXISTS`/count-in-`WHERE`, schema defaults, `#[model]`/`#[mcp]`) and move that logic to application code
- verify each migration by compiling, diffing the Rust vs TypeScript JSON AST for parity, and running against the same data

### `helix-query-optimize`

Use this skill when an agent needs to review or improve Helix query performance.

It teaches agents to:

- fix anchor choice before anything else
- match query shape to existing indexes
- move scope filters earlier
- shrink large projections
- review BM25 and vector search routes separately

### `helix-memory-system`

Use this skill when an agent needs to design or operate an AI agent memory system on Helix — generation, deduplication, updating/consolidation, deletion/forgetting, and categorisation, not just retrieval.

It teaches agents to:

- model per-user memory with `User`, `Memory`, `Category`, `Entity`, and `Session` labels plus the edges and indexes that make it fast and tenant-safe
- choose the right mechanism per operation: properties + equality index, graph edges, vector search, or BM25 text search
- run the full write/maintain lifecycle (dedup-on-generate, reinforce-on-access, supersede/correct, soft-delete, decay and expiry sweeps, upsert-and-link categorisation)
- build hybrid recall that fuses vector + BM25 app-side and expands through the graph

It is TypeScript-first (`@helixdb/enterprise-ql`) with a Rust DSL variant in `EXAMPLES.rust.md`.

## Shared References

Start here when working on the next skills:

- `docs/source-canon.md`
- `docs/dsl-cheatsheet.md`
- `docs/go-dsl-cheatsheet.md`
- `docs/cypher-rosetta.md`
- `docs/gremlin-rosetta.md`
- `docs/dynamic-query-examples.md`
- `docs/optimization-checklist.md`
- `examples/authoring-patterns.md`
- `examples/search-patterns.md`
- `examples/optimization-patterns.md`

## Notes

- This repo uses the hosted `skills.sh` layout: `skills/<name>/SKILL.md`.
- Local OpenCode discovery still uses `.opencode/skills/`, `.claude/skills/`, or `.agents/skills/` after installation.
- This repo is intentionally written against public Helix behavior and repo-local canonical examples rather than app-specific implementations.
