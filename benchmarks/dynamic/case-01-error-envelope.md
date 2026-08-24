# Case 01: Error Envelope Migration And Safe Retry

## Prompt

Update a raw `POST /v2/query` client so it works during a rolling HelixDB upgrade. The current server returns:

```json
{"error":"transaction_conflict","msg":"transaction commit conflicted with another writer"}
```

An older server may return:

```json
{"error":"transaction commit conflicted with another writer","code":"transaction_conflict"}
```

A noncanonical proxy or intermediary response might instead be:

```json
{"code":"external_error","message":"upstream rejected the request","details":{"request_id":"req_123"}}
```

Explain that the first shape is the current Helix contract, including through
the Cloud query gateway, while the third is defensive generic-remote
compatibility. Decode all three, preserve an unknown future code and raw
response metadata, and explain when the client may retry a read or rebuild a
failed write.

## Expected Skills

- `helix-query-json-dynamic`
- shared `docs/error-handling.md`

## Focus Areas

- current `error`/`msg` contract with no separate `code` field
- migration from legacy `error` diagnostic plus `code`
- generic noncanonical remote `code`/`message`/`details`
- unknown-code forward compatibility
- structured details and raw-body preservation
- HTTP status plus code classification
- retry only for safely replayable operations
- no message parsing

## Gold Expectations

- For current bodies, require string `error` and string `msg`; store `error` as the code and `msg` as diagnostic details.
- Otherwise, when `error` is a string, treat it as legacy diagnostic details and take an optional string `code` as the legacy code.
- Otherwise, take a string `code`, string `message`, and any structured `details`
  from the generic remote shape without calling it the gateway contract.
- Preserve the original response body for every remote failure and retain
  non-JSON/plain-text bodies as the message with no code.
- Preserve an unknown current code as an open string and fall back to conservative status-aware handling.
- Recognize `transaction_conflict` with HTTP 409 without searching the diagnostic text.
- Honor `Retry-After` on `429 rate_limited` when the transport exposes it and
  add jitter to bounded retries.
- Treat `408 query_timeout` on a write as an unknown commit outcome and
  reconcile before resubmission.
- Distinguish `503 rate_limit_unavailable`, which fails closed before execution,
  from `backend_unavailable` and generic `internal_error`.
- For a 409 write conflict, reload current state before rebuilding the mutation;
  replay only when it is idempotent or protected by an application idempotency key.
- Correct validation/schema/index errors before retrying; do not retry merely because a code exists.
- Mention that gRPC carries the code in `helix-error-code` metadata if cross-transport behavior is discussed.

## Gold Decoder Sketch

```ts
function decodeHelixError(status: number, body: string) {
  let code: string | undefined;
  let message = body;
  let details: unknown;
  try {
    const value = JSON.parse(body) as {
      error?: unknown;
      msg?: unknown;
      code?: unknown;
      message?: unknown;
      details?: unknown;
    };
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
  return { status, code, message, details, rawBody: body };
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
- [ ] Uses both status and code for classification
- [ ] Recognizes HTTP 409 plus `transaction_conflict` without parsing a message
- [ ] Honors `Retry-After` on 429 when available and bounds retries with jitter
- [ ] Reconciles a timed-out write before resubmission
- [ ] Distinguishes the Cloud 402/408/413/429/503 conditions by status and code
- [ ] Reloads state before rebuilding a conflict and replays writes only when safe
- [ ] Does not retry validation/planning failures without correcting the cause
