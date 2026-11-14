# HelixDB v3 Optimization Reference

Planner-selected physical behavior from
[PR #974](https://github.com/HelixDB/helix-db/pull/974) and
[PR #975](https://github.com/HelixDB/helix-db/pull/975) (merged in
[PR #996](https://github.com/HelixDB/helix-db/pull/996)), bounded runtime
equality domains ([PR #1015](https://github.com/HelixDB/helix-db/pull/1015)) and
adjacent-filter canonicalization ([PR #1017](https://github.com/HelixDB/helix-db/pull/1017)).
Public DSL and JSON syntax are unchanged. Contracts and rules are in `SKILL.md`.

## Source Map

Pinned to main commit `5ec14e5f`; cite paths and symbols, not line numbers.

| Concern | Canonical sources |
| --- | --- |
| Exact cross-numeric equality/order | [`crates/value-semantics/src/lib.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/value-semantics/src/lib.rs) |
| Logical equality/range set rewrites | [`crates/planner/src/rules/access/sets/equality_range/`](https://github.com/HelixDB/helix-db/tree/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/rules/access/sets/equality_range) |
| Runtime equality-domain analysis | [`analysis/index_atoms/equality.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/analysis/index_atoms/equality.rs), [`rules/access/filter/atoms/collect.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/rules/access/filter/atoms/collect.rs) |
| Runtime membership execution | [`access/membership.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/db/src/execution/interpreter/access/membership.rs) |
| Adjacent-filter canonicalization | [`logical/access/pipeline/canonical.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/logical/access/pipeline/canonical.rs) |
| Ordered range selection | [`range_direction.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/rules/access/order/rules/range_direction.rs), [`sets/range/`](https://github.com/HelixDB/helix-db/tree/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/rules/access/sets/range) |
| Physical equality/range programs | [`exec/access/node.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/exec/access/node.rs), [`exec/access/edge.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/exec/access/edge.rs), [`exec/selected/`](https://github.com/HelixDB/helix-db/tree/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/exec/selected) |
| Count programs and windows | [`exec/count.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/exec/count.rs), [`rules/cardinality.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/planner/src/rules/cardinality.rs) |
| Equality/range execution | [`secondary_set.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/db/src/execution/interpreter/access/secondary_set.rs), [`range.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/db/src/execution/interpreter/access/range.rs) |
| Count execution | [`interpreter/count.rs`](https://github.com/HelixDB/helix-db/blob/5ec14e5f8cf059aa03f42917d560b3cded09fb26/crates/db/src/execution/interpreter/count.rs) |

## Sources

| Source | Typical cost |
|---|---|
| `n` / `e` with exact IDs | direct lookup |
| `nWithLabelWhere` / `eWithLabelWhere` | index-eligible label-scoped predicate |
| `nWhere` / `eWhere` | predicate source; scope determines usable indexes |
| `nWithLabel` / `eWithLabel` | all elements under one label |
| all IDs | broad scan |
| vector search | HNSW top-k |
| text search | BM25 top-k |

`SourcePredicate` is the source-position predicate; `Predicate` is the general
`where` filter.

## Index families

| Index family | Intended operations | Correctness boundary |
|---|---|---|
| non-unique equality | exact bitmap point reads, membership, batched same-index unions | literal/parameter must be compatible and reflexive |
| unique equality | owner point read | authoritative owner verification remains required |
| range | ordered comparisons, bounded ranges, ordered reads | candidates are verified against authoritative values |
| vector | nearest-neighbor search on numeric arrays | tenant and `k` remain part of the plan |
| text | BM25 full-text search | tenant and `k` remain part of the plan |
| authoritative scan | null/non-indexable/residual fallback | correctness path, not necessarily a planner failure |

Node and edge indexes are distinct. Label, property, vector dimension, distance
metric and tenant property must match the query.

### Index build status

Index DDL is durable. `get_index_operation` returns `status` (`queued`,
`running`, `blocked`, `succeeded`, `aborted`) with `stage`, `attempt` and
`progress`. While a unique index builds, a write is rejected only if its value is
already claimed, by an entity the build has scanned or by a write since the build
started. A duplicate of a value held only by a not-yet-scanned entity is written,
and the build blocks (`uniqueness_violation`) when its scan reaches that entity;
duplicates in existing data block the build, not the writes.

## Exact value semantics

`helix_value_semantics::CanonicalNumber` is shared by planner proofs and storage
codecs. Numbers compare by exact mathematical value, not enum variant;
`42_i64 == 42.0_f64` only when the float represents the integer exactly. Finite
values and infinities have an exact total order for range planning.

## Equality set programs

A proven non-unique equality lookup reads one bitmap row; same-index equalities
(an indexable `or` or membership predicate) become a batched multi-get whose
bitmaps are unioned. Intersections combine equality bitmaps and compatible range
candidates before row materialization. An arm that changes label/property/index
identity, is null/NaN, or lacks proof declines the fast path. The planner owns
selected-child order; hand-ordering AST nodes does not replace catalog and
cardinality selection.

### Bounded runtime equality domains

Immutable, available request parameters are specialized before predicate
planning. A still runtime-bound `is_in_param` on a proven node or edge equality
index uses a `RuntimeEqualitySet` bounded by `max_index_union_branches`. At
execution, typed arrays, general arrays and scalars normalize into one exact
domain. A domain containing null, an unsupported or oversized value, or more
unique values than the bound uses authoritative scoped membership evaluation,
never a partial index answer.

## Stream bounds

Literal and parameterized bounds serialize as:

```json
{ "count": { "literal": 25 } }
{ "count": { "expr": { "param": "limit" } } }
```

Count plans normalize compatible `limit` / `skip` / `range` chains with
saturating/min/subtract arithmetic so large values do not wrap. Do not move a
window across a filter, distinctness, ordering, mutation or identity-sensitive
operation unless equivalence is proven.

## Ordered range driver

Without a matching range index, ordering a large property stream can
materialize and sort everything. With one, execution:

1. builds/intersects equality or range filter ID sets
2. scans the range index in the requested direction
3. admits only IDs in the filter set
4. stops after the post-filter limit/window is satisfied
5. materializes only surviving rows

Direction, property, label and catalog identity must match. Cursor pagination:
add an indexed comparison such as "`created_at` less than the last returned
value", keep the same order, and limit the page.

## Count programs

Physical alternatives to consuming a materialized row stream:

- constant or runtime-input cardinality
- node/edge equality bitmap cardinality
- batched bitmap union/intersection cardinality
- verified unique-owner cardinality
- label bitmap cardinality
- verified range cardinality, optionally with bitmap filters
- vector/text search cardinality
- streaming cursors for residual filters, expansion, order, distinctness,
  variables, identity-sensitive work and unsupported compositions

Adding `.id()`, `.project(...)` or client-side length forces work the count
planner could avoid.

## Correctness fallbacks

| Case | Why the direct fast path is declined or supplemented | Expected shape |
| --- | --- | --- |
| unique equality | index ownership needs authoritative confirmation | point lookup plus owner verification |
| range | encoded entry is a candidate, not final truth | ordered candidate scan plus authoritative verification |
| null equality | absent and explicit-null semantics need row inspection | scoped authoritative scan |
| NaN equality | equality is non-reflexive | non-indexable/empty proof, never an equality bitmap lookup |
| late-bound equality parameter | value is unavailable during early proof | dynamic equality program at execution, or fallback |
| runtime membership domain | domain is null, unsupported, oversized, or exceeds the union bound | authoritative scoped membership evaluation |
| unknown/mismatched index identity | element/label/property/direction/uniqueness would be unsafe | validation failure or authoritative alternative |
| identity-sensitive count | row identity/distinct/order semantics matter | streaming/materialized count cursor |
| residual predicate | no exact set proof exists | narrow indexed candidate plus residual evaluation, or scan |

Literal equality can be encoded during planning. A late-bound parameter can stay
dynamic and resolve from execution context, with index identity validated before
lookup: parameterized equality is neither always unindexed nor identical to a
proven literal bitmap program.

## Projections

`valueMap` / `value_map` returns selected properties; `project` handles aliases,
expressions, binding projections and endpoint projections. Virtual fields: `$id`,
`$label`, `$from` / `$to` (edges), `$distance` (vector hits), `$score` (text
hits). Rank values belong to the ranked stream.

## Search

Vector search requires a matching node/edge vector index, label and property,
dimension, query vector, top-k bound, and the tenant value when the index is
tenant-partitioned. Text search requires the analogous text index and query
text. Source-level search ranks the whole selected tenant partition; traversal-scoped
membership is exact even when approximate structures accelerate ranking.

Restricted BM25 is exact: it deduplicates candidate IDs, keeps full
tenant-partition BM25 statistics, and orders by score descending then entity ID
ascending. It is a materializing barrier. Common query terms can still enumerate
many BM25 matches, so candidate selectivity does not guarantee proportional
latency.

## Batch cost

Entries execute in order; later entries can reference earlier names. Only names
in `returns` are returned, but every entry runs. Conditional entries avoid work:
`var_not_empty`, `var_empty`, `var_min_size`, `prev_not_empty`. `for_each` cost
is array length times body cost; keep it bounded.

## Write cost

- `add_n` creates a node per applicable input row; `add_e` with an empty target
  fails the whole batch.
- Property mutation touches every element in the current stream.
- Review broad drops for graph cardinality.
- Keep the lookup, conditional update/create and related edge writes in one write
  batch so they share one transaction.

## Wire shape

Every SDK emits the same nested operation tree (full example in `EXAMPLES.md`).
There is no step array, stored route, registration table or bundle layer.

## Cypher and SQL plans

`POST /v2/cypher/explain` and `POST /v2/sql/explain` take the `/v2/cypher` /
`/v2/sql` body (`{"query", "parameters", "query_name"}`; SQL also accepts a
positional `parameters` list and `mappings`). The plan reports its `effect`
(`Read` or `Write`), selected access paths such as index lookups, estimated
cardinalities, blocking work, Cartesian products and optimizer warnings. Supply
every parameter the statement uses. An index is used only when every other
condition on that node cannot fail.
