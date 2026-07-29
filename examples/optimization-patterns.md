# v3 Optimization Patterns

Generic before-and-after patterns for direct forthcoming v3 SDK requests.

## Better Anchor Choice

```rust
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

All v3 SDK requests use the direct `POST /v1/query` route. Warm stable,
performance-sensitive reads with `X-Helix-Warm: true`.

Write warming is rejected. Fix a slow write's query and storage-access pattern.
