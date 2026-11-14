# Direct Query Examples

Canonical HelixDB v3 `POST /v2/query` requests. Cross-SDK contracts:
[source-canon.md](source-canon.md#contracts-every-query-skill-repeats).

## Core rules

- `request_type` is lowercase `read` or `write`.
- `query_name` is optional.
- `query` contains exactly one matching `read` or `write` batch.
- Each batch has ordered `entries` and `returns`.
- Operations form a nested `snake_case` tree; each chained operation wraps its
  predecessor under `input`.
- `parameters` and `parameter_types` are optional. When `parameter_types` is
  present, its keys exactly match `parameters`; typed and untyped values cannot
  be mixed in one request.
- One direct request per call; no stored routes or query bundles.
- Query warming is read-only.
- Node and edge IDs are JSON integers.
- A read may set `"search_consistency": "eventual"` (default `strong`).
- Cypher and SQL go to `POST /v2/cypher` / `POST /v2/sql` (and `/explain`) with
  `{"query", "parameters", "query_name"}`; use `/v2/query` for what their
  profiles reject (`MERGE`, variable-length paths, `UNION`, subqueries,
  `FOREACH`, search, index management).

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

Runtime values are ordinary JSON; add `parameter_types` when the SDK/query
declares them (the full request still needs the envelope and batch):

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

- Descriptors: `bool`, `i64`, `f32`, `f64`, `string`, `date_time`, `value`,
  `object`, recursive `array`. Raw bytes cannot be represented.
- Typed `f32`/`f64` accept integer and floating-point JSON numbers; values must
  be finite and `f32` within its finite range. Floats may be untyped, but a
  supplied `parameter_types` must describe every parameter.
- Body limit: 16 MiB locally (`400 invalid_request_body`), 2 MiB on Helix Cloud
  (`413 payload_too_large`); keep portable bodies ≤ 2 MiB. Nesting over 255
  levels is `400 invalid_query_json`.

## Write request

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

Response on a clean `ghcr.io/helixdb/helixdb:v0.0.16` instance (an unprojected
node is only its `$id`):

```json
{
  "user": [{ "$id": 0 }]
}
```

Row-stream returns are arrays (`[]` when empty); an empty `returns` list
produces `{}`. Writes wait for durability unless `X-Helix-Await-Durable: false`
is sent (see source-canon for both contracts).

## Query warming

Send the same read body with `X-Helix-Warm: true` (or `1`; `false`/`0` is the
ordinary path).

- Local server: executes the read and returns `200 OK` with the normal response.
- Helix Cloud: the gateway fans the read out to every eligible backend, discards
  the responses and returns `204 No Content` once one target succeeds (partial
  failure still `204`; all failing returns the normal error).
  `X-Helix-Require-Writer: true` warms only the writer. No eligible target is
  `503 Service Unavailable`.
- Any other header value, or a warm write, is `400` (`invalid_request_option`
  locally) before execution. Auth, read rate limits, retries and query timeouts
  still apply.
- The Cloud `204`: TypeScript 3.2.0 accepts it (`send()` resolves `undefined`);
  published Rust 3.0.0, Python 0.3.4 and Go 0.3.1 accept only 200 and surface
  it as a remote error (SDK `main` accepts it), so warm Cloud over direct HTTP
  from those.
- The CLI's `--warm` flag is local-only; it cannot warm a Cloud database.

## Query Failures

Non-success responses, including through the Cloud gateway, are
`{"error":"<code>","msg":"<diagnostic>","retryable":true|false}`. Both
`transaction_conflict` (`retryable: true`) and `unique_constraint_violation`
(`retryable: false`) are HTTP 409: branch on `error`/`retryable`, never on the
status or `msg`. No `code` field; keep unknown codes as open strings. Classes,
actions and Cloud gateway codes: [error-handling.md](error-handling.md).

## Common mistakes

Do not:

- put a route-name string under `query`
- send a query-bundle file
- use `mcp` as `request_type`
- use the obsolete `queries` plus `steps` AST
- use PascalCase enum tags
- mismatch `request_type` and the batch variant
- reverse the `error` and `msg` meanings, require a `code` field, or retry
  every 409
- send node or edge IDs as strings
- document internal `current`/`bindings` rows as the response

## See also

- [source-canon.md](source-canon.md), [error-handling.md](error-handling.md),
  [dsl-cheatsheet.md](dsl-cheatsheet.md),
  `skills/helix-query-json-dynamic/REFERENCE.md`
- `https://docs.helix-db.com/openapi.json`
- `https://docs.helix-db.com/database/helix-db/query-guides/{http-api,error-handling,search-consistency,cypher,sql}`
- `https://docs.helix-db.com/database/helix-cloud/operate/{error-handling,limits}`
- `https://docs.helix-db.com/database/helix-db/core-concepts/overview`
