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

For raw HTTP JSON, use `bool`, `i64`, `string`, `date_time`, `value`, `object`,
and recursive `array` descriptors. Send floating-point JSON values without
`parameter_types`; the published HTTP schema intentionally omits `f32` and
`f64`. Raw bytes cannot be represented on this JSON route. These restrictions
do not remove the typed float builders available inside the language SDKs.

Local requests may be at most 16 MiB; Helix Cloud requests may be at most
2 MiB. Keep portable request bodies at or below 2 MiB.

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

On a clean `ghcr.io/helixdb/helixdb:v0.0.4` instance, the response is normalized:

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

On the standalone `ghcr.io/helixdb/helixdb:v0.0.4` runtime, a warm read executes
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

The current published Rust 3.0.0, TypeScript 3.0.4, Python 0.3.4, and Go 0.3.1
SDK transports treat only HTTP 200 as success, so they currently surface this
Cloud `204` as a remote error. Use `helix query` or direct HTTP for Cloud warming
until an SDK release accepts `204 No Content`.

## Query Failures

Current Helix non-success responses, including responses delivered through the
Cloud query gateway, separate the stable code from the diagnostic:

```json
{"error":"transaction_conflict","msg":"transaction commit conflicted with another writer"}
```

Use HTTP status plus the open-string code in `error` for decisions; keep `msg`
for logs or display. There is no `code` field in the current Helix envelope.
During a rolling upgrade, also accept legacy
`{"error":"<diagnostic>","code":"<stable_code>"}` bodies.

A defensive client may additionally preserve a noncanonical proxy body such as:

```json
{"code":"external_error","message":"upstream rejected the request","details":{"request_id":"req_123"}}
```

Decode the canonical and legacy Helix shapes before this generic remote
fallback. Preserve structured `details`, raw JSON or plain text, and unknown
codes, but do not call `code`/`message` the gateway contract. The Cloud catalog
also distinguishes account, timeout, payload, rate-limit, and availability
failures; in particular, reconcile a timed-out write before resubmitting and
honor `Retry-After` on 429 when the transport exposes it. Reload state before
rebuilding a conflicting write and replay it only when safe; never identify a
failure by parsing the message. See `docs/error-handling.md`.

## Common mistakes

Do not:

- put a route-name string under `query`
- send a query-bundle file
- use `mcp` as `request_type`
- use the obsolete `queries` plus `steps` AST
- use PascalCase enum tags
- mismatch `request_type` and the batch variant
- reverse the current `error` and `msg` meanings, require a current `code`
  field, call generic `code`/`message` the gateway contract, or discard raw
  remote details
- document internal `current`/`bindings` rows as the response

## See also

- `docs/source-canon.md`
- `docs/error-handling.md`
- `docs/dsl-cheatsheet.md`
- `skills/helix-query-json-dynamic/REFERENCE.md`
- `https://docs.helix-db.com/openapi.json`
- `https://docs.helix-db.com/database/helix-db/query-guides/http-api`
- `https://docs.helix-db.com/database/helix-cloud/operate/error-handling`
- `https://docs.helix-db.com/database/helix-cloud/operate/limits`
- `https://docs.helix-db.com/database/helix-db/core-concepts/overview`
