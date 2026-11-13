# Helix Query Authoring — Rust DSL Reference

Builder catalog for the `helix-db` crate (`use helix_db::dsl::prelude::*;`), checked
against `HelixDB/helix-db` `main` at `5be60bdaa`. **(main)** marks APIs missing from
3.0.0; SKILL.md has the 3.0.0 fallbacks. Shared AST and builders:
[`crates/ast`](https://github.com/HelixDB/helix-db/tree/main/crates/ast); client and
macros: [`sdks/rust`](https://github.com/HelixDB/helix-db/tree/main/sdks/rust).

## Typestate Cheat Sheet

```text
Empty  -- n, n_where, n_with_label[_where], inject                      └─> OnNodes
Empty  -- add_n, drop_edge_by_id                                        └─> OnNodes (WriteEnabled)
Empty  -- e, e_where, e_with_label[_where]                              └─> OnEdges
Empty  -- vector_search_nodes[_with], text_search_nodes[_with]          └─> OnNodes
Empty  -- vector_search_edges[_with], text_search_edges[_with]          └─> OnEdges
Empty  -- shortest_path[_with], get_index_operation                     └─> Terminal
Empty  -- create_index_if_not_exists, drop_index, create_*_index_*,
          retry_index_operation, abort_index_operation                  └─> Terminal (WriteEnabled)
OnNodes -- out, in_, both, has, has_label, has_key, where_, dedup,
           within, without, limit, skip, range, as_, store, select,
           inject, bind, order_by[_multiple], repeat, union, choose,
           coalesce, optional, path, simple_path, fold, unfold, with_sack,
           sack_set, sack_add, sack_get, vector_search[_with],
           text_search[_with] (main)                                    ↻ OnNodes
OnNodes -- out_e, in_e, both_e                                          └─> OnEdges
OnNodes -- count, exists, id, label, values, value_map, project,
           project_bindings, project_distinct_bindings,
           group, group_count, aggregate_by                             └─> Terminal
OnNodes(WriteEnabled) -- add_n, add_e, set_property, remove_property,
           drop, drop_edge, drop_edge_labeled, drop_edge_by_id          ↻ OnNodes
OnEdges -- out_n, in_n, other_n                                         └─> OnNodes
OnEdges -- has, has_label, has_key, where_, edge_has, edge_has_label,
           dedup, limit, skip, range, as_, store, bind, order_by,
           vector_search[_with], text_search[_with] (main)              ↻ OnEdges
OnEdges -- count, exists, id, label, values, value_map, project,
           project_bindings, project_distinct_bindings, edge_properties └─> Terminal
OnEdges(WriteEnabled) -- drop (main), set_property, remove_property     ↻ OnEdges
```

Edge streams have no `within`, `without`, `select`, `inject`, `order_by_multiple`,
`repeat`, branching, or `drop_edge_by_id`. Delete the edges in a stream with `.drop()`
(main), or by ID with the source form `g().drop_edge_by_id(...)` (e.g. on an edge variable
via `EdgeRef::var`).

`ReadBatch::var_as` accepts only `Traversal<_, ReadOnly>`: a `WriteEnabled` step in a read
batch is a compile error. `WriteBatch::var_as` accepts either.

---

## Batch Entry Points

```text
pub fn read_batch() -> ReadBatch
pub fn write_batch() -> WriteBatch
pub fn g() -> Traversal<Empty>
pub fn sub() -> SubTraversal
```

`ReadBatch` / `WriteBatch`:

- `var_as<S>(name, traversal)` — store a named result.
- `var_as_if<S>(name, condition: BatchCondition, traversal)` — conditional entry.
- `for_each_param(param: &str, body: ReadBatch | WriteBatch)` — run `body` once per object
  in an array param; parameter names resolve against the current object's fields. A
  variable set in `body` holds only the **last** iteration's result, so do not return it as
  "everything created"; re-read afterwards if the caller needs the rows.
- `returning<I, S: Into<String>>(vars)` — restrict the response to these variables.

```text
BatchCondition::VarNotEmpty(name)
BatchCondition::VarEmpty(name)
BatchCondition::VarMinSize(name, n)
BatchCondition::PrevNotEmpty
```

---

## Sources  (`Traversal<Empty>` → `Traversal<On*, _>`)

```text
// Nodes
g().n(nodes: impl Into<NodeRef>)                      -> Traversal<OnNodes>
g().n_where(pred: SourcePredicate)                    -> Traversal<OnNodes>
g().n_with_label(label)                               -> Traversal<OnNodes>
g().n_with_label_where(label, pred: SourcePredicate)  -> Traversal<OnNodes>

// Edges
g().e(edges: impl Into<EdgeRef>)                      -> Traversal<OnEdges>
g().e_where(pred: SourcePredicate)                    -> Traversal<OnEdges>
g().e_with_label(label)                               -> Traversal<OnEdges>
g().e_with_label_where(label, pred: SourcePredicate)  -> Traversal<OnEdges>

// Whole-partition vector & text search sources
g().vector_search_nodes(label, property, query_vector: Vec<f32>, k: usize,
    tenant_value: Option<PropertyValue>)              -> Traversal<OnNodes>
g().vector_search_nodes_with(label, property,
    query_vector: impl Into<PropertyInput>,
    k: impl Into<StreamBound>,
    tenant_value: Option<PropertyInput>)              -> Traversal<OnNodes>
g().text_search_nodes(label, property, query_text, k: usize,
    tenant_value: Option<PropertyValue>)              -> Traversal<OnNodes>
g().text_search_nodes_with(label, property,
    query_text: impl Into<PropertyInput>,
    k: impl Into<StreamBound>,
    tenant_value: Option<PropertyInput>)              -> Traversal<OnNodes>
// Edge variants: vector_search_edges[_with], text_search_edges[_with]
```

Parameterized routes need the `_with` variants (they accept `PropertyInput::param("x")` and
`Expr::param("k")`); the plain forms take a concrete `Vec<f32>` and `usize`. Source search
covers the whole selected tenant partition; to rank only IDs already in a traversal, use
traversal-scoped search.

---

## Traversal

```text
// Node state
traversal.out(label: Option<impl Into<String>>)   -> Traversal<OnNodes, M>
traversal.in_(label: Option<impl Into<String>>)   -> Traversal<OnNodes, M>
traversal.both(label: Option<impl Into<String>>)  -> Traversal<OnNodes, M>
traversal.out_e(label)                            -> Traversal<OnEdges, M>
traversal.in_e(label)                             -> Traversal<OnEdges, M>
traversal.both_e(label)                           -> Traversal<OnEdges, M>

// Edge state
traversal.out_n()   -> Traversal<OnNodes, M>   // edge → target
traversal.in_n()    -> Traversal<OnNodes, M>   // edge → source
traversal.other_n() -> Traversal<OnNodes, M>   // edge → "other" endpoint

// Traversal-scoped vector and BM25 search (node and edge states)
traversal.vector_search(label, property, query_vector: Vec<f32>, k: usize,
    tenant_value: Option<PropertyValue>) -> Self
traversal.vector_search_with(label, property,
    query_vector: impl Into<PropertyInput>,
    k: impl Into<StreamBound>,
    tenant_value: Option<PropertyInput>) -> Self
traversal.text_search(label, property, query_text: impl Into<String>, k: usize,
    tenant_value: Option<PropertyValue>) -> Self                  // (main)
traversal.text_search_with(label, property,
    query_text: impl Into<PropertyInput>,
    k: impl Into<StreamBound>,
    tenant_value: Option<PropertyInput>) -> Self                  // (main)
```

Skip label filtering with `.out(None::<&str>)`; a bare `None` does not compile (ambiguous
type).

Traversal-scoped search enforces exact membership over the IDs in the current stream.
Vector ranking may use approximate index structures but never returns an ID outside the
stream; project `$distance`. BM25 equals exhaustive search of the tenant partition
intersected with those IDs, top-`k` by score descending then entity ID ascending, with
partition-wide statistics; project `$score`. Use the same tenant partition for candidates
and search, and narrow candidates (tenant, label, indexed predicates) first. Limits:
SKILL.md, Search.

---

## Filters

```text
.has(prop, value: impl Into<PropertyValue>)   // both Nodes & Edges
.has_label(label)
.has_key(prop)
.where_(pred: Predicate)
.dedup()
.within(var_name)                                  // node streams and sub()
.without(var_name)                                 // node streams and sub()
.edge_has(prop, value: impl Into<PropertyInput>)   // Edges only
.edge_has_label(label)                             // Edges only
```

On edge streams, `.has`, `.has_label`, `.has_key` and `.where_` filter stored edge
properties plus virtual fields `$id`, `$label`, `$from`, `$to`, `$distance`, `$score`. Use
`.edge_has` when the right-hand side is a `PropertyInput` expression or runtime parameter.

### `Predicate`

```text
Predicate::eq(prop, val)          Predicate::neq(prop, val)
Predicate::gt(prop, val)          Predicate::gte(prop, val)
Predicate::lt(prop, val)          Predicate::lte(prop, val)
Predicate::between(prop, min, max)
Predicate::has_key(prop)          Predicate::is_null(prop)
Predicate::is_not_null(prop)
Predicate::starts_with(prop, s)   Predicate::ends_with(prop, s)
Predicate::contains(prop, s)      Predicate::contains_param(prop, param)
Predicate::is_in(prop, vals: impl Into<PropertyValue>)
Predicate::is_in_expr(prop, expr) Predicate::is_in_param(prop, param)
Predicate::and(preds)             Predicate::or(preds)
Predicate::not(pred)
Predicate::compare(left: Expr, op: CompareOp, right: Expr)

// Parameterized comparison shortcuts (wrap Compare)
Predicate::eq_param(prop, param)  Predicate::neq_param(prop, param)
Predicate::gt_param(prop, param)  Predicate::gte_param(prop, param)
Predicate::lt_param(prop, param)  Predicate::lte_param(prop, param)

CompareOp::{Eq, Neq, Gt, Gte, Lt, Lte}
```

`SourcePredicate` is a type alias of `Predicate` (`pub type SourcePredicate = Predicate`),
so every constructor works in `n_where`, `n_with_label_where`, `e_where` and
`e_with_label_where`. Comparison values take `impl Into<PropertyInput>`:
`SourcePredicate::eq("status", Expr::param("s"))` and `SourcePredicate::eq("status",
"active")` both work. An equality, range or `is_in` on a top-level property indexed **for
that label** can use the index: write `n_with_label_where(label, pred)` (or
`n_with_label(label)` directly followed by `.where_(pred)`). `n_where(pred)` has no label,
scans every node, and cannot use label-scoped indexes.

### Nested properties (dotted paths)

Dotted object paths such as `Predicate::eq("metadata.externalID", "crm-42")` work in
predicates, `Expr::prop`, filtered `values` / `value_map`, `PropertyProjection::source` and
`order_by`. Lookup is exact-first: a top-level property named `metadata.externalID` wins
before walking the `metadata` object. Dotted paths are scan-only: secondary, range, text and
vector indexes cover top-level properties only, so duplicate indexed or searchable fields
onto explicit top-level properties. Arrays are opaque (no `tags.0`). `value_map(None)`
returns top-level properties as stored, without flattening nested objects.

---

## Expressions

```text
Expr::prop(name)                    Expr::val(value: impl Into<PropertyValue>)
Expr::id()                          Expr::param(name)
Expr::timestamp()                   // server UTC epoch millis (i64)
Expr::datetime()                    // server typed DateTime
expr.add(other)    expr.sub(other)  expr.mul(other)   expr.div(other)
expr.modulo(other) expr.neg()
Expr::case(when_then: Vec<(Predicate, Expr)>, else_expr: Option<Expr>)
```

- `Predicate::compare(Expr::prop("age"), CompareOp::Gte, Expr::param("minAge"))` —
  property-to-parameter comparison with typed coercion.
- `ExprProjection::new("age_plus_one", Expr::prop("age").add(Expr::val(1i64)))` — computed
  column.
- `add_n("Foo", vec![("createdAt", PropertyInput::from(Expr::timestamp()))])` — server-side
  timestamp.
- `Expr::case(vec![(Predicate::gte("score", 100i64), Expr::val("high"))],
  Some(Expr::val("low")))` inside `Projection::expr(...)` — per-row value (Cypher/SQL
  `CASE`); use it, not `choose`, when every row should survive.

---

## Stream Bounds, Variables, Ordering, Aggregation

```text
.limit(n: impl Into<StreamBound>)
.skip(n: impl Into<StreamBound>)
.range(start: impl Into<StreamBound>, end: impl Into<StreamBound>)
.limit(25usize)                 // StreamBound::Literal
.limit(Expr::param("limit"))    // StreamBound::Expr
```

`StreamBound` accepts `usize`, `u8`/`u16`/`u32`, `i64`/`i32` (errors into `Expr::Constant`
when negative), and `Expr`.

```text
.as_(name)          // store current stream
.store(name)        // alias of .as_
.select(name)       // replace current stream with a stored var
.inject(name)       // inject a var into the stream (source or mid-traversal)
g().inject(name)    // Empty -> OnNodes source form
```

Cross-entry references: `NodeRef::var(name)`, `EdgeRef::var(name)`,
`NodeRef::param(name)`, `EdgeRef::param(name)`.

```text
.order_by(property, order: Order)                       // Order::{Asc, Desc}; node and edge streams
.order_by_multiple(vec![(prop1, Order::Desc), (prop2, Order::Asc)])   // node streams and sub() only
```

Missing values sort first for `Asc`, last for `Desc`: when porting `ORDER BY`, filter with
`Predicate::is_not_null(prop)` first or accept the placement. Range indexes do not
accelerate nested paths.

```text
.count()           -> Traversal<Terminal, M>
.exists()          -> Traversal<Terminal, M>
.group(property)   -> Traversal<Terminal, M>
.group_count(property) -> Traversal<Terminal, M>
.aggregate_by(fn: AggregateFunction, property) -> Traversal<Terminal, M>
// AggregateFunction::{Count, Sum, Min, Max, Mean}
```

---

## Branching

Each arm is a `SubTraversal` built from `sub()`:

```text
.union(vec![sub_a, sub_b, ...])
.choose(condition: Predicate, then_t: SubTraversal, else_t: Option<SubTraversal>)
.coalesce(vec![sub_a, sub_b, ...])   // first non-empty wins
.optional(sub_a)                     // sub_a's rows, or the input row unchanged when sub_a is empty
```

- An empty `optional` branch leaves the current element as the input (a `User`, not a
  missing `Company`); for OPTIONAL MATCH see Row bindings.
- `choose` without else **drops** rows that fail the condition; it picks a traversal, not a
  value (`Expr::case`).

`SubTraversal` includes `out`, `in_`, `both`, `out_e`, `in_e`, `both_e`, `out_n`, `in_n`,
`other_n`, `has`, `has_label`, `has_key`, `where_`, `dedup`, `within`, `without`,
`edge_has`, `edge_has_label`, `limit`, `skip`, `range`, `as_`, `store`, `select`, `bind`,
`order_by`, `order_by_multiple`, `path` and `simple_path`; no projection or terminal steps.

---

## Repeat

```text
traversal.repeat(RepeatConfig::new(sub()).times(3))
traversal.repeat(
    RepeatConfig::new(sub().out(Some("KNOWS")))
        .until(Predicate::eq("title", "CEO"))
        .emit_after()
        .max_depth(10)
)
```

- `.times(n: usize)` — fixed iterations
- `.until(Predicate)` — stop when the predicate is true
- `.emit_after()` — emit each iteration's output (Gremlin postfix `.emit()`; Cypher `*1..n`)
- `.emit_before()` — emit each iteration's input (includes the seed, excludes the last
  hop's output)
- `.emit_all()` — both, so a row reached at depth 1 is emitted twice; follow with
  `.dedup()` if that matters
- `.emit_if(Predicate)` — emit matching rows after each iteration (sets emit to `After`)
- `.max_depth(n)` — safety cap (default 100)

Default `emit` is `EmitBehavior::None` (only the final iteration's rows). Bound every
repeat with `times` or `until`; do not rely on `max_depth` alone.

---

## Projections (terminals)

```text
.values(vec!["name", "email"])                              -> Traversal<Terminal, M>
.value_map(Some(vec!["$id", "name"]))                       -> Traversal<Terminal, M>
.value_map(None::<Vec<&str>>)                               -> Traversal<Terminal, M>  // all properties
.project(vec![...]: Vec<impl Into<Projection>>)             -> Traversal<Terminal, M>
.edge_properties()                                          -> Traversal<Terminal, M>  // OnEdges only

PropertyProjection::new("name")                 // no rename; source == alias
PropertyProjection::renamed("$distance", "distance")
ExprProjection::new("age_plus_one", Expr::prop("age").add(Expr::val(1i64)))
Projection::property("source", "alias")
Projection::expr("alias", expr)
Projection::from_endpoint("resource_id", "from_id")   // {"source":"$from.resource_id","alias":"from_id"}
Projection::to_endpoint("resource_id", "to_id")       // {"source":"$to.resource_id","alias":"to_id"}
```

`PropertyProjection` and `ExprProjection` both implement `Into<Projection>`; mix them in
`.project(vec![...])`. On edge streams the endpoint helpers return source/target node
properties without traversing to each endpoint; keep `.edge_properties()` for full edge
maps and the internal `$from` / `$to` node ids.

---

## Row bindings (multi-hop correlation)

`.project(...)` only sees the final stream. To correlate values captured at **different
hops** of one path, tag elements with `.bind(name)`, then build rows with
`.project_bindings(...)` / `.project_distinct_bindings(...)`.

```text
.bind(name: impl Into<String>)                                  ↻ same stream; enters row mode (panics on empty name)
.project_bindings(vec![...]: Vec<BindingProjection>)            -> Traversal<Terminal, M>  // preserves duplicate rows
.project_distinct_bindings(vec![...]: Vec<BindingProjection>)   -> Traversal<Terminal, M>  // dedups identical rows
```

`.bind()` does not change the stream; each path keeps row-local bindings, so later hops
(including inside `union`, `coalesce` and `optional`) can reference earlier captures. It is
available on node and edge `Traversal`s and on `SubTraversal`.

After a `bind`, the planner rejects `order_by[_multiple]`, `choose`, `repeat`, `id`,
`label`, `values`, `value_map`, `project` and `edge_properties`
(`invalid_after_bind_operation`). Order or repeat before the first `bind`; finish with
`project_bindings`, `project_distinct_bindings`, `count` or `exists`. A binding never set on
a row (empty `optional` branch), or a property it lacks, leaves that alias **out of the row
object** rather than `null`; decode such columns as `Option<T>` with `#[serde(default)]`.

OPTIONAL MATCH (one row per user, `employer` absent when there is none):

```rust
g().n_with_label("User")
    .bind("user")
    .optional(sub().out(Some("WORKS_AT")).has_label("Company").bind("employer"))
    .project_bindings(vec![
        BindingProjection::binding("user", "name", "name"),
        BindingProjection::binding("employer", "name", "employer"),
    ])
```

Not `.optional(sub().out(Some("WORKS_AT"))).project(...)`: for a user with no employer the
current element is still the user, so "employer" columns would read the user's own
properties.

```text
BindingProjection::current("$id", "current_id")           // read from the current element
BindingProjection::binding("service", "$id", "service_id")// read from a named binding
BindingProjection::property(BindingTarget::binding("svc"), "name", "svc_name")
BindingProjection::coalesce(vec![                          // first present non-null wins
    BindingValueRef::binding("deployment", "$id"),
    BindingValueRef::binding("owner", "$id"),
], "workload_id")
```

`BindingTarget` is `Current` or `Binding(name)`; `BindingValueRef { target, source }` has
`BindingValueRef::current(source)` / `BindingValueRef::binding(name, source)`. `source`
accepts stored properties and the virtual fields `$id`, `$label`, `$from`, `$to`,
`$distance`, `$score`. Worked multi-hop example: EXAMPLES.md, Row bindings. Wire shape:
`../helix-query-json-dynamic/REFERENCE.md`.

---

## Terminals (metadata)

`.count()`, `.exists()`, `.id()`, `.label()` work on node and edge streams;
`.edge_properties()` is edge-only.

---

## Mutations (write-only)

```text
// Source position: Traversal<Empty> -> Traversal<OnNodes, WriteEnabled>
g().add_n(label, vec![(prop, PropertyInput::from(val)), ...])
g().drop_edge_by_id(edges: impl Into<EdgeRef>)   // delete edges by ID (multigraph-safe)
g().inject(var_name)                             // ReadOnly source; usable in write batches

// Node state: Traversal<OnNodes, _> -> Traversal<OnNodes, WriteEnabled>
.add_n(label, vec![...])
.add_e(label, to: impl Into<NodeRef>, vec![(prop, PropertyInput::from(val)), ...])
.set_property(name, value: impl Into<PropertyInput>)
.remove_property(name)
.drop()
.drop_edge(to: impl Into<NodeRef>)
.drop_edge_labeled(to: impl Into<NodeRef>, label)
.drop_edge_by_id(edges: impl Into<EdgeRef>)

// Edge state: Traversal<OnEdges, _> -> Traversal<OnEdges, WriteEnabled>
.set_property(name, value)    .remove_property(name)    .drop()   // .drop() (main)
```

Delete a node's outgoing `FOLLOWS` edges with `.out_e(Some("FOLLOWS")).drop()` (main).

- `add_e` creates one edge per (source row, target node) pair every run; guard it with a
  lookup (`var_as` + `var_as_if(VarEmpty)`) when the edge must be unique. An empty target
  fails the whole batch; an empty source creates nothing.
- `NodeRef::var(name)` must name a **node stream**. A variable ending in `project`,
  `values`, `value_map`, `count`, or an index receipt fails at runtime ("variable is not a
  node stream"); keep the raw `add_n` in one variable and project in another.
- Unprojected mutation results return only `{"$id": N}` per element.

```text
PropertyInput::from("literal")              // wraps as Value(PropertyValue)
PropertyInput::from(Expr::timestamp())      // wraps Expr
PropertyInput::param("userId")              // wraps Expr::Param("userId"); prefer it to wrapping Expr::Param by hand
PropertyInput::from(PropertyValue::object(vec![("externalID", PropertyValue::from("crm-42"))]))
```

---

## Paths

```text
g().shortest_path(source: impl Into<NodeRef>, target: impl Into<NodeRef>, max_depth: usize)
    -> Traversal<Terminal>          // outgoing edges, any label
g().shortest_path_with(source, target, label: Option<impl Into<String>>,
    direction: ShortestPathDirection, max_depth: usize) -> Traversal<Terminal>
// ShortestPathDirection::{Out, In, Both}
```

Each endpoint (`NodeRef::id`, `::param`, `::var`) must resolve to exactly one node; several
is a query error. Returns node IDs from source to target (`[7]` when source equals target),
or `[]` when an endpoint is missing or no path exists within `max_depth` (must be
positive). Weighted shortest paths are not available; compute them in the application.

---

## Indexes (write-only)

```text
g().create_index_if_not_exists(spec: IndexSpec) -> Traversal<Terminal, WriteEnabled>   // the only create builder
g().drop_index(spec: IndexSpec)                 -> Traversal<Terminal, WriteEnabled>

// Convenience forms (same wire output as create_index_if_not_exists)
g().create_vector_index_nodes(label, property, dimension: NonZeroUsize, metric: VectorDistanceMetric, tenant_property: Option<_>)
g().create_vector_index_edges(label, property, dimension: NonZeroUsize, metric: VectorDistanceMetric, tenant_property: Option<_>)
g().create_text_index_nodes(label, property, tenant_property: Option<_>)
g().create_text_index_edges(label, property, tenant_property: Option<_>)

IndexSpec::node_equality(label, property)               // unique = false
IndexSpec::node_unique_equality(label, property)        // unique = true
IndexSpec::node_range(label, property)
IndexSpec::node_range_desc(label, property)
IndexSpec::node_range_with_direction(label, property, RangeIndexDirection::Desc)
IndexSpec::edge_equality(label, property)
IndexSpec::edge_range(label, property)
IndexSpec::edge_range_desc(label, property)
IndexSpec::edge_range_with_direction(label, property, RangeIndexDirection::Desc)
IndexSpec::node_vector(label, property, dimension, metric, tenant_property)
IndexSpec::node_text(label, property, tenant_property)
IndexSpec::edge_vector(label, property, dimension, metric, tenant_property)
IndexSpec::edge_text(label, property, tenant_property)
```

Unscoped index: `create_text_index_nodes("Doc", "body", None::<&str>)`; a bare `None`
cannot infer its type (E0282). Range indexes default to ascending; use
`RangeIndexDirection::Desc` for newest-first or high-score-first scans.

A unique equality index rejects a duplicate write with `unique_constraint_violation` (409,
`retryable: false`). While the build runs it rejects only a value already claimed, by an
entity the build has scanned or by a write since the build started; a duplicate of a value
held only by a not-yet-scanned entity is written, and the build blocks
(`uniqueness_violation`) when its scan reaches that entity.

### Index lifecycle

CREATE and DROP return an `IndexDdlReceipt` (`helix_db::IndexDdlReceipt`, also in the
prelude):

| Receipt `kind` | Fields | Meaning |
| --- | --- | --- |
| `accepted` | `operation_id`, `index_id`, `generation` | A new build or drop started. |
| `existing_operation` | `operation_id` | The same operation is already in flight. |
| `already_active` | `index_id`, `generation` | An identical index is active; nothing to wait for. |

`g().get_index_operation(id)` (read batch), `g().retry_index_operation(id)` and
`g().abort_index_operation(id)` (write batch) return an `IndexOperationStatus` tagged by
`status`: `queued`, `running`, `blocked` (`blocker_code`, `message`), `succeeded` or
`aborted`.

```rust
use std::time::Duration;
use helix_db::{Client, HelixError, IndexDdlReceipt, IndexOperationStatus};
use helix_db::dsl::prelude::*;

#[derive(serde::Deserialize)]
struct Ddl { index: IndexDdlReceipt }
#[derive(serde::Deserialize)]
struct Op { status: IndexOperationStatus }

async fn ensure_user_id_index(client: &Client) -> Result<(), HelixError> {
    let ddl: Ddl = client
        .query(QueryRequest::write(
            write_batch()
                .var_as(
                    "index",
                    g().create_index_if_not_exists(IndexSpec::node_unique_equality("User", "userId")),
                )
                .returning(["index"]),
        ))
        .send()
        .await?;
    let operation_id = match ddl.index {
        IndexDdlReceipt::AlreadyActive { .. } => return Ok(()),
        IndexDdlReceipt::Accepted { operation_id, .. }
        | IndexDdlReceipt::ExistingOperation { operation_id } => operation_id.to_string(),
    };
    loop {
        let op: Op = client
            .query(QueryRequest::read(
                read_batch()
                    .var_as("status", g().get_index_operation(operation_id.clone()))
                    .returning(["status"]),
            ))
            .send()
            .await?;
        match op.status {
            IndexOperationStatus::Succeeded { .. } => return Ok(()),
            IndexOperationStatus::Queued { .. } | IndexOperationStatus::Running { .. } => {
                tokio::time::sleep(Duration::from_millis(500)).await;
            }
            IndexOperationStatus::Blocked { .. } | IndexOperationStatus::Aborted { .. } => {
                // Blocked: fix what `blocker_code` names (duplicate or invalid source
                // data), then send `g().retry_index_operation(operation_id)` in a write
                // batch, or `g().abort_index_operation(operation_id)` to discard it.
                return Ok(()); // surface this to the caller in real code
            }
        }
    }
}
```

`blocker_code` is one of `invalid_source_data`, `uniqueness_violation`, `oversized_entity`,
`manifest_limit`, `object_store_configuration_unavailable`, `invariant_violation`; a
blocked build does not resume on its own. Lifecycle errors: `index_busy` (409: another
lifecycle operation on the index is running; wait for it), `index_build_blocked` (409: a
write would overflow a blocked build's queue; retry or abort the build first),
`index_operation_not_found` (404), `index_operation_not_abortable` (409).

---

## Reserved-name steps (they execute)

```text
.fold()              // collect the stream into one folded value; an empty fold returns []
.unfold()            // expand a folded value back into rows
.path()              // annotate each row with its traversal path in the response
.simple_path()       // keep only rows whose path repeats no element
.with_sack(PropertyValue::I64(0))   // set a per-row value
.sack_set(prop)      // sack = the element's property (cleared when missing)
.sack_add(prop)      // add a numeric property to the sack
.sack_get()          // include the sack in the response row
```

Rows with visible paths or sacks keep an annotated row envelope instead of `{"$id": N}`;
inspect the JSON before writing a decoder.

---

## `#[query]` Macro And Direct Requests

`sdks/rust/helix-dsl-macros/src/lib.rs`. Apply to a top-level function returning
`ReadBatch` or `WriteBatch`. Inside the body each argument is rebound as
`Expr::param("<name>")`: pass it where an `Expr` is accepted (`.limit(limit)`) or refer to
it by name (`Predicate::eq_param("tenantId", "tenant_id")`). The callable function returns
`Result<QueryRequest, QueryError>` with typed parameters and `query_name` set to the
function name.

```rust
#[query]
pub fn find_user(tenant_id: String, limit: i64) -> ReadBatch {
    read_batch()
        .var_as(
            "users",
            g().n_with_label("User")
                .where_(Predicate::eq_param("tenantId", "tenant_id"))
                .limit(limit)
                .value_map(Some(vec!["$id", "name"])),
        )
        .returning(["users"])
}

let req = find_user("acme".to_string(), 25)?;   // Result<QueryRequest, QueryError>
let json = req.to_json_string()?;               // includes "query_name":"find_user"
```

Param types: `bool`, `i64`, `f64`, `f32`, `String`, `DateTime`, `PropertyValue`,
`ParamValue`, `ParamObject`, `Vec<T>`, and string-keyed maps. Bytes cannot be sent on the
JSON route (`QueryError::UnsupportedBytesParameter`). Declare node/edge ID arguments as
`i64` or `Vec<i64>`, never `String`. `DateTime` is `helix_db::DateTime`:
`DateTime::from_millis(ms)` or `DateTime::parse_rfc3339("2026-01-01T00:00:00Z")?` (a
`chrono::ParseError`).

Pitfall: `#[expect(dead_code)]` on a helper fails the test build if tests use it; use
`#[allow(dead_code)]`.

### `QueryRequest`

```text
QueryRequest::read(batch: ReadBatch)
QueryRequest::write(batch: WriteBatch)
req.set_query_name("find_users")
req.clear_query_name()
req.with_query_name("find_users")
req.with_parameter_value(name, QueryValue::I64(42))                 // untyped; panics on invalid name/value or mixing
req.with_typed_parameter(name, QueryParamType::DateTime, value)?    // typed; Result<Self, QueryError>
req.try_insert_untyped_parameter(name, value)?                      // fallible untyped insert
req.with_search_consistency(SearchConsistency::Eventual)?           // (main); read requests only
req.to_json_string()   // Result<String, QueryError>
req.to_json_bytes()
```

A request is all-typed or all-untyped: a typed parameter after an untyped one returns
`QueryError::MixedParameterModes`; `with_parameter_value` after a typed one panics.
`QueryParamType` is `Bool | I64 | F64 | F32 | String | DateTime | Bytes | Value | Object |
Array(Box<_>)`.

`SearchConsistency::Strong` (default) makes every committed vector/text write searchable,
including work the index worker has not published, and can fail with retryable
`index_backpressure`. `Eventual` includes a bounded slice of unpublished work, never fails
for backpressure, and may return a node that has since changed tenant, label or indexed
property. Writes are always strong (`Eventual` on a write is an error).

Direct `QueryRequest::read/write` requests serialize `query_name: null` until a name is
set; missing or `null` falls back to `__dynamic__` at the gateway; blank names are
rejected. JSON wire encoding: `../helix-query-json-dynamic/REFERENCE.md`.

### `Client`

```text
use helix_db::{Client, HelixError};
use helix_db::QueryErrorCode;   // (main)

Client::new(url: Option<&str>) -> Result<Self, HelixError>   // default "http://localhost:6969"
    .with_api_key(api_key: Option<&str>) -> Self              // Authorization: Bearer <key>
    .with_database_id(id: Option<&str>) -> Self               // (main) X-Helix-Database-Id
    .query::<R: Deserialize>(request) -> QueryExecutionRequest<R>

client.request_builder::<R>()
    .writer_only()                       // X-Helix-Require-Writer: true
    .warm_only()                         // X-Helix-Warm: true (reads only)
    .should_await_durability(b: bool)    // X-Helix-Await-Durable: true|false (writes only)
    .query(request)

request.send().await -> Result<R, HelixError>
request.send_bytes().await -> Result<Vec<u8>, HelixError>
```

`should_await_durability(true)` is the default and unneeded; `false` returns once the write
is applied on the writer, so a crash before the WAL upload loses it. `warm_only()` on a
write is `400 invalid_request_option`. On a read, Helix Cloud fans it out to every eligible
backend and returns `204 No Content` once one succeeds (chain `writer_only()` to warm only
the authoritative writer); a local server returns the normal 200 response.

### Cypher and SQL (main)

`POST /v2/cypher`, `/v2/cypher/explain`, `/v2/sql`, `/v2/sql/explain`. Body
`{"query", "parameters", "query_name"}`; SQL also takes positional `parameters` for `?` and
`mappings`. Response `{"columns": [...], "rows": [[...]]}`.

```rust
use std::collections::BTreeMap;

let result = client
    .cypher(
        "MATCH (u:User {userId: $id})-[:WORKS_AT]->(c:Company) RETURN u.name AS name, c.name AS company",
        BTreeMap::from([("id".to_string(), serde_json::json!("u-42"))]),
        Some("user_company"),
    )
    .await?;                       // CypherResponse { columns, rows }
let plan = client.explain_cypher("MATCH (u:User) RETURN count(u) AS n", BTreeMap::new(), None).await?;
let rows = client
    .sql("SELECT u.name FROM User u WHERE u.age > ?", vec![serde_json::json!(30)], &helix_db::SqlMappings::default(), None)
    .await?;
```

The profiles reject `MERGE`, variable-length paths, `shortestPath`, `UNION`,
`CALL`/subqueries, list and pattern comprehensions, `FOREACH`, temporal functions; SQL
outer joins, subqueries, CTEs, window functions, upserts. Write the DSL for those, for
vector/text search and index management, and for typed batches, `var_as_if` or
`for_each_param`. Profiles:
https://docs.helix-db.com/database/helix-db/query-guides/cypher and
https://docs.helix-db.com/database/helix-db/query-guides/sql

### Query response shapes

One JSON object keyed by returned variable names: row streams are arrays (`[]` when empty,
including `n(id)`, `limit(1)`, folds, mutations and skipped `var_as_if`), `count()` an
integer, `exists()` a bool, index DDL/lifecycle a receipt or status object; an empty
returns list produces `{}`. Unprojected streams are `{"$id": N}` per element (search adds
`$distance` / `$score`). Docker images before v0.0.13 returned `null` for an empty
at-most-one return; v0.0.16 never does.

```rust
#[derive(serde::Deserialize)]
struct UserRow { id: i64, name: String }

#[derive(serde::Deserialize)]
struct FindUserResponse {
    user: Vec<UserRow>,      // [] when not found; use user.into_iter().next()
    friends: Vec<UserRow>,
    count: u64,
}
```

### Errors

Envelope `{"error": "<code>", "msg": "<diagnostic>", "retryable": true|false}`: `retryable`
is present only when the class settles it; there is no `code` field. Branch on the code and
`retryable`, never on the status alone or on `msg`.

| Class | HTTP | `retryable` | Failed write | Codes |
| --- | ---: | --- | --- | --- |
| Invalid request | 400 | absent | committed nothing | `invalid_request`, `invalid_query_json`, `invalid_request_body`, `invalid_request_option`, `invalid_node_id`, `unbound_parameter`, `active_text_mutation_limit_exceeded`, `unsupported_unique_index_value_type`, `invalid_vector_dimension`, ... |
| Planning | 400 | absent | committed nothing | `invalid_after_bind_operation`, `read_only_traversal_in_write_batch`, `duplicate_*`, `invalid_repeat_*`, `invalid_shortest_path_count`, `invalid_search_*`, ... |
| Not found | 404 | absent | committed nothing | `node_not_found`, `edge_not_found`, `index_not_found`, `index_operation_not_found` |
| Timeout | 408 | absent | **may have committed** | `query_deadline_exceeded` |
| Retryable conflict | 409 | `true` | committed nothing | `transaction_conflict`, `request_read_view_changed`, `stale_index_generation` |
| Conflict with state | 409 | `false` | committed nothing | `unique_constraint_violation`, `index_already_exists`, `index_definition_conflict`, `index_busy`, `index_operation_not_abortable`, `index_build_blocked` |
| Index backpressure | 429 | `true` | committed nothing | `index_backpressure` |
| Resource limit | 429 | absent | committed nothing | `query_memory_limit_exceeded` |
| Internal | 500 | absent | **may have committed** | `storage_error`, `internal_error`, ... |
| Unavailable | 503 | absent | committed nothing | `writer_mode_required`, `reader_mode_required`, `database_closed`, `migration_required`, ... |
| Commit outcome unknown | 503 | `false` | **may have committed** | `writer_fenced_commit_outcome_unknown` |

Beyond SKILL.md, Errors:

- `retryable: true`: rebuild a write from fresh reads if it depended on them.
- `unique_constraint_violation`: report the duplicate, or from an upsert's create branch
  re-run the upsert once (it now updates).
- `index_busy` / `index_build_blocked`: wait for, retry or abort the index operation
  (Index lifecycle) before resending.
- "May have committed": reconcile by reading back an application key.
- `query_memory_limit_exceeded`: reduce the work; unchanged it fails again.
- `writer_mode_required`: send writes with `writer_only()`.
- Helix Cloud gateway codes: `unauthorized` 401, `forbidden` 403, `query_timeout` 408,
  `payload_too_large` 413, `rate_limited` 429 with `Retry-After`, `backend_unavailable` 503,
  `write_outcome_unknown` 503 / `retryable: false`
  (https://docs.helix-db.com/database/helix-cloud/operate/error-handling).

Full code list: https://docs.helix-db.com/database/helix-db/query-guides/error-handling

`is_conflict()` means `transaction_conflict` only; `is_rate_limited()` means HTTP 429.
Known codes parse as `QueryErrorCode`; unknown codes stay available as strings. SDK errors
never expose response headers, so honor Cloud `Retry-After` through direct HTTP. Other
`HelixError` variants distinguish transport, serialization, invalid URL and invalid request
failures. Matching code: EXAMPLES.md §19.
