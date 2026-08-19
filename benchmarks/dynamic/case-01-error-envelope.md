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

Explain how to decode both shapes, how to handle an unknown future code, and when the client may retry a failed write.

## Expected Skills

- `helix-query-json-dynamic`
- shared `docs/error-handling.md`

## Focus Areas

- current `error`/`msg` contract with no separate `code` field
- migration from legacy `error` diagnostic plus `code`
- unknown-code forward compatibility
- HTTP status plus code classification
- retry only for safely replayable operations
- no message parsing

## Gold Expectations

- For current bodies, require string `error` and string `msg`; store `error` as the code and `msg` as diagnostic details.
- Otherwise, when `error` is a string, treat it as legacy diagnostic details and take an optional string `code` as the legacy code.
- Preserve non-JSON/plain-text bodies as details with no code.
- Preserve an unknown current code as an open string and fall back to conservative status-aware handling.
- Recognize `transaction_conflict` with HTTP 409 without searching the diagnostic text.
- Retry with bounded backoff only when the mutation is idempotent or protected by an application idempotency key.
- Correct validation/schema/index errors before retrying; do not retry merely because a code exists.
- Mention that gRPC carries the code in `helix-error-code` metadata if cross-transport behavior is discussed.

## Gold Decoder Sketch

```ts
function decodeHelixError(status: number, body: string) {
  try {
    const value = JSON.parse(body) as { error?: unknown; msg?: unknown; code?: unknown };
    if (typeof value.error === "string" && typeof value.msg === "string") {
      return { status, code: value.error, details: value.msg };
    }
    if (typeof value.error === "string") {
      return {
        status,
        code: typeof value.code === "string" ? value.code : undefined,
        details: value.error,
      };
    }
  } catch {
    // Preserve proxy/intermediary text below.
  }
  return { status, code: undefined, details: body };
}
```

## Scoring Checklist

- [ ] Targets `POST /v2/query`
- [ ] Reads the current stable code from `error` only when `msg` supplies the diagnostic
- [ ] States that the current envelope has no separate `code` field
- [ ] Accepts the legacy `error` + `code` body without reversing their meanings
- [ ] Preserves plain-text diagnostics and unknown future code strings
- [ ] Uses both status and code for classification
- [ ] Recognizes HTTP 409 plus `transaction_conflict` without parsing a message
- [ ] Limits retries to idempotent/idempotency-protected operations with bounded backoff
- [ ] Does not retry validation/planning failures without correcting the cause
