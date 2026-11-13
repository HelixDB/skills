# v3 Search Patterns

Generic Rust SDK (`helix-db`; see `docs/source-canon.md`) patterns for BM25,
vector search and bounded expansion, as direct requests. Search limits and
consistency: `docs/source-canon.md`.

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
            // Rust main only. helix-db 3.0.0: bind these candidates, then
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

The filters build the exact candidate stream before BM25 ranking. Restricted
search deduplicates the IDs and refills to `limit` when enough match, up to
`min(candidates, limit, 800)` rows. Pass the tenant partition used to build the
candidates.

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

No ID outside the candidate stream is returned, though approximate index
structures may accelerate ranking. Fails when `min(limit, unique candidates)`
exceeds 800 or above 1,000,000 unique candidates; a whole-index search (previous
pattern) returns at most 800 hits. For slightly stale but never
`index_backpressure`-rejected reads, request `SearchConsistency::Eventual` on the
`QueryRequest` (Rust `main`; published packages: `"search_consistency": "eventual"`
over HTTP).

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

`emit_after()` returns nodes reached at depths 1 to 3. `both` walks back to the
seed at depth 2, so `without("seed")` removes it (drop it if the seed should
count). `emit_all()` would also emit the seed and each intermediate depth twice.
