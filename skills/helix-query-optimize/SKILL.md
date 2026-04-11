---
name: helix-query-optimize
description: Review and improve HelixDB query performance and query shape. Use when the task is to optimize a slow Helix query, improve anchor choice, tighten index usage, reduce traversal breadth, slim projections, fix BM25 or vector search scope, or decide between stored and dynamic routes.
license: MIT
metadata:
  author: HelixDB
  version: 0.1.0
---

# Helix Query Optimization

Optimize Helix queries by improving anchor choice, index alignment, filter timing, traversal breadth, and response shape.

## When To Use

Use this skill when the task is to:

- optimize a slow Helix query
- review query shape for performance problems
- improve index usage
- tighten BM25 or vector search routes
- reduce over-broad traversal or oversized result projections
- decide whether a dynamic query should become a stored route

## First Steps

Before suggesting any changes:

1. Read the existing query and identify the first anchor.
2. List the labels, edge labels, predicates, projections, and traversal steps it uses.
3. Check which indexes already exist in the application.
4. Determine whether the route is stored or dynamic.
5. Identify whether the route is a normal read, a write, a text search, a vector search, or a repeat traversal.

Do not suggest optimizations before you understand the current anchor and index story.

## Optimization Workflow

### 1. Fix The Anchor First

Prefer this order:

1. node ID or edge ID
2. unique property lookup
3. equality-indexed property lookup
4. tenant-scoped label scan
5. broad label scan

If the route already knows `entityId`, `externalId`, `userId`, `tenantId`, or another indexed identifier, use that before broad traversal.

### 2. Match Query Shape To Existing Indexes

Check whether the query is aligned with:

- equality indexes
- range indexes
- text indexes
- vector indexes
- tenant-scoped text or vector indexes

If the query shape is good but the index is missing, say that clearly instead of pretending the DSL alone can solve it.

### 3. Move Filters Earlier

Apply scope and status filters before broad graph expansion when possible.

Key examples:

- `tenantId`
- `userId`
- active-record filtering like empty or null `deletedAt`
- exact entity or relation identifiers

### 4. Shrink The Projection

Review what the route returns.

Prefer:

- explicit `project(...)` for service-facing endpoints
- omitting embeddings unless they are the payload
- including `$distance` only when ranking metadata is needed

### 5. Control Traversal Breadth

Inspect whether the route should use:

- `dedup()`
- `limit(...)`
- `range(...)`
- `skip(...)`
- `count()`
- `first()`

Use these intentionally. Do not add them blindly.

### 6. Review Search Routes Separately

For BM25 routes:

- confirm the indexed property is correct
- confirm tenant scope is preserved
- consider over-fetch, post-filter, then trim when the search API cannot express the scope directly

For vector routes:

- confirm the vector index exists
- confirm tenant scope is preserved
- confirm embeddings are omitted from the returned projection unless needed

### 7. Prefer Stored Routes For Steady Traffic

If the route is stable and production-facing, favor stored queries over dynamic inline queries. Dynamic routes are more flexible but they should not be the default choice for steady traffic.

### 8. Use Query Warming Only For Reads

Query warming can help prepopulate caches for known read routes. It is not valid for writes.

## Canonical Examples

### Better Anchor Choice

```rust
// weaker
g().n_with_label("Entity")
    .where_(Predicate::eq_param("status", "status"))
    .both(Some("RELATED_TO"))

// stronger when entityId is already known
g().n_with_label("Entity")
    .where_(Predicate::eq_param("entityId", "entityId"))
    .both(Some("RELATED_TO"))
```

### Smaller Search Projection

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

### BM25 Over-Fetch Then Trim

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

## Anti-Patterns

Do not:

- recommend a broad scan before checking for indexed identifiers
- ignore tenant scope on text or vector search
- return embeddings by default in search results
- suggest dynamic routes for stable production traffic without a reason
- add `dedup`, `limit`, or `range` without tying them to route semantics
- focus on micro-tweaks before fixing the anchor or index alignment

## Validation Checklist

Before finishing:

- verify the first anchor is the narrowest practical indexed set
- verify the route shape matches the indexes that exist or should exist
- verify scope and status filters happen as early as possible
- verify projections omit heavy fields unless required
- verify traversal breadth is intentionally controlled
- verify BM25 and vector routes preserve tenant scope
- verify a stable production route is not using the dynamic path without a reason
- verify warming recommendations are read-only

## Repo References

For shared references in this repo, see:

- `docs/optimization-checklist.md`
- `docs/source-canon.md`
- `examples/search-patterns.md`
- `examples/optimization-patterns.md`
