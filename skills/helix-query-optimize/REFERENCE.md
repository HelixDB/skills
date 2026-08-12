# HelixDB v3 Optimization Reference

This reference follows the current public query model and future source locations in
[`HelixDB/helix-db`](https://github.com/HelixDB/helix-db):

- AST and builders:
  [`crates/ast`](https://github.com/HelixDB/helix-db/tree/main/crates/ast)
- Rust SDK:
  [`sdks/rust`](https://github.com/HelixDB/helix-db/tree/main/sdks/rust)
- TypeScript SDK:
  [`sdks/typescript`](https://github.com/HelixDB/helix-db/tree/main/sdks/typescript)
- Database query runtime:
  [`crates/db`](https://github.com/HelixDB/helix-db/tree/main/crates/db)

Use main-branch links in published skills. Line numbers are intentionally omitted
because the forthcoming v3 source is still changing.

## Sources

| Source | Typical cost characteristic |
|---|---|
| `n` / `e` with exact IDs | direct lookup |
| `nWithLabelWhere` / `eWithLabelWhere` | index-eligible label-scoped predicate |
| `nWhere` / `eWhere` | predicate source; scope determines usable indexes |
| `nWithLabel` / `eWithLabel` | all elements under one label |
| all IDs | broad scan |
| vector search | HNSW top-k |
| text search | BM25 top-k |

`SourcePredicate` is the source-position predicate surface. `Predicate` is the
general filter expression used by `where`. Prefer a label-scoped source predicate
when the filter is known before traversal.

## Index families

| Index family | Intended operations |
|---|---|
| equality | exact equality, membership, property presence where supported |
| range | ordered comparisons, bounded ranges, ordered reads |
| vector | nearest-neighbor search on numeric arrays |
| text | BM25 full-text search |

Node and edge indexes are distinct. Index label, property, vector dimension, distance
metric, and tenant property must match the query.

Index DDL is durable and asynchronous. A create request returns a receipt; poll its
status and wait for the index to be active before benchmarking the read path.

## Label scope

Equality and range definitions include a label and property. Preserve that scope in
the source:

```rust
g().n_with_label_where(
    "Order",
    SourcePredicate::eq("status", "active"),
)
```

This is clearer and more index-friendly than starting from all nodes and applying a
mid-stream status filter.

## Stream bounds

Place `limit`, `range`, or `skip` as close as possible to the operation it should
bound. `dedup().limit(n)` is a common pattern after graph expansion.

Limit and skip values are stream bounds. Literal values serialize as:

```json
{
  "count": { "literal": 25 }
}
```

Parameterized values serialize as expressions:

```json
{
  "count": { "expr": { "param": "limit" } }
}
```

## Ordering

Ordering a large property stream without a matching range index can require a full
materialize-and-sort path. Pair frequent large `orderBy(property, order).limit(n)`
queries with a range index for the same label/property.

For cursor pagination, add an indexed comparison such as “created_at less than the
last returned value,” preserve the same order, and limit the page.

## Projections

`valueMap`/`value_map` returns selected properties. Use `project` for aliases,
expressions, binding projections, and endpoint projections.

Virtual fields include:

- `$id`
- `$label`
- `$from` and `$to` for edges
- `$distance` for vector hits
- `$score` for text hits

Search rank values belong to the current ranked stream. Project them before graph
traversal changes the stream to neighbors or endpoints.

## Search

Vector search requires:

- matching node/edge vector index
- matching label and property
- matching dimension
- query vector
- top-k bound
- tenant value when the index is tenant-partitioned

Text search requires the analogous text index and query text. Source-level text
search ranks the whole selected tenant partition. If a traversal defines eligible
node or edge IDs, call traversal-scoped text search on that stream instead of
post-filtering source top-k hits.

Restricted BM25 search is exact: it deduplicates candidate IDs, preserves full
tenant-partition BM25 statistics, and returns at most `k` ordered by score
descending then entity ID ascending. It is a materializing barrier with a
1,000,000-unique-candidate limit. Common query terms can still enumerate many BM25
matches, so candidate selectivity does not guarantee proportional latency.

## Batch cost

Batch entries execute in order. Later entries can refer to earlier named results.
Only names in `returns` become response members, but non-returned entries still run.

Conditional entries can avoid unnecessary work:

- `var_not_empty`
- `var_empty`
- `var_min_size`
- `prev_not_empty`

`for_each` repeats its body once per parameter object. Its cost grows with both array
length and body cost; keep it bounded.

## Write cost and safety

- `add_n` creates a node for each applicable input row.
- `add_e` can create a product of source and target rows.
- property mutation touches every element in the current stream.
- broad drop operations should be reviewed for graph cardinality.
- upsert existence checks should use an equality-indexed key.

Use a write batch so the lookup, conditional update/create, and any related edge
write share one transaction.

## Wire shape

Every SDK emits the same nested operation tree:

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
            }
          }
        }
      ],
      "returns": ["users"]
    }
  }
}
```

There is no step array, stored route, registration table, or bundle layer.
