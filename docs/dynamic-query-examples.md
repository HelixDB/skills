# Direct Query Examples

Canonical examples for HelixDB v3 `POST /v1/query` requests.

## Core rules

- `request_type` is lowercase `read` or `write`.
- `query_name` is optional.
- `query` contains exactly one matching `read` or `write` batch.
- Each batch has ordered `entries` and `returns`.
- Operations form a nested `snake_case` tree; each chained operation wraps its
  predecessor under `input`.
- `parameters` and `parameter_types` are optional.
- The route accepts one direct request, not a stored route or query bundle.
- Query warming is read-only.

## Minimal read request

```json
{
  "request_type": "read",
  "query_name": "node_count",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "node_count",
            "root": {
              "count": {
                "input": {
                  "nodes_where": {
                    "predicate": {
                      "eq": {
                        "left": { "property": "$label" },
                        "right": { "constant": { "string": "User" } }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      ],
      "returns": ["node_count"]
    }
  }
}
```

## Parameters

Runtime values are ordinary JSON. Add a schema when the SDK/query declares one:

```json
{
  "parameters": {
    "created_after": "2026-04-05T10:00:00Z",
    "limit": 25
  },
  "parameter_types": {
    "created_after": "date_time",
    "limit": "i64"
  }
}
```

The full request still needs the normal envelope and query batch.

## Write request

A write request uses `request_type: "write"` and a `write` batch:

```json
{
  "request_type": "write",
  "query_name": "create_user",
  "query": {
    "write": {
      "entries": [
        {
          "query": {
            "name": "user",
            "root": {
              "add_n": {
                "label": "User",
                "properties": [
                  ["name", { "value": { "string": "Alice" } }]
                ]
              }
            }
          }
        }
      ],
      "returns": ["user"]
    }
  }
}
```

On a clean `ghcr.io/helixdb/helixdb:v0.0.1` instance, the response is normalized:

```json
{
  "user": [{ "$id": 0 }]
}
```

## Query warming

For a direct read request, warming uses the same body plus:

```text
X-Helix-Warm: true
```

Successful warm reads return `200 OK` with the normal normalized JSON response
while populating caches. Write warming is rejected.

## Common mistakes

Do not:

- put a route-name string under `query`
- send a query-bundle file
- use `mcp` as `request_type`
- use the obsolete `queries` plus `steps` AST
- use PascalCase enum tags
- mismatch `request_type` and the batch variant
- document internal `current`/`bindings` rows as the response

## See also

- `docs/source-canon.md`
- `docs/dsl-cheatsheet.md`
- `skills/helix-query-json-dynamic/REFERENCE.md`
- `https://docs.helix-db.com/database/helix-db/core-concepts/overview`
