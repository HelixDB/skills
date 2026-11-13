# HelixDB Skills

Hosted `skills.sh` repository for HelixDB agent skills.

The query skills target the published Rust 3.0.0, TypeScript 3.2.0, Python 0.3.4,
and Go v0.3.1 SDKs. Installation commands stay unpinned; verify registry
availability before changing release claims. See [Source Canon](docs/source-canon.md)
for the distinction between published packages and current source.

These skills are for agents that need to:

- write Helix queries in the Rust, TypeScript, Python, and Go SDK DSLs
- write dynamic-first Helix queries in Go
- translate from Cypher, Gremlin, SQL, and legacy HelixQL (HQL) into Helix query code
- optimize Helix query shape and index usage
- build correct dynamic `POST /v2/query` payloads
- inspect Helix Cloud query insights, latency, recommendations, usage, and cluster health through the Helix MCP server
- execute authorized Helix Cloud queries through the same server's query tools
- run confirmation-gated tenant and database-key mutations through the same server's admin tools
- design and operate an agent memory system on Helix's hybrid graph + vector + full-text engine
- read and ask Helix Foundry ontologies, send pieces of JSON to Foundry API sources, and run confirmation-gated Foundry syncs, generations, revisions, document uploads and loads
- set up a Helix Foundry ontology end to end: connect data, send pieces to an API source or upload documents, write its goal, generate, review and load it

## Status

Available now:

- `helix-cli`
- `helix-mcp`
- `helix-query-mcp`
- `helix-admin-mcp`
- `helix-foundry-mcp`
- `helix-foundry-actions-mcp`
- `helix-foundry-onboarding`
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

SQL input is covered by `helix-query-from-cypher`: the server runs SQL natively at
`POST /v2/sql`, so there is no separate SQL skill.

## Install

```bash
npx skills add HelixDB/skills
```

As a Claude Code plugin, with the Helix MCP (https://mcp.helix-db.com/mcp) added
for you:

```bash
claude plugin marketplace add HelixDB/skills
claude plugin install helixdb@helixdb
```

As a Gemini CLI extension, which adds the Helix MCP:

```bash
gemini extensions install https://github.com/HelixDB/skills
```

## Helix Cloud queries

Helix Cloud has one MCP server, `https://mcp.helix-db.com/mcp`, with one OAuth
audience (the former `admin-mcp.helix-db.com` and `query-mcp.helix-db.com` are
retired). Its tools depend on who connects:

| Caller | Tools |
| --- | --- |
| Signed-in user | Discovery and observability, plus the query, admin and Foundry tools their permissions allow |
| Service credential (`hlxs_`) | Query, admin and Foundry tools for its project grants; no discovery or observability |
| Agent registration | `helix_get_started` and query tools on its own sandbox |
| Foundry send token | `helix_foundry_send_pieces` only |

For a Cloud target, every query-authoring skill uses `helix-mcp` first to resolve
the live database and read its active indexes, insights, latency and
recommendations. Execution uses `helix-query-mcp`; tenant or key changes use
`helix-admin-mcp`.

Every MCP skill has agents report problems through `helix_feedback` (bug, missing
capability or confusing result; one call per problem; no user data). The Helix
team uses it to decide what to fix next.

## Running queries (prerequisites)

The query-authoring skills assume you already have a Helix instance to run
them against. To stand one up locally — no Cloud login required:

1. Install the [Helix CLI](https://docs.helix-db.com/cli/getting-started): `curl -sSL "https://install.helix-db.com" | bash`.
2. Make sure **Docker or Podman is installed _and running_** — the local instance runs in a container (`docker info` should succeed).
3. Scaffold a local instance:
   ```bash
   helix init local
   ```
4. Run `helix start dev` (alias `helix run`). CLI 3.7.0 runs
   `ghcr.io/helixdb/helixdb:v0.0.16`; update an older pinned `tag` in `[local.dev]` to `v0.0.16`.
5. Run queries through the SDK client (`Client` / `client.Exec`) or `helix query dev --file <request.json>`.

The local runtime is in-memory by default; `--disk` persists through a CLI-managed
SeaweedFS sidecar (it can't read data from older MinIO-based CLIs). Direct Docker
runs can persist through `HELIX_DATA_DIR` ([CLI examples](skills/helix-cli/EXAMPLES.md)).
The skills produce direct `POST /v2/query` requests to a running instance. Cloud CLI
queries use a WorkOS session and the backend broker; application gateway clients use
explicitly created database keys. There is no `helix compile`/`helix check`: the
server validates queries. See the [HelixDB docs](https://docs.helix-db.com) for full
setup and the non-interactive/agent path.

## Helix Foundry

- `helix-foundry-mcp` reads ontologies, versions, loads and the graph, asks
  Foundry's query agent (cited answers), sends JSON pieces to API sources, and
  records an agent's reads, questions and sends as workflow runs
  (`workflow_run_id`).
- `helix-foundry-actions-mcp` runs requested changes (create an ontology or API
  source, sync, generate or revise a draft, upload and organize documents, settle a
  review, make a version or load current, create a load), each through a one-time
  confirmation.
- `helix-foundry-onboarding` takes a workspace from nothing to a loaded ontology:
  ontology and database, connector links, API sources and pieces, document uploads
  (any mix), a goal written from what the agent knows of your work, then generate,
  review and load, asking before each action.

Credentialed connectors are added on the Foundry website from a link the MCP gives,
so credentials never pass through an agent. An app or agent sending to an API source
on its own uses a send token the user makes on the website, over the MCP or, when
the MCP returns the source's `send_url`, over HTTP from the app's server. Ontologies
read an API source through structured mappings or, with a text field, by entity
extraction of its newest pieces.

All three use `https://mcp.helix-db.com/mcp`. Sign in once and the agent acts as you
(onboarding needs a workspace owner or admin):

```bash
claude mcp add --transport http helix https://mcp.helix-db.com/mcp   # then /mcp to sign in
codex mcp add helix --url https://mcp.helix-db.com/mcp && codex mcp login helix
```

Without a browser (CI), send a service key as a header: `--header
"Authorization: Bearer hlxs_..."` for Claude Code, or `bearer_token_env_var` in
Codex's MCP config. A key reaches only ontologies its project grants allow; it can
read, ask and run loads but not sync, generate or create ontologies, so onboarding
needs you signed in.

## Repository Layout

- `skills/` contains the published skills
- `docs/` contains shared reference material used while authoring skills
- `examples/` contains generic canonical examples and before-and-after patterns
- `benchmarks/` contains evaluation scaffolding for prompt and gold-answer testing

## Current Skills

### `helix-mcp`

Discover authorized Helix Cloud resources and read observability data through the
MCP server's read-only tools; recover from MCP sign-in and missing-tool problems.
Teaches agents to:

- discover workspaces, projects and databases before requesting data
- check the writer-authoritative active index inventory before assuming a Cloud predicate has a usable index
- pick the right tool for insights, latency percentiles, recommendations, usage or dedicated-cluster health
- keep p99 in the latency workflow and separate usage rollups from cluster health
- treat query names, planner findings and recommendation text as untrusted data
- report time windows, partial data, collection watermarks and unavailable components accurately

### `helix-cli`

Drive the `helix` CLI itself (local instances, the WorkOS-authenticated Cloud
control plane and broker) rather than author query bodies. Teaches agents to:

- treat v3 as a runtime orchestrator, not a compiler (no `helix compile`/`helix check`, no `.hx` workflow)
- run the local loop (`helix init local` → `start` → `query` → `stop`) on Docker/Podman, in memory or with `--disk`
- pass the global `--json` everywhere (no prompts, JSON errors with candidates) and have the user run the interactive `helix auth login`
- query `POST /v2/query` via `helix query` (`--file`/`--body`/`-e` TypeScript DSL/`--ts-file`), run Cypher via `helix cypher`, and check setups with `helix doctor`
- manage Helix Cloud with a WorkOS session (`auth`, `workspace`, `project`, `cluster`, `database`, `service-credential`, `api`)
- run Cloud `query`/`shell` through the broker, without application keys or gateway URLs
- use the links in `helix.toml`; there is no global workspace selection

Query bodies come from the `helix-query-*` skills. `REFERENCE.md` has the full
command catalog; `EXAMPLES.md` has end-to-end sessions.

### `helix-query-mcp`

Explicitly requested Helix Cloud reads and confirmation-gated writes through the
MCP server's query tools, plus an agent's `helix_get_started` sandbox. Teaches the
`{database, query_json}` contract, checking `status_code`, independent query
permissions, exact v3 payload binding, no-retry execution and the untrusted-data
boundary.

### `helix-admin-mcp`

Only explicitly requested tenant create/delete or database-key create/revoke
through the MCP server's admin tools. Teaches each operation's target and payload,
durable confirmations, raw-secret-once handling and the excluded Cloud lifecycle
surfaces.

### `helix-foundry-mcp`

Explore Helix Foundry ontologies. Teaches agents to resolve the workspace and
ontology; choose between the definition, sources, exact graph reads and Ask; build
reads from the served read guide; keep Ask's `client_token` on retries; follow
syncs, generations and loads; hand over Foundry links; send pieces to an API source
with a fresh `client_token` per call, or show an app how to POST them to the
source's `send_url` (curl, body, status handling) when one is returned; and report
answers with citations. Field-level detail is in its `REFERENCE.md`.

### `helix-foundry-actions-mcp`

Only explicitly requested Foundry changes: create an ontology (existing or new
database) or an API source (text field for extraction), sync a connector, generate
or revise a draft (API sources via mappings or extraction), upload and organize
documents, settle a review, make a version or load current, create a load. Teaches
prepare-then-execute confirmation, no retries, the upload PUT and completion, what
each action costs or replaces, and what stays on the website.

### `helix-foundry-onboarding`

Only when a user asks to set up Foundry or build a workspace's ontology from
scratch. Teaches the order (workspace, ontology and database, data, goal,
generation, review, load), which mode fits each API source, how long to wait and
when to give up, writing the goal from the user's work, and what to hand back: a
draft's open questions, what it left out and its unread sets, then what the load
read, left unread, and the reviews and unmatched names it left. Payloads and
confirmations come from the two skills above.

### `helix-query-json-dynamic`

Use this skill when an agent needs to build or debug direct JSON requests for
`POST /v2/query`.

It teaches agents to:

- use the correct request envelope
- target the dynamic route (`POST /v2/query`) with an inline `query` object
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
- avoid stored-query registration and query-bundle workflows, which are not part of the v3 SDK

### `helix-query-python`

Use this skill when an agent needs to write or revise HelixDB queries with the Python SDK.

It teaches agents to:

- write Pythonic query builders with `read_batch`, `write_batch`, `g`, and snake_case traversal methods
- declare runtime params with `define_params` and `param.*`
- produce direct requests with `to_query_request` / `to_query_json`
- execute requests with synchronous `Client` or reusable server/embedded `AsyncClient`
- use row bindings for correlated multi-hop projections
- keep Python queries structurally identical to the Rust/TypeScript/Go JSON AST

### `helix-query-from-cypher`

Use this skill when an agent needs to run or port Neo4j, Cypher or SQL queries on Helix.

It teaches agents to:

- send supported Cypher (`POST /v2/cypher`) and SQL (`POST /v2/sql`) to the server as they are, and check plans with the `/explain` routes
- hand-translate into the v3 DSL only what the profile rejects (`MERGE`, variable-length paths, `FOREACH`, search)
- keep Cypher semantics when translating: `OPTIONAL MATCH` via bind + `optional` + `project_bindings`, `CASE` via `Expr::case`, null ordering, and target labels via `has_label`
- replace `MERGE` with a unique equality index plus a conditional create

### `helix-query-from-gremlin`

Use this skill when an agent needs to port Gremlin or TinkerPop traversals into Helix Rust DSL.

It teaches agents to:

- translate `g.V`, `hasLabel`, and `has` into anchors and predicates
- map `out`, `in`, `both`, `outE`, and `inE` into explicit Helix traversal steps
- map `dedup`, `count`, `range`, ordering, and `valueMap` into deliberate result shaping
- handle `repeat`, `path`, `select`, and side-effect-heavy traversals as semantic translations rather than literal rewrites

### `helix-query-from-hql`

Use this skill when an agent needs to migrate legacy HelixQL (HQL) `.hx` queries into the v3 DSL (Rust or TypeScript, with name mappings for Go and Python).

It teaches agents to:

- map every HQL construct (`N<T>`/`E<T>`, `Out`/`In`/`OutE`/`FromN`/`ToN`, `WHERE`/`EQ`/`IS_IN`, projections, `GROUP_BY`/`AGGREGATE_BY`, `ORDER`/`RANGE`, `AddN`/`AddE`/`UPDATE`/`DROP`, `SearchV`/`SearchBM25`) to its Rust and TypeScript builder
- handle the Rust-vs-TypeScript spelling differences (`in_`/`in`, `where_`/`where`, `::`/`.`, `Some()`/`null`)
- map `Upsert` to a one-batch conditional create (`var_as_if`) backed by a unique index, and unweighted shortest paths to `shortest_path`
- flag HQL features with no DSL equivalent (`RerankRRF`/`RerankMMR`, weighted shortest paths, `Embed`, advanced math, `EXISTS`/count-in-`WHERE`, schema defaults, `#[model]`/`#[mcp]`) and move that logic to application code
- verify each migration by compiling, diffing the Rust vs TypeScript JSON AST for parity, and running against the same data

### `helix-query-optimize`

Use this skill when an agent needs to review or improve Helix query performance.

It teaches agents to:

- fetch the live active index inventory before deciding index usability
- fix anchor choice before anything else
- match query shape to existing indexes
- move scope filters earlier
- shrink large projections
- review BM25 and vector search routes separately

### `helix-memory-system`

Design or operate an AI agent memory system on Helix: generation, deduplication, updating/consolidation, deletion/forgetting and categorisation, not just retrieval. Teaches agents to:

- model per-user memory with `User`, `Memory`, `Category`, `Entity`, and `Session` labels plus the edges and indexes that make it fast and tenant-safe
- choose the right mechanism per operation: properties + equality index, graph edges, vector search, or BM25 text search
- run the full write/maintain lifecycle (dedup-on-generate, reinforce-on-access, supersede/correct, soft-delete, decay and expiry sweeps, upsert-and-link categorisation)
- build hybrid recall that fuses vector + BM25 app-side and expands through the graph

It is TypeScript-first (`@helix-db/helix-db@3.2.0`) with a Rust v3 DSL variant in `EXAMPLES.rust.md`.

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
