# v3 Search Patterns

Generic Rust SDK patterns (`helix-db` crate; see `docs/source-canon.md`) for
BM25, vector search, and bounded expansion. These builders serialize direct
requests.

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
            // SDK main only. helix-db 3.0.0: bind these candidates, then
            // g().text_search_nodes_with(..).within("<var>") (can return fewer than k).
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
search deduplicates those IDs and refills to `limit` when enough candidates match,
up to `min(candidates, limit, 800)` rows. Pass the same tenant partition used to
construct candidates.

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

Limits: the request fails when `min(limit, unique candidates)` exceeds 800, and
more than 1,000,000 unique candidates fails the query. A whole-index search
(previous pattern) returns at most 800 hits.

Reads default to strong search consistency: committed but unpublished vector
and text writes are searchable, and a search that would need too much
unpublished work fails with retryable `index_backpressure` (429). Request
`SearchConsistency::Eventual` on the `QueryRequest` (SDK `main`; send
`"search_consistency": "eventual"` over HTTP with published packages) when
slightly stale results are acceptable.

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
                    .emit_after(),
            )
            .without("seed")
            .dedup()
            .limit(Expr::param("limit")),
    )
    .returning(["expanded"])
```

`emit_after()` returns every node reached at depths 1 to 3. `both` walks back to
the seed at depth 2, so `without("seed")` removes it; drop that step if the seed
itself should count when reached again. `emit_all()` would also emit the seed
and emit each intermediate depth twice.
