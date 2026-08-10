# v3 Optimization Patterns

Generic before-and-after patterns for direct forthcoming v3 SDK requests.

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

## Warm reads, not writes

All v3 SDK requests use the direct `POST /v2/query` route. Warm stable,
performance-sensitive reads with `X-Helix-Warm: true`.

The standalone `v0.0.3` runtime warms its single process and returns the normal
query body. Helix Cloud fans the read out to every eligible backend and returns
`204 No Content` after at least one succeeds. Add
`X-Helix-Require-Writer: true` to target only the writer.

Write warming is rejected with `400 Bad Request` before backend execution. Fix
a slow write's query and storage-access pattern.
