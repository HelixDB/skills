# Helix Query Optimization Checklist

Use this checklist when reviewing or improving Helix query performance.

## 1. Fix The Anchor First

Ask:

- what is the first set the query touches?
- is that set already uniquely identified?
- can the route start from an indexed property instead of a broad label scan?

Preferred order:

1. node ID or edge ID
2. unique property lookup
3. equality-indexed property lookup
4. scoped label scan
5. broad label scan

Example:

```text
// weaker
g().n_with_label("Entity")
    .where_(Predicate::eq_param("status", "status"))
    .both(Some("RELATED_TO"))

// stronger when entityId is already known
g().n_with_label("Entity")
    .where_(Predicate::eq_param("entityId", "entityId"))
    .both(Some("RELATED_TO"))
```

## 2. Check Index Alignment

Look for:

- equality indexes for exact-match anchors
- range indexes for ordered or threshold queries
- text indexes for BM25 routes
- vector indexes for similarity routes
- tenant-scoped text or vector indexes where the app needs them

If the route shape is good but the index is missing, call that out clearly.

Index builds are asynchronous. `create_index_if_not_exists` returns a receipt
(`accepted` with an `operation_id`, `existing_operation`, or `already_active`).
Poll `get_index_operation(operation_id)` until `status` is `succeeded` before
measuring; the planner does not use an index that has not activated. A
`blocked` build names a `blocker_code`; fix the data, then
`retry_index_operation` or `abort_index_operation`. `index_busy` and
`index_build_blocked` are 409 with `retryable: false`.

Upsert keys need a unique equality index (`IndexSpec::node_unique_equality`):
it serves owner point reads and stops concurrent creates of the same key from
both committing (`unique_constraint_violation`, 409, `retryable: false`).

## 3. Check Equality Semantics And Set Algebra

- Exact cross-numeric equality does not round integers through `f64`.
- `-0.0` and `0.0` normalize to the same equality key.
- NaN is non-reflexive and non-indexable; null equality needs an authoritative scan.
- Keep same-index equality alternatives in one `or`/membership expression so the
  planner can batch bitmap reads and union them.
- Keep compatible equality/range filters together so ID sets can intersect before
  rows are materialized.
- Keep `is_in_param` as one bounded runtime membership domain. Scalar and array
  inputs may use an equality union; null, unsupported, oversized, or over-limit
  domains retain authoritative evaluation.
- Adjacent filters canonicalize into one conjunction for access planning. A
  non-filter operation remains a semantic boundary.
- Retain unique-owner and range-candidate verification.

## 4. Move Filters Earlier

Apply scope and status filters before broad traversal whenever possible.

Common filters:

- `tenantId`, `userId`, or similar scope keys
- deleted or archived flags
- exact identifiers before `out`, `in_`, or `both`

## 5. Shrink The Projection

Check whether the route returns more than the caller needs.

Prefer:

- `project(...)` for stable service-facing output
- explicit omission of heavy properties such as embeddings
- `$distance` only when ranking metadata matters
- `count()` instead of IDs/rows plus client-side length when only cardinality is needed

Example:

```text
// weaker
g().vector_search_nodes_with(...)
    .value_map(None::<Vec<&str>>)

// stronger
g().vector_search_nodes_with(...)
    .project(vec![
        PropertyProjection::new("$id"),
        PropertyProjection::new("title"),
        PropertyProjection::renamed("$distance", "distance"),
    ])
```

Dedicated bitmap, range, unique-owner, label, search, runtime-input, and streaming
count programs are planner alternatives. Compatible `limit`/`skip`/`range` windows
use saturating arithmetic while preserving operator order.

## 6. Control Traversal Breadth

After the anchor, inspect how quickly the route expands.

Check whether it should use:

- `dedup()`
- `limit(...)`
- `range(...)`
- `skip(...)`
- `count()` instead of materializing full rows (without `order_by`, which
  never changes a count)
- `limit(1)` when the caller only reads one element (there is no `first()`
  builder)

These controls should be driven by route semantics, not habit.

Bounds never change the response shape: every row return, including
`limit(1)` and point lookups, is an array and `[]` when empty. Only `count()`
(`0`) and `exists()` (`false`) are scalars.

## 7. Review BM25 Routes Separately

For BM25 routes, check:

- is the indexed property the right one?
- is tenant scope passed directly to the search operation?
- does a traversal define the eligible node or edge IDs?
- if so, are candidates built before traversal-scoped text search?

Example (Rust SDK `main` only; with helix-db 3.0.0 bind the candidates, then
`g().text_search_nodes_with(..).within("<var>")`, which can underfill top-k):

```text
g().n_with_label("Document")
    .where_(Predicate::eq_param("tenantId", "tenantId"))
    .where_(Predicate::eq("published", true))
    .text_search_with(
        "Document",
        "body",
        PropertyInput::param("query"),
        Expr::param("limit"),
        Some(PropertyInput::param("tenantId")),
    )
```

Source text search followed by `where_` is a post-filter and can underfill top-k.
Traversal-scoped text search ranks the exact candidate IDs while retaining
partition-wide BM25 statistics. It returns at most `min(candidates, k, 800)`
rows and fails above 1,000,000 unique candidates.

## 8. Review Vector Routes Separately

For vector routes, check:

- is the vector index present?
- is tenant scope preserved?
- is the embedding omitted from the returned projection?
- is `$distance` included only when useful?
- does a traversal define the eligible node or edge IDs?
- if so, are candidates built before traversal-scoped vector search?

Example:

```text
g().n_with_label("Document")
    .where_(Predicate::eq_param("tenantId", "tenantId"))
    .where_(Predicate::eq("published", true))
    .vector_search_with(
        "Document",
        "embedding",
        PropertyInput::param("queryVector"),
        Expr::param("limit"),
        Some(PropertyInput::param("tenantId")),
    )
```

Source vector search followed by `where_` is a post-filter and can underfill
top-k. Traversal-scoped vector search enforces exact candidate membership.

Limits: a whole-index search clamps `k` to 800; a traversal-scoped vector search
fails when `min(k, unique candidates)` exceeds 800, and above 1,000,000 unique
candidates.

Search consistency (reads only): `strong` (default) includes committed but
unpublished index work and can fail with `index_backpressure` (429,
`retryable: true`) when indexing lags; `eventual` includes a bounded slice of
unpublished work, is never rejected that way, but can return hits whose tenant,
label or indexed property changed since. The published SDK packages cannot set
it; send `"search_consistency": "eventual"` in the request body.

## 9. Review Ordered Range Drivers

For `orderBy(property, direction).limit(n)` over a large stream:

- match a range index on element kind, label, property, and direction
- keep equality filters in the same logical route
- expect the ordered driver to filter candidate IDs before satisfying the limit
- avoid a redundant in-memory sort when the index supplies the requested order
- remember that range candidates are authoritatively verified
- prefer cursor predicates over a deep `skip`
- elements missing the property sort first for `Asc` and last for `Desc`
  (opposite to SQL/Cypher null ordering)

Do not claim this depends only on immediate `OrderBy -> Limit` lookahead.

## 10. Steady-Traffic Reads

Every query executes on the dynamic route (`POST /v2/query`), which parses and validates the inline AST per request; there are no stored routes. For stable, production-facing reads, warm the caches (see §11) rather than treating per-request parsing as the optimization target.

Cypher (`POST /v2/cypher`) and SQL (`POST /v2/sql`) run against the same indexes.
`POST /v2/cypher/explain` and `POST /v2/sql/explain` take the same body and
return the plan without running it, including the selected index access paths.

## 11. Query Warming

Consider query warming only for read queries that benefit from cache prepopulation.

Rules:

- warming only supports reads
- it uses the same request shape as the live read
- a standalone server (Docker `v0.0.16`) warms one process and returns `200 OK` with the normal response
- Helix Cloud fans out to every eligible backend and returns `204 No Content`
  after at least one succeeds; partial backend failure is best-effort success
- combine `X-Helix-Warm: true` with `X-Helix-Require-Writer: true` to warm only
  the authoritative writer
- invalid warm-header values and warm writes return `400 invalid_request_option`

## 12. Writes, Durability, And Retries

- Writes wait for durability by default. `X-Helix-Await-Durable: false` skips the
  wait for latency (a crash can lose the write); it does not reduce conflicts.
  `true` on a read is `400 invalid_request_option`.
- Branch retries on the error's `retryable` field, not the status. 409 is
  retryable for `transaction_conflict` / `request_read_view_changed` /
  `stale_index_generation`, and not for `unique_constraint_violation`,
  `index_busy` or `index_build_blocked`. 429 `index_backpressure` is retryable.
- `add_e` always creates edges; make edge writes idempotent with a lookup and
  `var_as_if`.

## 13. Common Optimization Mistakes

Do not:

- start from a broad label scan when an indexed identifier exists
- split one equality union/intersection into client-side queries
- assume runtime membership is always unindexed or expand it into unbounded requests
- move a filter across a traversal, window, order, projection, or mutation boundary
- treat null or NaN as an ordinary equality bitmap key
- materialize rows before `count()` when only cardinality is needed
- apply an ordered limit before selective equality filters
- remove unique/range verification or other correctness fallbacks
- ignore tenant scope on text or vector search
- return embeddings by default
- optimize around the edges before fixing the anchor and index story
- recommend stored routes, query registration, or bundles (v3 has none)
- benchmark before the index build has `succeeded`

## Review Output Template

When reviewing a query, answer in this order:

1. current anchor and whether it is optimal
2. matching or missing indexes
3. exact equality semantics and bitmap union/intersection opportunities
4. ordered range driver, post-filter window, and sort elimination
5. dedicated count alternative versus identity-sensitive fallback
6. filter timing, projection size, and traversal breadth
7. search-specific issues if the route uses BM25 or vectors
8. index build status and search consistency
9. whether steady-traffic reads should be warmed

## See Also

- `docs/dsl-cheatsheet.md`
- `examples/search-patterns.md`
- `examples/optimization-patterns.md`
