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

```rust
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

## 3. Move Filters Earlier

Apply scope and status filters before broad traversal whenever possible.

Common filters:

- `tenantId`, `userId`, or similar scope keys
- deleted or archived flags
- exact identifiers before `out`, `in_`, or `both`

## 4. Shrink The Projection

Check whether the route returns more than the caller needs.

Prefer:

- `project(...)` for stable service-facing output
- explicit omission of heavy properties such as embeddings
- `$distance` only when ranking metadata matters

Example:

```rust
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

## 5. Control Traversal Breadth

After the anchor, inspect how quickly the route expands.

Check whether it should use:

- `dedup()`
- `limit(...)`
- `range(...)`
- `skip(...)`
- `count()` instead of materializing full rows
- `first()` instead of returning a whole stream

These controls should be driven by route semantics, not habit.

## 6. Review BM25 Routes Separately

For BM25 routes, check:

- is the indexed property the right one?
- is tenant scope preserved directly or by post-filtering?
- does the route need over-fetch, filter, then trim?

Example:

```rust
g().text_search_nodes_with(
    "Document",
    "body",
    PropertyInput::param("query"),
    Expr::param("bm25K"),
    None,
)
.where_(Predicate::eq_param("tenantId", "tenantId"))
.range(0, Expr::param("limit"))
```

## 7. Review Vector Routes Separately

For vector routes, check:

- is the vector index present?
- is tenant scope preserved?
- is the embedding omitted from the returned projection?
- is `$distance` included only when useful?

## 8. Stored Versus Dynamic

If a route is stable and production-facing, prefer a stored query over a dynamic inline query.

Stored queries reduce runtime overhead. Dynamic queries are useful for flexibility, but they should not be the default optimization target for steady traffic.

## 9. Query Warming

Consider query warming only for read queries that benefit from cache prepopulation.

Rules:

- warming only supports reads
- it uses the same request shape as the live read
- it returns `204 No Content`

## 10. Common Optimization Mistakes

Do not:

- start from a broad label scan when an indexed identifier exists
- ignore tenant scope on text or vector search
- return embeddings by default
- optimize around the edges before fixing the anchor and index story
- recommend dynamic routes for stable production traffic without a reason

## Review Output Template

When reviewing a query, answer in this order:

1. current anchor and whether it is optimal
2. matching or missing indexes
3. filter timing issues
4. projection-size issues
5. traversal breadth issues
6. search-specific issues if the route uses BM25 or vectors
7. whether the route should remain dynamic or become stored

## See Also

- `docs/dsl-cheatsheet.md`
- `examples/search-patterns.md`
- `examples/optimization-patterns.md`
