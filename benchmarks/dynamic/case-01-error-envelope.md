# Case 01: Error Envelope Migration And Safe Retry

## Prompt

Update a raw `POST /v2/query` client so it works during a rolling HelixDB upgrade. The current server returns, both with HTTP 409:

```json
{"error":"transaction_conflict","msg":"transaction commit conflicted with another writer","retryable":true}
```

```json
{"error":"unique_constraint_violation","msg":"unique index User.email already owns the value","retryable":false}
```

An older server may return:

```json
{"error":"transaction commit conflicted with another writer","code":"transaction_conflict"}
```

A noncanonical proxy or intermediary response might instead be:

```json
{"code":"external_error","message":"upstream rejected the request","details":{"request_id":"req_123"}}
```

Explain that the first two bodies are the current Helix contract, including
through the Cloud query gateway, while the proxy body is defensive
generic-remote compatibility. Decode every shape, preserve an unknown future
code and raw response metadata, and explain which failures the client may
resend and when it must reconcile a write instead.

## Expected Skills

- `helix-query-json-dynamic`

## Focus Areas

- current `error`/`msg`/`retryable` contract with no separate `code` field
- HTTP 409 covers a retryable class and a non-retryable class
- migration from legacy `error` diagnostic plus `code`
- generic noncanonical remote `code`/`message`/`details`
- unknown-code forward compatibility
- structured details and raw-body preservation
- HTTP status plus code classification
- retry only for safely replayable operations
- no message parsing

## Gold Expectations

- For current bodies, require string `error` and string `msg`; store `error` as the code, `msg` as diagnostic details, and an optional boolean `retryable` (absent when the class does not settle it).
- Decide retries from `retryable` and the code, not from the 409 status: resend
  `transaction_conflict`, `request_read_view_changed`, `stale_index_generation`
  and `429 index_backpressure` with bounded backoff and jitter; never resend
  `unique_constraint_violation`, `index_busy`, `index_build_blocked`,
  `index_already_exists`, `index_definition_conflict` or
  `index_operation_not_abortable` unchanged.
- Otherwise, when `error` is a string, treat it as legacy diagnostic details and take an optional string `code` as the legacy code.
- Otherwise, take a string `code`, string `message`, and any structured `details`
  from the generic remote shape without calling it the gateway contract.
- Preserve the original response body for every remote failure and retain
  non-JSON/plain-text bodies as the message with no code.
- Preserve an unknown current code as an open string and fall back to conservative status-aware handling.
- Recognize both 409 codes without searching the diagnostic text.
- Honor `Retry-After` on Cloud `429 rate_limited` when the transport exposes it
  and add jitter to bounded retries.
- Treat a write as possibly committed after `408 query_deadline_exceeded`
  (database), `408 query_timeout` (Cloud gateway), any 500, `503
  writer_fenced_commit_outcome_unknown` or Cloud `503 write_outcome_unknown`,
  and reconcile before resubmission.
- Distinguish `503 rate_limit_unavailable`, which fails closed before execution,
  from `backend_unavailable` and generic `internal_error`.
- For a retryable write conflict, rebuild the mutation from freshly read state
  when it depends on what it read; replay only when it is idempotent or
  protected by an application idempotency key.
- For a legacy body without `retryable`, treat only `transaction_conflict` as
  retryable.
- Correct validation/schema/index errors before retrying; do not retry merely because a code exists.
- Mention that gRPC carries the code in `helix-error-code` metadata if cross-transport behavior is discussed.

## Gold Decoder Sketch

```ts
function decodeHelixError(status: number, body: string) {
  let code: string | undefined;
  let message = body;
  let details: unknown;
  let retryable: boolean | undefined;
  try {
    const value = JSON.parse(body) as {
      error?: unknown;
      msg?: unknown;
      code?: unknown;
      message?: unknown;
      details?: unknown;
      retryable?: unknown;
    };
    if (typeof value.retryable === "boolean") retryable = value.retryable;
    if (typeof value.error === "string" && typeof value.msg === "string") {
      code = value.error;
      message = value.msg;
    } else if (typeof value.error === "string" && typeof value.code === "string") {
      code = value.code;
      message = value.error;
    } else {
      code = typeof value.code === "string" ? value.code : undefined;
      message = typeof value.message === "string"
        ? value.message
        : typeof value.error === "string"
          ? value.error
          : body;
    }
    if (Object.hasOwn(value, "details")) details = value.details;
  } catch {
    // Preserve proxy/intermediary text below.
  }
  // Legacy bodies predate `retryable`; only a transaction conflict was retryable.
  if (retryable === undefined && code === "transaction_conflict") retryable = true;
  return { status, code, message, details, retryable, rawBody: body };
}

function mayResendUnchanged(error: { retryable?: boolean }): boolean {
  return error.retryable === true;
}
```

## Scoring Checklist

- [ ] Targets `POST /v2/query`
- [ ] Reads the current stable code from `error` only when `msg` supplies the diagnostic
- [ ] States that the current envelope has no separate `code` field
- [ ] Accepts the legacy `error` + `code` body without reversing their meanings
- [ ] Accepts generic remote `code` + `message` + structured `details` defensively
- [ ] States that Cloud `/v2/query` still canonically uses `error` + `msg`
- [ ] Preserves plain-text diagnostics and unknown future code strings
- [ ] Preserves the raw response body for every remote failure
- [ ] Uses `retryable` and the code, not the status alone, for retry decisions
- [ ] Does not retry `unique_constraint_violation` (409, `retryable: false`)
- [ ] Recognizes both 409 codes without parsing a message
- [ ] Honors `Retry-After` on 429 when available and bounds retries with jitter
- [ ] Reconciles a write after `query_deadline_exceeded`, `query_timeout`, 500 or an unknown commit outcome before resubmission
- [ ] Distinguishes the Cloud 402/408/413/429/503 conditions by status and code
- [ ] Reloads state before rebuilding a conflict and replays writes only when safe
- [ ] Does not retry validation/planning failures without correcting the cause
