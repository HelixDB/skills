# Helix Query Error Handling

Use the static error code for control flow and the diagnostic message for logs or user-facing context. Error messages may change; codes are compatibility identifiers.

The canonical upstream catalog is [Handle query errors](https://github.com/HelixDB/helix-db/blob/07d3cc023514faea4fa0f5d06c1811b7d2138f04/docs/database/helix-db/query-guides/error-handling.mdx). Keep the complete catalog upstream. This guide records the wire contract and the decisions that recur across the skills.

## HTTP Contract

Every non-success response from `POST /v2/query` uses `error` for the stable code and `msg` for the diagnostic:

```json
{
  "error": "index_not_found",
  "msg": "planner error: missing text index for `Document.body`"
}
```

There is no separate `code` field in the current envelope. Treat `error` as the code only when `msg` is also present.

Older servers used this shape:

```json
{
  "error": "planner error: missing text index for `Document.body`",
  "code": "index_not_found"
}
```

During migration, decode both shapes:

1. If `error` and `msg` are strings, use `error` as the code and `msg` as the diagnostic.
2. Otherwise, if `error` is a string, use it as the diagnostic and an optional string `code` as the legacy code.
3. Otherwise, preserve the raw response text as diagnostic details and leave the code unset.

Codes are open strings. Preserve an unknown future code, log it, and fall back to status-aware generic handling; never reject or collapse it because a local enum or switch is older than the server.

## SDK Surfaces

| SDK | Stable-code access | Diagnostic/status access |
| --- | --- | --- |
| Rust | `QueryErrorCode`; `HelixError::error_code() -> Option<&str>`; coded remote and embedded variants | `RemoteError { code, details }`; `EmbeddedError { code, details }` |
| TypeScript | `HelixError.code?: string` | `HelixError.details`; `HelixError.kind` |
| Go | `QueryErrorCode`; `HelixError.Code` | `HelixError.Details`; `HelixError.StatusCode`; `IsConflict` / `ErrConflict` remain available |
| Python | `HelixError.code` | `HelixError.details`; `HelixError.status_code`; `HelixError.kind` |

The SDK wire fields intentionally remain strings so a newer server's code survives even when the local SDK does not yet know it.

## Retry Decisions

Use both HTTP status and stable code. A code classifies the failure; it does not prove that replaying the operation is safe.

- Retry only a safely replayable operation: an idempotent read, an idempotent mutation, or a mutation protected by an application-level idempotency key.
- `transaction_conflict` is the HTTP 409 conflict classification. A bounded retry with backoff is normally reasonable only when the operation is safe to replay.
- Availability or lifecycle errors may be retried after the named condition changes.
- Validation, planning, schema, and missing-index errors require a corrected request or configuration before retry.
- Treat unknown codes conservatively using their status; retain the code and diagnostic for telemetry.
- Do not parse `msg` or exception text to identify conflicts or other conditions.

## gRPC And Embedded Parity

gRPC keeps the readable diagnostic in the status message and attaches the same stable code as ASCII metadata under `helix-error-code`. Use the gRPC status class and metadata together.

Embedded Rust errors expose `error_code()`. UniFFI errors carry the explicit pair `error` (code) and `msg` (diagnostic), and generated SDK bindings preserve that pair. Embedded callers should not infer a code from exception text.
