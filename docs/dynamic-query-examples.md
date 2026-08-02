# Direct Query Examples

Canonical examples for HelixDB v3 `POST /v2/query` requests.

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

On the standalone `ghcr.io/helixdb/helixdb:v0.0.1` runtime, a warm read executes
on the single process and returns `200 OK` with the normal normalized response.

On Helix Cloud, the `/v2/query` gateway fans the same read out to every eligible
database backend, discards the query responses, and returns `204 No Content`
after at least one target succeeds. Partial backend failure still returns `204`;
if every target fails, the gateway returns the normal deterministic error. Add
`X-Helix-Require-Writer: true` to warm only the authoritative writer.

`X-Helix-Warm: true` or `1` enables warming; `false` or `0` uses the ordinary
query path. Any other value returns `400 Bad Request`. A warm write is rejected
with `400 Bad Request` before backend execution, and a managed cluster with no
eligible warming target returns `503 Service Unavailable`. Authentication, read
rate limits, retries, and normal query timeouts still apply.

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
