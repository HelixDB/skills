---
name: helix-query-authoring
description: Write and revise HelixDB Rust DSL stored queries from scratch. Use when the task is to add, update, or review a Helix query built with read_batch, write_batch, traversal builders, projections, indexes, BM25 text search, or vector search. Inspect local labels, edges, properties, and existing query patterns before inventing new code.
license: MIT
metadata:
  author: HelixDB
  version: 0.1.0
---

# Helix Query Authoring

Write Helix Rust DSL queries in a way that is schema-aware, explicit, and easy for agents to reason about.

## When To Use

Use this skill when the task is to:

- write a new Helix query in Rust
- revise an existing Helix Rust DSL route
- add a stored query for deployment
- choose between `read_batch()` and `write_batch()`
- add traversal, projection, pagination, BM25 search, or vector search to an existing query

Do not use this skill as the main guide for inline `POST /v1/query` payloads. Use the dynamic-query skill for that.

## First Steps

Before writing any query code:

1. Inspect the local repo for existing labels, edge labels, properties, and route patterns.
2. Find the closest existing query and reuse its naming, projection, and scoping style.
3. Decide whether the route is a read or a write.
4. Identify the narrowest indexed anchor before planning the traversal.

If the local repo is thin on Helix examples, use this repository's canonical references in this order:

1. `docs/dsl-cheatsheet.md`
2. `examples/authoring-patterns.md`
3. `examples/search-patterns.md`
4. `docs/source-canon.md`

## Core Authoring Rules

### 1. Start With The Right Batch Type

Use:

- `read_batch()` for read-only routes
- `write_batch()` for any mutation

If the query adds nodes, adds edges, updates properties, or deletes graph data, it is a write route.

### 2. Anchor Narrow, Then Traverse

Prefer this anchor order:

1. node ID or edge ID
2. unique property lookup
3. equality-indexed property lookup
4. scoped label scan
5. broad label scan as a last resort

Do not start from a broad label scan when the application already has an indexed identifier like `entityId`, `externalId`, `userId`, `tenantId`, or a similar key.

### 3. Reuse Existing Property And Label Casing

Do not normalize names to your own preferred style.

If the application uses `entityId`, `updatedAt`, `FOLLOWS`, or `RelatesTo`, reuse those exact names.

### 4. Filter Early

Apply scope and status filters before broad traversal whenever possible.

Common examples:

- tenant filters like `tenantId` or `userId`
- soft-delete or archived filters such as empty or null `deletedAt`
- specific ID filters before `both`, `out`, or `in_`

### 5. Keep Output Shape Intentional

Use:

- `project(...)` for stable service-facing response shapes
- `value_map(...)` when returning all or many properties is acceptable
- `edge_properties()` for edge streams

Do not return oversized properties like embeddings unless the caller explicitly needs them.

### 6. Preserve Search Scope

For BM25 and vector search:

- keep the chosen text or vector property explicit
- preserve tenant scope when the index is scoped
- post-filter only when the search API cannot express the scope directly

### 7. Use Traversal Controls Deliberately

Apply `dedup`, `limit`, `range`, `skip`, `count`, and `first` because the route needs them, not by habit.

`repeat(...)` is often used with a deliberate bounded depth. Do not assume arbitrary runtime repeat depth unless the local code already supports it.

### 8. Prefer Explicit Write Branching Over Invented MERGE Semantics

When you need create-or-update behavior, follow this pattern:

1. load existing nodes
2. branch with `var_as_if`
3. update when found
4. create when missing

## Canonical Examples

### Read By Indexed Identifier

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId"))
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("userId"),
                PropertyProjection::new("name"),
            ]),
    )
    .returning(["user"])
```

### Explicit Create Or Update

```rust
write_batch()
    .var_as(
        "existing",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId")),
    )
    .var_as_if(
        "updated",
        BatchCondition::VarNotEmpty("existing".to_string()),
        g().n(NodeRef::var("existing"))
            .set_property("name", PropertyInput::param("name")),
    )
    .var_as_if(
        "created",
        BatchCondition::VarEmpty("existing".to_string()),
        g().add_n(
            "User",
            vec![
                ("userId", PropertyInput::param("userId")),
                ("name", PropertyInput::param("name")),
            ],
        ),
    )
    .returning(["updated", "created"])
```

### Scoped Search Route

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

## Anti-Patterns

Do not:

- invent labels, edge labels, or property names without checking the codebase
- start from broad scans when an indexed ID or scoped predicate exists
- return embeddings by default in search results
- ignore tenant scope on text or vector search
- add `dedup` or `limit` without a reason
- assume dynamic inline-query rules apply to stored Rust DSL routes
- treat BM25 as if it searches every property automatically

## Validation Checklist

Before finishing:

- verify `read_batch()` versus `write_batch()` is correct
- verify labels, edge labels, and properties match the repo exactly
- verify the first anchor is the narrowest practical indexed set
- verify scope filters happen before or as early as possible
- verify the returned variable names and shape match service expectations
- verify text and vector routes preserve tenant scope when required
- verify large properties are omitted unless needed
- verify the query matches surrounding local style more than any generic example

## Repo References

For shared references in this repo, see:

- `docs/source-canon.md`
- `docs/dsl-cheatsheet.md`
- `examples/authoring-patterns.md`
- `examples/search-patterns.md`
