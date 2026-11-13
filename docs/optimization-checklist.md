# Helix Query Optimization Checklist

For reviewing Helix query performance. Shared contracts (empty returns, index
DDL receipts, search limits and consistency, durability) are in
`docs/source-canon.md`; error codes and retries in `docs/error-handling.md`.

## 1. Fix The Anchor First

- What is the first set the query touches? Is it already uniquely identified?
- Can the route start from an indexed property instead of a broad label scan?

Preferred order: node or edge ID > unique property lookup > equality-indexed
property lookup > scoped label scan > broad label scan.

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

- equality indexes for exact-match anchors
- range indexes for ordered or threshold queries
- text indexes for BM25 routes
- vector indexes for similarity routes
- tenant-scoped text or vector indexes where the app needs them

Call out a missing index when the route shape is good. Poll a new index's build
(`get_index_operation`) to `succeeded` before measuring; the planner does not use
an index that has not activated. Upsert keys need a unique equality index
(`IndexSpec::node_unique_equality`): owner point reads, and concurrent creates of
the same key cannot both commit.

## 3. Check Equality Semantics And Set Algebra

- Exact cross-numeric equality does not round integers through `f64`.
- `-0.0` and `0.0` normalize to the same equality key.
- NaN is non-reflexive and non-indexable; null equality needs an authoritative scan.
- Keep same-index equality alternatives in one `or`/membership expression so the
  planner can batch and union bitmap reads.
- Keep compatible equality/range filters together so ID sets intersect before
  rows are materialized.
- Keep `is_in_param` as one bounded runtime membership domain. Scalar and array
  inputs may use an equality union; null, unsupported, oversized or over-limit
  domains retain authoritative evaluation.
- Adjacent filters canonicalize into one conjunction for access planning; a
  non-filter operation remains a semantic boundary.
- Retain unique-owner and range-candidate verification.

## 4. Move Filters Earlier

Apply scope and status filters before broad traversal: `tenantId`, `userId` or
similar scope keys, deleted or archived flags, exact identifiers before `out`,
`in_` or `both`.

## 5. Shrink The Projection

- `project(...)` for stable service-facing output
- omit heavy properties such as embeddings
- `$distance` only when ranking metadata matters
- `count()` instead of IDs/rows plus client-side length when only cardinality is
  needed (dedicated bitmap, range, unique-owner, label, search, runtime-input and
  streaming count programs; `limit`/`skip`/`range` windows saturate in operator order)

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

## 6. Control Traversal Breadth

Driven by route semantics, not habit, check whether the route needs:

- `dedup()`, `limit(...)`, `range(...)`, `skip(...)`
- `count()` instead of full rows, without `order_by` (it never changes a count)
- `limit(1)` when the caller reads one element (there is no `first()` builder)

## 7. Review BM25 Routes Separately

- Is the indexed property the right one?
- Is tenant scope passed directly to the search operation?
- If a traversal defines the eligible node or edge IDs, are candidates built
  before traversal-scoped text search?

Rust `main` only; with helix-db 3.0.0 bind the candidates, then
`g().text_search_nodes_with(..).within("<var>")`, which can underfill top-k:

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

Source text search followed by `where_` is a post-filter and can underfill.
Traversal-scoped text search ranks the exact candidate IDs with partition-wide
BM25 statistics.

## 8. Review Vector Routes Separately

- Is the vector index present and tenant scope preserved?
- Is the embedding omitted from the projection, and `$distance` included only when useful?
- If a traversal defines the eligible IDs, are candidates built before
  traversal-scoped vector search?

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

Source vector search followed by `where_` can underfill; traversal-scoped search
enforces exact candidate membership. Check `k` and candidate counts against the
search limits, and use `eventual` search consistency only where stale hits are
acceptable (`docs/source-canon.md`).

## 9. Review Ordered Range Drivers

For `orderBy(property, direction).limit(n)` over a large stream:

- match a range index on element kind, label, property and direction
- keep equality filters in the same logical route
- expect the driver to filter candidate IDs before satisfying the limit and to
  skip the redundant in-memory sort
- range candidates are authoritatively verified
- prefer cursor predicates over a deep `skip`
- missing values sort first for `Asc`, last for `Desc` (opposite to SQL/Cypher)

This does not depend only on immediate `OrderBy -> Limit` lookahead.

## 10. Steady-Traffic Reads

Every query runs on the dynamic route (`POST /v2/query`), which parses and
validates the inline AST per request; there are no stored routes. Warm stable
production reads (§11) instead of optimizing per-request parsing.

Cypher (`POST /v2/cypher`) and SQL (`POST /v2/sql`) use the same indexes;
`POST /v2/cypher/explain` and `POST /v2/sql/explain` return the plan, including
selected index access paths, without running it.

## 11. Query Warming

Only for reads that benefit from cache prepopulation:

- reads only; same request shape as the live read
- a standalone server (Docker `v0.0.16`) warms one process and returns `200 OK` with the normal response
- Helix Cloud fans out to every eligible backend and returns `204 No Content`
  after at least one succeeds; partial backend failure is best-effort success
- `X-Helix-Warm: true` plus `X-Helix-Require-Writer: true` warms only the
  authoritative writer
- invalid warm-header values and warm writes return `400 invalid_request_option`

## 12. Writes

- Durability and retries: `docs/source-canon.md` (Durability) and
  `docs/error-handling.md`. Skipping the durability wait does not reduce conflicts.
- `add_e` always creates edges; make edge writes idempotent with a lookup and
  `var_as_if`.

## 13. Common Optimization Mistakes

Do not:

- start from a broad label scan when an indexed identifier exists
- split one equality union/intersection into client-side queries
- assume runtime membership is always unindexed or expand it into unbounded requests
- move a filter across a traversal, window, order, projection or mutation boundary
- treat null or NaN as an ordinary equality bitmap key
- materialize rows before `count()` when only cardinality is needed
- apply an ordered limit before selective equality filters
- remove unique/range verification or other correctness fallbacks
- ignore tenant scope on text or vector search
- return embeddings by default
- optimize around the edges before fixing the anchor and index story
- recommend stored routes, query registration or bundles (v3 has none)
- benchmark before the index build has `succeeded`

## Review Output Template

Answer in this order:

1. current anchor and whether it is optimal
2. matching or missing indexes
3. exact equality semantics and bitmap union/intersection opportunities
4. ordered range driver, post-filter window and sort elimination
5. dedicated count alternative versus identity-sensitive fallback
6. filter timing, projection size and traversal breadth
7. search-specific issues for BM25 or vector routes
8. index build status and search consistency
9. whether steady-traffic reads should be warmed

## See Also

- `docs/dsl-cheatsheet.md`
- `examples/search-patterns.md`
- `examples/optimization-patterns.md`
