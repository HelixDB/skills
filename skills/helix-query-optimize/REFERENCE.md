# HelixDB v3 Optimization Reference

This reference describes the planner-selected physical behavior introduced by
[PR #974](https://github.com/HelixDB/helix-db/pull/974) and
[PR #975](https://github.com/HelixDB/helix-db/pull/975), in the cumulative stack
merged by [PR #996](https://github.com/HelixDB/helix-db/pull/996). Public DSL and
JSON syntax are unchanged.

## Source Map

The links are pinned to the reviewed stack at `07d3cc0`; prefer paths and symbols
over brittle line-number citations.

| Concern | Canonical sources |
| --- | --- |
| Exact cross-numeric equality/order | [`crates/value-semantics/src/lib.rs`](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/value-semantics/src/lib.rs) |
| Logical equality/range set rewrites | [`crates/planner/src/rules/access/sets/equality_range/`](https://github.com/HelixDB/helix-db/tree/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/planner/src/rules/access/sets/equality_range) |
| Ordered range selection | [`range_direction.rs`](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/planner/src/rules/access/order/rules/range_direction.rs), [`sets/range/`](https://github.com/HelixDB/helix-db/tree/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/planner/src/rules/access/sets/range) |
| Physical equality/range programs | [`exec/access/node.rs`](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/planner/src/exec/access/node.rs), [`exec/access/edge.rs`](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/planner/src/exec/access/edge.rs), [`exec/selected/`](https://github.com/HelixDB/helix-db/tree/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/planner/src/exec/selected) |
| Count programs and windows | [`exec/count.rs`](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/planner/src/exec/count.rs), [`rules/cardinality.rs`](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/planner/src/rules/cardinality.rs) |
| Equality/range execution | [`secondary_set.rs`](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/db/src/execution/interpreter/access/secondary_set.rs), [`range.rs`](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/db/src/execution/interpreter/access/range.rs) |
| Count execution | [`interpreter/count.rs`](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/crates/db/src/execution/interpreter/count.rs) |

The planner directory is intentionally decomposed; do not describe the runtime as
one monolithic interpreter-only model.

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

| Index family | Intended operations | Correctness boundary |
|---|---|---|
| non-unique equality | exact bitmap point reads, membership, batched same-index unions | literal/parameter must be compatible and reflexive |
| unique equality | owner point read | authoritative owner verification remains required |
| range | ordered comparisons, bounded ranges, ordered reads | candidates are verified against authoritative values |
| vector | nearest-neighbor search on numeric arrays | tenant and `k` remain part of the plan |
| text | BM25 full-text search | tenant and `k` remain part of the plan |
| authoritative scan | null/non-indexable/residual fallback | correctness path, not necessarily a planner failure |

Node and edge indexes are distinct. Index label, property, vector dimension, distance
metric, and tenant property must match the query.

Index DDL is durable and asynchronous. A create request returns a receipt; poll its
status and wait for the index to be active before benchmarking the read path.

## Exact Value Semantics

`helix_value_semantics::CanonicalNumber` is shared by planner proofs and storage
codecs.

- Integer and floating representations compare by exact mathematical value, not
  by enum variant and not by converting integers through `f64`.
- `42_i64 == 42.0_f64` when the floating value represents the integer exactly.
- `-0.0` and `0.0` canonicalize to the same zero.
- Finite values and infinities have an exact total ordering for range planning.
- NaN stays non-reflexive and cannot be an equality bitmap key.

Keep parameter types truthful, but do not add client-side coercion merely to
match an index representation.

## Equality Set Programs

A proven non-unique equality lookup reads one bitmap row. Equalities on the same
index can become a batched multi-get whose bitmaps are unioned; surface forms
include an indexable `or` or equivalent membership predicate.

Intersections combine equality bitmaps and compatible range candidates before
row materialization. Keep all arms in one logical expression. If an arm changes
label/property/index identity, is null/NaN, or otherwise lacks proof, the fast
path is declined. The planner owns selected-child order; hand-ordering AST nodes
is not a substitute for catalog and cardinality selection.

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
bound, after every filter/order operation that must semantically precede it.
`dedup().limit(n)` is a common pattern after graph expansion.

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

Count plans normalize compatible `limit`, `skip`, and `range` chains with
saturating/min/subtract arithmetic so large values do not wrap. Do not move a
window across a filter, distinctness, ordering, mutation, or identity-sensitive
operation unless equivalence is proven; the fallback retains semantic order.

## Ordering

Ordering a large property stream without a matching range index can require a full
materialize-and-sort path. With a compatible ordered range index, execution can:

1. build/intersect equality or range filter ID sets
2. scan the range index in the requested direction
3. admit only IDs present in the filter set
4. stop after the post-filter limit/window is satisfied
5. materialize only surviving rows

This filters before the limit and avoids a redundant sort. Direction, property,
label, and catalog identity must match; range candidates remain authoritatively
verified. Unsupported multi-key order or residual expressions can still require
sorting/materialization. This is stronger than an old immediate
`OrderBy -> Limit` lookahead claim.

For cursor pagination, add an indexed comparison such as “created_at less than the
last returned value,” preserve the same order, and limit the page.

## Count Programs

`Count` has dedicated physical alternatives rather than always consuming a fully
materialized row stream. Alternatives include:

- constant or runtime-input cardinality
- node/edge equality bitmap cardinality
- batched bitmap union/intersection cardinality
- verified unique-owner cardinality
- label bitmap cardinality
- verified range cardinality, optionally with bitmap filters
- vector/text search cardinality
- streaming cursors for residual filters, expansion, order, distinctness,
  variables, identity-sensitive work, and unsupported compositions

Use `.count()` directly after the logical operations whose cardinality is needed.
Adding `.id()`, `.project(...)`, or client-side length forces work the count
planner could otherwise avoid.

## Correctness Fallbacks

| Case | Why the direct fast path is declined or supplemented | Expected shape |
| --- | --- | --- |
| unique equality | index ownership needs authoritative confirmation | point lookup plus owner verification |
| range | encoded entry is a candidate, not final truth | ordered candidate scan plus authoritative verification |
| null equality | absent and explicit-null semantics need row inspection | scoped authoritative scan |
| NaN equality | equality is non-reflexive | non-indexable/empty proof, never an equality bitmap lookup |
| late-bound equality parameter | value is unavailable during early proof | dynamic equality program at execution, or fallback |
| unknown/mismatched index identity | element/label/property/direction/uniqueness would be unsafe | validation failure or authoritative alternative |
| identity-sensitive count | row identity/distinct/order semantics matter | streaming/materialized count cursor |
| residual predicate | no exact set proof exists | narrow indexed candidate plus residual evaluation, or scan |

Literal equality can be encoded during planning. A genuinely late-bound parameter
can remain dynamic and resolve from execution context, with index identity
validated before lookup. Parameterized equality is therefore neither always
unindexed nor identical to a fully proven literal bitmap program.

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

Source-level vector search ranks the whole selected tenant partition. If a
traversal defines eligible node or edge IDs, call traversal-scoped vector search
on that stream. Membership is exact even when approximate index structures
accelerate ranking.

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
write share one transaction. Awaiting durability can reduce concurrent-write
conflicts, but classify retries with the stable `transaction_conflict` code and
replay only safe operations; see `../../docs/error-handling.md`.

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
