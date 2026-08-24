# v3 Optimization Patterns

Generic before-and-after patterns for direct published v3 SDK requests.

## Better Anchor Choice

```text
// weaker
g().n_with_label("Entity")
    .where_(Predicate::eq_param("status", "status"))

// stronger when the caller already knows the entity identifier
g().n_with_label_where(
    "Entity",
    SourcePredicate::eq("entityId", "known-id"),
)
```

## Indexed Count Instead Of Row Materialization

```rust
// weaker when the caller only uses len()
g().n_with_label_where(
    "Order",
    SourcePredicate::eq("status", "open"),
)
.id()

// stronger: allows a dedicated bitmap/range/streaming count program
g().n_with_label_where(
    "Order",
    SourcePredicate::eq("status", "open"),
)
.count()
```

Compatible `limit`/`skip`/`range` windows are normalized with saturating
arithmetic. Identity-sensitive or unsupported pipelines keep a streaming count.

## Equality Union And Intersection Before Rows Load

```rust
g().n_with_label_where(
    "Order",
    SourcePredicate::and(vec![
        SourcePredicate::or(vec![
            SourcePredicate::eq("status", "open"),
            SourcePredicate::eq("status", "queued"),
        ]),
        SourcePredicate::eq("region", "eu"),
    ]),
)
```

With compatible non-unique indexes, the status points can use one batched bitmap
union and intersect the region bitmap before row materialization. Null and NaN do
not use an ordinary equality bitmap; unique hits and range candidates remain
authoritatively verified.

## Ordered Range Driver Filters Before Limit

```rust
g().n_with_label_where(
    "Order",
    SourcePredicate::eq("region", "eu"),
)
.order_by("createdAt", Order::Desc)
.limit(50)
.count()
```

With a descending `Order.createdAt` range index and an `Order.region` equality
index, the planner can filter the ordered range scan before satisfying the limit,
avoid a redundant sort, and select a dedicated count program. A genuinely
late-bound equality parameter may use a dynamic equality program.

## Smaller search projection

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

The ellipsis marks a review pattern, not compilable Rust. A concrete v3 form is:

```rust
g().vector_search_nodes_with(
    "Document",
    "embedding",
    PropertyInput::param("queryVector"),
    Expr::param("limit"),
    Some(PropertyInput::param("tenantId")),
)
.project(vec![
    PropertyProjection::new("$id"),
    PropertyProjection::new("title"),
    PropertyProjection::renamed("$distance", "distance"),
])
```

## Tenant-scoped BM25

```rust
g().text_search_nodes_with(
    "Document",
    "body",
    PropertyInput::param("query"),
    Expr::param("limit"),
    Some(PropertyInput::param("tenantId")),
)
.project(vec![
    PropertyProjection::new("$id"),
    PropertyProjection::new("title"),
    PropertyProjection::renamed("$score", "score"),
])
```

## Traversal-scoped vector prefilter

```rust
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
    .project(vec![
        PropertyProjection::new("$id"),
        PropertyProjection::renamed("$distance", "distance"),
    ])
```

This enforces exact candidate membership. Source vector search followed by
`where_` can underfill top-k.

## Traversal-scoped Full Text Search prefilter

```rust
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
    .project(vec![
        PropertyProjection::new("$id"),
        PropertyProjection::renamed("$score", "score"),
    ])
```

This ranks the exact candidate IDs and refills to `limit` when enough candidates
match. Source BM25 followed by `where_` can underfill.

## Warm reads, not writes

All v3 SDK requests use the direct `POST /v2/query` route. Warm stable,
performance-sensitive reads with `X-Helix-Warm: true`.

The standalone `v0.0.4` runtime warms its single process and returns the normal
query body. Helix Cloud fans the read out to every eligible backend and returns
`204 No Content` after at least one succeeds. Add
`X-Helix-Require-Writer: true` to target only the writer.

Write warming is rejected with `400 Bad Request` before backend execution. Fix
a slow write's query and storage-access pattern.
