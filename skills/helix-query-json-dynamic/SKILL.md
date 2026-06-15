---
name: helix-query-json-dynamic
description: Build and validate HelixDB dynamic inline-query requests for POST /v1/query. Use when the task involves dynamic queries, inline query JSON, query_name, the inline AST (steps, predicates, expressions, projections), parameter_types, DateTime coercion, query warming, or debugging a request body sent directly to the Helix gateway. See REFERENCE.md for every AST variant and EXAMPLES.md for copy-pasteable payloads.
license: MIT
metadata:
  author: HelixDB
  version: 0.2.0
---

# Helix Dynamic Query JSON

Use this skill for inline dynamic query requests sent directly to `POST /v1/query`.

The inline `query` body is a JSON serialization of the Rust DSL AST. Every variant an agent can send is documented in the companion files. **If you are writing anything beyond a trivial read, open `REFERENCE.md` first** — do not guess variant names or field shapes.

> **Prefer a DSL when you are authoring queries inside a codebase.** If the app is TypeScript, build queries with `helix-query-typescript` (`@helix-db/helix-db`); if it is Rust, use `helix-query-rust`. Those builders are type-checked and emit exactly this JSON, so you get the same wire format without hand-writing tagged ASTs. Reach for this skill (raw dynamic JSON) when you are debugging a `POST /v1/query` call, sending a one-off / dynamically-shaped request, working in a language without a DSL, or hand-inspecting the wire format — not as the default way to write application queries.

## Reference Files

- `REFERENCE.md` — complete AST variant catalog (every `Step`, `Predicate`, `Expr`, `PropertyValue`, `IndexSpec`, `RepeatConfig`, `BatchCondition`, envelope field). Use when writing a non-trivial request.
- `EXAMPLES.md` — working end-to-end JSON bodies: reads, writes, vector/text search, `Repeat`, `Choose`, `Coalesce`, `Union`, aggregations, upserts, `ForEach`, index management, warming. Copy the closest scenario as a starting point.

## When To Use

Use this skill when the task is to:

- build a dynamic Helix request body
- name a dynamic request for gateway logs or query diagnostics with `query_name`
- debug a failing `POST /v1/query` call
- add `parameter_types` to a dynamic request
- send `DateTime` or typed-array parameters correctly
- understand read versus write behavior on the dynamic route
- use query warming on a dynamic read
- store nested object/array properties or read object fields with dotted paths
- translate a Rust DSL query you already have into its JSON form

Do not use this skill as the main guide for writing DSL query functions. Use `helix-query-rust` (Rust) or `helix-query-typescript` (TypeScript) for that.

## First Steps

Before writing the payload:

1. Confirm whether the request is a read or a write. A query that contains any mutation step (`AddN`, `AddE`, `SetProperty`, `RemoveProperty`, `Drop`, `DropEdge`, `DropEdgeLabeled`, `DropEdgeById`, or any `Create*Index` / `DropIndex`) must use `request_type: "write"`.
2. Choose a `query_name` if logs or diagnostics should identify this inline query; omit it or set it to `null` only for ad-hoc requests that can aggregate under `__dynamic__`.
3. Confirm whether the inline `query` object already exists in code, a test, or a serialized payload — prefer copying a known-good shape.
4. Identify any parameters that need explicit typing, especially `DateTime` and typed arrays.

## Required Envelope Rules

- send requests to `POST /v1/query`
- `request_type` must be `"read"` or `"write"` (**lowercase** — the enum uses `#[serde(rename_all = "lowercase")]`)
- `query_name` is optional top-level operational metadata for gateway logs and slow-query diagnostics; use exactly `query_name`, never `name` or `queryName`
- `query_name: null` or a missing `query_name` falls back to `__dynamic__`; a blank or whitespace-only `query_name` is rejected
- `query` must be a single inline route object (a `ReadBatch` or `WriteBatch`), **not** the full `queries.json` bundle
- `parameters` is optional
- `parameter_types` is optional until you need schema-aware coercion (see Parameter Typing)
- `X-Helix-Warm: true` is an optional request header, valid only for reads

## Canonical Request Shape

```json
{
  "request_type": "read",
  "query_name": "node_exists",
  "query": {
    "queries": [
      {
        "Query": {
          "name": "node_exists",
          "steps": ["Count"],
          "condition": null
        }
      }
    ],
    "returns": ["node_exists"]
  },
  "parameters": {
    "name": "Alice",
    "entity_id": 123
  },
  "parameter_types": {
    "name": "String",
    "entity_id": "I64"
  }
}
```

Notes on the shape:

- `query_name` names the whole dynamic request for observability. It is unrelated to `Query.name` inside `query.queries[*]`, which names result variables.
- `query` contains a `ReadBatch` (or `WriteBatch`); both have `{ "queries": [...], "returns": [...] }`.
- Each element of `queries` is a `BatchEntry` — either `{"Query": {...}}` or `{"ForEach": {...}}`.
- `"steps": ["Count"]` is a valid step list: `Count` is a unit variant so it serializes as a bare string. Data-carrying variants are wrapped: `{"Limit": 10}`, `{"Has": ["name", {"String": "Alice"}]}`, etc.

## Serde Encoding Rules

Every encoding in `REFERENCE.md` follows these rules. Internalize them or the request will fail with `unknown variant` / `invalid type` errors.

1. **Default encoding is externally tagged.** Given a Rust enum `E::Var(..)` without a `#[serde(...)]` attribute:
   - **Unit variant** (no data): bare string. `Step::Count` → `"Count"`. `Predicate::HasKey` is a tuple-with-data variant, not unit — see rule 2.
   - **Tuple variant with 1 field**: `{"Var": <inner>}`. `Step::N(NodeRef::Ids(vec![644]))` → `{"N": {"Ids": [644]}}`.
   - **Tuple variant with 2+ fields**: `{"Var": [a, b, ...]}`. `Predicate::Eq("status", PropertyValue::String("active"))` → `{"Eq": ["status", {"String": "active"}]}`. `Predicate::Between("score", 60, 100)` → `{"Between": ["score", {"I64": 60}, {"I64": 100}]}`.
   - **Struct variant**: `{"Var": {"field": ...}}`. `Step::VectorSearchNodes { label, property, ... }` → `{"VectorSearchNodes": {"label": "...", "property": "...", ...}}`.

2. **Three enums are `#[serde(untagged)]` — no variant wrapper:**
   - `BatchQuery` (the value of the envelope's `query` field): write the `ReadBatch` / `WriteBatch` object inline. There is no `{"Read": ...}` wrapper.
   - `Projection` (element of a `Project` step's list): write the inner struct directly. `PropertyProjection` → `{"source": "name", "alias": "name"}`. `ExprProjection` → `{"alias": "age_plus_one", "expr": {...}}`. **Do not** write `{"Property": {...}}` or `{"Expr": {...}}` wrappers.
   - `DynamicQueryValue` (values inside the top-level `parameters` map): bare JSON. `"limit": 25`, `"tags": ["a","b"]`, `"user": {"name": "Alice"}`. No `{"I64": 25}` wrapping here — that form is `PropertyValue`, which is *inside the AST*, not at parameter-value position.

3. **`DynamicQueryRequestType` is `rename_all = "lowercase"`**: use `"read"` / `"write"`, never `"Read"` / `"Write"`.

4. **Optional fields may be omitted or set to `null`.** Top-level `query_name` may be omitted or set to `null` to use the `__dynamic__` fallback. `tenant_value`, `condition`, `else_traversal`, `emit_predicate`, and similar all serialize via `skip_serializing_if = "Option::is_none"` when unset, but the server accepts explicit `null`.

5. **`PropertyValue` is distinct from `DynamicQueryValue`.** Inside the AST (literals in `Has`, `Eq`, `AddN` properties wrapped in `PropertyInput::Value`, etc.) values are *tagged*: `{"String": "..."}`, `{"I64": 42}`, `{"Bool": true}`, `{"F64": 3.14}`, `{"F64Array": [0.1, 0.2]}`, `{"Array": [{"String": "x"}]}`, `{"Object": {"k": {"I64": 1}}}`, `{"Null": null}` is wrong — use the bare string `"Null"` for the unit variant. At *parameter-value position* (top-level `parameters` map) values are untagged bare JSON.

6. **`DateTime` over JSON:** supply an RFC3339 string *or* epoch-millis integer as the parameter value, and declare `parameter_types: {"p": "DateTime"}`. No implicit coercion — a plain string parameter without the type declaration is just a string.

7. **`Bytes` is not round-trippable.** The builder raises `UnsupportedBytesParameter`. Do not send `Bytes` parameters through the JSON dynamic route.

8. **Dotted property names are property paths at read time.** Property-name slots such as `Has`, `Predicate`, `Expr.Property`, `Values`, `ValueMap`, `Project.source`, and `OrderBy` accept names like `metadata.externalID`. Lookup is exact-first: a top-level property literally named `metadata.externalID` wins before walking the nested `metadata` object. Dotted paths are scan-only in V1; secondary, text, and vector indexes remain top-level only. Arrays are opaque, so no `tags.0` syntax. On edge streams, `Project.source` also accepts endpoint-qualified sources such as `"$from.resource_id"` and `"$to.resource_id"`; these are still plain untagged `Projection` entries, not a separate AST variant.

## Envelope Decision Table

| Goal | `request_type` | `query.queries[*]` shape | Notes |
|---|---|---|---|
| Simple read | `"read"` | `{"Query": {"name": "...", "steps": [...], "condition": null}}` | |
| Conditional step after prior step | `"read"` or `"write"` | `{"Query": {..., "condition": {"VarNotEmpty": "prev"}}}` | Conditions: `VarNotEmpty`, `VarEmpty`, `VarMinSize`, `PrevNotEmpty` |
| Single mutation | `"write"` | `{"Query": {...}}` with a mutation step | See EXAMPLES.md §Write |
| Upsert | `"write"` | Multi-entry: load → `VarNotEmpty` update → `VarEmpty` create | See EXAMPLES.md §Upsert |
| Per-row iteration over a param | `"read"` or `"write"` | `{"ForEach": {"param": "items", "body": [...]}}` | `param` must be typed `{"Array": "Object"}` |
| Warm a read | `"read"` | normal body + header `X-Helix-Warm: true` | Returns `204 No Content` on success |

## AST Quick-Map

Step categories and their JSON form (one-liners). Full signatures in `REFERENCE.md`.

**Sources** (start a traversal):
- `{"N": {"Ids": [1,2]}}` / `{"N": {"Var": "x"}}` / `{"N": {"Param": "ids"}}` — nodes by id / variable / parameter
- `{"NWhere": <SourcePredicate>}` — nodes matching a source-safe predicate
- `{"E": {...}}` / `{"EWhere": <SourcePredicate>}` — edges
- `{"VectorSearchNodes": {"label":"...","property":"...","query_vector":{...},"k":{...},"tenant_value":{...}}}`
- `{"TextSearchNodes": {...}}` — BM25 on nodes
- `{"VectorSearchEdges": {...}}`, `{"TextSearchEdges": {...}}`

**Traversal** (navigate):
- `{"Out": "LABEL"}` / `{"Out": null}` — also `In`, `Both`, `OutE`, `InE`, `BothE` (same shape)
- `"OutN"` / `"InN"` / `"OtherN"` — unit variants, from an edge stream back to a node

**Filters:**
- `{"Has": ["prop", {"String": "v"}]}` — property equals
- `{"Where": {"Eq": ["metadata.externalID", {"String": "crm-42"}]}}` — dotted object path filter, scan-only
- `{"HasLabel": "User"}`, `{"HasKey": "email"}`
- `{"Where": <Predicate>}` — full predicate
- `"Dedup"` — unit variant
- `{"Within": "var"}`, `{"Without": "var"}` — set ops against a stored variable
- `{"EdgeHas": ["weight", {"Value": {"I64": 1}}]}`, `{"EdgeHasLabel": "KNOWS"}`
- Generic `Has` / `HasLabel` / `HasKey` / `Where` work on edge streams too; use `EdgeHas` when the RHS must be a `PropertyInput` expression or parameter.

**Limits:**
- `{"Limit": 10}`, `{"Skip": 5}`, `{"Range": [0, 25]}` — literal
- `{"LimitBy": {"Param": "n"}}`, `{"SkipBy": ...}`, `{"RangeBy": [<StreamBound>, <StreamBound>]}` — runtime

**Variables:**
- `{"As": "x"}` / `{"Store": "x"}` — name the current stream
- `{"Select": "x"}` — replace stream with a stored var
- `{"Inject": "x"}` — inject var into stream (source or mid-traversal)

**Ordering:**
- `{"OrderBy": ["created_at", "Desc"]}` — single property
- `{"OrderBy": ["metadata.score", "Desc"]}` — dotted path ordering, fallback scan/sort only
- `{"OrderByMultiple": [["priority", "Desc"], ["name", "Asc"]]}`

**Aggregation:**
- `{"Group": "status"}`, `{"GroupCount": "status"}`
- `{"AggregateBy": ["Sum", "price"]}` — functions: `Count`, `Sum`, `Min`, `Max`, `Mean`

**Branching** (each branch is a `SubTraversal` = `{"steps": [...]}`):
- `{"Union": [{"steps":[...]}, {"steps":[...]}]}`
- `{"Choose": {"condition": <Predicate>, "then_traversal": {"steps":[...]}, "else_traversal": null}}`
- `{"Coalesce": [{"steps":[...]}, ...]}`
- `{"Optional": {"steps":[...]}}`

**Repeat:**
- `{"Repeat": {"traversal": {"steps":[{"Out":null}]}, "times": 3, "until": null, "emit": "After", "emit_predicate": null, "max_depth": 100}}`
- `emit` is one of `"None"`, `"Before"`, `"After"`, `"All"`

**Projections (terminal):**
- `{"Values": ["name", "email"]}`
- `{"ValueMap": ["$id", "name", "metadata.externalID"]}` or `{"ValueMap": null}` for all top-level stored properties
- `{"Project": [{"source":"name","alias":"name"}, {"source":"$from.resource_id","alias":"from_id"}, {"alias":"age_plus_one","expr":{"Add":[{"Property":"age"},{"Constant":{"I64":1}}]}}]}` — **no `{"Property":...}` / `{"Expr":...}` wrapper** (untagged)
- `"EdgeProperties"` — unit variant

**Terminals (scalar result):**
- `"Count"`, `"Exists"`, `"Id"`, `"Label"`

**Mutations** (write-only):
- `{"AddN": {"label": "User", "properties": [["name", {"Value": {"String": "Alice"}}]]}}`
- `{"AddE": {"label": "FOLLOWS", "to": {"Ids":[42]}, "properties": []}}`
- `{"SetProperty": ["name", {"Value": {"String": "Bob"}}]}`, `{"RemoveProperty": "temp"}`
- `"Drop"` — delete current nodes & their edges
- `{"DropEdge": {"Ids": [42]}}`, `{"DropEdgeLabeled": {"to": {...}, "label": "X"}}`, `{"DropEdgeById": {"Ids": [7]}}`

**Indexes** (write-only):
- `{"CreateIndex": {"spec": <IndexSpec>, "if_not_exists": true}}`, `{"DropIndex": {"spec": <IndexSpec>}}`
- Legacy vector/text convenience steps: `{"CreateVectorIndexNodes": {...}}`, `CreateVectorIndexEdges`, `CreateTextIndexNodes`, `CreateTextIndexEdges`

**Reserved (currently no-ops — safe to include but have no effect):** `"Fold"`, `"Unfold"`, `"Path"`, `"SimplePath"`, `{"WithSack": <PropertyValue>}`, `{"SackSet": "prop"}`, `{"SackAdd": "prop"}`, `"SackGet"`.

## Virtual Fields

Available in projections, `value_map`, and `Has` predicates without being declared in your schema:

- `$id` — node or edge id
- `$label` — node or edge label
- `$distance` — on vector / text search hits; order is ascending (smaller = closer)
- `$score` — on ranked text/vector hits when the engine provides a score
- `$from`, `$to` — on edge streams (including `edge_properties`) and edge vector/text hits

**Distance lifecycle:** `$distance` is present on the direct hit stream produced by `VectorSearchNodes` / `VectorSearchEdges` / `TextSearchNodes` / `TextSearchEdges`. It is *lost* once traversal steps off the hit stream (`Out`, `In`, `Both`, `OutN`, `InN`, `OtherN`). Project the distance before navigating if you need to keep it.

## Parameter Typing Rules

Use `parameter_types` when Helix must coerce JSON into a specific parameter type. Every type string is a `QueryParamType`.

### Type string encoding

Unit scalars serialize as bare strings:

```text
"Bool" | "I64" | "F64" | "F32" | "String" | "DateTime" | "Bytes" | "Value" | "Object"
```

`Array` is a single-field tuple variant — it wraps its element type:

```json
{"Array": "String"}                     // array of strings
{"Array": {"Array": "F64"}}             // array of arrays of F64
{"Array": "Object"}                     // array of objects
```

Required any time the value needs a non-default interpretation: `DateTime`, typed scalar coercion, or arrays whose element shape the runtime must know.

### DateTime

```json
{
  "parameters":      {"created_after": "2026-04-05T10:00:00Z"},
  "parameter_types": {"created_after": "DateTime"}
}
```

Accepted value forms: RFC3339 string, epoch-millis integer. **No implicit coercion** — a plain string parameter without the type declaration is just a string.

### Typed array example

```json
{
  "parameters":      {"statuses": ["active", "pending"]},
  "parameter_types": {"statuses": {"Array": "String"}}
}
```

### Vector array example

```json
{
  "parameters":      {"query_vector": [0.12, 0.44, 0.91]},
  "parameter_types": {"query_vector": {"Array": "F64"}}
}
```

### Unsupported Bytes

Do not send `Bytes` parameters through the JSON dynamic route. The builder raises `UnsupportedBytesParameter` and the gateway cannot round-trip the shape.

## Read Versus Write Rules

- `request_type: "read"` — no mutation / index step may appear anywhere in the AST.
- `request_type: "write"` — allowed to mix read steps and mutation / index steps in the same batch.

Dynamic requests do not support a `"mcp"` request type. That's only for the MCP tool surface.

If the inline AST contains a write step, the request must also be marked `"write"` — the gateway uses `request_type` to pick the transaction kind.

## Query Warming

Dynamic query warming uses the same request body plus the header:

```text
X-Helix-Warm: true
```

Rules:

- only supported for reads
- rejected for writes
- successful warm requests return `204 No Content`

Setting this header (and `Authorization: Bearer`) by hand is only needed on this raw JSON route — the TS/Rust SDK clients set them for you via `.warmOnly()` / `.warm_only()` and `.withApiKey()` / `.with_api_key()` (see `helix-query-typescript` / `helix-query-rust`).

## Practical Workflow

1. Locate or generate the exact inline `query` AST first — either serialize from a Rust `DynamicQueryRequest::read(...).to_json_string()` or copy from a test fixture.
2. Add `query_name` if the query should appear by name in logs and diagnostics.
3. Add `parameters` only for the names the AST expects.
4. Add `parameter_types` for `DateTime`, typed arrays, and any other parameters needing schema-aware coercion.
5. Validate that the body contains one inline route object, not a full query bundle.
6. If warming, ensure the request is read-only and add `X-Helix-Warm: true`.

## Anti-Patterns

Do not:

- send the full `queries.json` file under `query` — send a single route (the `ReadBatch` / `WriteBatch` inline)
- use `name` or `queryName` for request naming — the gateway only accepts top-level `query_name`
- send a blank or whitespace-only `query_name`
- use `"mcp"` as the dynamic request type
- capitalize `"Read"` / `"Write"` in `request_type` — the enum is lowercase
- rely on implicit `DateTime` parsing without `parameter_types`
- send `Bytes` parameters
- invent inline AST variant names such as `N.Id` when the parser expects `N.Ids`, `N.Var`, or `N.Param`. The parser rejects with `unknown variant 'Id', expected one of 'Ids', 'Var', 'Param'`. Same foot-gun for `Has` (single vs array), `OrderBy` ordering (always `[prop, Order]`, not `{prop: Order}`), and `Project` entries (no `{"Property": ...}` / `{"Expr": ...}` wrapper — the enum is untagged).
- hand-wave typed array encoding if you have not verified it locally — copy from `tests/register_metadata_tests.rs` or a recorded request
- wrap `Projection` entries with a variant tag — `Projection` is `#[serde(untagged)]`
- wrap top-level parameter values with variant tags — `DynamicQueryValue` is untagged (bare JSON)
- default to dynamic queries for stable production traffic

## Validation Checklist

Before finishing:

- [ ] target endpoint is `POST /v1/query`
- [ ] `request_type` is `"read"` or `"write"` (lowercase)
- [ ] `query_name`, if present, is the exact top-level field name, non-blank, and not an alias such as `name` or `queryName`
- [ ] `query` is a single inline route object (a `ReadBatch` or `WriteBatch`), not a bundle
- [ ] `queries[*]` entries are `{"Query": {...}}` or `{"ForEach": {...}}`, each `Query` has `name`, `steps`, `condition`
- [ ] unit-variant steps are encoded as bare strings (`"Count"`, `"Dedup"`, `"Exists"`, `"Id"`, `"Label"`, `"OutN"`, `"InN"`, `"OtherN"`, `"EdgeProperties"`, `"Drop"`)
- [ ] tuple-variant steps with 2+ fields use arrays (`{"Has": ["name", {"String": "v"}]}`)
- [ ] struct-variant steps use objects (`{"VectorSearchNodes": {"label": ...}}`)
- [ ] `Project` entries have no variant wrapper (untagged enum)
- [ ] inner AST values use tagged `PropertyValue` (`{"I64": 1}`); top-level `parameters` values are bare JSON (`1`)
- [ ] `parameter_types` covers every parameter that needs typed coercion (`DateTime`, typed arrays)
- [ ] `DateTime` parameters are RFC3339 strings or epoch-millis integers **and** declared in `parameter_types`
- [ ] no `Bytes` parameters
- [ ] warming is only applied to reads
- [ ] if the AST contains any mutation or index step, `request_type` is `"write"`

## Source References

Authoritative source files (for when the reference answer is ambiguous). The canonical AST lives in the `helix-db` crate at `sdks/rust/src/dsl.rs`:

- `sdks/rust/src/dsl.rs:2606-3062` — `Step` enum (every variant)
- `sdks/rust/src/dsl.rs:1564` — `Predicate`; `:1619` — `SourcePredicate`
- `sdks/rust/src/dsl.rs:1368` — `Expr`
- `sdks/rust/src/dsl.rs:973` — `PropertyValue`; `:1197` — `PropertyInput`
- `sdks/rust/src/dsl.rs:1241` / `:1308` — `NodeRef` / `EdgeRef`
- `sdks/rust/src/dsl.rs:1988-2062` — `PropertyProjection` / `ExprProjection` / `Projection` (untagged)
- `sdks/rust/src/dsl.rs:2350` — `RepeatConfig`; `:2084` — `EmitBehavior`
- `sdks/rust/src/dsl.rs:2427` — `IndexSpec`
- `sdks/rust/src/dsl.rs:4142` / `:4168` / `:4156` — `BatchCondition`, `BatchEntry`, `NamedQuery`
- `sdks/rust/src/dsl.rs:4190` / `:4280` / `:4365` — `ReadBatch` / `WriteBatch` / `BatchQuery` (untagged)
- `sdks/rust/src/dsl.rs:4448` / `:4458` / `:4480` — `DynamicQueryRequestType` (lowercase), `DynamicQueryValue` (untagged), `DynamicQueryRequest`
- `sdks/rust/src/query_generator.rs:10` — `QueryParamType`
- `sdks/rust/src/dsl.rs:4593` and `sdks/rust/src/lib.rs:200` (`mod tests`), `sdks/typescript/test/basic.test.ts` — ground-truth serialized examples
