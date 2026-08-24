# HelixDB v3 Optimization Examples

Each example contrasts a broad shape with a more selective direct-request shape.

## Anchor a property filter with its label

Broader:

```rust
read_batch()
    .var_as(
        "users",
        g()
            .n_where(SourcePredicate::eq("status", "active"))
            .limit(25),
    )
    .returning(["users"]);
```

Stronger when the equality index is defined for `User.status`:

```rust
read_batch()
    .var_as(
        "users",
        g()
            .n_with_label_where(
                "User",
                SourcePredicate::eq("status", "active"),
            )
            .limit(25)
            .value_map(Some(vec!["$id", "name"])),
    )
    .returning(["users"]);
```

TypeScript equivalent:

```ts
readBatch()
  .varAs(
    "users",
    g()
      .nWithLabelWhere(
        "User",
        SourcePredicate.eq("status", "active"),
      )
      .limit(25)
      .valueMap(["$id", "name"]),
  )
  .returning(["users"]);
```

Serialized request:

```json
{
  "request_type": "read",
  "query_name": "active_users",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "users",
            "root": {
              "value_map": {
                "input": {
                  "limit": {
                    "input": {
                      "nodes_where": {
                        "predicate": {
                          "and": {
                            "predicates": [
                              {
                                "eq": {
                                  "left": { "property": "$label" },
                                  "right": { "constant": { "string": "User" } }
                                }
                              },
                              {
                                "eq": {
                                  "left": { "property": "status" },
                                  "right": { "constant": { "string": "active" } }
                                }
                              }
                            ]
                          }
                        }
                      }
                    },
                    "count": { "literal": 25 }
                  }
                },
                "properties": ["$id", "name"]
              }
            }
          }
        }
      ],
      "returns": ["users"]
    }
  }
}
```

## Create the matching equality index

```rust
write_batch()
    .var_as(
        "index",
        g().create_index_if_not_exists(
            IndexSpec::node_equality("User", "status"),
        ),
    )
    .returning(["index"]);
```

```ts
writeBatch()
  .varAs(
    "index",
    g().createIndexIfNotExists(
      IndexSpec.nodeEquality("User", "status"),
    ),
  )
  .returning(["index"]);
```

```json
{
  "request_type": "write",
  "query_name": "create_user_status_index",
  "query": {
    "write": {
      "entries": [
        {
          "query": {
            "name": "index",
            "root": {
              "create_index": {
                "spec": {
                  "node_equality": {
                    "label": "User",
                    "property": "status",
                    "unique": false
                  }
                },
                "if_not_exists": true
              }
            }
          }
        }
      ],
      "returns": ["index"]
    }
  }
}
```

Wait for the DDL receipt to become active before benchmarking `active_users`.

## Bound graph expansion

Broader:

```ts
g()
  .nWithLabel("User")
  .out("FOLLOWS")
  .valueMap(["$id", "name"])
```

Bounded:

```ts
g()
  .nWithLabel("User")
  .out("FOLLOWS")
  .dedup()
  .limit(25)
  .valueMap(["$id", "name"])
```

If the start user is known, replace the label-wide source with an exact ID or an
indexed unique property.

## Project only what the API returns

Broader:

```text
.valueMap(null)
```

Stronger:

```text
.valueMap(["$id", "name", "status"])
```

For counts:

```ts
readBatch()
  .varAs(
    "active_count",
    g()
      .nWithLabelWhere(
        "User",
        SourcePredicate.eq("status", "active"),
      )
      .count(),
  )
  .returning(["active_count"]);
```

Keep this as `count()` rather than projecting IDs and taking the client-side
array length. With a compatible `User.status` equality index, the planner can
select a bitmap count without materializing user rows. Compatible
`skip`/`limit`/`range` windows are normalized with saturating arithmetic; an
identity-sensitive or unsupported pipeline retains a streaming count.

## Keep Equality Union And Intersection As One Set Expression

With non-unique equality indexes on `Order.status` and `Order.region`:

```ts
g()
  .nWithLabelWhere(
    "Order",
    SourcePredicate.and([
      SourcePredicate.or([
        SourcePredicate.eq("status", "open"),
        SourcePredicate.eq("status", "queued"),
      ]),
      SourcePredicate.eq("region", "eu"),
    ]),
  )
  .valueMap(["$id", "status", "region"])
```

The two same-index status points can become one batched bitmap union. The
result can intersect the region bitmap before rows are loaded. Do not split
this into separate client requests merely to force index use; every arm still
needs compatible label/property/index identity.

## Keep Runtime Membership Bounded

When the caller supplies the status domain as a parameter, keep it as one
membership predicate:

```ts
g()
  .nWithLabelWhere(
    "Order",
    SourcePredicate.isInParam("status", "statuses"),
  )
  .valueMap(["$id", "status"])
```

With a compatible non-unique equality index, a scalar or bounded array can use
a runtime equality union. Duplicate values collapse and NaN members are skipped.
Null, unsupported, oversized, or over-limit domains fall back to authoritative
membership evaluation; they never produce a partial indexed answer. An empty
domain returns the normal empty collection shape.

## Keep Related Filters Adjacent

These filters are canonicalized into one conjunction for access planning:

```ts
g()
  .nWithLabel("Order")
  .where(Predicate.eqParam("region", "region"))
  .where(Predicate.isInParam("status", "statuses"))
  .valueMap(["$id", "status", "region"])
```

The planner can combine label scope and indexed predicates even though the SDK
chain used separate `where` calls. A traversal, `limit`, `orderBy`, projection,
mutation, or any other non-filter operation ends the contiguous run; do not move
filters across that boundary unless the query semantics independently allow it.

## Rank vectors with traversal prefiltering

Post-filtering source top-k hits can underfill:

```ts
g()
  .vectorSearchNodesWith("Document", "embedding", queryVector, 50, tenant)
  .where(Predicate.eq("published", true))
  .limit(10)
```

Build candidates first, then rank only their IDs:

```ts
g()
  .nWithLabel("Document")
  .where(Predicate.eq("tenantId", tenant))
  .where(Predicate.eq("published", true))
  .vectorSearchWith("Document", "embedding", queryVector, 10, tenant)
```

The second shape cannot return an ID outside the candidate stream.

## Rank Full Text Search within exact traversal candidates

Post-filtering source top-k hits can underfill:

```ts
g()
  .textSearchNodesWith("Document", "body", query, 50, tenant)
  .where(Predicate.eq("published", true))
  .limit(10)
```

Build candidates first, then rank only their IDs:

```ts
g()
  .nWithLabel("Document")
  .where(Predicate.eq("tenantId", tenant))
  .where(Predicate.eq("published", true))
  .textSearchWith("Document", "body", query, 10, tenant)
```

The second shape is exact and refills to ten when at least ten candidate documents
match the text query.

## Use a range index for large ordered pages

```ts
writeBatch()
  .varAs(
    "index",
    g().createIndexIfNotExists(
      IndexSpec.nodeRangeDesc("Order", "createdAt"),
    ),
  )
  .returning(["index"]);
```

```ts
readBatch()
  .varAs(
    "orders",
    g()
      .nWithLabelWhere(
        "Order",
        SourcePredicate.and([
          SourcePredicate.or([
            SourcePredicate.eq("status", "open"),
            SourcePredicate.eq("status", "queued"),
          ]),
          SourcePredicate.eq("region", "eu"),
        ]),
      )
      .orderBy("createdAt", Order.Desc)
      .limit(25)
      .valueMap(["$id", "createdAt", "total"]),
  )
  .returning(["orders"]);
```

Wait for the descending range index before measuring the ordered query. The
planner can union status IDs, intersect the region IDs, drive the route from the
descending range index, filter before satisfying the 25-row limit, and avoid a
redundant in-memory sort. Range candidates remain authoritatively verified.

If the caller needs only the cardinality of this ordered window, replace
`.valueMap(...)` with `.count()`. Null equality still needs a scan, NaN is
non-indexable, a unique equality hit verifies its owner, and a genuinely
late-bound equality parameter may select a dynamic equality program.

## Scope vector search to its tenant

When the vector index has a tenant property, include the tenant input in the search:

```ts
const vectorParams = defineParams({
  queryVector: param.array(param.f32()),
  limit: param.i64(),
  tenantId: param.string(),
});

function tenantVectorSearch(p = vectorParams) {
  return g()
    .vectorSearchNodesWith(
      "Document",
      "embedding",
      p.queryVector,
      p.limit,
      p.tenantId,
    )
    .valueMap(["$id", "title", "$distance"]);
}
```

Do not run an unscoped top-k query and try to repair it with a later tenant filter.

## Preserve rank fields

Project the search result while it is still ranked:

```ts
g()
  .textSearchNodes("Document", "body", "consensus protocol", 10)
  .valueMap(["$id", "title", "$score"])
```

If the query must traverse to related nodes, keep the ranked projection as one named
entry and run the traversal from a second named entry.

## Keep write batches bounded

Use `forEachParam` for small, bounded object arrays. For large imports, page the input
and measure transaction duration instead of sending an unbounded batch.

For an application-level upsert, build one write batch:

1. find the existing object by a label-scoped equality-indexed key
2. conditionally update when the named result is non-empty
3. conditionally create when it is empty

This keeps the decision and mutation in one direct request without stored routes or
query registration.
