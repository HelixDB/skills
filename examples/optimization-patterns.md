# v3 Optimization Patterns

Before-and-after patterns for direct v3 SDK requests.

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

`limit`/`skip`/`range` windows normalize with saturating arithmetic;
identity-sensitive or unsupported pipelines keep a streaming count. Leave
`order_by` out of count-only routes.

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

With non-unique indexes, the status points become one batched bitmap union
intersected with the region bitmap before rows load. Null and NaN never use an
equality bitmap; unique hits and range candidates are verified.

## Ordered Range Driver Filters Before Limit

```rust
g().n_with_label_where(
    "Order",
    SourcePredicate::eq("region", "eu"),
)
.order_by("createdAt", Order::Desc)
.limit(50)
.value_map(Some(vec!["$id", "createdAt", "total"]))
```

With a descending `Order.createdAt` range index and an `Order.region` equality
index, the planner filters the ordered range scan before the limit and skips the
sort. A late-bound equality parameter may use a dynamic equality program. Orders
without `createdAt` sort last for `Desc`, first for `Asc`.

For only the window's size, drop the ordering:
`g().n_with_label_where("Order", SourcePredicate::eq("region", "eu")).limit(50).count()`
counts the region bitmap and clamps it to 50.

## Race-Safe Upsert Key

```rust
write_batch()
    .var_as(
        "index",
        g().create_index_if_not_exists(IndexSpec::node_unique_equality("User", "email")),
    )
    .returning(["index"])
```

Poll `get_index_operation(operation_id)` until `status` is `succeeded`. The
upsert batch reads the key, updates under `BatchCondition::VarNotEmpty` and
creates under `BatchCondition::VarEmpty`. A concurrent duplicate create fails
with `unique_constraint_violation` (409, `retryable: false`); re-running the
upsert takes the update branch.

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

The ellipsis is a review pattern, not compilable Rust. Concrete form:

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

Exact candidate membership; source vector search plus `where_` can underfill.

## Traversal-scoped Full Text Search prefilter

Rust `main` only; with helix-db 3.0.0 bind the candidates, then
`g().text_search_nodes_with(..).within("<var>")`, which filters after top-k and
can underfill.

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

Ranks the exact candidates and refills to `limit` when enough match; source BM25
plus `where_` can underfill.

## Warm reads, not writes

All v3 requests use `POST /v2/query`. Warm stable, performance-sensitive reads
with `X-Helix-Warm: true`. A standalone server (Docker `v0.0.16`) warms its one
process and returns the normal body; Helix Cloud fans out to every eligible
backend and returns `204 No Content` after at least one succeeds.
`X-Helix-Require-Writer: true` targets only the writer.

Write warming is rejected with `400 invalid_request_option` before execution.
Fix a slow write's query and access pattern; `X-Helix-Await-Durable: false`
lowers write latency at the cost of crash safety and does not reduce conflicts.
