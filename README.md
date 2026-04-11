# HelixDB Skills

Hosted `skills.sh` repository for HelixDB agent skills.

These skills are for agents that need to:

- write Helix queries in the Rust DSL
- translate from Cypher, Gremlin, and SQL into Helix query code
- optimize Helix query shape and index usage
- build correct dynamic `POST /v1/query` payloads

## Status

Available now:

- `helix-query-authoring`
- `helix-query-from-cypher`
- `helix-query-from-gremlin`
- `helix-query-json-dynamic`
- `helix-query-optimize`

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
- distinguish stored routes from inline dynamic routes
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

### `helix-query-optimize`

Use this skill when an agent needs to review or improve Helix query performance.

It teaches agents to:

- fix anchor choice before anything else
- match query shape to existing indexes
- move scope filters earlier
- shrink large projections
- review BM25 and vector search routes separately

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
