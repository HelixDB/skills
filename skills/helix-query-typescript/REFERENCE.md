# Helix Query Authoring — TypeScript DSL Reference

Exhaustive builder catalog for the forthcoming
`@helix-db/helix-db@3.0.0` TypeScript DSL. Use when `SKILL.md` points
you at a category or when you need a signature confirmed.

The public surface is defined under
[`sdks/typescript/src`](https://github.com/HelixDB/helix-db/tree/main/sdks/typescript/src).
The compatibility target is structural JSON equality with the Rust SDK; encoding
rules live in `../helix-query-json-dynamic/REFERENCE.md`.

## Quick Navigation

- Start with **Import**, **Typestate Cheat Sheet**, and **Entry Points** for new queries.
- Use **Sources**, **Traversal**, **Filters**, **Projections**, and **Expressions** for reads.
- Use **Mutations**, **Indexes**, **Parameters**, **Direct Requests**, and **Client** for writes and execution.

## Import

```text
import { g, sub, readBatch, writeBatch, NodeRef, EdgeRef, Predicate, SourcePredicate,
         PropertyValue, PropertyInput, Expr, StreamBound, PropertyProjection, ExprProjection,
         Projection, BindingProjection, BindingTarget, RepeatConfig, IndexSpec, Order,
         EmitBehavior, AggregateFunction, CompareOp, BatchCondition, DateTime,
         RangeIndexDirection, VectorDistanceMetric, QueryRequest, defineParams, param,
         stringifyJson, i64, f32, f64, bytes, dateTime } from "@helix-db/helix-db";
```

A `prelude` object re-exports the common DSL surface for convenience.

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
edges  -- has, hasLabel, hasKey, where, edgeHas, edgeHasLabel, dedup, within,
          without, limit, skip, range, as, store, select, orderBy[Multiple],
          textSearch[With]                                                   ↻ edges
edges  -- count, exists, id, label, edgeProperties                          └─> terminal
```

`ReadBatch.varAs` accepts only a read traversal. `WriteBatch.varAs` accepts
either mode.

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

`NamedQuery` and `BatchEntry` are built for you by `varAs` / `forEachParam` —
you rarely construct them directly.

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

`PropertyValueInput` is the union accepted wherever a literal is allowed:
`null | boolean | number | bigint | string | Uint8Array | DateTime |
PropertyValue | arrays | { object: ... }`. Objects and generic arrays are
stored as property values. Homogeneous primitive arrays may use tagged
`i64_array`, `f64_array`, or `string_array` values; mixed or nested arrays use
`PropertyValue.array(...)`.

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

Prefer the `*With` variants for parameterized routes. The high-level `vectorSearchNodes` wraps `queryVector` as `PropertyValue.f32Array` and `k` as `StreamBound.literal`.

These source methods search the whole selected tenant partition. To rank only
IDs already present in a traversal, use traversal-scoped vector or text search
below.

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

Both forms enforce exact membership over the IDs in the current stream. Vector
ranking may still use approximate index structures, but cannot return an ID
outside that stream; project `$distance`. BM25 results equal exhaustive search
of the tenant partition intersected with those IDs, then top-`k` ordered by
score descending and entity ID ascending; project `$score`. BM25 statistics
remain partition-wide. Use the same tenant partition for candidate construction
and search.

The label argument is optional; omit it (`out()`) or pass a string
(`out("FOLLOWS")`). On the wire the nested `out` node has an `input` and omits
`label` when it is absent.

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

On edge streams, generic `.has`, `.hasLabel`, `.hasKey`, and `.where` filter
stored edge properties plus virtual fields `$id`, `$label`, `$from`, `$to`,
`$distance`, and `$score`. Keep `.edgeHas` for edge filters whose right-hand
side must be a `PropertyInput` expression or runtime parameter.

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

Use index-friendly predicate shapes at the source:

```text
SourcePredicate.eq / neq / gt / gte / lt / lte / between / hasKey / startsWith / and / or
```

The v3 wire format serializes predicates as expression trees, for example
`{"eq":{"left":{"property":"u"},"right":{"constant":{"string":"alice"}}}}`.
Use `.where(Predicate....)` after a source for filters that are not suitable as
an indexed source anchor.

Property-name strings in filters can be dotted object paths, for example `Predicate.eq("metadata.externalID", "crm-42")`. Lookup is exact-first: a top-level property named `metadata.externalID` wins before walking the `metadata` object. Dotted paths are scan-only in the current runtime; secondary, text, and vector indexes remain top-level only. Arrays are opaque and do not support `tags.0` syntax.

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

Typical uses:

- `Predicate.compare(Expr.prop("age"), CompareOp.Gte, Expr.param("minAge"))` — property-to-parameter comparison.
- `Expr.prop("metadata.score")` — nested object field lookup with the same exact-first dotted-path rules as filters.
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

Use `Order.Asc` or `Order.Desc`.
Dotted paths such as `metadata.score` are valid for fallback ordering, but current
range indexes do not accelerate nested paths.

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
.optional(subA)                // pass through if subA is empty
```

`SubTraversal` supports: `out`, `in`, `both`, `outE`, `inE`, `bothE`, `outN`, `inN`, `otherN`, `has`, `hasLabel`, `hasKey`, `where`, `dedup`, `within`, `without`, `edgeHas`, `edgeHasLabel`, `limit`, `skip`, `range`, `as`, `store`, `select`, `orderBy`, `orderByMultiple`, `path`, `simplePath`.

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

Default `emit` is `EmitBehavior.None` (only the final result). Bound every
repeat with `times` or `until`.

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

Mix `PropertyProjection` and `ExprProjection` freely in `.project([...])`.
Filtered `values(...)`, filtered `valueMap(...)`, `PropertyProjection.source`, and `Expr.prop(...)` accept dotted object paths. `valueMap(null)` returns all top-level stored properties as-is and does not flatten nested objects.

On edge streams, `Projection.fromEndpoint(prop, alias)` serializes to
`{"source":"$from.<prop>","alias":"<alias>"}` and
`Projection.toEndpoint(prop, alias)` serializes to
`{"source":"$to.<prop>","alias":"<alias>"}`. Use these to return source/target
node properties such as resource ids without traversing from every edge to its
endpoints. Keep `.edgeProperties()` for full edge maps and the internal `$from`
/ `$to` node ids.

---

## Row bindings (multi-hop correlation)

`.project(...)` only sees the final stream. When one output row must combine
values captured at **different hops** of one path, tag elements with
`.bind(name)` as you pass them, then assemble rows with `.projectBindings(...)`
/ `.projectDistinctBindings(...)`.

```text
.bind(name: string)                                ↻ same stream; enters row mode (throws on empty name)
.projectBindings(projs: BindingProjection[])       -> Traversal<"terminal", M>  // preserves duplicate rows
.projectDistinctBindings(projs: BindingProjection[])-> Traversal<"terminal", M> // dedups identical rows
```

`.bind()` does not change the stream — each path keeps its own row-local
bindings, so hops inside `union` / `optional` / `choose` can still reference
earlier captures. Available on `Traversal` (node and edge streams) and on
`SubTraversal` inside branches supports `bind` and binding projection.

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

Worked example:

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

The binding projection is part of the normal direct `QueryRequest`. See
`../helix-query-json-dynamic/REFERENCE.md` for its JSON wire shape.

---

## Terminals (metadata)

```text
.count()   .exists()   .id()   .label()
```

Usable on node and edge streams. `.edgeProperties()` is edge-only.

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

`addN`/`addE` properties accept an object (`{ name: "Alice" }`) or an array of
tuples (`[["name", "Bob"]]`); values may be raw literals, nested
objects/arrays, `PropertyInput.param(...)`, or a `ParamRef`. On the wire a
literal property is `["name", {"value": {"string": "Alice"}}]`.

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

Range indexes default to ascending physical order. Use `RangeIndexDirection.Desc` for descending indexes that primarily serve newest-first or high-score-first scans.

`createVectorIndexNodes(...)` serializes to the same `create_index` operation
as `createIndexIfNotExists(IndexSpec.nodeVector(...))`.
Index properties are top-level only in the current runtime. Do not declare `metadata.externalID` as an equality, range, vector, or text index; duplicate indexed/searchable fields onto explicit top-level properties.

---

## Reserved / no-op builders

Emit the corresponding steps but have no effect in the current interpreter. Safe to include for forward-compatible queries.

```text
.fold()   .unfold()   .path()   .simplePath()
.withSack(initial)   .sackSet(prop)   .sackAdd(prop)   .sackGet()
```

---

## Parameters

`param` schema constructors:

```text
param.bool()  param.i64()  param.f64()  param.f32()  param.string()
param.dateTime()  param.bytes()  param.value()
param.object()  param.object(inner)  param.array(inner)
```

`defineParams(schema)` returns a `DefinedParams<T>` — an object of typed
`ParamRef`s (`p.limit`, `p.tenantId`) plus hidden metadata. Pass it as the
default argument of a builder function (`function f(p = params) { ... }`).
A `ParamRef` can be used directly where a `StreamBound`/`Expr`/property value
is expected; `.toExpr()` converts it explicitly.

`QueryParamType` is the on-the-wire parameter type: scalar schemas serialize
as lowercase strings (`"string"`, `"i64"`, `"date_time"`, …); arrays and
objects use their structured `snake_case` schema form.

`param.bytes()` cannot be sent through the JSON route — conversion throws
`QueryError.UnsupportedBytesParameter`.

---

## Direct Requests

```text
type QueryOptions = { queryName?: string | null }

QueryRequest.read(batch: ReadBatch, queryName?: string | null)
QueryRequest.write(batch: WriteBatch, queryName?: string | null)
req.insertParameterValue(name, value)   req.insertParameterType(name, ty)
req.withParameterValue(name, value)      req.withParameterType(name, ty)
req.setQueryName(name)                   req.clearQueryName()
req.withQueryName(name)
req.toJsonString()   req.toJsonBytes()
// req.requestType -> "read" | "write" (lowercase on the wire)
// req.queryName -> string | null         (serialized as top-level query_name)
```

Most code reaches requests through
`batch.toQueryJson(params, values, { queryName })` or
`.toQueryRequest(...)`, which fill `parameters` and `parameter_types`
automatically. Direct unnamed requests serialize `query_name: null`.

`QueryValue` is an untagged JSON value in the top-level `parameters` map,
distinct from the tagged `PropertyValue` used inside the AST.

For the exact JSON wire encoding these produce (externally-tagged enums,
untagged `Projection`/`BatchQuery`/`QueryValue`, `parameter_types` rules, and
`DateTime` coercion), see `../helix-query-json-dynamic/REFERENCE.md`.

---

## Client (sending requests)

Built-in HTTP client for running a request against a Helix instance. Uses the global `fetch`, so there are no extra dependencies. Strict port of the Rust `helix_db::Client`.

```text
new Client(url?: string | null)           // defaults to http://localhost:6969
Client.server(url?: string | null)
  .withApiKey(key?: string | null)        // Authorization: Bearer <key> (null/undefined clears it)
  .query<R = unknown>(request)             // direct POST /v2/query

// Advanced server-only request headers:
client.requestBuilder<R>()
  .writerOnly()                            // X-Helix-Require-Writer: true
  .warmOnly()                              // X-Helix-Warm: true
  .shouldAwaitDurability(b: boolean)       // X-Helix-Await-Durable: true|false
  .query(request)

await request.send(): Promise<R>           // 200 -> parsed JSON; Cloud warm success -> 204/no payload; other status -> HelixError
```

For Cloud warming, use a no-content response type such as
`requestBuilder<void>()`. Partial target failure still succeeds when at least
one backend warms successfully.

Prefer `.shouldAwaitDurability(true)` on writes. Under concurrent writers, not awaiting durability raises the chance of HTTP 409 write conflicts; awaiting it reduces them (but does not eliminate them, so callers still own retry). Leaving it off is fine for low-concurrency or read paths.

```text
import { Client, HelixError } from "@helix-db/helix-db";

const client = new Client("https://helix.example.com").withApiKey(apiKey);

const request = findUsers().toQueryRequest(params, {
  tenantId: "acme",
  limit: 25n,
});
const users = await client.query<UserRow[]>(request).send();
```

Build the `QueryRequest` with `batch.toQueryRequest(...)`. Stored routes,
registration, and query bundles are not supported.

---

## Errors

- `HelixError` — raised by `Client`/`send()`. `kind` identifies network,
  remote, serialization, and URL errors; remote errors carry the server
  response body in `details`.
- `QueryError` — invalid parameter values, unknown parameters, serialization,
  or unsupported bytes parameters.

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

`stringifyJson(value, pretty?)`, `parseJsonStructural(json)`,
`structuralJsonEqual(a, b)`, and `canonicalizeJson(value)` are the bigint-safe
JSON utilities. Use `stringifyJson` or `toJsonString` instead of raw
`JSON.stringify` whenever a payload may contain `bigint`.

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
| `#[query] fn` + fn params | `defineParams(...)` + a normal builder function |
| `QueryRequest::read(b).with_query_name("route").to_json_string()` | `batch.toQueryJson(params, values, { queryName: "route" })` |
| `Client::new(Some(url))?` / `.with_api_key(...)` | `new Client(url)` / `.withApiKey(...)` |
| `client.request_builder().warm_only().query(r).send()` | `client.requestBuilder().warmOnly().query(r).send()` |

The wire output (enum tags, field names, omitted/null fields) is identical between the two DSLs — only the surface naming differs.
