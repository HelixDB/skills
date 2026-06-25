---
name: helix-query-typescript
description: Write and revise HelixDB queries with the TypeScript DSL (@helix-db/helix-db). Use when the task is to add, update, or review a Helix query built in TypeScript with readBatch, writeBatch, g(), traversal builders, projections, indexes, BM25 text search, or vector search — producing dynamic POST /v1/query requests (toDynamicJson/toDynamicRequest) and, optionally, a query bundle (defineQueries/registerRead/registerWrite). Inspect local labels, edges, properties, and existing query patterns before inventing new code. See REFERENCE.md for the full builder catalog and EXAMPLES.md for end-to-end patterns.
license: MIT
metadata:
  author: HelixDB
  version: 0.2.0
---

# Helix Query Authoring — TypeScript

Write Helix TypeScript DSL queries in a way that is schema-aware, explicit, and easy for agents to reason about. The TypeScript builder (`@helix-db/helix-db`) produces the same JSON AST as the Rust DSL; the compatibility target is structural JSON equality with Rust serde output.

This is the preferred way to author Helix queries in a TypeScript codebase — type-checked, and it emits the dynamic-request JSON for you. Drop to raw dynamic JSON (`helix-query-json-dynamic`) only for debugging or dynamically-shaped requests.

## When To Use

Use this skill when the task is to:

- write a new Helix query in TypeScript
- revise an existing TypeScript query function
- produce a dynamic `POST /v1/query` request from TypeScript (`toDynamicJson` / `toDynamicRequest`)
- send a request to a running Helix instance with the built-in `Client` (`client.query().dynamic(req).send()`)
- generate a query bundle (`defineQueries(...).generate("queries.json")`)
- add traversal, projection, pagination, BM25 search, or vector search to an existing query
- migrate a Rust DSL query (`#[register]`, `read_batch()`, …) to TypeScript

Do not use this skill for inline JSON AST hand-authoring — for the wire format and serde rules that govern what these builders emit, use `helix-query-json-dynamic`. For the Rust DSL, use `helix-query-rust`.

## First Steps

Before writing any query code:

1. Inspect the local repo for existing labels, edge labels, properties, and route patterns. Reuse exact casing (`tenantId`, `FOLLOWS`, `RelatesTo`) — do not normalize names.
2. Find the closest existing query and reuse its naming, projection, and scoping style.
3. Decide whether the route is a read (`readBatch()`) or a write (`writeBatch()`).
4. Identify the narrowest indexed anchor before planning the traversal.

If the local repo is thin on examples, use the companion files:

1. `EXAMPLES.md` — working end-to-end TypeScript queries (reads, writes, search, repeat, branching, upsert, `forEachParam`, index management). Scenarios are numbered to match `../helix-query-rust/EXAMPLES.md` and `../helix-query-json-dynamic/EXAMPLES.md` 1:1.
2. `REFERENCE.md` — full builder catalog organized by category, with typestate notes and `src/index.ts` line citations.

Open `REFERENCE.md` whenever you need a builder beyond the common surface (`addE`, `dropEdgeById`, `createVectorIndexNodes`, `repeat`, `choose`, `coalesce`, `optional`, `aggregateBy`, `groupCount`, `inject`, `orderByMultiple`, `Expr.case`, the `*With` search variants, etc.) — do not invent method names from memory.

## Core Authoring Rules

### 1. Start With The Right Batch Type

- `readBatch()` for read-only routes
- `writeBatch()` for any mutation (adds a node/edge, updates/removes a property, drops data, or creates/drops an index)

`ReadBatch.varAs` accepts only read-only traversals and throws `TypeError` at runtime if handed a write traversal (the type system also rejects it at compile time). `WriteBatch.varAs` accepts either.

### 2. Compose With `varAs` / `returning`

A batch is a list of named query entries plus a returns list:

```ts
readBatch()
  .varAs("user", g().nWhere(SourcePredicate.eq("username", "alice")))
  .varAs("friends", g().n(NodeRef.var("user")).out("FOLLOWS").dedup().limit(100))
  .returning(["user", "friends"]);
```

- `.varAs(name, traversal)` — store a named result.
- `.varAsIf(name, condition, traversal)` — conditional entry (`BatchCondition.varNotEmpty(name)`, `varEmpty`, `varMinSize`, `prevNotEmpty`).
- `.forEachParam(paramName, body)` — run `body` (a batch) once per object in an array parameter.
- `.returning([...])` — restrict the response to these variable names.

Cross-entry references use `NodeRef.var(name)` / `EdgeRef.var(name)`; parameters use `NodeRef.param(name)` / `EdgeRef.param(name)`.

### 3. Anchor Narrow, Then Traverse

Prefer this anchor order: node/edge ID → unique property lookup → equality-indexed property lookup → scoped label scan → broad label scan (last resort). `nWithLabel("User")` desugars to `nWhere(SourcePredicate.eq("$label", "User"))`; `nWithLabelWhere("User", pred)` builds the scoped `and`. Do not start from a broad label scan when an indexed identifier exists.

### 4. Keep Output Shape Intentional

- `.project([...])` for stable service-facing response shapes (mix `PropertyProjection` and `ExprProjection`).
- `.valueMap(["$id", "name"])` (or `.valueMap(null)` for all) when returning many properties is acceptable.
- `.edgeProperties()` for edge streams.
- For edge endpoint properties, prefer edge-stream `.project([...])` with
  `Projection.fromEndpoint(prop, alias)` / `Projection.toEndpoint(prop, alias)`
  instead of traversing to every endpoint first.

Do not return oversized properties like embeddings unless the caller explicitly needs them.

### 5. Preserve Search Scope

For BM25 and vector search: keep the chosen text/vector property explicit, pass the tenant value when the index is scoped, and project `$distance` **before** traversing off the hit stream (`out`/`in`/`both` drop the distance metadata). Prefer the `*With` variants for parameterized routes — they accept `PropertyInput.param(...)`, `Expr.param(...)`, and `StreamBound`.

### 6. Use Traversal Controls Deliberately

Apply `dedup`, `limit`, `range`, `skip`, `count` because the route needs them, not by habit. Bound every `repeat(...)` with `times` or `until`; the default `maxDepth` is 100.

### 7. Prefer Explicit Write Branching Over Invented MERGE Semantics

For create-or-update: load existing nodes, branch with `varAsIf` (`VarNotEmpty` → update, `VarEmpty` → create). See EXAMPLES.md §13.

### 8. Parameters: `defineParams` + Plain Builder Functions

Query builders are plain functions that return a `ReadBatch`/`WriteBatch`. Define parameter schemas once and reference them:

```ts
const params = defineParams({ tenantId: param.string(), limit: param.i64() });

function findUsers(p = params) {
  return readBatch()
    .varAs("users", g().nWithLabel("User").where(Predicate.eqParam("tenantId", "tenantId")).limit(p.limit).valueMap(["$id", "name"]))
    .returning(["users"]);
}
```

- A `ParamRef` (e.g. `p.limit`) can be passed directly to `.limit(...)`, search `k`, etc.
- Predicate `*Param` helpers (`Predicate.eqParam(prop, paramName)`) and `PropertyInput.param(paramName)` reference parameters by **name string**.
- Supported schemas: `param.bool/i64/f64/f32/string/dateTime/bytes/value/object/object(inner)/array(inner)`.

### 9. Choose The Output Path

- **Dynamic request:** `findUsers().toDynamicJson(params, { tenantId: "acme", limit: 25n }, { queryName: "find_users" })` → request JSON string for `POST /v1/query`. Use `toDynamicRequest(...)` for the object, `toDynamicBytes(...)` for bytes. No-parameter queries take no schema argument: `countUsers().toDynamicJson({ queryName: "count_users" })`. Unnamed requests serialize `query_name: null`, which the gateway records as `__dynamic__`.
- **Raw batch JSON:** `findUsers().toJsonString()` — the inline `query` body only (no envelope).
- **Bundle:** register queries and generate a `queries.json` (see Rule 10).
- **Send it with the client:** `new Client(url).withApiKey(key).query<R>().dynamic(findUsers().toDynamicRequest(params, values, { queryName: "find_users" })).send()` POSTs to `/v1/query` and returns the parsed JSON on HTTP 200, else throws `HelixError`. Add `.warmOnly()` / `.writerOnly()` / `.shouldAwaitDurability(b)` for the matching request headers; use `.stored(name).body(x)` for a deployed named route. Prefer `.shouldAwaitDurability(true)` on writes — under concurrent writers it reduces HTTP 409 write conflicts (callers still own retry). See REFERENCE.md → "Client".

### 10. Bundles: `registerRead` / `registerWrite` / `defineQueries`

Registration is needed when bundling queries into a `queries.json`:

```ts
export const queries = defineQueries({
  read: { find_users: registerRead(findUsers, params) },
  write: { add_user: registerWrite(addUser, addUserParams) },
});

queries.call.find_users({ tenantId: "acme", limit: 25n }); // -> DynamicQueryRequest with query_name="find_users"
await queries.generate("queries.json");                    // bundle, version 4
```

Route names must be unique across read and write routes — duplicates throw `GenerateError`.

## Number & DateTime Handling

- Use `bigint` (`25n`) or `i64(...)` for full `i64` range; plain `number` is accepted only for safe integers when an integer is required.
- Serialize bigint-bearing payloads with `toJsonString()` / `stringifyJson()` / `serializeQueryBundle()`, **never** raw `JSON.stringify`.
- `DateTime` stores epoch milliseconds (negative allowed): `DateTime.fromMillis(ms)`, `DateTime.parseRfc3339(s)`, `.toRfc3339()`. Declare the parameter as `param.dateTime()`; dynamic request values render as UTC RFC3339 with millisecond precision.
- Nested object/array property values are supported through normal object and array inputs or `PropertyValue.object/array`. Read nested object fields with dotted property strings such as `metadata.externalID`; lookup is exact-first and scan-only in V1.

## Builder Surface At A Glance

| Category | Primary builders | Notes |
|---|---|---|
| Entry points | `g()`, `sub()`, `readBatch()`, `writeBatch()` | `g()` starts a `Traversal<"empty","read">`. |
| Sources | `n`, `nWhere`, `nWithLabel`, `nWithLabelWhere`, `e`, `eWhere`, `eWithLabel`, `eWithLabelWhere`, `vectorSearchNodes[With]`, `textSearchNodes[With]`, `vectorSearchEdges[With]`, `textSearchEdges[With]` | Anchor narrowly. `*With` variants accept params/exprs. |
| Traversal | `out`, `in`, `both`, `outE`, `inE`, `bothE`, `outN`, `inN`, `otherN` | Label arg is optional (`out("FOLLOWS")` or `out()`). `*E` switch to the edge stream. |
| Filters | `has`, `hasLabel`, `hasKey`, `where`, `dedup`, `within`, `without`, `edgeHas`, `edgeHasLabel` | `Predicate.*` + `Predicate.*Param`; dotted paths like `metadata.externalID` are scan-only. |
| Limits | `limit`, `skip`, `range` | Accept `number`, `bigint`, `Expr`, `ParamRef`, or `StreamBound`. |
| Variables | `as`, `store`, `select`, `inject` | Cross-entry refs via `NodeRef.var/param`, `EdgeRef.var/param`. |
| Ordering | `orderBy`, `orderByMultiple` | `Order.Asc` / `Order.Desc`. |
| Aggregation | `count`, `exists`, `group`, `groupCount`, `aggregateBy` | `AggregateFunction.{Count,Sum,Min,Max,Mean}`. |
| Branching | `union`, `choose`, `coalesce`, `optional` | Each arm is a `sub()` sub-traversal. |
| Repeat | `repeat(RepeatConfig.new(sub).times(n).until(pred).emitAfter().maxDepth(100))` | Bound with `times`/`until`; default `maxDepth` 100. |
| Projection | `values`, `valueMap`, `project`, `edgeProperties` | `project` mixes `PropertyProjection` (incl. `renamed`) and `ExprProjection`; filtered outputs accept dotted paths; edge streams can project endpoint fields with `Projection.fromEndpoint` / `Projection.toEndpoint`. |
| Expressions | `Expr.prop/val/id/timestamp/datetime/param`, `.add/.sub/.mul/.div/.modulo/.neg`, `Expr.case` | `Expr.timestamp()` writes server UTC millis; `Expr.datetime()` writes typed datetime. |
| Mutations | `addN`, `addE`, `setProperty`, `removeProperty`, `drop`, `dropEdge`, `dropEdgeLabeled`, `dropEdgeById` | `dropEdgeById` is multigraph-safe. |
| Indexes | `createIndexIfNotExists(spec)`, `dropIndex(spec)`, plus `createVectorIndexNodes/Edges`, `createTextIndexNodes/Edges`; `IndexSpec.nodeEquality/nodeUniqueEquality/nodeRange/nodeRangeDesc/nodeRangeWithDirection/edgeEquality/edgeRange/edgeRangeDesc/edgeRangeWithDirection/nodeVector/nodeText/edgeVector/edgeText` | All write-only and top-level only for indexed properties. `RangeIndexDirection.Desc` sets descending physical order. |
| Output | `toJsonString`, `toDynamicJson`, `toDynamicRequest`, `toDynamicBytes` | Dynamic forms take `(params, values, options)` unless the query has no parameters; pass `{ queryName }` to set top-level `query_name`. |
| Client / transport | `new Client(url)`, `.withApiKey`, `.query<R>()`, `.writerOnly`/`.warmOnly`/`.shouldAwaitDurability`, `.body`, `.dynamic`/`.stored`, `.send()` | Sends to `POST /v1/query`; `send()` resolves parsed JSON on 200, else throws `HelixError`. |
| Bundles | `defineParams`, `param.*`, `registerRead`, `registerWrite`, `defineQueries`, `serializeQueryBundle`, `.buildQueryBundle()`, `.generate()` | `QUERY_BUNDLE_VERSION = 5` (reads v4 + v5). |

See `REFERENCE.md` for full signatures and typestate constraints.

## Canonical Examples

### Read By Indexed Identifier

```ts
const params = defineParams({ userId: param.string() });

function userById(p = params) {
  return readBatch()
    .varAs(
      "user",
      g()
        .nWithLabel("User")
        .where(Predicate.eqParam("userId", "userId"))
        .project([
          PropertyProjection.renamed("$id", "id"),
          PropertyProjection.new("userId"),
          PropertyProjection.new("name"),
        ]),
    )
    .returning(["user"]);
}

const body = userById().toDynamicJson(params, { userId: "u-42" });
```

### Explicit Create Or Update

```ts
const upsertParams = defineParams({ userId: param.string(), name: param.string() });

function upsertUser(p = upsertParams) {
  return writeBatch()
    .varAs("existing", g().nWithLabel("User").where(Predicate.eqParam("userId", "userId")))
    .varAsIf(
      "updated",
      BatchCondition.varNotEmpty("existing"),
      g().n(NodeRef.var("existing")).setProperty("name", PropertyInput.param("name")),
    )
    .varAsIf(
      "created",
      BatchCondition.varEmpty("existing"),
      g().addN("User", { userId: PropertyInput.param("userId"), name: PropertyInput.param("name") }),
    )
    .returning(["updated", "created"]);
}
```

### Scoped Search Route

```ts
const searchParams = defineParams({ tenantId: param.string(), queryVector: param.array(param.f64()), limit: param.i64() });

function nearestDocuments(p = searchParams) {
  return readBatch()
    .varAs(
      "results",
      g()
        .vectorSearchNodesWith("Document", "embedding", PropertyInput.param("queryVector"), Expr.param("limit"), PropertyInput.param("tenantId"))
        .project([
          PropertyProjection.renamed("$id", "id"),
          PropertyProjection.new("title"),
          PropertyProjection.renamed("$distance", "distance"),
        ]),
    )
    .returning(["results"]);
}
```

## Anti-Patterns

Do not:

- invent labels, edge labels, or property names without checking the codebase
- start from broad scans when an indexed ID or scoped predicate exists
- return embeddings by default in search results, or ignore tenant scope on text/vector search
- add `dedup` or `limit` without a reason
- call `JSON.stringify` on a payload that may contain `bigint` — use `toJsonString` / `stringifyJson`
- pass a `param.bytes()` parameter through the dynamic route — it throws `DynamicQueryError` (`UnsupportedBytesParameter`)
- reuse a route name across read and write routes — `defineQueries` throws `GenerateError`
- put a write traversal into `readBatch().varAs(...)` — it is rejected at compile time and throws at runtime
- traverse off a vector/text hit stream before projecting `$distance`

## Validation Checklist

Before finishing:

- verify `readBatch()` versus `writeBatch()` is correct
- verify labels, edge labels, and properties match the repo exactly
- verify the first anchor is the narrowest practical indexed set
- verify the returned variable names and shape match service expectations
- verify text/vector routes pass the tenant value when the index is scoped, and project `$distance` before navigating
- verify `bigint`/`i64(...)` is used for large integers and serialization goes through `toJsonString`/`stringifyJson`
- verify `DateTime` parameters use `param.dateTime()` and `DateTime.*` values
- verify route names are unique if registering a bundle
- verify the query matches surrounding local style more than any generic example

## Reference Files

- `REFERENCE.md` — full builder catalog (entry points, scalars, refs, expressions, predicates, projections, branching, repeat, mutations, indexes, batches, parameters, registration/bundles, dynamic requests), with `src/index.ts` citations and a Rust↔TS naming map.
- `EXAMPLES.md` — end-to-end TypeScript queries mirroring the scenarios in `../helix-query-rust/EXAMPLES.md` and `../helix-query-json-dynamic/EXAMPLES.md`, so you can move fluently between the Rust DSL, TypeScript DSL, and JSON forms.
