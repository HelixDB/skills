---
name: helix-query-json-dynamic
description: Build and validate HelixDB dynamic inline-query requests for POST /v1/query. Use when the task involves dynamic queries, inline query JSON, parameter_types, DateTime coercion, query warming, or debugging a request body sent directly to the Helix gateway.
license: MIT
metadata:
  author: HelixDB
  version: 0.1.0
---

# Helix Dynamic Query JSON

Use this skill for inline dynamic query requests sent directly to `POST /v1/query`.

## When To Use

Use this skill when the task is to:

- build a dynamic Helix request body
- debug a failing `POST /v1/query` call
- add `parameter_types` to a dynamic request
- send `DateTime` parameters correctly
- understand read versus write behavior on the dynamic route
- use query warming on a dynamic read

Do not use this skill as the main guide for writing stored Rust DSL query functions. Use the authoring skill for that.

## First Steps

Before writing the payload:

1. Decide whether this should really be a stored route instead of a dynamic route.
2. Confirm whether the request is a read or a write.
3. Confirm whether the inline `query` object already exists in code, a test, or a serialized payload.
4. Identify any parameters that need explicit typing, especially `DateTime`.

If the request is part of steady-state application traffic, prefer a stored route when possible. Dynamic queries are more flexible but less optimized than stored procedures.

## Required Envelope Rules

- send requests to `POST /v1/query`
- `request_type` must be `read` or `write`
- `query` must be a single inline route object
- do not send the entire `queries.json` bundle
- `parameters` is optional
- `parameter_types` is optional until you need schema-aware coercion
- `embeddings` is optional and should only be included when the route expects it

## Canonical Request Shape

```json
{
  "request_type": "read",
  "query": {
    "queries": [
      {
        "name": "node_exists",
        "steps": ["Count"],
        "condition": null
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

## Inline AST Variant Rules

Helix parses inline query JSON strictly. Enum and step variant names must match the parser exactly.

For node selector steps like `"N": {...}`:

- use accepted variants such as `Ids`, `Var`, or `Param`
- if selecting one literal node id, still encode it under `Ids`
- do not invent singular variants from memory

Good fragments:

```json
{
  "N": {
    "Ids": [644]
  }
}
```

```json
{
  "N": {
    "Param": "entity_ids"
  }
}
```

```json
{
  "N": {
    "Var": "seed_nodes"
  }
}
```

Bad fragment:

```json
{
  "N": {
    "Id": 644
  }
}
```

That bad form is rejected by the dynamic parser with an error like:

```text
unknown variant `Id`, expected one of `Ids`, `Var`, `Param`
```

When the inline AST is large or unfamiliar, prefer copying a known-good serialized payload from code, tests, or logs instead of hand-authoring variant names from memory.

## Parameter Typing Rules

Use `parameter_types` when you need Helix to coerce JSON into a specific parameter type.

Most important cases:

- `DateTime`
- arrays whose element type matters
- objects whose shape needs to be preserved intentionally

### DateTime

If a parameter should be treated as `DateTime`, declare it explicitly:

```json
{
  "parameters": {
    "created_after": "2026-04-05T10:00:00Z"
  },
  "parameter_types": {
    "created_after": "DateTime"
  }
}
```

Helix accepts:

- RFC3339 strings
- epoch-millis integers

Do not assume a plain JSON string will be interpreted as `DateTime` without the matching type declaration.

### Typed Arrays

If an array parameter needs an explicit inner type, declare it intentionally and verify the exact encoded form in your environment before shipping.

Do not guess nested type encoding in production requests.

### Unsupported Bytes

Do not send `Bytes` parameters through the JSON dynamic route.

## Read Versus Write Rules

Use:

- `request_type: "read"` for read queries
- `request_type: "write"` for writes

Dynamic requests do not support `mcp`.

If the inline AST is a write query, the request must also be marked as `write` so the gateway can route it correctly.

## Query Warming

Dynamic query warming uses the same request body plus:

```text
X-Helix-Warm: true
```

Rules:

- only supported for reads
- rejected for writes
- successful warm requests return `204 No Content`

## Practical Workflow

1. Prefer a stored route if the query is stable and production-facing.
2. If using the dynamic route, locate or generate the exact inline `query` AST first.
3. Add `parameters` only for the names the AST expects.
4. Add `parameter_types` for `DateTime` and any other parameters that require schema-aware coercion.
5. Validate that the body contains one inline route object, not a full query bundle.
6. If warming, ensure the request is read-only and add `X-Helix-Warm: true`.

## Anti-Patterns

Do not:

- send the full `queries.json` file under `query`
- use `mcp` as the dynamic request type
- rely on implicit `DateTime` parsing without `parameter_types`
- send `Bytes` parameters
- invent inline AST variant names such as `N.Id` when the parser expects `N.Ids`, `N.Var`, or `N.Param`
- hand-wave typed array encoding if you have not verified it locally
- default to dynamic queries for stable production traffic

## Validation Checklist

Before finishing:

- verify the target endpoint is `POST /v1/query`
- verify `request_type` is `read` or `write`
- verify `query` is a single inline route object
- verify the request is not sending the full route bundle
- verify strict inline AST variant names are used, especially for node selector steps like `N.Ids`, `N.Var`, and `N.Param`
- verify `parameter_types` covers every parameter that needs typed coercion
- verify `DateTime` parameters are RFC3339 strings or epoch millis
- verify the request does not use unsupported `Bytes`
- verify warming is only applied to reads

## Repo References

For shared references in this repo, see:

- `docs/dynamic-query-examples.md`
- `docs/source-canon.md`
- `helix-skills-repo-plan.md`
