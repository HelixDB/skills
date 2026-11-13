# Direct Query Examples

Canonical examples for HelixDB v3 `POST /v2/query` requests.

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
- The route accepts one direct request, not a stored route or query bundle.
- Query warming is read-only.
- Node and edge IDs are integers; send ID parameters as JSON integers.
- A read may set `"search_consistency": "eventual"`; the default is `strong`.
- Cypher and SQL statements go to `POST /v2/cypher` / `POST /v2/sql` (and
  `/explain`) with `{"query", "parameters", "query_name"}`; use `/v2/query` for
  what their profiles reject (`MERGE`, variable-length paths, `UNION`,
  subqueries, `FOREACH`, search, index management).

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

For raw HTTP JSON, use `bool`, `i64`, `f32`, `f64`, `string`, `date_time`, `value`,
`object`, and recursive `array` descriptors. Typed `f32`/`f64` accept integer
and floating-point JSON numbers. Values must be finite; `f32` values must fit
within its finite range. Floating-point parameters may also be untyped, but a
supplied `parameter_types` map must describe every parameter. Raw bytes cannot
be represented on this route.

A local body over 16 MiB is `400 invalid_request_body`; Helix Cloud rejects
bodies over 2 MiB with `413 payload_too_large`. JSON nested deeper than 255
levels is `400 invalid_query_json`. Keep portable request bodies at or below
2 MiB.

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

On a clean `ghcr.io/helixdb/helixdb:v0.0.16` instance, the response is normalized;
an unprojected node returns only its `$id`:

```json
{
  "user": [{ "$id": 0 }]
}
```

Every row-stream return is an array and `[]` when empty, including at-most-one
lookups, `limit(1)` and skipped `var_as_if` entries. Only `count` (`0`),
`exists` (`false`) and index DDL / lifecycle results are scalars or objects. An
empty `returns` list produces `{}`.

Writes wait for durability unless the request sends
`X-Helix-Await-Durable: false`, which trades crash durability for latency and
does not reduce conflicts. Sending `true` on a read is `400
invalid_request_option`.

## Query warming

For a direct read request, warming uses the same body plus:

```text
X-Helix-Warm: true
```

On a standalone local server, a warm read executes on that process and returns
`200 OK` with the normal normalized response.

On Helix Cloud, the `/v2/query` gateway fans the same read out to every eligible
database backend, discards the query responses, and returns `204 No Content`
after at least one target succeeds. Partial backend failure still returns `204`;
if every target fails, the gateway returns the normal deterministic error. Add
`X-Helix-Require-Writer: true` to warm only the authoritative writer.

`X-Helix-Warm: true` or `1` enables warming; `false` or `0` uses the ordinary
query path. Any other value, or a warm write, returns `400`
(`invalid_request_option` locally) before execution, and a managed cluster with no
eligible warming target returns `503 Service Unavailable`. Authentication, read
rate limits, retries, and normal query timeouts still apply.

TypeScript 3.2.0 accepts this `204`; its `send()` resolves `undefined`. The
current published Rust 3.0.0, Python 0.3.4, and Go 0.3.1 SDK transports treat
only HTTP 200 as success, so they surface this Cloud `204` as a remote error.
From those SDKs, use direct HTTP for Cloud warming until a release accepts
`204 No Content`.

The CLI's `--warm` flag is local-only and cannot warm a Cloud database. Current
SDK source accepts 204, but that fix is absent from the published Rust, Python,
and Go versions.

## Query Failures

Non-success responses, including through the Cloud gateway, carry the code in
`error`, the diagnostic in `msg`, and `retryable` when the code's class settles
it:

```json
{"error":"transaction_conflict","msg":"<diagnostic>","retryable":true}
```

```json
{"error":"unique_constraint_violation","msg":"<diagnostic>","retryable":false}
```

Both are HTTP 409. Branch on `retryable` and `error`, never on the status alone
or on `msg`:

- `retryable: true` (`transaction_conflict`, `request_read_view_changed`,
  `stale_index_generation`, `index_backpressure`): resend with bounded backoff
  and jitter.
- `retryable: false` 409 (`unique_constraint_violation`, `index_busy`,
  `index_build_blocked`, `index_already_exists`, `index_definition_conflict`,
  `index_operation_not_abortable`): resending unchanged fails again.
- A write may have committed after `408 query_deadline_exceeded`, a 500, `503
  writer_fenced_commit_outcome_unknown`, or the Cloud gateway's `408
  query_timeout` / `503 write_outcome_unknown`: reconcile before resubmitting.
- Cloud `429 rate_limited` did not execute: honor `Retry-After`.

There is no `code` field. Keep unknown codes as open strings. The full code
table is in `docs/error-handling.md`.

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

- `docs/source-canon.md`
- `docs/error-handling.md`
- `docs/dsl-cheatsheet.md`
- `skills/helix-query-json-dynamic/REFERENCE.md`
- `https://docs.helix-db.com/openapi.json`
- `https://docs.helix-db.com/database/helix-db/query-guides/http-api`
- `https://docs.helix-db.com/database/helix-db/query-guides/error-handling`
- `https://docs.helix-db.com/database/helix-db/query-guides/search-consistency`
- `https://docs.helix-db.com/database/helix-db/query-guides/cypher`
- `https://docs.helix-db.com/database/helix-db/query-guides/sql`
- `https://docs.helix-db.com/database/helix-cloud/operate/error-handling`
- `https://docs.helix-db.com/database/helix-cloud/operate/limits`
- `https://docs.helix-db.com/database/helix-db/core-concepts/overview`
