# HelixDB v3 Optimization Examples

Broad shape versus selective direct-request shape.

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

Stronger, with an equality index on `User.status`:

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

Response: `{"index": {"kind": "accepted", "operation_id": "…", "index_id": "7", "generation": "1"}}`.
Poll until it succeeds before benchmarking `active_users`:

```ts
readBatch()
  .varAs("op", g().getIndexOperation(operationId))
  .returning(["op"]);
// repeat with backoff until op.status === "succeeded";
// "blocked" needs a data fix, then g().retryIndexOperation(operationId) in a write batch
```

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

If the start user is known, start from an exact ID or an indexed unique property.

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

With a `User.status` equality index this is a bitmap count; no user rows load.

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

The status points become one batched bitmap union, intersected with the region
bitmap before rows load. Do not split it into client requests.

## Keep Runtime Membership Bounded

Keep a caller-supplied domain as one membership predicate:

```ts
g()
  .nWithLabelWhere(
    "Order",
    SourcePredicate.isInParam("status", "statuses"),
  )
  .valueMap(["$id", "status"])
```

With a non-unique equality index, a scalar or bounded array uses a runtime
equality union.

## Keep Related Filters Adjacent

Canonicalized into one conjunction for access planning:

```ts
g()
  .nWithLabel("Order")
  .where(Predicate.eqParam("region", "region"))
  .where(Predicate.isInParam("status", "statuses"))
  .valueMap(["$id", "status", "region"])
```

A traversal, `limit`, `orderBy`, projection, mutation or other non-filter
operation ends the run.

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

It cannot return an ID outside the candidate stream.

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

Exact; refills to ten when at least ten candidates match the text query.

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

After the build succeeds, the planner unions status IDs, intersects region IDs,
drives the route from the descending range index, filters before the 25-row
limit, and skips the in-memory sort.

For only the window's cardinality, drop `.orderBy(...)` and `.valueMap(...)` and
end in `.limit(25).count()`: no range index is needed; the planner counts the
status/region bitmap intersection and clamps it to 25.

## Scope vector search to its tenant

With a tenant-partitioned vector index, pass the tenant to the search:

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

If a strong search hits `index_backpressure` and stale hits are acceptable, read
eventually (main):

```ts
readBatch()
  .varAs("hits", tenantVectorSearch())
  .returning(["hits"])
  .toQueryRequest(
    vectorParams,
    { queryVector, limit: 10, tenantId },
    { searchConsistency: SearchConsistency.Eventual },
  );
```

## Preserve rank fields

Project while the stream is still ranked:

```ts
g()
  .textSearchNodes("Document", "body", "consensus protocol", 10)
  .valueMap(["$id", "title", "$score"])
```

To traverse to related nodes, keep the ranked projection as one named entry and
traverse from a second.

## Keep write batches bounded

Use `forEachParam` only for small arrays; page large imports and measure
transaction duration.

Upsert: unique equality index on the key, then one write batch:

```ts
writeBatch()
  .varAs(
    "index",
    g().createIndexIfNotExists(IndexSpec.nodeUniqueEquality("User", "email")),
  )
  .returning(["index"]);
```

```ts
const upsertParams = defineParams({ email: param.string(), name: param.string() });

function upsertUser(p = upsertParams) {
  return writeBatch()
    .varAs("existing", g().nWithLabelWhere("User", SourcePredicate.eq("email", p.email)))
    .varAsIf(
      "updated",
      BatchCondition.varNotEmpty("existing"),
      g().n(NodeRef.var("existing")).setProperty("name", p.name),
    )
    .varAsIf(
      "created",
      BatchCondition.varEmpty("existing"),
      g().addN("User", { email: p.email, name: p.name }),
    )
    .returning(["updated", "created"]);
}
```

Exactly one of `updated` / `created` holds `[{"$id": N}]`; the other is `[]`. Re-run
once on `unique_constraint_violation` (it takes the update branch); retry
`transaction_conflict` with backoff.
