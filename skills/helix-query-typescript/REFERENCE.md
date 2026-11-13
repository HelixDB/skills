# Helix Query Authoring — TypeScript DSL Reference

Builder catalog for `@helix-db/helix-db`, defined under
[`sdks/typescript/src`](https://github.com/HelixDB/helix-db/tree/main/sdks/typescript/src).
**(main)** marks APIs missing from 3.2.0; SKILL.md has the fallbacks. Output is
structurally equal to the Rust SDK's JSON; encoding rules:
`../helix-query-json-dynamic/REFERENCE.md`.

## Import

```text
import { g, sub, readBatch, writeBatch, NodeRef, EdgeRef, Predicate, SourcePredicate,
         PropertyValue, PropertyInput, Expr, StreamBound, PropertyProjection, ExprProjection,
         Projection, BindingProjection, BindingTarget, RepeatConfig, IndexSpec, Order,
         EmitBehavior, AggregateFunction, CompareOp, BatchCondition, DateTime,
         RangeIndexDirection, VectorDistanceMetric, QueryRequest, defineParams, param,
         ShortestPathDirection, parseIndexDdlReceipt, parseIndexOperationStatus,
         Client, HelixError, stringifyJson, i64, f32, f64, bytes, dateTime } from "@helix-db/helix-db";
// (main): SearchConsistency
```

A `prelude` object re-exports the common DSL surface.

## Typestate Cheat Sheet

`Traversal<S extends TraversalState, M extends MutationMode>` tracks state in the
type system. `TraversalState = "empty" | "nodes" | "edges" | "terminal"` and
`MutationMode = "read" | "write"`.

```text
empty  -- n,nWhere,nWithLabel[Where],inject,addN,createIndexIfNotExists,dropIndex,
          createVectorIndexNodes/Edges,createTextIndexNodes/Edges            └─> nodes
empty  -- e,eWhere,eWithLabel[Where]                                         └─> edges
empty  -- vectorSearchNodes[With], textSearchNodes[With]                     └─> nodes
empty  -- vectorSearchEdges[With], textSearchEdges[With]                     └─> edges
empty  -- shortestPath, getIndexOperation, retryIndexOperation,
          abortIndexOperation                                                └─> terminal
nodes  -- out, in, both, has, hasLabel, hasKey, where, dedup, within, without,
          limit, skip, range, as, store, select, inject, bind, orderBy[Multiple],
          repeat, union, choose, coalesce, optional, path, simplePath,
          fold, unfold, withSack, sack*, textSearch[With]                    ↻ nodes
nodes  -- outE, inE, bothE                                                   └─> edges
nodes  -- count, exists, id, label, values, valueMap, project, projectBindings,
          projectDistinctBindings, group, groupCount, aggregateBy            └─> terminal
nodes("write") -- addE, setProperty, removeProperty, drop, dropEdge,
          dropEdgeLabeled, dropEdgeById                                      ↻ nodes
edges  -- outN, inN, otherN                                                  └─> nodes
edges  -- has, hasLabel, hasKey, where, edgeHas, edgeHasLabel, dedup, limit,
          skip, range, as, store, bind, orderBy, vectorSearch[With],
          textSearch[With]                                                   ↻ edges
edges("write") -- setProperty, removeProperty, drop                         ↻ edges
edges  -- count, exists, id, label, values, valueMap, project,
          projectBindings, edgeProperties                                    └─> terminal
```

`ReadBatch.varAs` accepts only a read traversal; `WriteBatch.varAs` accepts either. The
types also allow `within`, `without`, `select`, `orderByMultiple` and `dropEdgeById` on an
edge stream, but Rust does not: keep edge streams to the list above for parity.

---

## Entry Points

```text
g(): Traversal<"empty", "read">
sub(): SubTraversal
readBatch(): ReadBatch
writeBatch(): WriteBatch
```

### `ReadBatch` / `WriteBatch`

```text
.varAs(name: string, traversal): ReadBatch | WriteBatch         // store named result
.varAsIf(name: string, condition: BatchCondition, traversal)    // conditional entry
.forEachParam(paramName: string, body): ReadBatch | WriteBatch  // run body per object in array param
.returning(vars: Iterable<string>)                              // restrict response variables
.toJsonString(): string                                         // raw batch JSON (inline query body)
.toJsonBytes(): Uint8Array
.toQueryJson(options?: QueryOptions): string           // no-param dynamic request JSON
.toQueryJson(params: DefinedParams<T>, values: ParamInputs<T>, options?: QueryOptions): string
.toQueryRequest(..., options?: QueryOptions): QueryRequest
.toQueryBytes(..., options?: QueryOptions): Uint8Array
```

### `BatchCondition`

```text
BatchCondition.varNotEmpty(name)   // {"var_not_empty": name}
BatchCondition.varEmpty(name)      // {"var_empty": name}
BatchCondition.varMinSize(name, n) // {"var_min_size": [name, n]}
BatchCondition.prevNotEmpty()      // "prev_not_empty"
```

`varAs` / `forEachParam` build `NamedQuery` and `BatchEntry` for you.

---

## Scalar Constructors & Values

Literal helpers disambiguate numeric width:

```text
i64(value: number | bigint)   f32(value: number)   f64(value: number)
bytes(value: Uint8Array | number[])   dateTime(value: DateTime)
```

### `PropertyValue` — tagged on the wire

```text
PropertyValue.null()              // "null"
PropertyValue.bool(b)             // {"bool": b}
PropertyValue.i64(n)              // {"i64": n}      (number | bigint)
PropertyValue.f64(n)  PropertyValue.f32(n)
PropertyValue.string(s)           // {"string": s}
PropertyValue.bytes(u8)           // {"bytes": [...]}
PropertyValue.dateTime(dt | ms)   PropertyValue.datetimeMillis(ms)
PropertyValue.i64Array(xs)  PropertyValue.f64Array(xs)  PropertyValue.f32Array(xs)  PropertyValue.stringArray(xs)
PropertyValue.array(xs)  PropertyValue.object(record)
PropertyValue.from(input)         // smart conversion from PropertyValueInput
// accessors: asStr, asI64, asDatetimeMillis, asF64, asBool, asArray, asObject
```

`PropertyValueInput` (accepted wherever a literal is): `null | boolean | number | bigint |
string | Uint8Array | DateTime | PropertyValue | arrays | { object: ... }`. Homogeneous
primitive arrays may use tagged `i64_array`, `f64_array` or `string_array`; mixed or nested
arrays use `PropertyValue.array(...)`.

### `PropertyInput` — value-or-expression

Used for write property values and `edgeHas` / search args:

```text
PropertyInput.value(v: PropertyValueInput)  // {"value": <PropertyValue>}
PropertyInput.expr(e: Expr)                 // {"expr": <Expr>}
PropertyInput.param(name: string)           // {"expr": {"param": name}}
PropertyInput.from(input)                   // smart constructor
```

### `DateTime`

```text
DateTime.fromMillis(ms: number | bigint)   DateTime.parseRfc3339(s: string)
.millis(): bigint   .toRfc3339(): string   // UTC, millisecond precision; negative epochs supported
```

---

## References: Nodes & Edges

`NodeRef` / `EdgeRef`:

```text
NodeRef.all()              // "all"          (nodes only)
NodeRef.id(id)             // {"ids": [id]}
NodeRef.ids(iterable)      // {"ids": [...]}
NodeRef.var(name)          // {"var": name}
NodeRef.param(name)        // {"param": name}
NodeRef.from(value)        // accepts NodeRef | id | id[] | "var-name"
// EdgeRef: id, ids, var, param, from (no `all`)
```

`g().n(...)` accepts `NodeRef | NodeId | NodeId[] | string`; `g().e(...)` accepts `EdgeRef | EdgeId | EdgeId[]`. `NodeId`/`EdgeId` are `number | bigint`.

---

## Sources (`Traversal<"empty">` → `Traversal<"nodes"|"edges">`)

```text
g().n(nodes)                                  -> Traversal<"nodes">
g().nWhere(pred: SourcePredicate)             -> Traversal<"nodes">
g().nWithLabel(label)                         -> Traversal<"nodes">     // = nWhere(SourcePredicate.eq("$label", label))
g().nWithLabelWhere(label, pred)              -> Traversal<"nodes">     // = nWhere(and([eq($label,label), pred]))
g().e(edges)                                  -> Traversal<"edges">
g().eWhere(pred)  g().eWithLabel(label)  g().eWithLabelWhere(label, pred)

// Whole-partition vector & text search sources (high-level: concrete vector + numeric k)
g().vectorSearchNodes(label, property, queryVector: number[], k: number, tenantValue?: PropertyValueInput | null)
g().textSearchNodes(label, property, queryText: string, k: number, tenantValue?: PropertyValueInput | null)
g().vectorSearchEdges(...)   g().textSearchEdges(...)

// `*With` variants (parameterized): accept PropertyInput | Expr | ParamRef | PropertyValueInput,
// k accepts StreamBound | Expr | ParamRef | number | bigint, tenantValue accepts the same (or null)
g().vectorSearchNodesWith(label, property, queryVector, k, tenantValue?)
g().textSearchNodesWith(label, property, queryText, k, tenantValue?)
g().vectorSearchEdgesWith(...)   g().textSearchEdgesWith(...)
```

Prefer `*With` for parameterized routes; `vectorSearchNodes` wraps `queryVector` as
`PropertyValue.f32Array` and `k` as `StreamBound.literal`. Sources search the whole
selected tenant partition; to rank only IDs already in a traversal, use traversal-scoped
search.

---

## Traversal

Node-stream navigation:

```text
.out(label?: string)   .in(label?: string)   .both(label?: string)   -> Traversal<"nodes", M>
.outE(label?: string)  .inE(label?: string)  .bothE(label?: string)  -> Traversal<"edges", M>
```

Edge-stream navigation:

```text
.outN()    -> Traversal<"nodes", M>   // edge → target
.inN()     -> Traversal<"nodes", M>   // edge → source
.otherN()  -> Traversal<"nodes", M>   // edge → "other" endpoint
```

Traversal-scoped vector and BM25 search on node or edge streams:

```text
.vectorSearch(label, property, queryVector: number[], k: number,
    tenantValue?: PropertyValueInput | null)
.vectorSearchWith(label, property,
    queryVector: PropertyInput | Expr | ParamRef | PropertyValueInput,
    k: StreamBound | Expr | ParamRef | number | bigint,
    tenantValue?: PropertyInput | Expr | ParamRef | PropertyValueInput | null)
.textSearch(label, property, queryText: string, k: number,
    tenantValue?: PropertyValueInput | null)
.textSearchWith(label, property,
    queryText: PropertyInput | Expr | ParamRef | PropertyValueInput,
    k: StreamBound | Expr | ParamRef | number | bigint,
    tenantValue?: PropertyInput | Expr | ParamRef | PropertyValueInput | null)
```

Traversal-scoped search enforces exact membership over the IDs in the current stream.
Vector ranking may use approximate index structures but never returns an ID outside the
stream; project `$distance`. BM25 equals exhaustive search of the tenant partition
intersected with those IDs, top-`k` by score descending then entity ID ascending, with
partition-wide statistics; project `$score`. Use the same tenant partition for candidates
and search. Limits: SKILL.md, Search.

An omitted label (`out()`) is omitted from the wire `out` node.

---

## Filters

```text
.has(prop, value: PropertyValueInput)    // both node & edge streams
.hasLabel(label)
.hasKey(prop)
.where(pred: Predicate)
.dedup()
.within(varName)    .without(varName)
.edgeHas(prop, value: PropertyInput | PropertyValueInput)   // edge streams
.edgeHasLabel(label)                                        // edge streams
```

On edge streams, `.has`, `.hasLabel`, `.hasKey` and `.where` filter stored edge properties
plus virtual fields `$id`, `$label`, `$from`, `$to`, `$distance`, `$score`. Use `.edgeHas`
when the right-hand side is a `PropertyInput` expression or runtime parameter.

### `Predicate`

Literal constructors:

```text
Predicate.eq(prop, val)    Predicate.neq(prop, val)
Predicate.gt(prop, val)    Predicate.gte(prop, val)    Predicate.lt(prop, val)    Predicate.lte(prop, val)
Predicate.between(prop, min, max)
Predicate.hasKey(prop)     Predicate.isNull(prop)      Predicate.isNotNull(prop)
Predicate.startsWith(prop, s)   Predicate.endsWith(prop, s)   Predicate.contains(prop, s)   Predicate.containsParam(prop, paramName)
Predicate.isIn(prop, values)    Predicate.isInExpr(prop, expr | paramRef)   Predicate.isInParam(prop, paramName)
Predicate.and(preds)   Predicate.or(preds)   Predicate.not(pred)
Predicate.compare(left: Expr, op: CompareOp, right: Expr)
```

Parameterized comparison shortcuts:

```text
Predicate.eqParam(prop, paramName)   Predicate.neqParam(...)
Predicate.gtParam(...)   Predicate.gteParam(...)   Predicate.ltParam(...)   Predicate.lteParam(...)
```

### `SourcePredicate` — used in `nWhere` / `eWhere`

`SourcePredicate` is an alias of `Predicate`
(`SourcePredicate.eq / neq / gt / gte / lt / lte / between / isIn / hasKey / startsWith /
and / or`). Index-friendly shapes are equality and range comparisons on top-level
properties, combined with `and`, scoped with `nWithLabelWhere` (an unlabeled `nWhere`
cannot use a label-scoped index). Put other filters in `.where(Predicate....)` after the
source. Predicates serialize as expression trees, e.g.
`{"eq":{"left":{"property":"u"},"right":{"constant":{"string":"alice"}}}}`.

### Nested properties (dotted paths)

Dotted object paths such as `Predicate.eq("metadata.externalID", "crm-42")` work in
predicates, `Expr.prop`, filtered `values` / `valueMap`, `PropertyProjection.source` and
`orderBy`. Lookup is exact-first: a top-level property named `metadata.externalID` wins
before walking the `metadata` object. Dotted paths are scan-only: secondary, range, text
and vector indexes cover top-level properties only, so duplicate indexed or searchable
fields onto explicit top-level properties. Arrays are opaque (no `tags.0`).
`valueMap(null)` returns top-level properties as stored, without flattening.

### `CompareOp`

```text
CompareOp.Eq | Neq | Gt | Gte | Lt | Lte
```

---

## Expressions

`Expr`:

```text
Expr.prop(name)    Expr.val(value: PropertyValueInput)
Expr.id()          Expr.param(name)
Expr.timestamp()   // server UTC epoch millis
Expr.datetime()    // server typed DateTime
expr.add(other)  expr.sub(other)  expr.mul(other)  expr.div(other)  expr.modulo(other)  expr.neg()
Expr.case(whenThen: [Predicate, Expr][], elseExpr?: Expr | null)
```

`ParamRef` has `.toExpr()` so a `param` reference can be used where an `Expr`
is expected.

- `Predicate.compare(Expr.prop("age"), CompareOp.Gte, Expr.param("minAge"))` — property-to-parameter comparison.
- `ExprProjection.new("age2", Expr.prop("age").add(Expr.val(1)))` — computed column.
- `g().addN("Foo", { createdAt: PropertyInput.expr(Expr.timestamp()) })` — server-side timestamp.

---

## Stream Bounds & Limits

```text
.limit(n)   .skip(n)   .range(start, end)
```

Each accepts `number`, `bigint`, `Expr`, `ParamRef`, or `StreamBound`:

```text
StreamBound.literal(n)        // {"literal": n}
StreamBound.expr(e)           // {"expr": <Expr>}
StreamBound.from(value)       // negative numbers become an expression bound
```

---

## Variables & Injection

```text
.as(name)       // store current stream
.store(name)    // alias of .as
.select(name)   // replace current stream with a stored var
.inject(name)   // inject a var into the stream (source or mid-traversal)
g().inject(name)  // "empty" -> "nodes" source form
```

Cross-entry references: `NodeRef.var(name)`, `EdgeRef.var(name)`, `NodeRef.param(name)`, `EdgeRef.param(name)`.

---

## Ordering

```text
.orderBy(property, order: Order)                                  // Order.Asc | Order.Desc
.orderByMultiple([[prop1, Order.Desc], [prop2, Order.Asc]])
```

Missing values sort first for `Asc`, last for `Desc`; `.where(Predicate.isNotNull(prop))`
before ordering drops them. Range indexes do not accelerate nested paths.

---

## Aggregation (terminals)

```text
.count()   .exists()   .group(property)   .groupCount(property)
.aggregateBy(fn: AggregateFunction, property)
// AggregateFunction.{Count, Sum, Min, Max, Mean}
```

---

## Branching

Each arm is a `SubTraversal` from `sub()`:

```text
.union([subA, subB, ...])
.choose(condition: Predicate, thenTraversal: SubTraversal, elseTraversal?: SubTraversal | null)
.coalesce([subA, subB, ...])   // first non-empty wins
.optional(subA)                // subA's rows, or the input row itself when subA is empty
```

- `choose` without `elseTraversal` **drops** rows that fail the condition (per-row value:
  `Expr.case(...)`).
- `.optional(sub().out("WORKS_AT")).values(["name"])` returns the *user's* name for users
  without an employer; for OPTIONAL MATCH see
  [Row bindings](#row-bindings-multi-hop-correlation).

`SubTraversal` supports: `out`, `in`, `both`, `outE`, `inE`, `bothE`, `outN`, `inN`, `otherN`, `has`, `hasLabel`, `hasKey`, `where`, `dedup`, `within`, `without`, `edgeHas`, `edgeHasLabel`, `limit`, `skip`, `range`, `as`, `store`, `select`, `bind`, `orderBy`, `orderByMultiple`, `path`, `simplePath`.

---

## Repeat

```text
.repeat(RepeatConfig.new(sub().out("KNOWS")).times(3))
.repeat(
  RepeatConfig.new(sub().out("REPORTS_TO"))
    .until(Predicate.eq("title", "CEO"))
    .emitAfter()
    .maxDepth(10),
)
```

`RepeatConfig`:

- `.times(n)` — fixed iterations
- `.until(pred)` — stop when predicate is true
- `.emitAll()` / `.emitBefore()` / `.emitAfter()` — emit policy
- `.emitIf(pred)` — emit only matching elements (sets emit to `After`)
- `.maxDepth(n)` — safety cap (default 100)

Default `emit` is `EmitBehavior.None` (only the final iteration's rows). `emitAfter`
emits each iteration's output (Gremlin postfix `.emit()`); `emitBefore` each iteration's
input, starting with the seed; `emitAll` both, so a depth-1 row is emitted twice.

---

## Projections (terminals)

```text
.values(["name", "email"])                  -> Traversal<"terminal", M>
.valueMap(["$id", "name"])                  -> Traversal<"terminal", M>
.valueMap(null)                             -> all properties
.project([...])                             -> Traversal<"terminal", M>
.edgeProperties()                           -> Traversal<"terminal", M>   // edge streams only
```

Projection constructors:

```text
PropertyProjection.new("name")                       // {source:"name", alias:"name"}
PropertyProjection.renamed("$distance", "distance")  // {source:"$distance", alias:"distance"}
ExprProjection.new("age2", Expr.prop("age").add(Expr.val(1)))   // {alias:"age2", expr:{...}}
Projection.property("source", "alias")
Projection.expr("alias", expr)
Projection.fromEndpoint("resource_id", "from_id")
Projection.toEndpoint("resource_id", "to_id")
Projection.from(value)
```

Mix `PropertyProjection` and `ExprProjection` in `.project([...])`. On edge streams,
`Projection.fromEndpoint(prop, alias)` serializes to
`{"source":"$from.<prop>","alias":"<alias>"}` and `Projection.toEndpoint(prop, alias)` to
`{"source":"$to.<prop>","alias":"<alias>"}`: endpoint node properties without traversing to
each endpoint. Keep `.edgeProperties()` for full edge maps and the internal `$from` / `$to`
node ids.

---

## Row bindings (multi-hop correlation)

`.project(...)` only sees the final stream. To combine values from **different hops** of
one path, tag elements with `.bind(name)`, then build rows with `.projectBindings(...)` /
`.projectDistinctBindings(...)`.

```text
.bind(name: string)                                ↻ same stream; enters row mode (throws on empty name)
.projectBindings(projs: BindingProjection[])       -> Traversal<"terminal", M>  // preserves duplicate rows
.projectDistinctBindings(projs: BindingProjection[])-> Traversal<"terminal", M> // dedups identical rows
```

`.bind()` does not change the stream; each path keeps row-local bindings, so hops inside
`union` / `optional` / `coalesce` can reference earlier captures. It works on node and edge
`Traversal`s and on `SubTraversal`. After a `bind`, `orderBy`, `choose`, `repeat`,
`values`, `valueMap`, `project`, `id`, `label` and `edgeProperties` are rejected
(`invalid_after_bind_operation`); finish with `projectBindings`, `projectDistinctBindings`,
`count` or `exists`. A binding never set on a row (empty
`optional` branch) leaves its alias out of that row's object.

`BindingProjection` constructors:

```text
BindingProjection.current("$id", "current_id")              // read from current element
BindingProjection.binding("service", "$id", "service_id")   // read from a named binding
BindingProjection.property(BindingTarget.binding("svc"), "name", "svc_name")
BindingProjection.coalesce([                                // first present non-null wins
  BindingProjection.bindingRef("deployment", "$id"),
  BindingProjection.bindingRef("owner", "$id"),
], "workload_id")
```

`BindingTarget` is `"current"` or `{ binding: name }`
(`BindingTarget.current()` / `BindingTarget.binding(name)`);
`BindingValueRef = { target, source }` via
`BindingProjection.currentRef(source)` / `.bindingRef(name, source)`.
`source` accepts stored properties and the virtual fields `$id`, `$label`,
`$from`, `$to`, `$distance`, `$score`.

Worked example (one row per path):

```text
g().nWithLabel("Service")
  .bind("service")
  .out("ROUTES_TO").bind("pod")
  .optional(sub().in("CREATES").bind("deployment"))
  .union([
    sub().in("MANAGES").bind("owner"),
    sub().out("ROUTES_TO").bind("workload"),
  ])
  .projectDistinctBindings([
    BindingProjection.binding("service", "$id", "service_id"),
    BindingProjection.current("$id", "current_id"),
    BindingProjection.coalesce([
      BindingProjection.bindingRef("deployment", "$id"),
      BindingProjection.bindingRef("owner", "$id"),
    ], "workload_id"),
  ]);
```

OPTIONAL MATCH (`MATCH (u:User) OPTIONAL MATCH (u)-[:WORKS_AT]->(c:Company)
RETURN u.name, c.name AS employer`):

```ts
g().nWithLabel("User")
  .bind("user")
  .optional(sub().out("WORKS_AT").hasLabel("Company").bind("employer"))
  .projectBindings([
    BindingProjection.binding("user", "name", "name"),
    BindingProjection.binding("employer", "name", "employer"), // key absent when no employer
  ]);
```

Without the bindings, `employer` would silently become the user's own name. Keep
`hasLabel` when the pattern names one (`out` ignores the target label). Wire shape:
`../helix-query-json-dynamic/REFERENCE.md`.

---

## Terminals (metadata)

`.count()`, `.exists()`, `.id()`, `.label()` work on node and edge streams;
`.edgeProperties()` is edge-only.

---

## Mutations (write-only)

Source-position mutation (`Traversal<"empty">` → `Traversal<"nodes", "write">`):

```text
g().addN(label, properties)            // properties: Record<string, PropertyInput|PropertyValueInput|ParamRef> OR [string, ...][]
g().dropEdgeById(edges)
g().inject(varName)
```

Node-state mutations (→ `Traversal<"nodes", "write">`):

```text
.addE(label, to: NodeRef | NodeId | ..., properties)
.setProperty(name, value: PropertyInput | PropertyValueInput)
.removeProperty(name)
.drop()
.dropEdge(to)              .dropEdgeLabeled(to, label)        .dropEdgeById(edges)
```

`addN` / `addE` properties are an object (`{ name: "Alice" }`) or tuples
(`[["name", "Bob"]]`) of raw literals, nested objects/arrays, `PropertyInput.param(...)` or a
`ParamRef`. On the wire: `["name", {"value": {"string": "Alice"}}]`.

---

## Indexes (write-only)

```text
g().createIndexIfNotExists(spec: IndexSpec)   -> Traversal<"terminal", "write">
g().dropIndex(spec: IndexSpec)                -> Traversal<"terminal", "write">

// convenience source forms (tenantProperty optional)
g().createVectorIndexNodes(label, property, dimension, metric, tenantProperty?)
g().createVectorIndexEdges(label, property, dimension, metric, tenantProperty?)
g().createTextIndexNodes(label, property, tenantProperty?)
g().createTextIndexEdges(label, property, tenantProperty?)
```

`IndexSpec` constructors:

```text
IndexSpec.nodeEquality(label, property)         // unique = false
IndexSpec.nodeUniqueEquality(label, property)   // unique = true
IndexSpec.nodeRange(label, property)
IndexSpec.nodeRangeDesc(label, property)
IndexSpec.nodeRangeWithDirection(label, property, RangeIndexDirection.Desc)
IndexSpec.edgeEquality(label, property)
IndexSpec.edgeRange(label, property)
IndexSpec.edgeRangeDesc(label, property)
IndexSpec.edgeRangeWithDirection(label, property, RangeIndexDirection.Desc)
IndexSpec.nodeVector(label, property, dimension, metric, tenantProperty?)
IndexSpec.nodeText(label, property, tenantProperty?)
IndexSpec.edgeVector(label, property, dimension, metric, tenantProperty?)
IndexSpec.edgeText(label, property, tenantProperty?)
```

Range indexes default to ascending; use `RangeIndexDirection.Desc` for newest-first or
high-score-first scans. `createVectorIndexNodes(...)` serializes to the same `create_index`
operation as `createIndexIfNotExists(IndexSpec.nodeVector(...))`.

A unique equality index (`IndexSpec.nodeUniqueEquality`) rejects a duplicate write with
`unique_constraint_violation` (409, `retryable: false`). While the build runs it rejects
only a value already claimed, by an entity the build has scanned or by a write since the
build started; a duplicate of a value held only by a not-yet-scanned entity is written, and
the build blocks (`uniqueness_violation`) when its scan reaches that entity.

### Index lifecycle

Each `createIndexIfNotExists` / `dropIndex` entry returns one receipt object (not an
array):

```text
{ kind: "accepted", operation_id, index_id, generation }   // new build/drop queued
{ kind: "existing_operation", operation_id }                // same request already in flight
{ kind: "already_active", index_id, generation }            // identical index is active; nothing to wait for
```

```text
g().getIndexOperation(operationId)     -> Traversal<"terminal", M>        // read batch
g().retryIndexOperation(operationId)   -> Traversal<"terminal", "write">  // after fixing a blocker
g().abortIndexOperation(operationId)   -> Traversal<"terminal", "write">  // discard a constructing build
parseIndexDdlReceipt(value): IndexDdlReceipt
parseIndexOperationStatus(value): IndexOperationStatus
```

`IndexOperationStatus.status` is `queued`, `running`, `blocked`, `succeeded` or `aborted`,
with `operation_kind`, `family`, `stage`, `attempt` and `progress`. `blocked` adds
`blocker_code` (`invalid_source_data`, `uniqueness_violation`, `oversized_entity`,
`manifest_limit`, `object_store_configuration_unavailable`, `invariant_violation`) and an
optional `message`. Lifecycle errors: `index_busy` (another lifecycle change is in
progress), `index_build_blocked` (a write would overflow a blocked build's queue; fix the
blocker and retry or abort the build first), `index_operation_not_abortable`,
`index_operation_not_found`. A request with several index operations commits each as it
runs, so read state before resending a partly failed batch.

---

## Fold, path and sack steps

These execute; they are not no-ops.

```text
.fold()              // collect the stream into one folded value ([] when empty)
.unfold()            // expand a folded value back into a stream
.path()              // keep each row's traversal path in the output
.simplePath()        // drop rows whose path revisits an element
.withSack(initial)   // set a per-row sack value
.sackSet(prop)       // sack = the row's property (cleared when missing)
.sackAdd(prop)       // sack += numeric property (non-numeric or overflow fails)
.sackGet()           // expose the sack in the output
```

After `path()` or `sackGet()` (or with unprojected bindings) rows return as
`{ "bindings": {...}, "current": <element>, "path"?: [...], "sack"?: value }`.

---

## Parameters

`param` schema constructors:

```text
param.bool()  param.i64()  param.f64()  param.f32()  param.string()
param.dateTime()  param.bytes()  param.value()
param.object()  param.object(inner)  param.array(inner)
```

`defineParams(schema)` returns a `DefinedParams<T>`: typed `ParamRef`s (`p.limit`,
`p.tenantId`) plus hidden metadata, passed as a builder's default argument
(`function f(p = params) { ... }`). A `ParamRef` works where a `StreamBound` / `Expr` /
property value is expected; `.toExpr()` converts it explicitly. `QueryParamType` is the wire
type: scalars are lowercase strings (`"string"`, `"i64"`, `"date_time"`, …), arrays and
objects their structured `snake_case` form.

---

## Direct Requests

```text
type QueryOptions = { queryName?: string | null; searchConsistency?: SearchConsistency } // searchConsistency: (main)

QueryRequest.read(batch: ReadBatch, queryName?: string | null)
QueryRequest.write(batch: WriteBatch, queryName?: string | null)
req.insertUntypedParameter(name, value: JsonValue)                 req.withUntypedParameter(name, value)
req.insertTypedParameter(name, type: QueryParamType, value)        req.withTypedParameter(name, type, value)
req.setQueryName(name)                   req.clearQueryName()
req.withQueryName(name)
req.withSearchConsistency(SearchConsistency.Eventual)  // (main); throws on a write request
req.toJsonString()   req.toJsonBytes()
// req.requestType -> "read" | "write" (lowercase on the wire)
// req.queryName -> string | null         (serialized as top-level query_name)
```

A request is all untyped or all typed: mixing `insertUntypedParameter` and
`insertTypedParameter`, or a duplicate name, throws `TypeError`. `batch.toQueryJson(...)` /
`.toQueryRequest(...)` fill `parameters` and `parameter_types` for you. `QueryValue` is an
untagged JSON value in `parameters`, unlike the tagged `PropertyValue` inside the AST. Wire
encoding (externally tagged enums, untagged `Projection` / `BatchQuery` / `QueryValue`,
`parameter_types`, `DateTime` coercion): `../helix-query-json-dynamic/REFERENCE.md`.

---

## Client (sending requests)

Uses the global `fetch` (no extra dependencies); a strict port of the Rust
`helix_db::Client`.

```text
new Client(url?: string | null)           // defaults to http://localhost:6969
Client.server(url?: string | null)
  .withApiKey(key?: string | null)        // Authorization: Bearer <key> (null/undefined clears it)
  .withDatabaseId(id?: string | null)     // x-helix-database-id: <id> on every request (null/undefined clears it)
  .query<R = unknown>(request)             // direct POST /v2/query

// (main): native Cypher and SQL (POST /v2/cypher, /v2/sql and their /explain routes)
client.cypher(query, parameters = {}, queryName?): Promise<{ columns: string[]; rows: unknown[][] }>
client.explainCypher(query, parameters = {}, queryName?)
client.sql(query, parameters: unknown[] | Record<string, unknown> = [], mappings: SqlMappings = {}, queryName?)
client.explainSql(query, parameters = [], mappings = {}, queryName?)

// Advanced server-only request headers:
client.requestBuilder<R>()
  .writerOnly()                            // X-Helix-Require-Writer: true
  .warmOnly()                              // X-Helix-Warm: true (reads only)
  .shouldAwaitDurability(b: boolean)       // X-Helix-Await-Durable: true|false (writes only)
  .query(request)                          // (main): .cypher(...) / .sql(...) take the same options

await request.send(): Promise<R>           // 200 -> parsed JSON; Cloud warm 204 -> undefined; any other status -> HelixError
```

Cypher and SQL failures return
`{ "error": "<category>", "msg", "details": { "detail", "phase", "span" } }`. A Cloud warm
fanout is a success when at least one backend warms, even if others fail. Embedded clients
ignore `withDatabaseId`.

```text
const client = new Client(process.env.HELIX_URL)
  .withApiKey(process.env.HELIX_API_KEY)
  .withDatabaseId(process.env.HELIX_DATABASE_ID);
```

The response is keyed by returned variable name (rules: SKILL.md, Empty returns); `count`
is a `number`, `exists` a `boolean`, index DDL / lifecycle one object, an empty returns
list `{}`; search hits add `$distance` or `$score`. Type the whole response:

```ts
type FindUserResponse = {
  user: UserRow[];      // at most one row; read user[0]
  friends: UserRow[];
  count: number;
};

const request = findUser().toQueryRequest(params, values); // returns user, friends, count
const response = await client.query<FindUserResponse>(request).send();
const user = response.user[0]; // undefined when not found
```

---

## Errors

- `HelixError` (from `Client` / `send()`): `kind` is network, remote, serialization, URL,
  invalid-request, embedded-unavailable or embedded. Remote errors expose `statusCode`,
  open-string `code` (the body's `error`), `serverMessage` (`msg`), `retryable`,
  structured `serverDetails`, `rawBody`, and `details` (diagnostic compatibility field).
  `isRetryable()` is the retry test; `isConflict()` is not (SKILL.md table);
  `isRateLimited()` is any 429; `isIndexBackpressure()` (main) is
  `code === "index_backpressure"`. Preserve unknown codes; never parse `msg`.
- `QueryError`: invalid or unknown parameters, serialization, unsupported bytes parameters.

### Error classes

Envelope `{ "error": "<code>", "msg": "<diagnostic>", "retryable"?: boolean }`; `retryable`
is present only when the class settles it. Each code's class sets the status:

| Class | HTTP | `retryable` | A failed write | Codes |
| --- | ---: | --- | --- | --- |
| Invalid request | 400 | absent | committed nothing | `invalid_request`, `invalid_query_json`, `invalid_request_body`, `invalid_request_option`, `unbound_parameter`, `invalid_node_id`, `active_text_mutation_limit_exceeded`, `invalid_vector_dimension`, `unsupported_unique_index_value_type`, other `invalid_*` value codes |
| Planning | 400 | absent | committed nothing | `invalid_after_bind_operation`, `read_only_traversal_in_write_batch`, `duplicate_*`, `invalid_search_*`, `invalid_repeat_*`, `invalid_shortest_path_count`, `unbound_context`, other planner codes |
| Not found | 404 | absent | committed nothing | `node_not_found`, `edge_not_found`, `index_not_found`, `index_operation_not_found` |
| Timeout | 408 | absent | **may have committed** | `query_deadline_exceeded` |
| Retryable conflict | 409 | `true` | committed nothing | `transaction_conflict`, `request_read_view_changed`, `stale_index_generation` |
| Conflict with state | 409 | `false` | committed nothing | `unique_constraint_violation`, `index_already_exists`, `index_definition_conflict`, `index_busy`, `index_operation_not_abortable`, `index_build_blocked` |
| Index backpressure | 429 | `true` | committed nothing | `index_backpressure` |
| Resource limit | 429 | absent | committed nothing | `query_memory_limit_exceeded` |
| Internal | 500 | absent | **may have committed** | `storage_error`, `internal_error`, `invalid_query`, `response_serialization_error`, `*_exhausted`, other internal codes |
| Unavailable | 503 | absent | committed nothing | `writer_mode_required`, `reader_mode_required`, `database_closed`, `index_lifecycle_unavailable`, `migration_required`, `writer_migration_required`, `query_cancelled_by_reader_retirement` |
| Commit outcome unknown | 503 | `false` | **may have committed** | `writer_fenced_commit_outcome_unknown` |

Beyond SKILL.md, Errors:

- A retried write that depends on what it read is rebuilt from fresh state.
- `unique_constraint_violation`: report the duplicate or choose another key; from an
  upsert's create branch, re-run the upsert once (it then updates).
- `index_busy`: wait for the running operation (`getIndexOperation`).
  `index_build_blocked`: fix the build's `blocker_code`, then `retryIndexOperation` or
  `abortIndexOperation`, before resending the write.
- `query_memory_limit_exceeded`: reduce the work; unchanged it fails again.
- `invalid_request_body`: body over 16 MiB (Helix Cloud: over 2 MiB is
  `413 payload_too_large`). `invalid_query_json`: malformed JSON, unknown fields, or
  nesting deeper than 255 levels.

Helix Cloud gateway codes: `tenant_id_required` / `tenant_id_not_allowed` (400),
`unauthorized` (401), `tenant_disabled` (402), `forbidden` (403), `query_timeout` (408,
reconcile writes), `payload_too_large` (413), `rate_limited` (429, honor `Retry-After`),
`backend_unavailable` / `rate_limit_unavailable` (503, back off), `failover_wait_unavailable`
(503, not sent; retry after `Retry-After`), `write_outcome_unknown` (503, reconcile).
References: https://docs.helix-db.com/database/helix-db/query-guides/error-handling and
https://docs.helix-db.com/database/helix-cloud/operate/error-handling.

---

## Enums

```text
CompareOp.{Eq, Neq, Gt, Gte, Lt, Lte}
Order.{Asc, Desc}                              // lowercase strings on the wire
EmitBehavior.{None, Before, After, All}
AggregateFunction.{Count, Sum, Min, Max, Mean}
QueryRequestType.{Read, Write}                 // lowercase on the wire
```

---

## JSON Utilities

Bigint-safe: `stringifyJson(value, pretty?)`, `parseJsonStructural(json)`,
`structuralJsonEqual(a, b)`, `canonicalizeJson(value)`.

---

## Rust ↔ TypeScript Naming Map

| Rust | TypeScript |
|---|---|
| `read_batch()` / `write_batch()` | `readBatch()` / `writeBatch()` |
| `var_as(...)` / `var_as_if(...)` | `varAs(...)` / `varAsIf(...)` |
| `for_each_param(...)` | `forEachParam(...)` |
| `bind(...)` | `bind(...)` |
| `project_bindings(...)` / `project_distinct_bindings(...)` | `projectBindings(...)` / `projectDistinctBindings(...)` |
| `BindingProjection::binding(...)` / `::coalesce(...)` | `BindingProjection.binding(...)` / `.coalesce(...)` |
| `BindingValueRef::binding(...)` | `BindingProjection.bindingRef(...)` |
| `n_with_label[_where]` | `nWithLabel[Where]` |
| `in_` | `in` |
| `where_(...)` | `where(...)` |
| `value_map(...)` | `valueMap(...)` |
| `order_by[_multiple]` | `orderBy[Multiple]` |
| `NodeRef::var(...)` | `NodeRef.var(...)` |
| `SourcePredicate::eq(...)` | `SourcePredicate.eq(...)` |
| `Predicate::eq_param(...)` | `Predicate.eqParam(...)` |
| `vector_search_nodes_with(...)` | `vectorSearchNodesWith(...)` |
| `shortest_path(src, dst, depth)` / `shortest_path_with(src, dst, label, dir, depth)` | `shortestPath(src, dst, depth, { label, direction })` |
| `Expr::case(vec![(pred, expr)], Some(else))` | `Expr.case([[pred, expr]], elseExpr)` |
| `get_index_operation` / `retry_index_operation` / `abort_index_operation` | `getIndexOperation` / `retryIndexOperation` / `abortIndexOperation` |
| `with_typed_parameter(name, ty, value)?` | `withTypedParameter(name, type, value)` |
| `#[query] fn` + fn params | `defineParams(...)` + a normal builder function |
| `QueryRequest::read(b).with_query_name("route").to_json_string()` | `batch.toQueryJson(params, values, { queryName: "route" })` |
| `Client::new(Some(url))?` / `.with_api_key(...)` | `new Client(url)` / `.withApiKey(...)` |
| `client.request_builder().warm_only().query(r).send()` | `client.requestBuilder().warmOnly().query(r).send()` |

Wire output (enum tags, field names, omitted/null fields) is identical; only names differ.
