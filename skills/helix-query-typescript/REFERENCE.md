# Helix Query Authoring — TypeScript DSL Reference

Exhaustive builder catalog for the `@helix-db/helix-db` TypeScript DSL. Use when `SKILL.md` points you at a category or when you need a signature confirmed. Categories line up 1:1 with `../helix-query-rust/REFERENCE.md` and `../helix-query-json-dynamic/REFERENCE.md` so you can jump between TypeScript, Rust, and JSON forms.

All signatures come from `sdks/typescript/src/index.ts`; line numbers are cited inline. The builder is intentionally close to the Rust enum names *on the wire* (e.g. `Step`, `Predicate` variants serialize identically) while exposing camelCase TypeScript methods. The compatibility target is structural JSON equality with Rust serde output — encoding rules live in `../helix-query-json-dynamic/REFERENCE.md`.

## Import

```ts
import { g, sub, readBatch, writeBatch, NodeRef, EdgeRef, Predicate, SourcePredicate,
         PropertyValue, PropertyInput, Expr, StreamBound, PropertyProjection, ExprProjection,
         Projection, RepeatConfig, IndexSpec, Order, EmitBehavior, AggregateFunction, CompareOp,
         BatchCondition, DateTime, RangeIndexDirection, defineParams, param, registerRead, registerWrite, defineQueries,
         serializeQueryBundle, stringifyJson, i64, f32, f64, bytes, dateTime } from "@helix-db/helix-db";
```

A `prelude` object (`src/index.ts:2467`) re-exports all of the above for convenience.

## Typestate Cheat Sheet

`Traversal<S extends TraversalState, M extends MutationMode>` (`src/index.ts:1284`) tracks state in the type system. `TraversalState = "empty" | "nodes" | "edges" | "terminal"` and `MutationMode = "read" | "write"` (`src/index.ts:1281-1282`).

```text
empty  -- n,nWhere,nWithLabel[Where],inject,addN,createIndexIfNotExists,dropIndex,
          createVectorIndexNodes/Edges,createTextIndexNodes/Edges            └─> nodes
empty  -- e,eWhere,eWithLabel[Where]                                         └─> edges
empty  -- vectorSearchNodes[With], textSearchNodes[With]                     └─> nodes
empty  -- vectorSearchEdges[With], textSearchEdges[With]                     └─> edges
nodes  -- out, in, both, has, hasLabel, hasKey, where, dedup, within, without,
          limit, skip, range, as, store, select, inject, bind, orderBy[Multiple],
          repeat, union, choose, coalesce, optional, path, simplePath,
          fold, unfold, withSack, sack*                                      ↻ nodes
nodes  -- outE, inE, bothE                                                   └─> edges
nodes  -- count, exists, id, label, values, valueMap, project, projectBindings,
          projectDistinctBindings, group, groupCount, aggregateBy            └─> terminal
nodes("write") -- addE, setProperty, removeProperty, drop, dropEdge,
          dropEdgeLabeled, dropEdgeById                                      ↻ nodes
edges  -- outN, inN, otherN                                                  └─> nodes
edges  -- has, hasLabel, hasKey, where, edgeHas, edgeHasLabel, dedup, within,
          without, limit, skip, range, as, store, select, orderBy[Multiple]  ↻ edges
edges  -- count, exists, id, label, edgeProperties                          └─> terminal
```

`ReadBatch.varAs` accepts only `Traversal<_, "read">` — both the compiler and a runtime guard reject a write traversal (`src/index.ts:1840-1842`). `WriteBatch.varAs` accepts either mode.

---

## Entry Points

`src/index.ts:1674, 1775, 1930, 1933`:

```ts
g(): Traversal<"empty", "read">
sub(): SubTraversal
readBatch(): ReadBatch
writeBatch(): WriteBatch
```

### `ReadBatch` / `WriteBatch`  (`src/index.ts:1832, 1880`)

```ts
.varAs(name: string, traversal): ReadBatch | WriteBatch         // store named result
.varAsIf(name: string, condition: BatchCondition, traversal)    // conditional entry
.forEachParam(paramName: string, body): ReadBatch | WriteBatch  // run body per object in array param
.returning(vars: Iterable<string>)                              // restrict response variables
.toJsonString(): string                                         // raw batch JSON (inline query body)
.toJsonBytes(): Uint8Array
.toDynamicJson(options?: DynamicQueryOptions): string           // no-param dynamic request JSON
.toDynamicJson(params: DefinedParams<T>, values: ParamInputs<T>, options?: DynamicQueryOptions): string
.toDynamicRequest(..., options?: DynamicQueryOptions): DynamicQueryRequest
.toDynamicBytes(..., options?: DynamicQueryOptions): Uint8Array
```

### `BatchCondition`  (`src/index.ts:1779`)

```ts
BatchCondition.varNotEmpty(name)   // {"VarNotEmpty": name}
BatchCondition.varEmpty(name)      // {"VarEmpty": name}
BatchCondition.varMinSize(name, n) // {"VarMinSize": [name, n]}
BatchCondition.prevNotEmpty()      // "PrevNotEmpty"
```

`NamedQuery` (`src/index.ts:1805`) and `BatchEntry` (`src/index.ts:1816`, `.query(...)` / `.forEach(...)`) are built for you by `varAs` / `forEachParam` — you rarely construct them directly.

---

## Scalar Constructors & Values

Literal helpers (`src/index.ts:288-300`) disambiguate numeric width:

```ts
i64(value: number | bigint)   f32(value: number)   f64(value: number)
bytes(value: Uint8Array | number[])   dateTime(value: DateTime)
```

### `PropertyValue`  (`src/index.ts:326`)  — tagged on the wire

```ts
PropertyValue.null()              // "Null"
PropertyValue.bool(b)             // {"Bool": b}
PropertyValue.i64(n)              // {"I64": n}      (number | bigint)
PropertyValue.f64(n)  PropertyValue.f32(n)
PropertyValue.string(s)           // {"String": s}
PropertyValue.bytes(u8)           // {"Bytes": [...]}
PropertyValue.dateTime(dt | ms)   PropertyValue.datetimeMillis(ms)
PropertyValue.i64Array(xs)  PropertyValue.f64Array(xs)  PropertyValue.f32Array(xs)  PropertyValue.stringArray(xs)
PropertyValue.array(xs)  PropertyValue.object(record)
PropertyValue.from(input)         // smart conversion from PropertyValueInput
// accessors: asStr, asI64, asDatetimeMillis, asF64, asBool, asArray, asObject
```

`PropertyValueInput` (`src/index.ts:307`) is the union accepted wherever a literal is allowed: `null | boolean | number | bigint | string | Uint8Array | DateTime | PropertyValue | arrays | { object: ... }`.
Objects and generic arrays are stored as property values. Homogeneous primitive arrays may use the typed array variants (`I64Array`, `F64Array`, `StringArray`); mixed or nested arrays use `PropertyValue.array(...)`.

### `PropertyInput`  (`src/index.ts:431`)  — value-or-expression

Used for write property values and `edgeHas` / search args:

```ts
PropertyInput.value(v: PropertyValueInput)  // {"Value": <PropertyValue>}
PropertyInput.expr(e: Expr)                 // {"Expr": <Expr>}
PropertyInput.param(name: string)           // {"Expr": {"Param": name}}
PropertyInput.from(input)                   // smart constructor
```

### `DateTime`  (`src/index.ts:239`)

```ts
DateTime.fromMillis(ms: number | bigint)   DateTime.parseRfc3339(s: string)
.millis(): bigint   .toRfc3339(): string   // UTC, millisecond precision; negative epochs supported
```

---

## References: Nodes & Edges

`NodeRef` (`src/index.ts:459`) / `EdgeRef` (`src/index.ts:490`):

```ts
NodeRef.all()              // "All"          (nodes only)
NodeRef.id(id)             // {"Ids": [id]}
NodeRef.ids(iterable)      // {"Ids": [...]}
NodeRef.var(name)          // {"Var": name}
NodeRef.param(name)        // {"Param": name}
NodeRef.from(value)        // accepts NodeRef | id | id[] | "var-name"
// EdgeRef: id, ids, var, param, from (no `all`)
```

`g().n(...)` accepts `NodeRef | NodeId | NodeId[] | string`; `g().e(...)` accepts `EdgeRef | EdgeId | EdgeId[]`. `NodeId`/`EdgeId` are `number | bigint`.

---

## Sources  (`Traversal<"empty">` → `Traversal<"nodes"|"edges">`)

`src/index.ts:1329-1476`:

```ts
g().n(nodes)                                  -> Traversal<"nodes">
g().nWhere(pred: SourcePredicate)             -> Traversal<"nodes">
g().nWithLabel(label)                         -> Traversal<"nodes">     // = nWhere(SourcePredicate.eq("$label", label))
g().nWithLabelWhere(label, pred)              -> Traversal<"nodes">     // = nWhere(and([eq($label,label), pred]))
g().e(edges)                                  -> Traversal<"edges">
g().eWhere(pred)  g().eWithLabel(label)  g().eWithLabelWhere(label, pred)

// Vector & text search (high-level: concrete vector + numeric k)
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

---

## Traversal

Node-stream navigation (`src/index.ts` Traversal class):

```ts
.out(label?: string)   .in(label?: string)   .both(label?: string)   -> Traversal<"nodes", M>
.outE(label?: string)  .inE(label?: string)  .bothE(label?: string)  -> Traversal<"edges", M>
```

Edge-stream navigation:

```ts
.outN()    -> Traversal<"nodes", M>   // edge → target
.inN()     -> Traversal<"nodes", M>   // edge → source
.otherN()  -> Traversal<"nodes", M>   // edge → "other" endpoint
```

The label argument is optional; omit it (`out()`) or pass a string (`out("FOLLOWS")`). On the wire, `out()` → `{"Out": null}`, `out("FOLLOWS")` → `{"Out": "FOLLOWS"}`.

---

## Filters

```ts
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

### `Predicate`  (`src/index.ts:624`)

Literal constructors:

```ts
Predicate.eq(prop, val)    Predicate.neq(prop, val)
Predicate.gt(prop, val)    Predicate.gte(prop, val)    Predicate.lt(prop, val)    Predicate.lte(prop, val)
Predicate.between(prop, min, max)
Predicate.hasKey(prop)     Predicate.isNull(prop)      Predicate.isNotNull(prop)
Predicate.startsWith(prop, s)   Predicate.endsWith(prop, s)   Predicate.contains(prop, s)   Predicate.containsParam(prop, paramName)
Predicate.isIn(prop, values)    Predicate.isInExpr(prop, expr | paramRef)   Predicate.isInParam(prop, paramName)
Predicate.and(preds)   Predicate.or(preds)   Predicate.not(pred)
Predicate.compare(left: Expr, op: CompareOp, right: Expr)
```

Parameterized comparison shortcuts (wrap `Compare`):

```ts
Predicate.eqParam(prop, paramName)   Predicate.neqParam(...)
Predicate.gtParam(...)   Predicate.gteParam(...)   Predicate.ltParam(...)   Predicate.lteParam(...)
```

### `SourcePredicate`  (`src/index.ts:722`)  — used in `nWhere` / `eWhere`

Index-friendly subset:

```ts
SourcePredicate.eq / neq / gt / gte / lt / lte / between / hasKey / startsWith / and / or
```

Each comparison **auto-routes** by argument type: a literal keeps the plain variant (`SourcePredicate.eq("u","alice")` → `{"Eq": ["u", {"String": "alice"}]}`); an `Expr`/`ParamRef` routes to the `*Expr` variant (`SourcePredicate.eq("u", Expr.param("name"))` → `{"EqExpr": ["u", {"Param": "name"}]}`). `.toPredicate()` converts `*Expr` variants to `Compare`. Not available at source position: `isNull`, `isNotNull`, `contains[Param]`, `endsWith`, `isIn*`, `not`, `compare` — push those into a following `.where(Predicate....)`.

Property-name strings in filters can be dotted object paths, for example `Predicate.eq("metadata.externalID", "crm-42")`. Lookup is exact-first: a top-level property named `metadata.externalID` wins before walking the `metadata` object. Dotted paths are scan-only in V1; secondary, text, and vector indexes remain top-level only. Arrays are opaque and do not support `tags.0` syntax.

### `CompareOp`  (`src/index.ts:517`)

```ts
CompareOp.Eq | Neq | Gt | Gte | Lt | Lte
```

---

## Expressions

`Expr`  (`src/index.ts:543`):

```ts
Expr.prop(name)    Expr.val(value: PropertyValueInput)
Expr.id()          Expr.param(name)
Expr.timestamp()   // server UTC epoch millis
Expr.datetime()    // server typed DateTime
expr.add(other)  expr.sub(other)  expr.mul(other)  expr.div(other)  expr.modulo(other)  expr.neg()
Expr.case(whenThen: [Predicate, Expr][], elseExpr?: Expr | null)
```

`ParamRef` (`src/index.ts:2048`) has `.toExpr()` so a `param` reference can be used where an `Expr` is expected.

Typical uses:

- `Predicate.compare(Expr.prop("age"), CompareOp.Gte, Expr.param("minAge"))` — property-to-parameter comparison.
- `Expr.prop("metadata.score")` — nested object field lookup with the same exact-first dotted-path rules as filters.
- `ExprProjection.new("age2", Expr.prop("age").add(Expr.val(1)))` — computed column.
- `g().addN("Foo", { createdAt: PropertyInput.expr(Expr.timestamp()) })` — server-side timestamp.

---

## Stream Bounds & Limits

```ts
.limit(n)   .skip(n)   .range(start, end)
```

Each accepts `number`, `bigint`, `Expr`, `ParamRef`, or `StreamBound`. `StreamBound` (`src/index.ts:596`):

```ts
StreamBound.literal(n)        // {"Literal": n}
StreamBound.expr(e)           // {"Expr": <Expr>}
StreamBound.from(value)       // negative numbers become Expr (e.g. -1 -> {"Expr": {"Constant": {"I64": -1}}})
```

---

## Variables & Injection

```ts
.as(name)       // store current stream
.store(name)    // alias of .as
.select(name)   // replace current stream with a stored var
.inject(name)   // inject a var into the stream (source or mid-traversal)
g().inject(name)  // "empty" -> "nodes" source form
```

Cross-entry references: `NodeRef.var(name)`, `EdgeRef.var(name)`, `NodeRef.param(name)`, `EdgeRef.param(name)`.

---

## Ordering

```ts
.orderBy(property, order: Order)                                  // Order.Asc | Order.Desc
.orderByMultiple([[prop1, Order.Desc], [prop2, Order.Asc]])
```

`Order` at `src/index.ts:525`.
Dotted paths such as `metadata.score` are valid for fallback ordering, but V1 range indexes cannot accelerate nested paths.

---

## Aggregation (terminals)

```ts
.count()   .exists()   .group(property)   .groupCount(property)
.aggregateBy(fn: AggregateFunction, property)
// AggregateFunction.{Count, Sum, Min, Max, Mean}  (src/index.ts:535)
```

---

## Branching

Each arm is a `SubTraversal` from `sub()` (`src/index.ts:1678`):

```ts
.union([subA, subB, ...])
.choose(condition: Predicate, thenTraversal: SubTraversal, elseTraversal?: SubTraversal | null)
.coalesce([subA, subB, ...])   // first non-empty wins
.optional(subA)                // pass through if subA is empty
```

`SubTraversal` supports: `out`, `in`, `both`, `outE`, `inE`, `bothE`, `outN`, `inN`, `otherN`, `has`, `hasLabel`, `hasKey`, `where`, `dedup`, `within`, `without`, `edgeHas`, `edgeHasLabel`, `limit`, `skip`, `range`, `as`, `store`, `select`, `orderBy`, `orderByMultiple`, `path`, `simplePath`.

---

## Repeat

```ts
.repeat(RepeatConfig.new(sub().out("KNOWS")).times(3))
.repeat(
  RepeatConfig.new(sub().out("REPORTS_TO"))
    .until(Predicate.eq("title", "CEO"))
    .emitAfter()
    .maxDepth(10),
)
```

`RepeatConfig` (`src/index.ts:884`):

- `.times(n)` — fixed iterations
- `.until(pred)` — stop when predicate is true
- `.emitAll()` / `.emitBefore()` / `.emitAfter()` — emit policy
- `.emitIf(pred)` — emit only matching elements (sets emit to `After`)
- `.maxDepth(n)` — safety cap (default 100)

Default `emit` is `EmitBehavior.None` (`src/index.ts:529`; only the final result). Bound every repeat with `times` or `until`.

---

## Projections (terminals)

```ts
.values(["name", "email"])                  -> Traversal<"terminal", M>
.valueMap(["$id", "name"])                  -> Traversal<"terminal", M>
.valueMap(null)                             -> all properties
.project([...])                             -> Traversal<"terminal", M>
.edgeProperties()                           -> Traversal<"terminal", M>   // edge streams only
```

Projection constructors (`src/index.ts:837, 853, 868`) — all `#[serde(untagged)]` on the wire (no variant tag):

```ts
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

```ts
.bind(name: string)                                ↻ same stream; enters row mode (throws on empty name)
.projectBindings(projs: BindingProjection[])       -> Traversal<"terminal", M>  // preserves duplicate rows
.projectDistinctBindings(projs: BindingProjection[])-> Traversal<"terminal", M> // dedups identical rows
```

`.bind()` does not change the stream — each path keeps its own row-local
bindings, so hops inside `union` / `optional` / `choose` can still reference
earlier captures. Available on `Traversal` (node and edge streams) and on
`SubTraversal` inside branches (`src/index.ts` `bind`/`projectBindings` —
`dsl.ts:1234,1258,1666,1693,1696,1866`).

`BindingProjection` constructors (`dsl.ts:915-955`) — tagged on the wire by `kind`:

```ts
BindingProjection.current("$id", "current_id")              // read from current element
BindingProjection.binding("service", "$id", "service_id")   // read from a named binding
BindingProjection.property(BindingTarget.binding("svc"), "name", "svc_name")
BindingProjection.coalesce([                                // first present non-null wins
  BindingProjection.bindingRef("deployment", "$id"),
  BindingProjection.bindingRef("owner", "$id"),
], "workload_id")
```

`BindingTarget` is `"Current"` or `{ Binding: name }`
(`BindingTarget.current()` / `BindingTarget.binding(name)`);
`BindingValueRef = { target, source }` via
`BindingProjection.currentRef(source)` / `.bindingRef(name, source)`.
`source` accepts stored properties and the virtual fields `$id`, `$label`,
`$from`, `$to`, `$distance`, `$score`.

Worked example:

```ts
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

Emits a query bundle at **v5** (`QUERY_BUNDLE_VERSION = 5`, `dsl.ts:2447-2449`;
v4 is still accepted on read via `SUPPORTED_QUERY_BUNDLE_VERSIONS`). See
`../helix-query-json-dynamic/REFERENCE.md` for the JSON wire shape.

---

## Terminals (metadata)

```ts
.count()   .exists()   .id()   .label()
```

Usable on node and edge streams. `.edgeProperties()` is edge-only.

---

## Mutations (write-only)

Source-position mutation (`Traversal<"empty">` → `Traversal<"nodes", "write">`):

```ts
g().addN(label, properties)            // properties: Record<string, PropertyInput|PropertyValueInput|ParamRef> OR [string, ...][]
g().dropEdgeById(edges)
g().inject(varName)
```

Node-state mutations (→ `Traversal<"nodes", "write">`):

```ts
.addE(label, to: NodeRef | NodeId | ..., properties)
.setProperty(name, value: PropertyInput | PropertyValueInput)
.removeProperty(name)
.drop()
.dropEdge(to)              .dropEdgeLabeled(to, label)        .dropEdgeById(edges)
```

`addN`/`addE` properties accept an object (`{ name: "Alice" }`) or an array of tuples (`[["name", "Bob"]]`); values may be raw literals, nested objects/arrays, `PropertyInput.param(...)`, or a `ParamRef`. On the wire each becomes `["name", {"Value": {"String": "Alice"}}]` or, for nested values, a tagged `{"Object": ...}` / `{"Array": ...}` `PropertyValue`.

---

## Indexes (write-only)

```ts
g().createIndexIfNotExists(spec: IndexSpec)   -> Traversal<"terminal", "write">
g().dropIndex(spec: IndexSpec)                -> Traversal<"terminal", "write">

// convenience source forms (tenantProperty optional)
g().createVectorIndexNodes(label, property, tenantProperty?)
g().createVectorIndexEdges(label, property, tenantProperty?)
g().createTextIndexNodes(label, property, tenantProperty?)
g().createTextIndexEdges(label, property, tenantProperty?)
```

`IndexSpec` constructors (`src/index.ts:963`):

```ts
IndexSpec.nodeEquality(label, property)         // unique = false
IndexSpec.nodeUniqueEquality(label, property)   // unique = true
IndexSpec.nodeRange(label, property)
IndexSpec.nodeRangeDesc(label, property)
IndexSpec.nodeRangeWithDirection(label, property, RangeIndexDirection.Desc)
IndexSpec.edgeEquality(label, property)
IndexSpec.edgeRange(label, property)
IndexSpec.edgeRangeDesc(label, property)
IndexSpec.edgeRangeWithDirection(label, property, RangeIndexDirection.Desc)
IndexSpec.nodeVector(label, property, tenantProperty?)
IndexSpec.nodeText(label, property, tenantProperty?)
IndexSpec.edgeVector(label, property, tenantProperty?)
IndexSpec.edgeText(label, property, tenantProperty?)
```

Range indexes default to ascending physical order. Use `RangeIndexDirection.Desc` for descending indexes that primarily serve newest-first or high-score-first scans.

`createVectorIndexNodes(...)` serializes identically to `createIndexIfNotExists(IndexSpec.nodeVector(...))` — `{"CreateIndex": {"spec": {"NodeVector": {...}}, "if_not_exists": true}}`.
Index properties are top-level only in V1. Do not declare `metadata.externalID` as an equality, range, vector, or text index; duplicate indexed/searchable fields onto explicit top-level properties.

---

## Reserved / no-op builders

Emit the corresponding steps but have no effect in the current interpreter. Safe to include for forward-compatible queries.

```ts
.fold()   .unfold()   .path()   .simplePath()
.withSack(initial)   .sackSet(prop)   .sackAdd(prop)   .sackGet()
```

---

## Raw `Step` factory

`Step` (`src/index.ts:1002`) exposes every AST step as a static factory (`Step.n`, `Step.out`, `Step.vectorSearchEdges`, `Step.addN`, `Step.createVectorIndexNodes`, `Step.inject`, …) for building step lists directly. Most code should use the fluent `Traversal` methods; reach for `Step` only when assembling steps programmatically. `traversal.intoSteps()` returns the underlying `Step[]`.

---

## Parameters

`param` schema constructors (`src/index.ts:2033`):

```ts
param.bool()  param.i64()  param.f64()  param.f32()  param.string()
param.dateTime()  param.bytes()  param.value()
param.object()  param.object(inner)  param.array(inner)
```

`defineParams(schema)` (`src/index.ts:2068`) returns a `DefinedParams<T>` — an object of typed `ParamRef`s (`p.limit`, `p.tenantId`) plus hidden metadata. Pass it as the default argument of a builder function (`function f(p = params) { ... }`). A `ParamRef` (`src/index.ts:2048`) can be used directly where a `StreamBound`/`Expr`/property value is expected; `.toExpr()` converts it explicitly.

`QueryParamType` (`src/index.ts:1937`) is the on-the-wire parameter type: unit scalars serialize as bare strings (`"String"`, `"I64"`, `"DateTime"`, …); `array` is a single-field tuple (`{"Array": "String"}`).

`param.bytes()` cannot be sent through the dynamic route — conversion throws `DynamicQueryError` (`UnsupportedBytesParameter`).

---

## Registration & Bundles

```ts
registerRead(builder, params): RegisteredReadQuery    // src/index.ts:2299
registerWrite(builder, params): RegisteredWriteQuery  // src/index.ts:2308

const queries = defineQueries({                       // src/index.ts:2416
  read:  { route_a: registerRead(builderA, paramsA) },
  write: { route_b: registerWrite(builderB, paramsB) },
});

queries.call.route_a({ ... })       // -> DynamicQueryRequest with query_name="route_a" (typed input; unknown keys throw TypeError)
queries.buildQueryBundle()          // -> QueryBundle (version 4)
await queries.generate("queries.json")  // write bundle to path

serializeQueryBundle(bundle)        // src/index.ts:2439  (pretty JSON string)
deserializeQueryBundle(json)        // src/index.ts:2443  (validates version)
```

`DefinedQueries` is at `src/index.ts:2329`; `QUERY_BUNDLE_VERSION = 5` (`dsl.ts:2447-2449`) — bundles serialize at v5; v4 is still accepted on read via `SUPPORTED_QUERY_BUNDLE_VERSIONS = [4, 5]`; `QueryBundle` shape (`version`, `read_routes`, `write_routes`, `read_parameters`, `write_parameters`). Route names must be unique across read + write — duplicates throw `GenerateError` (`src/index.ts:197`).

---

## Dynamic Requests

```ts
type DynamicQueryOptions = { queryName?: string | null }

DynamicQueryRequest.read(batch: ReadBatch, queryName?: string | null)     // src/index.ts:2191
DynamicQueryRequest.write(batch: WriteBatch, queryName?: string | null)
req.insertParameterValue(name, value)   req.insertParameterType(name, ty)
req.withParameterValue(name, value)      req.withParameterType(name, ty)
req.setQueryName(name)                   req.clearQueryName()
req.withQueryName(name)
req.toJsonString()   req.toJsonBytes()
// req.requestType -> "read" | "write"   (DynamicQueryRequestType, src/index.ts:2174, lowercase on the wire)
// req.queryName -> string | null         (serialized as top-level query_name)
```

Most code reaches dynamic requests through `batch.toDynamicJson(params, values, { queryName })` / `.toDynamicRequest(...)` or `queries.call.route(...)`, which fill `parameters` and `parameter_types` automatically. Direct unnamed requests serialize `query_name: null`; `queries.call.route(...)` sets `query_name` to the registered route key automatically.

`DynamicQueryValue` (`src/index.ts:2179`) provides bare-JSON value helpers (`.null/.bool/.i64/.f64/.f32/.string/.array/.object`) for the top-level `parameters` map — these are untagged, distinct from the tagged `PropertyValue` used inside the AST.

For the exact JSON wire encoding these produce (externally-tagged enums, untagged `Projection`/`BatchQuery`/`DynamicQueryValue`, `parameter_types` rules, `DateTime` coercion), see `../helix-query-json-dynamic/REFERENCE.md`.

---

## Client (sending requests)

Built-in HTTP client for running a request against a Helix instance. Uses the global `fetch`, so there are no extra dependencies. Strict port of the Rust `helix_db::Client`.

```ts
new Client(url?: string | null)          // default "http://localhost:6969"; throws HelixError (InvalidUrl) on a bad URL
  .withApiKey(key?: string | null)        // Authorization: Bearer <key> (null/undefined clears it)
  .query<R = unknown>()                    // -> QueryBuilder<R>

// QueryBuilder<R> — request headers + body, then pick a route:
  .writerOnly()                            // X-Helix-Require-Writer: true
  .warmOnly()                              // X-Helix-Warm: true
  .shouldAwaitDurability(b: boolean)       // X-Helix-Await-Durable: true|false
  .body(data: unknown)                     // JSON body for a stored route (bigint-safe)
  .dynamic(req: DynamicQueryRequest)       // -> QueryRequest<R>  (POST /v1/query)
  .stored(name: string)                    // -> QueryRequest<R>  (POST /v1/query/{name})

await request.send(): Promise<R>           // 200 -> parsed JSON (parseJsonStructural); any other status -> throws HelixError
```

Prefer `.shouldAwaitDurability(true)` on writes. Under concurrent writers, not awaiting durability raises the chance of HTTP 409 write conflicts; awaiting it reduces them (but does not eliminate them, so callers still own retry). Leaving it off is fine for low-concurrency or read paths.

```ts
import { Client, HelixError } from "@helix-db/helix-db";

const client = new Client("https://helix.example.com").withApiKey(apiKey);

const users = await client
  .query<UserRow[]>()
  .dynamic(findUsers().toDynamicRequest(params, { tenantId: "acme", limit: 25n }))
  .send();
```

Only HTTP `200` is treated as success (mirrors the Rust client). Build the `DynamicQueryRequest` argument with `batch.toDynamicRequest(...)` or `queries.call.route(...)`.

---

## Errors

- `HelixError` (`src/index.ts`) — raised by `Client`/`send()`. `kind` ∈ `Network | Remote | Serialization | InvalidUrl`; `Remote` carries the server response body in `details`.
- `DynamicQueryError` (`src/index.ts:158`) — `kind` ∈ `Serialize | Utf8 | UnsupportedBytesParameter | InvalidDateTimeParameter`.
- `GenerateError` (`src/index.ts:197`) — `kind` ∈ `DuplicateQueryName | Io | Json | UnsupportedVersion`.

---

## Enums

```ts
CompareOp.{Eq, Neq, Gt, Gte, Lt, Lte}                // src/index.ts:517
Order.{Asc, Desc}                                    // src/index.ts:525  (bare strings on the wire)
EmitBehavior.{None, Before, After, All}              // src/index.ts:529
AggregateFunction.{Count, Sum, Min, Max, Mean}       // src/index.ts:535
DynamicQueryRequestType.{Read, Write}                // src/index.ts:2174 (lowercase on the wire)
```

---

## JSON Utilities

`stringifyJson(value, pretty?)`, `parseJsonStructural(json)`, `structuralJsonEqual(a, b)`, `canonicalizeJson(value)` (`src/index.ts:48-69`). Use `stringifyJson` (or `toJsonString` / `serializeQueryBundle`) instead of raw `JSON.stringify` whenever a payload may contain `bigint`.

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
| `#[register] fn` + fn params | `defineParams(...)` + `registerRead/registerWrite` |
| `DynamicQueryRequest::read(b).with_query_name("route").to_json_string()` | `batch.toDynamicJson(params, values, { queryName: "route" })` |
| `Client::new(Some(url))?` / `.with_api_key(...)` | `new Client(url)` / `.withApiKey(...)` |
| `client.query().warm_only().dynamic(r).send()` | `client.query().warmOnly().dynamic(r).send()` |

The wire output (enum tags, field names, omitted/null fields) is identical between the two DSLs — only the surface naming differs.
