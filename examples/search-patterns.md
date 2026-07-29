# v3 Search Patterns

Generic forthcoming `helix-db = "3.0.0"` Rust SDK patterns for BM25, vector
search, and bounded expansion. These builders serialize direct requests.

## Tenant-Scoped BM25 Search

```rust
read_batch()
    .var_as(
        "results",
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
        ]),
    )
    .returning(["results"])
```

## BM25 Over-Fetch Then Trim

```rust
read_batch()
    .var_as(
        "results",
        g().text_search_nodes_with(
            "Document",
            "body",
            PropertyInput::param("query"),
            Expr::param("bm25K"),
            None,
        )
        .where_(Predicate::eq_param("tenantId", "tenantId"))
        .range(0, Expr::param("limit"))
        .project(vec![
            PropertyProjection::new("$id"),
            PropertyProjection::new("title"),
        ]),
    )
    .returning(["results"])
```

Use this only when the index is not tenant-partitioned and the search API cannot
express the filter at lookup time. For a tenant-partitioned index, pass the tenant
input to the search itself.

## Tenant-Scoped Vector Search

```rust
read_batch()
    .var_as(
        "results",
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
        ]),
    )
    .returning(["results"])
```

## Fixed-Depth Expansion

```rust
read_batch()
    .var_as(
        "seed",
        g().n_with_label("Entity")
            .where_(Predicate::eq_param("entityId", "entityId")),
    )
    .var_as(
        "expanded",
        g().n(NodeRef::var("seed"))
            .repeat(
                RepeatConfig::new(sub().both(Some("RELATED_TO")))
                    .times(3)
                    .emit_all(),
            )
            .without("seed")
            .dedup()
            .limit(Expr::param("limit")),
    )
    .returning(["expanded"])
```
