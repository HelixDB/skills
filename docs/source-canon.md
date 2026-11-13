# Source Canon

The one place that records which Helix release the skills target and the
contracts every query skill repeats. When a version or a contract changes, change
it here first, then update every skill that inlines it (installed skills only
contain `skills/<name>/`, so they cannot link to this file).

Checked against `HelixDB/helix-db` main at `5be60bdaa` ("Release CLI v3.7.0 with
Docker v0.0.16 default").

## Release set

| Component | Version | Install |
| --- | --- | --- |
| Docker image | `ghcr.io/helixdb/helixdb:v0.0.16` | Default of Helix CLI 3.7.0. With an older CLI set `tag = "v0.0.16"` in `[local.dev]` of `helix.toml`. |
| Helix CLI | 3.7.0 | `curl -sSL "https://install.helix-db.com" \| bash` |
| Rust SDK | crates.io `helix-db` 3.0.0 (import `helix_db`) | `cargo add helix-db` |
| TypeScript SDK | npm `@helix-db/helix-db` 3.2.0 | `npm install @helix-db/helix-db` |
| Python SDK | PyPI `helix-db` 0.3.4 (import `helixdb`) | `pip install helix-db` |
| Go SDK | `github.com/helixdb/helix-db/sdks/go` v0.3.1 (tag `sdks/go/v0.3.1`) | `go get github.com/helixdb/helix-db/sdks/go@latest`, then `import helix "github.com/helixdb/helix-db/sdks/go"` (no `/v3` suffix) |

Snippets are written against the SDK source at the commit above. These parts of
that source are newer than the published packages:

| Feature | Missing from | Use instead |
| --- | --- | --- |
| Cypher and SQL client methods (`cypher`, `sql`, `explain_*`) | all four packages | `POST /v2/cypher`, `/v2/sql` and their `/explain` routes over HTTP |
| Search consistency on the request builder | all four packages | `"search_consistency": "eventual"` in a direct HTTP body |
| Structured remote errors (`status_code()`, `remote_code()`, `retryable()`, `is_retryable()`) | Rust 3.0.0 (`RemoteError { details }` holds the raw body) | Parse `details` as the JSON envelope |
| `IsRetryable`, `HelixError.Retryable` | Go v0.3.1 (has `HelixError.Code` and `StatusCode`) | Branch on `HelixError.Code` |
| `isConflict()` / `IsConflict` limited to `transaction_conflict` | TypeScript 3.2.0 and Go v0.3.1 report `true` for every 409, including `unique_constraint_violation` | `isRetryable()` (TypeScript) or `Code` (Go) |

If a helper named in a skill is missing from the installed package, read the
error body's `error` and `retryable` fields directly.

## Contracts every query skill repeats

| Contract | Rule | Source (helix-db) |
| --- | --- | --- |
| Empty returns | Every row-stream return is `[]` when empty, including at-most-one lookups (`n(id)`, `limit(1)`, a skipped `var_as_if`). Only `count` (`0`), `exists` (`false`) and index DDL / lifecycle operations return scalars. Decode a single lookup as a list and take the first element. Docker v0.0.13+ (older images returned `null` for at-most-one). | `crates/planner/src/exec/returns.rs` |
| IDs | Node and edge `$id` values are unsigned integers. Bind ID parameters as `i64` / integer (`param.i64`, `ParamI64`, `PropertyInput::param` with an integer value); a string ID fails at runtime. | `crates/db/src/execution/interpreter/access/params.rs` |
| Element output | An unprojected node or edge stream, read or mutation, returns `{"$id": N}` per element (search streams add `$distance` or `$score`). Project (`project`, `value_map`, `values`) to get properties. Rows that still carry bindings, a path or a sack come back as `{"bindings": {...}, "current": {...}, ...}`. `shortest_path` returns an array of node IDs. Index receipts and statuses carry `index_id` and `generation` as decimal strings. | `crates/db/src/query_service.rs` (`QueryResponse`), `sdks/rust/src/lifecycle.rs` |
| Error envelope | `{"error": "<code>", "msg": "<diagnostic>", "retryable": true\|false}`; `retryable` is present only when the class settles it. There is no `code` field. | `crates/server/src/http.rs`, `crates/ast/src/error_code.rs` |
| 409 | Two classes. Retryable (`retryable: true`): `transaction_conflict`, `request_read_view_changed`, `stale_index_generation`. Not retryable unchanged (`retryable: false`): `unique_constraint_violation`, `index_already_exists`, `index_definition_conflict`, `index_busy`, `index_operation_not_abortable`, `index_build_blocked`. Branch on `retryable`, never on the status alone. | `crates/ast/src/error_code.rs` |
| Durability | Writes wait for durability by default (no header). `X-Helix-Await-Durable: false` skips the wait for latency; a crash before the WAL upload loses the write. It does not reduce conflicts. `true` on a read is `400 invalid_request_option`. | `crates/server/src/http.rs` |
| Reserved steps | `fold`, `unfold`, `path`, `simple_path`, `with_sack`, `sack_set`, `sack_add`, `sack_get` execute; they are not no-ops. | `crates/db/src/execution/interpreter/reserved.rs` |
| `optional(sub)` | When the branch is empty, the input row passes through unchanged, so the current element is still the input. For OPTIONAL MATCH semantics bind the anchor, bind inside the branch, and read through `project_bindings`; a missing binding's key is absent from the row. | `crates/db/src/execution/interpreter/control/branch.rs` |
| `choose` | Without an else branch, rows that fail the condition are dropped. A per-row value choice is `Expr::case`. | `crates/db/src/execution/interpreter/control/branch.rs` |
| Ordering | Rows missing the sort property sort first for `Asc` and last for `Desc` (the opposite of Cypher and SQL `NULLS` defaults). | `crates/db/src/execution/interpreter/stream/order.rs` |
| After `bind` | `order_by`, `choose`, `repeat`, `values`, `value_map`, `project`, `id`, `label` and `edge_properties` are rejected (`invalid_after_bind_operation`). Order before binding; finish with `project_bindings`, `count` or `exists`. `bind` and `project_bindings` are read-only: a write batch rejects them (`read_only_traversal_in_write_batch`). | `crates/planner/src/planning/selected/native/context_usage.rs`, `crates/planner/src/planning/envelope/write_contract.rs` |
| `repeat` emit | `emit_after` emits each iteration's output (Gremlin postfix `.emit()`); `emit_before` emits each iteration's input; `emit_all` emits both, so a row reached at depth 1 appears twice. Gremlin prefix `emit()` with `times(n)` is `emit_before()` with `times(n + 1)`. `until(pred)` stops the whole loop once any row of the new frontier matches and returns that whole frontier; it is not per-traverser like Gremlin. | `crates/db/src/execution/interpreter/control/repeat.rs` |
| `add_e` | Always creates one edge per (source, target) pair; it is not idempotent. An empty target fails the whole batch; an empty source creates nothing. | `crates/db/src/execution/interpreter/mutation/ops.rs` |
| Upsert | One write batch: read into a variable, then `var_as_if(VarNotEmpty, update)` and `var_as_if(VarEmpty, create)`. A unique equality index (`IndexSpec::node_unique_equality`) on the key makes concurrent creates fail with `unique_constraint_violation` instead of duplicating; re-run the upsert once, which then takes the update branch. | `crates/ast/src/batch.rs`, `crates/ast/src/index.rs` |
| Index DDL | Asynchronous. `create_index_if_not_exists` / `drop_index` return a receipt `{"kind": "accepted", "operation_id", "index_id", "generation"}`, `{"kind": "existing_operation", "operation_id"}` or `{"kind": "already_active", "index_id", "generation"}`. Poll `get_index_operation(operation_id)` until `status` is `succeeded`; `blocked` carries `blocker_code` and needs a fix then `retry_index_operation`, or `abort_index_operation`. | `sdks/rust/src/lifecycle.rs`, `crates/ast/src/traversal.rs` |
| Search consistency | Read requests take `search_consistency`: `strong` (default; includes committed but unpublished vector/text work) or `eventual` (bounded unpublished work, can return stale tenant/label/property matches). Writes are always strong. | `crates/ast/src/query.rs` |
| Search limits | Whole-index vector search caps the effective result count at 800. A traversal-scoped (prefiltered) vector search fails when `min(k, unique candidates)` exceeds 800; text returns at most `min(candidates, k, 800)`. More than 1,000,000 unique candidates fails. | `crates/db/src/search/vector/hnsw/restricted.rs` |
| Request limits | Body 16 MiB locally (2 MiB on Helix Cloud); JSON nesting at most 255 levels. A larger body is `400 invalid_request_body` (Helix Cloud: `413 payload_too_large`); deeper nesting is `400 invalid_query_json`. | `crates/server/src/lib.rs`, `crates/ast/src/query.rs` |
| Native Cypher and SQL | `POST /v2/cypher`, `/v2/cypher/explain`, `/v2/sql`, `/v2/sql/explain` (Docker v0.0.13+ for Cypher). Body `{"query", "parameters", "query_name"}`; SQL also takes positional `parameters` and `mappings`. Send supported statements directly; hand-translate only what the profile rejects (`MERGE`, variable-length paths, `shortestPath`, `UNION`, subqueries, `FOREACH`, outer joins, upserts, vector/text search, index management). | `crates/cypher/src/api.rs`, `crates/cypher/src/request.rs`, `crates/cypher/src/sql/request.rs` |

## Working order

When an agent writes or reviews Helix query code it uses, in order:

1. the user's repo and schema
2. this repository's `docs/` and `examples/`
3. the public Helix documentation for behavior
4. the SDK source on `HelixDB/helix-db` `main` for exact identifiers

## Public Helix references

- Start: `https://docs.helix-db.com/database/helix-db/start-here/quickstart`,
  `.../start-here/local-development/local-server`,
  `.../start-here/sdk-setup/{rust,typescript,go,python}-project-setup`
- Query guides (`https://docs.helix-db.com/database/helix-db/query-guides/<page>`):
  `writing-data`, `reading-data`, `traversals`, `filtering`, `projections`,
  `parameters`, `advanced`, `secondary-indexes`, `vector-indexes`,
  `text-indexes`, `prefiltering`, `search-consistency`, `cypher`, `sql`,
  `error-handling`, `http-api`, `troubleshooting`
- Core concepts: `https://docs.helix-db.com/database/helix-db/core-concepts/overview`
- Helix Cloud: `https://docs.helix-db.com/database/helix-cloud/connect/mcp`,
  `.../helix-cloud/operate/error-handling`, `.../helix-cloud/operate/limits`
- SDK source: `https://github.com/HelixDB/helix-db/tree/main/sdks/{rust,typescript,go,python}`
- Skill packaging: `https://skills.sh/docs`, `https://opencode.ai/docs/skills`

## Repo-local references

`docs/dsl-cheatsheet.md`, `docs/go-dsl-cheatsheet.md`, `docs/cypher-rosetta.md`,
`docs/gremlin-rosetta.md`, `docs/dynamic-query-examples.md`,
`docs/optimization-checklist.md`, `docs/error-handling.md`,
`examples/authoring-patterns.md`, `examples/search-patterns.md`,
`examples/optimization-patterns.md`.

These are authoring sources. A published skill inlines what it needs from them
or links the public docs; it never links `../../docs/...`.

## Rules

- No machine-local paths or feature-branch links in published content.
- No application-specific implementations as canonical references; generalize first.
- Install commands stay unpinned; the release set above records what was verified.
- Generic labels, properties and edge names in examples.
- The user's repo is the authority for their schema, naming and route style.
