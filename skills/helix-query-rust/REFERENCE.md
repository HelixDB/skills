# Helix Query Authoring — Rust DSL Reference

Exhaustive builder catalog for the published `helix-db = "3.0.0"` Rust crate,
imported as `helix_db`. These names follow `HelixDB/helix-db` `main`.

Import: `use helix_db::dsl::prelude::*;`. The SDK re-exports the shared AST and
builders from
[`crates/ast`](https://github.com/HelixDB/helix-db/tree/main/crates/ast);
client and macro surfaces live under
[`sdks/rust`](https://github.com/HelixDB/helix-db/tree/main/sdks/rust).

## Typestate Cheat Sheet

```text
Empty  -- n,n_where,n_with_label[_where],inject,add_n,create_*_index_*,create_index_if_not_exists,drop_index
        └─> OnNodes
Empty  -- e,e_where,e_with_label[_where]                                └─> OnEdges
Empty  -- vector_search_nodes[_with], text_search_nodes[_with]          └─> OnNodes
Empty  -- vector_search_edges[_with], text_search_edges[_with]          └─> OnEdges
OnNodes -- out, in_, both, has, has_label, has_key, where_, dedup,
           within, without, limit, skip, range, as_, store, select,
           inject, bind, order_by[_multiple], repeat, union, choose,
           coalesce, optional, path, simple_path, fold, unfold, sack_*,
           text_search[_with]                                          ↻ OnNodes
OnNodes -- out_e, in_e, both_e                                          └─> OnEdges
OnNodes -- count, exists, id, label, values, value_map, project,
           project_bindings, project_distinct_bindings,
           group, group_count, aggregate_by                             └─> Terminal
OnNodes(WriteEnabled) -- add_e, set_property, remove_property,
           drop, drop_edge, drop_edge_labeled, drop_edge_by_id          ↻ OnNodes
OnEdges -- out_n, in_n, other_n                                         └─> OnNodes
OnEdges -- has, has_label, has_key, where_, edge_has, edge_has_label,
           dedup, within, without, limit, skip, range, as_, store,
           select, order_by[_multiple], text_search[_with]              ↻ OnEdges
OnEdges -- count, exists, id, label, edge_properties                    └─> Terminal
OnEdges(WriteEnabled) -- drop_edge_by_id                                ↻ OnEdges
```

`ReadBatch::var_as` accepts only `Traversal<_, ReadOnly>` — mixing a mutation builder into a read batch is a compile error. `WriteBatch::var_as` accepts either.

---

## Batch Entry Points

```text
pub fn read_batch() -> ReadBatch
pub fn write_batch() -> WriteBatch
pub fn g() -> Traversal<Empty>
pub fn sub() -> SubTraversal
```

### `ReadBatch` / `WriteBatch`

- `var_as<S>(name, traversal)` — store a named result, unconditional.
- `var_as_if<S>(name, condition: BatchCondition, traversal)` — conditional entry.
- `for_each_param(param: &str, body: ReadBatch | WriteBatch)` — run `body` once per object in an array param. `body.queries` are inlined inside a `BatchEntry::ForEach`.
- `returning<I, S: Into<String>>(vars)` — restrict the response to these variable names.

### `BatchCondition`

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

Prefer the `_with` variants for parameterized routes — they accept `PropertyInput::param("x")` and `Expr::param("k")`.

These source methods search the whole selected tenant partition. To rank only
IDs already present in a traversal, use traversal-scoped vector or text search
below.

---

## Traversal

Node state:

```text
traversal.out(label: Option<impl Into<String>>)   -> Traversal<OnNodes, M>
traversal.in_(label: Option<impl Into<String>>)   -> Traversal<OnNodes, M>
traversal.both(label: Option<impl Into<String>>)  -> Traversal<OnNodes, M>
traversal.out_e(label)                            -> Traversal<OnEdges, M>
traversal.in_e(label)                             -> Traversal<OnEdges, M>
traversal.both_e(label)                           -> Traversal<OnEdges, M>
```

Edge state:

```text
traversal.out_n()   -> Traversal<OnNodes, M>   // edge → target
traversal.in_n()    -> Traversal<OnNodes, M>   // edge → source
traversal.other_n() -> Traversal<OnNodes, M>   // edge → "other" endpoint
```

Traversal-scoped vector and BM25 search (node and edge states):

```text
traversal.vector_search(label, property, query_vector: Vec<f32>, k: usize,
    tenant_value: Option<PropertyValue>) -> Self
traversal.vector_search_with(label, property,
    query_vector: impl Into<PropertyInput>,
    k: impl Into<StreamBound>,
    tenant_value: Option<PropertyInput>) -> Self
traversal.text_search(label, property, query_text: impl Into<String>, k: usize,
    tenant_value: Option<PropertyValue>) -> Self
traversal.text_search_with(label, property,
    query_text: impl Into<PropertyInput>,
    k: impl Into<StreamBound>,
    tenant_value: Option<PropertyInput>) -> Self
```

Both forms enforce exact membership over the IDs in the current stream. Vector
ranking may still use approximate index structures, but cannot return an ID
outside that stream; project `$distance`. BM25 results equal exhaustive search
of the tenant partition intersected with those IDs, then top-`k` ordered by
score descending and entity ID ascending; project `$score`. BM25 statistics
remain partition-wide. Use the same tenant partition for candidate construction
and search.

Pass `None::<&str>` to skip label filtering: `.out(None::<&str>)`.

---

## Filters

```text
.has(prop, value: impl Into<PropertyValue>)   // both Nodes & Edges
.has_label(label)
.has_key(prop)
.where_(pred: Predicate)
.dedup()
.within(var_name)
.without(var_name)
.edge_has(prop, value: impl Into<PropertyInput>)   // Edges only
.edge_has_label(label)                             // Edges only
```

On edge streams, generic `.has`, `.has_label`, `.has_key`, and `.where_` filter
stored edge properties plus virtual fields `$id`, `$label`, `$from`, `$to`,
`$distance`, and `$score`. Keep `.edge_has` for edge filters whose right-hand
side must be a `PropertyInput` expression or runtime parameter.

### `Predicate`

Literal constructors:

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
```

Parameterized comparison shortcuts (wrap `Compare`):

```text
Predicate::eq_param(prop, param)  Predicate::neq_param(prop, param)
Predicate::gt_param(prop, param)  Predicate::gte_param(prop, param)
Predicate::lt_param(prop, param)  Predicate::lte_param(prop, param)
```

### `SourcePredicate`

Restricted subset for `n_where` / `e_where` (must be index-friendly):

```text
SourcePredicate::eq / neq / gt / gte / lt / lte / between / has_key / starts_with / and / or
```

Each comparison **auto-routes** by argument type. A literal keeps the plain variant (`SourcePredicate::eq("status", "active")` → `Eq("status", String("active"))`); an `Expr`/param routes to the `*Expr` variant (`SourcePredicate::eq("status", Expr::param("s"))` → `EqExpr("status", Param("s"))`). The enum carries both forms (`Eq`/`EqExpr`, `Between`/`BetweenExpr`, etc.); `.to_predicate()` maps the `*Expr` variants to `Compare`.

**Not available** at source position: `is_null`, `is_not_null`, `contains[_param]`, `ends_with`, `is_in*`, `not`, `compare`. Push those into a following `.where_(Predicate::...)`.

Property-name strings in filters can be dotted object paths, for example `Predicate::eq("metadata.externalID", "crm-42")`. Lookup is exact-first: a top-level property named `metadata.externalID` wins before walking the `metadata` object. Dotted paths are scan-only in the current runtime; secondary, text, and vector indexes remain top-level only. Arrays are opaque and do not support `tags.0` syntax.

### `CompareOp`

```text
CompareOp::{Eq, Neq, Gt, Gte, Lt, Lte}
```

---

## Expressions

`Expr`:

```text
Expr::prop(name)                    Expr::val(value: impl Into<PropertyValue>)
Expr::id()                          Expr::param(name)
Expr::timestamp()                   // server UTC epoch millis (i64)
Expr::datetime()                    // server typed DateTime
expr.add(other)    expr.sub(other)  expr.mul(other)   expr.div(other)
expr.modulo(other) expr.neg()
Expr::case(when_then: Vec<(Predicate, Expr)>, else_expr: Option<Expr>)
```

Typical uses:

- `Predicate::compare(Expr::prop("age"), CompareOp::Gte, Expr::param("minAge"))` — property-to-parameter comparison with typed coercion.
- `Expr::prop("metadata.score")` — nested object field lookup with the same exact-first dotted-path rules as filters.
- `ExprProjection::new("age_plus_one", Expr::prop("age").add(Expr::val(1i64)))` — computed column.
- `PropertyInput::from(Expr::timestamp())` inside `add_n("Foo", vec![("createdAt", Expr::timestamp())])` — server-side timestamp stamp.

---

## Stream Bounds & Limits

```text
.limit(n: impl Into<StreamBound>)
.skip(n: impl Into<StreamBound>)
.range(start: impl Into<StreamBound>, end: impl Into<StreamBound>)
```

`StreamBound` accepts `usize`, `u8`/`u16`/`u32`, `i64`/`i32` (errors into `Expr::Constant` when negative), and `Expr`. Canonical forms:

```text
.limit(25usize)                 // StreamBound::Literal
.limit(Expr::param("limit"))    // StreamBound::Expr
```

---

## Variables & Injection

```text
.as_(name)          // store current stream
.store(name)        // alias of .as_
.select(name)       // replace current stream with a stored var
.inject(name)       // inject a var into the stream (source or mid-traversal)
g().inject(name)    // Empty -> OnNodes source form
```

Cross-entry references use `NodeRef::var(name)`, `EdgeRef::var(name)`, `NodeRef::param(name)`, `EdgeRef::param(name)`.

---

## Ordering

```text
.order_by(property, order: Order)                       // Order::{Asc, Desc}
.order_by_multiple(vec![(prop1, Order::Desc), (prop2, Order::Asc)])
```

Dotted paths such as `metadata.score` are valid for fallback ordering, but current
range indexes do not accelerate nested paths.

---

## Aggregation (terminals)

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

Each arm is a `SubTraversal`, built by `sub()` + the same filter / traversal / projection methods:

```text
.union(vec![sub_a, sub_b, ...])
.choose(condition: Predicate, then_t: SubTraversal, else_t: Option<SubTraversal>)
.coalesce(vec![sub_a, sub_b, ...])   // first non-empty wins
.optional(sub_a)                     // pass through if sub_a is empty
```

`SubTraversal` includes: `out`, `in_`, `both`, `out_e`, `in_e`, `both_e`,
`out_n`, `in_n`, `other_n`, `has`, `has_label`, `has_key`, `where_`,
`dedup`, `within`, `without`, `edge_has`, `edge_has_label`, `limit`, `skip`,
`range`, `as_`, `store`, `select`, `order_by`, `order_by_multiple`, `path`,
and `simple_path`.

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

`RepeatConfig`:

- `.times(n: usize)` — fixed iterations
- `.until(Predicate)` — stop when predicate is true
- `.emit_all()`, `.emit_before()`, `.emit_after()` — emit policy
- `.emit_if(Predicate)` — emit only matching elements after each iteration (sets emit to `After`)
- `.max_depth(n)` — safety cap (default 100)

Default `emit` is `EmitBehavior::None` (only the final result is returned). Bound every repeat with `times` or `until`; don't rely on `max_depth` alone.

---

## Projections (terminals)

```text
.values(vec!["name", "email"])                              -> Traversal<Terminal, M>
.value_map(Some(vec!["$id", "name"]))                       -> Traversal<Terminal, M>
.value_map(None::<Vec<&str>>)                               -> Traversal<Terminal, M>  // all properties
.project(vec![...]: Vec<impl Into<Projection>>)             -> Traversal<Terminal, M>
.edge_properties()                                          -> Traversal<Terminal, M>  // OnEdges only
```

Projection constructors:

```text
PropertyProjection::new("name")                 // no rename; source == alias
PropertyProjection::renamed("$distance", "distance")
ExprProjection::new("age_plus_one", Expr::prop("age").add(Expr::val(1i64)))
Projection::property("source", "alias")
Projection::expr("alias", expr)
Projection::from_endpoint("resource_id", "from_id")
Projection::to_endpoint("resource_id", "to_id")
```

`PropertyProjection` and `ExprProjection` both implement `Into<Projection>`, so you can mix them freely in `.project(vec![...])`.
Filtered `values(...)`, filtered `value_map(...)`, `PropertyProjection::source`, and `Expr::prop(...)` accept dotted object paths. `value_map(None)` returns all top-level stored properties as-is and does not flatten nested objects.

On edge streams, `Projection::from_endpoint(prop, alias)` serializes to
`{"source":"$from.<prop>","alias":"<alias>"}` and
`Projection::to_endpoint(prop, alias)` serializes to
`{"source":"$to.<prop>","alias":"<alias>"}`. Use these to return source/target
node properties such as resource ids without traversing from every edge to its
endpoints. Keep `.edge_properties()` for full edge maps and the internal `$from`
/ `$to` node ids.

---

## Row bindings (multi-hop correlation)

`.project(...)` only sees the *final* stream. When you need columns captured at
**different hops** of one traversal correlated on the same path, use row
bindings: tag elements as you pass them with `.bind(name)`, then build the output
rows with `.project_bindings(...)` / `.project_distinct_bindings(...)`.

```text
.bind(name: impl Into<String>)                                  ↻ same stream; enters row mode (panics on empty name)
.project_bindings(vec![...]: Vec<BindingProjection>)            -> Traversal<Terminal, M>  // preserves duplicate rows
.project_distinct_bindings(vec![...]: Vec<BindingProjection>)   -> Traversal<Terminal, M>  // dedups identical rows
```

`.bind()` does not change the stream — each path keeps its own row-local
bindings, so later hops (including those inside `union`, `optional`, `choose`)
can still reference earlier captures. `.bind()` is available on `Traversal`
(both node and edge streams) and on `SubTraversal` inside branches.
`BindingProjection` constructors:

```text
BindingProjection::current("$id", "current_id")           // read from the current element
BindingProjection::binding("service", "$id", "service_id")// read from a named binding
BindingProjection::property(BindingTarget::binding("svc"), "name", "svc_name")
BindingProjection::coalesce(vec![                          // first present non-null wins
    BindingValueRef::binding("deployment", "$id"),
    BindingValueRef::binding("owner", "$id"),
], "workload_id")
```

`BindingTarget` is `Current` or `Binding(name)`; `BindingValueRef { target, source }`
has `BindingValueRef::current(source)` / `BindingValueRef::binding(name, source)`.
The `source` accepts stored properties and the virtual fields `$id`, `$label`,
`$from`, `$to`, `$distance`, `$score` — same set as `.project(...)`.

Worked example (a service → pod → owner/workload correlation, one row per path):

```text
g().n_with_label("Service")
    .bind("service")
    .out(Some("ROUTES_TO")).bind("pod")
    .optional(sub().in_(Some("CREATES")).bind("deployment"))
    .union(vec![
        sub().in_(Some("MANAGES")).bind("owner"),
        sub().out(Some("ROUTES_TO")).bind("workload"),
    ])
    .project_distinct_bindings(vec![
        BindingProjection::binding("service", "$id", "service_id"),
        BindingProjection::current("$id", "current_id"),
        BindingProjection::coalesce(
            vec![
                BindingValueRef::binding("deployment", "$id"),
                BindingValueRef::binding("owner", "$id"),
            ],
            "workload_id",
        ),
    ]);
```

The binding projection is part of a normal direct `QueryRequest`. See
`../helix-query-json-dynamic/REFERENCE.md` for the wire shape.

---

## Terminals (metadata)

```text
.count()    .exists()    .id()    .label()
```

Usable on both node and edge streams. `.edge_properties()` is edge-only.

---

## Mutations (write-only)

Source-position mutation (`Traversal<Empty>` → `Traversal<OnNodes, WriteEnabled>`):

```text
g().add_n(label, vec![(prop, PropertyInput::from(val)), ...])
g().drop_edge_by_id(edges: impl Into<EdgeRef>)
g().inject(var_name)  // from var (ReadOnly side), safe to use in write batches
```

Node-state mutations (`Traversal<OnNodes, _>` → `Traversal<OnNodes, WriteEnabled>`):

```text
.add_e(label, to: impl Into<NodeRef>, vec![(prop, PropertyInput::from(val)), ...])
.set_property(name, value: impl Into<PropertyInput>)
.remove_property(name)
.drop()
.drop_edge(to: impl Into<NodeRef>)
.drop_edge_labeled(to: impl Into<NodeRef>, label)
.drop_edge_by_id(edges: impl Into<EdgeRef>)
```

Edge-state mutation:

```text
.drop_edge_by_id(edges: impl Into<EdgeRef>)   // OnEdges -> OnEdges, WriteEnabled
```

Key `PropertyInput` shortcuts:

```text
PropertyInput::from("literal")              // wraps as Value(PropertyValue)
PropertyInput::from(Expr::timestamp())      // wraps Expr
PropertyInput::param("userId")              // wraps Expr::Param("userId")
PropertyInput::from(PropertyValue::object(vec![("externalID", PropertyValue::from("crm-42"))]))
```

---

## Indexes (write-only)

Generic `IndexSpec` forms:

```text
g().create_index_if_not_exists(spec: IndexSpec) -> Traversal<Terminal, WriteEnabled>
g().drop_index(spec: IndexSpec)                 -> Traversal<Terminal, WriteEnabled>
```

Convenience source forms:

```text
g().create_vector_index_nodes(label, property, dimension: NonZeroUsize, metric: VectorDistanceMetric, tenant_property)
g().create_vector_index_edges(label, property, dimension: NonZeroUsize, metric: VectorDistanceMetric, tenant_property)
g().create_text_index_nodes(label, property, tenant_property)
g().create_text_index_edges(label, property, tenant_property)
```

`IndexSpec` constructors:

```text
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

Range indexes default to ascending physical order. Use `RangeIndexDirection::Desc` for descending indexes that primarily serve newest-first or high-score-first scans.

Index properties are top-level only in the current runtime. Do not declare `metadata.externalID` as an equality, range, vector, or text index; duplicate indexed/searchable fields onto explicit top-level properties.

---

## Reserved / no-op builders

Emit the corresponding steps but have no effect in the current interpreter. Safe to include for forward-compatible queries.

```text
.fold()    .unfold()    .path()    .simple_path()
.with_sack(PropertyValue::I64(0))
.sack_set(prop)    .sack_add(prop)    .sack_get()
```

---

## `#[query]` Macro And Direct Requests

`sdks/rust/helix-dsl-macros/src/lib.rs`. Apply to a top-level function returning `ReadBatch` or `WriteBatch`; the macro generates a wrapper that constructs a `QueryRequest` with the function's arguments as typed parameters and sets top-level `query_name` to the Rust function name.

```text
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

// Generated: callable function that returns QueryRequest directly.
let req = find_user("acme".to_string(), 25);
let json = req.to_json_string()?;
```

The serialized request includes `"query_name":"find_user"`, so logs and
diagnostics can group the direct request by name.

Supported param types include primitives (`bool`, `i64`, `f64`, `f32`,
`String`, `DateTime`), `PropertyValue`, `ParamValue`, `ParamObject`,
`Vec<T>`, and string-keyed maps. Bytes cannot be represented on the JSON query
route and raise `QueryError::UnsupportedBytesParameter`.

### `QueryRequest`

```text
QueryRequest::read(batch: ReadBatch)
QueryRequest::write(batch: WriteBatch)
req.set_query_name("find_users")
req.clear_query_name()
req.with_query_name("find_users")
req.with_parameter_value(name, QueryValue::String("x".into()))
req.with_parameter_type(name, QueryParamType::DateTime)
req.to_json_string()   // Result<String, QueryError>
req.to_json_bytes()
```

Direct requests built with `QueryRequest::read/write` serialize `query_name: null` until a name is set. Missing or `null` falls back to `__dynamic__` at the gateway; blank names are rejected.

For the JSON wire encoding this produces, see `../helix-query-json-dynamic/REFERENCE.md`.

### `Client` (sending requests)

Async HTTP client for running a direct request against a Helix instance.

```text
use helix_db::{Client, HelixError, QueryErrorCode};

Client::new(url: Option<&str>) -> Result<Self, HelixError>   // default "http://localhost:6969"; InvalidURL on bad url
    .with_api_key(api_key: Option<&str>) -> Self              // Authorization: Bearer <key>
    .query::<R: Deserialize>(request) -> QueryExecutionRequest<R>

// Advanced server headers:
client.request_builder::<R>()
    .writer_only()                       // X-Helix-Require-Writer: true
    .warm_only()                         // X-Helix-Warm: true
    .should_await_durability(b: bool)    // X-Helix-Await-Durable: true|false
    .query(request)

request.send().await -> Result<R, HelixError>                // published 3.0.0: 200 -> R; every other status, including Cloud warm 204, -> RemoteError
```

### Query response shapes

Only empty declared returns use inferred shapes. At-most-one empties are JSON
`null`; collection, fold, and mutation empties are `[]`; scalar terminals keep
`0` and `false`; an empty returns list produces `{}`. Populated values retain
their existing representation, including the one-element array for an
at-most-one traversal.

Deserialize an at-most-one field as `Option<Vec<T>>` and a collection field as
`Vec<T>`:

```rust
#[derive(serde::Deserialize)]
struct FindUserResponse {
    user: Option<Vec<UserRow>>,
    friends: Vec<UserRow>,
    count: usize,
}
```

Do not use a custom decoder to turn `null` into an empty vector; that erases
the semantic distinction.

The Cloud service returns `204 No Content` after a successful warm fanout, but
the published Rust 3.0.0 client accepts only 200. Use `helix query` or direct
HTTP for Cloud warming until a newer SDK release accepts 204. Partial target
failure is still a service-level success when at least one backend warms.

Prefer `.should_await_durability(true)` on writes. Under concurrent writers, not awaiting durability raises the chance of HTTP 409 write conflicts; awaiting it reduces them (but does not eliminate them, so callers still own retry). Leaving it off is fine for low-concurrency or read paths.

`HelixError::error_code() -> Option<&str>` returns a stable code when present.
For remote failures, `status_code()`, `remote_code()`, `remote_message()`,
`remote_details()`, and `raw_response_body()` preserve the HTTP status,
open-string code, diagnostic, structured `details`, and original body.
`is_conflict()` is true for HTTP 409 and `is_rate_limited()` for HTTP 429. The
decoder supports canonical Helix `error`/`msg` (`error` is the code), legacy
Helix `error`/`code`, and defensive generic-remote
`code`/`message`/`details` bodies. The generic shape is not the Cloud gateway
contract. `EmbeddedError { code: String, details }` provides code/diagnostic
separation in embedded mode. Known Helix strings can be parsed as
`QueryErrorCode`; unknown Helix or generic remote strings remain available.

```rust
match request.send().await {
    Err(error) if error.is_conflict()
        && error.error_code() == Some(QueryErrorCode::TransactionConflict.as_str()) => {
        // Reload state before rebuilding this write. Replay only if it is safe.
    }
    Err(error) => return Err(error),
    Ok(response) => return Ok(response),
}
```

Use structured fields rather than parsing error text. Cloud `rate_limited` did not execute, but Rust 3.0.0 does not expose `Retry-After`; use an application policy or a direct transport that retains it. Reconcile a `query_timeout` write before resubmitting. For writes, reload state after a conflict and do not blindly replay a general server failure whose commit outcome may be unknown. See `../../docs/error-handling.md` for the gateway catalog, envelope migration, retry rules, and gRPC metadata. Other `HelixError` variants distinguish transport, serialization, invalid URL, and invalid request failures. Build the request from a `#[query]` function call or
`QueryRequest::read/write(batch)`. Stored routes, registration, and bundles
are not supported.

---

## Common Pitfalls

- `#[expect(dead_code)]` on a helper fails the test build if tests use it — use `#[allow(dead_code)]`.
- `ReadBatch::var_as` rejects a traversal containing any `WriteEnabled` step at compile time — if a builder call returns `Traversal<_, WriteEnabled>`, the enclosing batch must be a `WriteBatch`.
- `.out(None)` doesn't compile (ambiguous type). Use `.out(None::<&str>)` or pass `Some("LABEL")`.
- `PropertyInput::param("x")` is the idiomatic way to tie a property write to a parameter; do not construct `Expr::Param` and then wrap manually unless you need composition.
- `n_where(SourcePredicate::contains(...))` is a compile error — `SourcePredicate` does not have `contains`. Move the predicate into `.where_(Predicate::contains(...))` after the source.
- `vector_search_*` (non-`_with`) takes a concrete `Vec<f32>` + `usize`; parameterized routes need `vector_search_*_with` to accept `PropertyInput::param` / `Expr::param`.
