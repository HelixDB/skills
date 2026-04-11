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

## Prefer Stored Routes For Stable Traffic

Use the dynamic route when you need flexibility.

Prefer a stored route when the query is:

- stable
- performance-sensitive
- part of steady production traffic

## Warm Reads, Not Writes

Only recommend warming for read queries.

If a write query is slow, fix the route and storage access pattern instead of trying to warm it.
