---
name: helix-query-python
description: Write and revise HelixDB queries with the Python SDK (helix-db, imported as helixdb). Use when building dynamic Helix queries in Python with read_batch, write_batch, g(), traversal builders, projections, parameters, query bundles, vector/BM25 search, and the dependency-free Client. Pythonic snake_case API; emits the same dynamic POST /v1/query JSON AST as the Rust, TypeScript, and Go SDKs.
license: MIT
metadata:
  author: HelixDB
  version: 0.1.0
---

# Helix Query Authoring - Python

Write HelixDB Python SDK queries that are schema-aware, explicit, and easy for application code to call. The package is `helix-db`, imported as `helixdb`. The Python API is intentionally snake_case (`read_batch`, `write_batch`, `var_as`, `value_map`, `to_dynamic_request`) while keeping compatibility aliases for users translating TypeScript examples.

The Python DSL emits the same dynamic-query JSON AST as the Rust, TypeScript, and Go SDKs. Use the built-in `Client` to POST dynamic requests to `/v1/query` or stored route calls to `/v1/query/{name}`.

## When To Use

Use this skill when the task is to:

- write a new Helix query in Python
- revise an existing Python query function
- produce a dynamic `POST /v1/query` request with `to_dynamic_json` / `to_dynamic_request`
- send a request with `Client(...).query().dynamic(request).send()`
- generate a query bundle with `define_queries`, `register_read`, and `register_write`
- add traversal, projection, pagination, BM25 text search, or vector search to Python code
- translate a Rust or TypeScript DSL query into Python

Do not use this skill for hand-authored JSON AST payloads; use `helix-query-json-dynamic` for wire-format work. For Rust, TypeScript, or Go source, use the language-specific skill.

## First Steps

Before writing code:

1. Inspect the local repo for existing labels, edge labels, properties, response models, and query functions.
2. Reuse exact casing such as `tenantId`, `externalId`, `FOLLOWS`, or `Document`.
3. Decide whether the query is read-only (`read_batch`) or write-capable (`write_batch`).
4. Anchor as narrowly as possible: ID, indexed property, scoped label, then broad scan.
5. Open `REFERENCE.md` for method names before inventing a builder.

## Core Rules

### 1. Start With The Right Batch

```python
from helixdb import g, read_batch, write_batch

read_batch().var_as("users", g().n_with_label("User")).returning(["users"])
write_batch().var_as("user", g().add_n("User", {"name": "Alice"})).returning(["user"])
```

`ReadBatch.var_as` rejects write traversals. `WriteBatch.var_as` accepts read-only and write traversals.

### 2. Use Pythonic Names

Prefer snake_case in Python code:

- `read_batch()` / `write_batch()`
- `.var_as(...)`, `.var_as_if(...)`, `.for_each_param(...)`
- `.n_with_label(...)`, `.value_map(...)`, `.order_by(...)`
- `.to_dynamic_request(...)`, `.to_dynamic_json(...)`
- `Client(...).with_api_key(...)`, `.warm_only()`, `.writer_only()`, `.should_await_durability(True)`

Compatibility aliases such as `readBatch`, `varAs`, and `valueMap` exist for translation, but do not use them in fresh Python.

### 3. Parameterize Request-Specific Values

Define parameter schemas once and pass `ParamRef` values into predicates, bounds, property inputs, source refs, and search inputs:

```python
from helixdb import Predicate, define_params, g, param, read_batch

params = define_params({"tenant_id": param.string(), "limit": param.i64()})

def find_users(p=params):
    return (
        read_batch()
        .var_as(
            "users",
            g()
            .n_with_label("User")
            .where(Predicate.eq("tenantId", p.tenant_id))
            .limit(p.limit)
            .value_map(["$id", "name", "tenantId"]),
        )
        .returning(["users"])
    )
```

Direct values are serialized as literals in the AST. Use direct values only for constants; use params for values that change per request so the request shape stays stable.

### 4. Produce Dynamic Requests Explicitly

```python
request = find_users().to_dynamic_request(
    params,
    {"tenant_id": "acme", "limit": 25},
    query_name="find_users",
)
```

- `to_dynamic_request(...)` returns a `DynamicQueryRequest` object.
- `to_dynamic_json(...)` returns the JSON string for `POST /v1/query`.
- Omit `query_name` for ad-hoc requests (`query_name: null`); set it for logs and diagnostics.
- If you pass parameter values without a schema, the SDK raises `TypeError`.

### 5. Execute With `Client`

```python
from helixdb import Client, HelixError

client = Client("https://helix.example.com", api_key="hx_secret")

try:
    response = client.query().dynamic(request).send()
except HelixError as error:
    if error.kind == "Remote":
        raise RuntimeError(error.details) from error
```

Transport toggles are request-builder methods:

```python
client.query().writer_only().should_await_durability(True).dynamic(write_request).send()
client.query().warm_only().dynamic(read_request).send()
client.query().body({"tenant_id": "acme"}).stored("find_users").send()
```

Prefer `should_await_durability(True)` on writes. It reduces HTTP 409 conflicts under concurrent writers, but the SDK does not retry conflicts; application code owns retry policy and idempotency.

### 6. Shape Responses Deliberately

- Use `.project([...])` for stable service-facing response shapes.
- Use `.value_map(["$id", "name"])` when returning selected properties is fine.
- For edge endpoint properties, prefer edge-stream `.project([...])` with
  `Projection.from_endpoint(prop, alias)` / `Projection.to_endpoint(prop,
  alias)` instead of traversing to every endpoint first.
- Avoid returning large properties such as embeddings unless the caller needs them.
- Match `.returning([...])` names to the response keys your application expects.

> **Row bindings are not available in the Python SDK yet.** The `bind` /
> `project_bindings` / `project_distinct_bindings` multi-hop correlation steps
> exist in the Rust, TypeScript, and Go SDKs but not in Python. If you need them
> from Python, hand-write the `Bind` / `ProjectBindings` JSON AST (see
> `helix-query-json-dynamic`) or generate the query from another SDK.

### 7. Use Bundles Only When Needed

Python supports the same bundle metadata shape as TypeScript:

```python
from helixdb import define_queries, register_read

queries = define_queries({
    "read": {"find_users": register_read(find_users, params)},
})

request = queries.call.find_users({"tenant_id": "acme", "limit": 25})
queries.generate("queries.json")
```

Use bundles when your deployment or runtime workflow consumes `queries.json`. For direct dynamic calls, `to_dynamic_request` is simpler.

## Validation Checklist

Before finishing:

- verify read queries use `read_batch` and writes use `write_batch`
- verify write traversals are not placed in read batches
- verify request-specific values use `define_params` refs instead of direct literals
- verify `.returning([...])` names match the expected response shape
- verify vector/text search preserves tenant scope when the index is scoped
- verify `$distance` is projected before traversing away from search hits
- verify write callers use explicit conflict retry only when safe to replay
- run the Python tests or at minimum serialize the request and inspect the JSON

## Companion Files

- `REFERENCE.md` - Python builder catalog and signatures.
- `EXAMPLES.md` - canonical Python query functions for reads, writes, search, branching, bundles, and execution.
