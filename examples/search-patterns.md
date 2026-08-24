# v3 Search Patterns

Generic published `helix-db = "3.0.0"` Rust SDK patterns for BM25, vector
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

## Full Text Search Prefiltering Over Traversal Candidates

```rust
read_batch()
    .var_as(
        "results",
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
                PropertyProjection::new("title"),
                PropertyProjection::renamed("$score", "score"),
            ]),
    )
    .returning(["results"])
```

The filters construct the exact candidate stream before BM25 ranking. Restricted
search deduplicates those IDs and refills to `limit` when enough candidates match.
Pass the same tenant partition used to construct candidates.

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

## Vector Prefiltering Over Traversal Candidates

```rust
read_batch()
    .var_as(
        "results",
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
                PropertyProjection::new("title"),
                PropertyProjection::renamed("$distance", "distance"),
            ]),
    )
    .returning(["results"])
```

The filters construct the exact candidate stream before vector ranking. The
engine cannot return an ID outside that stream, although approximate index
structures may accelerate ranking.

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
