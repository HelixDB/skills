# Helix Query Error Handling

Use the stable error code for control flow and the diagnostic message for logs or user-facing context. Error messages may change; codes are compatibility identifiers.

The canonical query catalog is [Handle query errors](https://github.com/HelixDB/helix-db/blob/907ff2283240dcaf416a91d3b8a522f734a7c159/docs/database/helix-db/query-guides/error-handling.mdx). Keep the complete catalog upstream. This guide records the Helix envelope, defensive SDK compatibility behavior, and the decisions that recur across the skills.

## HTTP Contract

Helix `POST /v2/query` non-success responses use `error` for the stable code and
`msg` for the diagnostic, including responses delivered through the Cloud query
gateway:

```json
{
  "error": "index_not_found",
  "msg": "planner error: missing text index for `Document.body`"
}
```

There is no separate `code` field in the current Helix envelope. Treat `error`
as the code when `msg` is also present.

Older servers used this shape:

```json
{
  "error": "planner error: missing text index for `Document.body`",
  "code": "index_not_found"
}
```

The current Rust and TypeScript SDKs also defensively decode a generic remote
body such as:

```json
{
  "code": "external_error",
  "message": "request rejected by an upstream intermediary",
  "details": { "request_id": "req_123" }
}
```

This is compatibility handling for a noncanonical proxy/intermediary response,
not the Helix query error contract. Do not document `code`/`message` as the
gateway's canonical envelope or require a generic remote code to be a known
`QueryErrorCode` value.

For a direct HTTP consumer, decode all supported shapes in this order:

1. If `error` and `msg` are strings, use `error` as the code and `msg` as the diagnostic.
2. Otherwise, if `error` and `code` are strings, use `code` as the legacy code and `error` as the diagnostic.
3. Otherwise, preserve an optional string `code`, use a string `message` or `error` as the diagnostic, and retain structured `details` when the client surface supports it.
4. Otherwise, preserve the raw response text as the diagnostic and leave the code unset.

Codes are open strings. Preserve an unknown future code, log it, and fall back to status-aware generic handling; never reject or collapse it because a local enum or switch is older than the server.

## SDK Surfaces

| SDK | Stable-code access | Diagnostic/status access |
| --- | --- | --- |
| Rust | `QueryErrorCode`; `HelixError::error_code()`; `remote_code()` | `status_code()`, `remote_message()`, `remote_details()`, `raw_response_body()`, `is_conflict()`, `is_rate_limited()` |
| TypeScript | `HelixError.code` | `statusCode`, `serverMessage`, `serverDetails`, `rawBody`, `details`, `kind`, `isConflict()`, `isRateLimited()` |
| Go | `QueryErrorCode`; `HelixError.Code` for current/legacy Helix envelopes | `HelixError.Details`; `HelixError.StatusCode`; `IsConflict` / `ErrConflict`. A generic `message`/`code` remote body remains raw `Details` in v0.3.1. |
| Python | `HelixError.code` for current/legacy Helix envelopes | `HelixError.details`; `HelixError.status_code`; `HelixError.kind`. A generic `message`/`code` remote body remains raw `details` in v0.3.4. |

The SDK wire fields intentionally remain strings so a newer server's code survives even when the local SDK does not yet know it.

Rust and TypeScript preserve structured metadata from generic remote bodies in
addition to the canonical and legacy Helix envelopes. Their conflict and
rate-limit helpers classify the HTTP status (`409` and `429` respectively);
they do not assert a particular application code.

## Retry Decisions

Use both HTTP status and stable code. A code classifies the failure; it does not prove that replaying the operation is safe.

- Retry idempotent reads after HTTP 429 or a temporary 5xx response only with bounded backoff.
- `transaction_conflict` is the database HTTP 409 classification. For a write conflict, reload current state before rebuilding the mutation; retry only when replay is safe.
- Do not blindly retry a write after a general server or network failure. The mutation may have committed before the response failed.
- A write is safely replayable only when it is idempotent or protected by an application-level idempotency key.
- Availability or lifecycle errors may be retried after the named condition changes.
- Validation, planning, schema, and missing-index errors require a corrected request or configuration before retry.
- Treat unknown codes conservatively using their status; retain the code and diagnostic for telemetry.
- Do not parse `msg`, `message`, or exception text to identify conflicts, rate limits, or other conditions.

## gRPC And Embedded Parity

gRPC keeps the readable diagnostic in the status message and attaches the same stable code as ASCII metadata under `helix-error-code`. Use the gRPC status class and metadata together.

Embedded Rust errors expose `error_code()`. UniFFI errors carry the explicit pair `error` (code) and `msg` (diagnostic), and generated SDK bindings preserve that pair. Embedded callers should not infer a code from exception text.
