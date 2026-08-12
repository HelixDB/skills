---
name: helix-query-json-dynamic
description: Author and debug direct HelixDB v3 JSON query requests for POST /v2/query. Use for request envelopes, nested read/write batches, operation-tree AST nodes, parameters and parameter_types, BM25 traversal prefiltering, and normalized response objects. Do not use the removed step-array or queries.json bundle formats.
license: MIT
metadata:
  author: HelixDB
  version: 3.0.0
---

# HelixDB v3 JSON Requests

Use this skill when a caller needs raw JSON rather than a v3 SDK builder. A request is
one direct operation-tree query sent to `POST /v2/query`.

## Request contract

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

The envelope rules are strict:

- `request_type` is lowercase `read` or `write`.
- `query_name` is optional. When present it must be non-empty.
- `query` contains exactly one `read` or `write` batch matching `request_type`.
- A batch contains ordered `entries` and `returns`.
- A normal entry is `{ "query": { "name": "...", "root": { ... } } }`.
- A `for_each` entry is `{ "for_each": { "param": "...", "body": [...] } }`.
- Every operation and enum variant is `snake_case`.
- Chained operations nest the previous operation under `input`; there is no `steps`
  array.
- `parameters` and `parameter_types` are optional top-level maps.

## Build nested operation trees

The builder chain:

```ts
g().nWithLabel("User").where(Predicate.eq("status", "active")).limit(25)
```

serializes from the outside inward:

```json
{
  "limit": {
    "input": {
      "where": {
        "input": {
          "nodes_where": {
            "predicate": {
              "eq": {
                "left": { "property": "$label" },
                "right": { "constant": { "string": "User" } }
              }
            }
          }
        },
        "predicate": {
          "eq": {
            "left": { "property": "status" },
            "right": { "constant": { "string": "active" } }
          }
        }
      }
    },
    "count": { "literal": 25 }
  }
}
```

Do not flatten this into a list. The nested tree is the v3 wire contract.

### Traversal-scoped BM25 prefilter

Wrap the candidate operation under `text_search_nodes_within` or
`text_search_edges_within`:

```json
{
  "text_search_nodes_within": {
    "input": {
      "nodes": { "reference": { "param": "candidate_ids" } }
    },
    "label": "Document",
    "property": "body",
    "tenant_value": { "expr": { "param": "tenant_id" } },
    "query_text": { "expr": { "param": "query" } },
    "k": { "expr": { "param": "limit" } }
  }
}
```

This ranks only the unique IDs produced by `input`. Source variants
`text_search_nodes` and `text_search_edges` search the whole tenant partition.
Use the same tenant partition for candidates and search.

## Literals, parameters, and references

Property literals use a tagged `PropertyValue`:

```json
{
  "string": "Alice"
}
```

Operation arguments that may be either literals or expressions use
`PropertyInput`:

```json
{
  "value": { "string": "Alice" }
}
```

```json
{
  "expr": { "param": "limit" }
}
```

Batch results are referenced by name:

```json
{
  "nodes": {
    "reference": { "var": "alice" }
  }
}
```

Parameters are untagged JSON values in `parameters` and their schemas are
`snake_case` values in `parameter_types`:

```json
{
  "parameters": {
    "tenant_id": "acme",
    "limit": 25
  },
  "parameter_types": {
    "tenant_id": "string",
    "limit": "i64"
  }
}
```

## Execute a request

```bash
curl -sS http://localhost:6969/v2/query \
  -H 'content-type: application/json' \
  --data-binary @request.json
```

For Helix Cloud GA, send both the Bearer API key and tenant context:

```bash
curl -sS "${HELIX_URL%/}/v2/query" \
  -H 'content-type: application/json' \
  -H "authorization: Bearer ${HELIX_API_KEY}" \
  -H "x-helix-tenant-id: ${HELIX_TENANT_ID}" \
  --data-binary @request.json
```

`HELIX_TENANT_ID` is an application-side variable in this example; the wire
contract is the `x-helix-tenant-id` header. Omitting it in GA mode returns
`400` with code `TENANT_ID_REQUIRED`.

### Warm a read

Add `X-Helix-Warm: true` to an ordinary read request. Helix Cloud fans the read
out to every eligible backend and returns `204 No Content` with no query body
after at least one succeeds. Add `X-Helix-Require-Writer: true` to target only
the authoritative writer. Partial backend failure is best-effort success; if
every target fails, the normal deterministic error is returned. A managed
cluster with no eligible target returns `503 Service Unavailable`.

The standalone `v0.0.3` runtime instead warms its single process and returns
`200 OK` with the normal query body. Header values `false` and `0` use the
ordinary query path; warm writes and any other header value return
`400 Bad Request`.

For the CLI, use the same file directly:

```bash
helix query local --file request.json
```

## Response contract

Returned names become top-level object keys. Graph elements are normalized into
user-facing objects; internal interpreter rows such as `current` and `bindings` are
not part of the response.

```json
{
  "alice": [{ "$id": 0 }],
  "bob": [{ "$id": 1 }],
  "friends": [{ "$id": 1, "name": "Bob" }]
}
```

## Never emit

- a `queries.json` bundle
- stored-route names or registration metadata
- `{ "queries": [...], "returns": [...] }`
- `{ "Query": { "steps": [...] } }`
- PascalCase variants such as `"Count"` or `"NodesWhere"`
- `request_type` values other than lowercase `read` or `write`
- a `read` batch containing write operations

See `REFERENCE.md` for the wire-shape catalog and `EXAMPLES.md` for complete requests.
The canonical public documentation is
[`docs.helix-db.com/database/helix-db/core-concepts/overview`](https://docs.helix-db.com/database/helix-db/core-concepts/overview).
