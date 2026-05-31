# Optimization Patterns

Generic before-and-after patterns for Helix query optimization.

## Better Anchor Choice

```rust
// weaker
g().n_with_label("Entity")
    .where_(Predicate::eq_param("status", "status"))

// stronger when the caller already knows the entity identifier
g().n_with_label("Entity")
    .where_(Predicate::eq_param("entityId", "entityId"))
```

## Smaller Search Projection

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

## BM25 Trim Pattern

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

## Warm Stable Read Traffic

Every query runs on the dynamic route (`POST /v1/query`). For queries that are:

- stable
- performance-sensitive
- part of steady production traffic

warm the caches at startup (see below) instead of optimizing away the per-request AST parse.

## Warm Reads, Not Writes

Only recommend warming for read queries.

If a write query is slow, fix the route and storage access pattern instead of trying to warm it.
