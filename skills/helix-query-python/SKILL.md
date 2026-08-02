---
name: helix-query-python
description: Write and revise queries with the forthcoming HelixDB v3 Python SDK (package `helix-db`, import `helixdb`). Use for `read_batch`, `write_batch`, direct `to_query_request`/`to_query_json` payloads, row bindings, traversal builders, projections, parameters, vector/BM25 search, and `Client.query`. Stored routes and query bundles are not v3 SDK APIs.
license: MIT
metadata:
  author: HelixDB
  version: 3.0.0
---

# Helix Query Authoring - Python

Write HelixDB Python SDK queries that are schema-aware, explicit, and easy for
application code to call. The forthcoming package is `helix-db`, imported as
`helixdb`. No Python package version is invented before publication.

The Python DSL emits the same direct-request JSON AST as the Rust, TypeScript,
and Go SDKs. Use the built-in `Client` to post requests to `/v2/query`.

## When To Use

Use this skill when the task is to:

- write a new Helix query in Python
- revise an existing Python query function
- produce a dynamic `POST /v2/query` request with `to_query_json` / `to_query_request`
- send a request with `Client(...).query(request)`
- retain correlated traversal values with row bindings
- add traversal, projection, pagination, BM25 text search, or vector search to Python code
- translate a Rust or TypeScript DSL query into Python

Do not use this skill for hand-authored JSON AST payloads; use
`helix-query-json-dynamic` for wire-format work. Stored routes and query
bundles are not supported by the v3 SDK.

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
- `.to_query_request(...)`, `.to_query_json(...)`
- `Client(...).with_api_key(...)`; advanced request builders expose
  `.warm_only()`, `.writer_only()`, and `.should_await_durability(True)`

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
request = find_users().to_query_request(
    params,
    {"tenant_id": "acme", "limit": 25},
    query_name="find_users",
)
```

- `to_query_request(...)` returns a `QueryRequest` object.
- `to_query_json(...)` returns the JSON string for `POST /v2/query`.
- Omit `query_name` for ad-hoc requests (`query_name: null`); set it for logs and diagnostics.
- If you pass parameter values without a schema, the SDK raises `TypeError`.

### 5. Execute With `Client`

```python
from helixdb import Client, HelixError

client = Client("https://helix.example.com", api_key="hx_secret")

try:
    response = client.query(request)
except HelixError as error:
    if error.kind == "Remote":
        raise RuntimeError(error.details) from error
```

Transport toggles are available through `execute`:

```python
client.execute(write_request, writer_only=True, await_durability=True)
client.execute(read_request, warm_only=True)
```

Prefer `await_durability=True` with `execute` or
`client.request_builder().should_await_durability(True)` on writes. This
reduces HTTP 409 conflicts under concurrent writers, but the SDK does not retry
conflicts; application code owns retry policy and idempotency.

### 6. Shape Responses Deliberately

- Use `.project([...])` for stable service-facing response shapes.
- Use `.value_map(["$id", "name"])` when returning selected properties is fine.
- For edge endpoint properties, prefer edge-stream `.project([...])` with
  `Projection.from_endpoint(prop, alias)` / `Projection.to_endpoint(prop,
  alias)` instead of traversing to every endpoint first.
- Avoid returning large properties such as embeddings unless the caller needs them.
- Match `.returning([...])` names to the response keys your application expects.

Python v3 supports row-local correlation with `bind`,
`project_bindings`, and `project_distinct_bindings`:

```python
from helixdb import BindingProjection, g, read_batch

query = (
    read_batch()
    .var_as(
        "pairs",
        g()
        .n_with_label("User")
        .bind("user")
        .out("FOLLOWS")
        .bind("friend")
        .project_distinct_bindings([
            BindingProjection.binding("user", "$id", "user_id"),
            BindingProjection.binding("friend", "$id", "friend_id"),
        ]),
    )
    .returning(["pairs"])
)
```

## Validation Checklist

Before finishing:

- verify read queries use `read_batch` and writes use `write_batch`
- verify write traversals are not placed in read batches
- verify request-specific values use `define_params` refs instead of direct literals
- verify `.returning([...])` names match the expected response shape
- verify vector/text search preserves tenant scope when the index is scoped
- verify `$distance` or `$score` is projected before traversing away from search hits
- verify write callers use explicit conflict retry only when safe to replay
- run the Python tests or at minimum serialize the request and inspect the JSON

## Companion Files

- `REFERENCE.md` - Python builder catalog and signatures.
- `EXAMPLES.md` - canonical Python query functions for reads, writes, search, branching, row bindings, and execution.
