# Dynamic Query Examples

Canonical examples for Helix dynamic `POST /v1/query` requests.

## Core Rules

- send dynamic queries to `POST /v1/query`
- `request_type` must be `read` or `write`
- `query` must be a single inline route object
- do not send the entire `queries.json` bundle
- `parameters` is optional
- `parameter_types` is required when the route needs schema-aware coercion such as `DateTime`
- `Bytes` is not supported on the JSON query route
- query warming only supports reads

## Minimal Read Request

Use this as the canonical baseline shape:

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

## DateTime Parameter Fragment

When a parameter should be interpreted as a Helix `DateTime`, declare it explicitly.

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

Accepted input forms:

- RFC3339 strings
- epoch-millis integers

## Write Request Rule

Write requests use the same outer envelope but must set:

```json
{
  "request_type": "write"
}
```

The inline `query` must be a write-route AST, not a read-route AST.

If you already have the route in Rust DSL, prefer generating or copying the serialized inline-query form rather than hand-authoring a large write AST from memory.

## Query Warming

For a dynamic read query, warming uses the same body plus:

```text
X-Helix-Warm: true
```

Important:

- warming is only supported for reads
- write warming is rejected
- warm requests return `204 No Content`

## Common Mistakes

Do not:

- send a stored query name to `POST /v1/query` instead of an inline `query` object
- send the full `queries.json` bundle under `query`
- use `mcp` as `request_type`
- assume `DateTime` will coerce correctly without `parameter_types`
- send `Bytes` parameters through the JSON route

## Typed Arrays

When an array parameter needs a specific inner type, make the typing explicit in the same way you would for scalars.

If the exact encoded nested type shape is unclear in your environment, verify it locally before shipping. Do not guess typed-array encoding in a production request.

## See Also

- `docs/source-canon.md`
- `docs/dsl-cheatsheet.md`
- `https://docs.helix-db.com/enterprise/introduction`
