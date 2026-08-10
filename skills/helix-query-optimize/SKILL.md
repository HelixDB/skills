---
name: helix-query-optimize
description: Review and improve HelixDB v3 query performance. Use for index-aware sources, label scope, equality and range indexes, bounded traversals, projection size, vector and BM25 search, tenant-scoped indexes, and safe write batches. Examples use direct v3 SDK requests and the nested JSON AST.
license: MIT
metadata:
  author: HelixDB
  version: 3.0.0
---

# HelixDB v3 Query Optimization

Optimize the query shape before tuning the transport. The forthcoming v3 SDKs all
serialize the same direct operation tree, so the same rules apply to Rust,
TypeScript, Python, Go, and raw JSON.

## Review order

1. Identify the first source operation.
2. Find the narrowest label and property predicate available.
3. Confirm a compatible index exists and is active.
4. Bound expansion with filters, `dedup`, and `limit`.
5. Project only the fields the caller uses.
6. Check search tenant scope and rank-field lifetime.
7. Check write idempotency and batch cardinality.

## 1. Start from the narrowest source

Prefer, in order:

- exact node or edge IDs
- a labeled source with an indexed property predicate
- a label-only source
- an unconstrained scan

Use a source predicate when the filter can anchor the query:

```rust
g().n_with_label_where(
    "User",
    SourcePredicate::eq("status", "active"),
)
```

```ts
g().nWithLabelWhere(
  "User",
  SourcePredicate.eq("status", "active"),
)
```

`where` is still useful after a traversal, but starting broad and filtering later can
materialize more elements.

## 2. Match the index to the predicate

| Workload | Index |
|---|---|
| equality and membership | node or edge equality |
| range predicates and large ordered result sets | node or edge range |
| nearest-neighbor search | node or edge vector |
| full-text relevance | node or edge text |

Do not expect an equality index to accelerate an arbitrary range, substring, or
full-text query. Create indexes through a write request and wait for the returned DDL
operation to become active before relying on indexed performance.

## 3. Keep label scope

Equality and range indexes are label-scoped. Prefer
`nWithLabelWhere("User", ...)`/`n_with_label_where("User", ...)` when the label is
known. A property predicate without label scope may require a wider scan.

## 4. Push bounds close to expansion

Apply `dedup` and `limit` immediately after the source or traversal they should bound:

```ts
g()
  .nWithLabel("User")
  .out("FOLLOWS")
  .dedup()
  .limit(25)
  .valueMap(["$id", "name"])
```

Avoid expanding a large subgraph, applying several broad filters, and limiting only
at the end.

## 5. Project narrowly

Prefer:

```text
.valueMap(["$id", "name"])
```

over loading every property when the response needs only two. For a count, finish
with `count` rather than returning every matching object to the client.

## 6. Treat search scope as part of the index lookup

Vector and text index definitions may include a tenant property. Pass the matching
tenant value to the search operation itself. A later `where` cannot repair a search
that selected top-k hits from the wrong partition.

Project `$distance` for vector results or `$score` for text results before traversing
away from the ranked hit stream.

## 7. Use range indexes for large ordered reads

`orderBy`/`order_by` may otherwise require materializing and sorting the matching
stream. If ordering is a frequent large query, create a range index for the same
label and property, then apply a practical limit.

Deep offset pagination still does work proportional to the skipped prefix. Prefer a
cursor predicate on the ordered property where possible.

## 8. Bound recursive and branching work

- Set an explicit maximum depth on recursive traversal.
- Put cheap `coalesce` probes before expensive fallbacks.
- Keep `forEachParam`/`for_each_param` arrays bounded.
- Break large bulk writes into measured pages.

## 9. Make writes idempotent where required

`addN`/`add_n` creates new data. For an upsert:

1. Load the existing object by an equality-indexed unique property.
2. Conditionally update when the named result is non-empty.
3. Conditionally create when it is empty.

On multigraphs, identify the exact edge or use a label-scoped drop. Avoid a broad
source/target deletion when parallel edges may exist.

## Direct requests only

The v3 SDKs build `QueryRequest` values and execute them directly:

- TypeScript: `Client.query(request)`
- Rust: `client.query(request)`
- Python: `Client(...).query(request)`
- Go: `Client.Exec(ctx, request)`

Stored routes, registration, `defineQueries`, and `queries.json` bundles are not part
of the v3 SDK contract. Authoring with Rust `#[query]` still produces a direct request.

## Checklist

- [ ] source is the narrowest practical indexed set
- [ ] label scope is present for label-scoped indexes
- [ ] index family matches the predicate or search
- [ ] index creation has completed before performance is measured
- [ ] expansion is bounded near its source
- [ ] projection includes only required fields
- [ ] tenant-scoped search passes the tenant value at search time
- [ ] `$distance` or `$score` is projected before leaving the hit stream
- [ ] large ordering has a range index or an accepted sort cost
- [ ] recursive depth and bulk batch sizes are bounded
- [ ] writes are idempotent where the application requires it

See `REFERENCE.md` for the mechanism map and `EXAMPLES.md` for stronger query shapes.
