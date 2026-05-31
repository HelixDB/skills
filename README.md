# HelixDB Skills

Hosted `skills.sh` repository for HelixDB agent skills.

These skills are for agents that need to:

- write Helix queries in the Rust DSL
- translate from Cypher, Gremlin, SQL, and legacy HelixQL (HQL) into Helix query code
- optimize Helix query shape and index usage
- build correct dynamic `POST /v1/query` payloads
- design and operate an agent memory system on Helix's hybrid graph + vector + full-text engine

## Status

Available now:

- `helix-query-authoring`
- `helix-query-from-cypher`
- `helix-query-from-gremlin`
- `helix-query-from-hql`
- `helix-query-json-dynamic`
- `helix-query-optimize`
- `helix-memory-system`

Planned next:

- `helix-query-from-sql`

## Install

```bash
npx skills add HelixDB/skills
```

## Repository Layout

- `skills/` contains the published skills
- `docs/` contains shared reference material used while authoring skills
- `examples/` contains generic canonical examples and before-and-after patterns
- `benchmarks/` contains evaluation scaffolding for prompt and gold-answer testing
- `helix-skills-repo-plan.md` is the working implementation plan and checklist

## Current Skills

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
