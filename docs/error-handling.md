# Helix Query Error Handling

Branch on the stable code and the `retryable` field; log `msg`. Codes are
compatibility identifiers, messages are not. Source of truth:
`crates/ast/src/error_code.rs` (every code has one class, and the class alone
sets the HTTP status and `retryable`). Public reference:
https://docs.helix-db.com/database/helix-db/query-guides/error-handling

## Envelope

Every non-success response from `POST /v2/query` uses:

```json
{ "error": "unique_constraint_violation", "msg": "<diagnostic>", "retryable": false }
```

- `error` is the code. There is no `code` field.
- `retryable` is present only when the class settles it (`true` or `false`);
  otherwise it is absent.
- Codes are open strings: keep an unknown code, log it, and fall back to the
  status class.

`POST /v2/cypher`, `/v2/sql` and their `/explain` routes report a failed
statement as `{"error": "<category>", "msg", "details": {"detail", "phase", "span"}}`
(see [Cypher and SQL errors](#cypher-and-sql-errors)); request, storage and
transaction failures on those routes use the envelope above.

## Classes

| Class | HTTP | `retryable` | A failed write | Codes |
| --- | ---: | --- | --- | --- |
| Invalid request | 400 | absent | committed nothing | `invalid_request`, `invalid_query_json`, `invalid_request_body`, `invalid_request_option`, `invalid_index_operation_id`, `invalid_node_id`, `unbound_parameter`, `secondary_lifecycle_stepping_requires_disabled_mode`, `migration_stepping_requires_disabled_mode`, `active_text_mutation_limit_exceeded`, `index_operation_batch_too_large`, `invalid_index_source_data`, `invalid_secondary_index_value`, `invalid_vector_configuration`, `unsupported_unique_index_value_type`, `invalid_vector_dimension`, `invalid_vector_component`, `vector_component_magnitude_exceeded`, `zero_norm_cosine_vector` |
| Planning | 400 | absent | committed nothing | `internal_planner_error`, `unsupported_edge_all_target`, `non_literal_index_expression`, `missing_planning_equality_parameter`, `unsupported_planning_equality_parameter`, `invalid_search_tenant`, `invalid_search_tenant_value`, `invalid_search_result_count`, `invalid_search_result_count_expression`, `invalid_search_input`, `invalid_batch_condition_min_size`, `invalid_initial_batch_condition`, `duplicate_property_assignment`, `duplicate_property_selection`, `duplicate_projection_alias`, `duplicate_return_variable`, `duplicate_element_id`, `duplicate_order_key`, `unbound_context`, `invalid_sub_traversal_operation`, `invalid_after_bind_operation`, `read_only_traversal_in_write_batch`, `invalid_branch_arity`, `invalid_batch_arity`, `invalid_repeat_emit`, `invalid_repeat_count`, `invalid_shortest_path_count`, `invalid_order_keys`, `invalid_projection_arity`, `invalid_stream_range`, `invalid_stream_bound_expression`, `invalid_empty_name`, `invalid_predicate_arity` |
| Not found | 404 | absent | committed nothing | `node_not_found`, `edge_not_found`, `index_not_found`, `index_operation_not_found` |
| Timeout | 408 | absent | **may have committed** | `query_deadline_exceeded` |
| Retryable conflict | 409 | `true` | committed nothing | `transaction_conflict`, `request_read_view_changed`, `stale_index_generation` |
| Conflict with database state | 409 | `false` | committed nothing | `unique_constraint_violation`, `index_already_exists`, `index_definition_conflict`, `index_busy`, `index_operation_not_abortable`, `index_build_blocked` |
| Index backpressure | 429 | `true` | committed nothing | `index_backpressure` |
| Resource limit | 429 | absent | committed nothing | `query_memory_limit_exceeded` |
| Internal | 500 | absent | **may have committed** | `storage_error`, `invalid_configuration`, `invalid_index_model`, `unsupported_index_storage_version`, `identifier_exhausted`, `index_id_exhausted`, `vector_physical_id_exhausted`, `index_generation_exhausted`, `index_revision_exhausted`, `index_operation_revision_exhausted`, `invalid_query`, `response_serialization_error`, `internal_error` |
| Unavailable | 503 | absent | committed nothing | `writer_mode_required`, `reader_mode_required`, `database_closed`, `query_cancelled_by_reader_retirement`, `index_lifecycle_unavailable`, `migration_required`, `writer_migration_required` |
| Commit outcome unknown | 503 | `false` | **may have committed** | `writer_fenced_commit_outcome_unknown` |

An index-management request with several create, drop, retry or abort
operations commits each one as it runs; if a later one fails, the earlier ones
stay committed.

## What to do

| Code(s) | Action |
| --- | --- |
| `transaction_conflict`, `request_read_view_changed`, `stale_index_generation` | Retry the whole request with bounded backoff and jitter. For a write, rebuild it from freshly read state if it depends on what it read. |
| `index_backpressure` | Retry unchanged after a backoff; the whole request was rejected before it took effect. An `eventual` search is never rejected this way. |
| `unique_constraint_violation` | Do not resend unchanged. Report a duplicate, pick another key, or, from an upsert's create branch, re-run the upsert once (it now takes the update branch). |
| `index_busy` | Another lifecycle operation on the index is running. Wait for it (`get_index_operation`), then decide. |
| `index_build_blocked` | A write would overflow a blocked index build's queue. Fix what the build's `blocker_code` names, then `retry_index_operation`, or `abort_index_operation`; resending the write before that fails again. |
| `index_already_exists`, `index_definition_conflict` | Send `"if_not_exists": true` (the SDKs' `create_index_if_not_exists` always does), or drop the conflicting definition first. |
| `index_operation_not_abortable` | Only a build that is still constructing can be aborted. Read its status; if it succeeded, drop the index instead. |
| `index_not_found` | Create the index (and wait until its build succeeds), or change the query. |
| `query_deadline_exceeded`, `writer_fenced_commit_outcome_unknown`, 500 codes | A write may have committed. Reconcile (read back by an application key) before resubmitting; never auto-retry a non-idempotent write. |
| `query_memory_limit_exceeded` | Reduce the work (narrower anchor, `limit`, smaller projection); unchanged it fails again. |
| `writer_mode_required` | Send the write to the writer (`X-Helix-Require-Writer: true` / `writer_only()`). |
| `invalid_request_option` | Fix the header: `X-Helix-Warm` is read-only, `X-Helix-Await-Durable: true` is write-only. |
| `invalid_request_body` | The body could not be read, for example over 16 MiB. |
| `invalid_query_json` | Malformed query JSON, a wrong shape, or nesting deeper than 255 levels. |
| Other 400 / 404 | Fix the request, schema or data; do not retry unchanged. |
| Other 503 | Retry only after the named condition changes. |

Never parse `msg` to classify a failure.

## SDK access

Snippets in the skills use the SDK source on `main`. The published packages
(Rust 3.0.0, TypeScript 3.2.0, Python 0.3.4, Go v0.3.1) lag it; see
`docs/source-canon.md`.

| SDK | Code | Retry decision | Status | Published-package caveat |
| --- | --- | --- | --- | --- |
| Rust | `err.remote_code()` / `err.error_code()` | `err.is_retryable()`, `err.retryable()` | `err.status_code()` | 3.0.0 has only `HelixError::RemoteError { details }` (the raw body): parse it as JSON. |
| TypeScript | `err.code` | `err.isRetryable()`, `err.retryable` | `err.statusCode` | 3.2.0 `isConflict()` is `true` for every 409, including `unique_constraint_violation`; use `isRetryable()`. |
| Python | `err.code` | `err.is_retryable()`, `err.retryable` | `err.status_code` | If `code` / `retryable` are missing, parse `err.details` as JSON. |
| Go | `herr.Code` (after `errors.As(err, &herr)`) | `helix.IsRetryable(err)`, `herr.Retryable` | `herr.StatusCode` | v0.3.1 has no `IsRetryable`/`Retryable`, and its `IsConflict` is `true` for every 409; branch on `herr.Code`. |

`isConflict()` / `is_conflict()` / `IsConflict` on `main` mean
`transaction_conflict` only. `is_index_backpressure()` / `isIndexBackpressure()` /
`IsIndexBackpressure` match `index_backpressure`. SDK error objects do not expose
response headers, so honor Cloud `Retry-After` through direct HTTP.

## Cypher and SQL errors

| Category | HTTP | Meaning |
| --- | ---: | --- |
| `syntax_error`, `unsupported_feature`, `type_error`, `argument_error`, `arithmetic_error`, `parameter_missing`, `entity_not_found`, `constraint_verification_failed` | 400 | Fix the statement, parameters or data. `unsupported_feature` names the construct in `details.detail` (`merge`, `variable_length_pattern`, `shortest_path`, `union`, `foreach`, `sql_construct`, ...). |
| `resource_limit` | 429 | A per-query budget (`memory_limit`, `result_limit`, `collection_limit`, `expression_depth`). Reduce the work. Committed nothing. |
| `access_mode_error` | 503 | A write reached a reader or warm-only request; send it to the writer. |
| `internal_planner_error` | 500 | Do not retry automatically. |

`details.phase` is `compile` (nothing ran) or `runtime`.

## Helix Cloud gateway codes

The managed gateway adds its own codes before or around database execution
(https://docs.helix-db.com/database/helix-cloud/operate/error-handling):

| HTTP | Code | Action |
| ---: | --- | --- |
| 400 | `tenant_id_required` | Send `X-Helix-Database-Id` in GA mode. |
| 400 | `tenant_id_not_allowed` | Remove the database/tenant header in cluster mode. |
| 401 | `unauthorized` | Refresh or replace the API key. |
| 402 | `tenant_disabled` | Resolve the account's credit before retrying. |
| 403 | `forbidden` | Use a key with the required permission (read-only keys cannot write). |
| 408 | `query_timeout` | The gateway's wall-clock limit. Reconcile a write before resubmitting. |
| 413 | `payload_too_large` | Keep Cloud bodies under 2 MiB. |
| 429 | `rate_limited` | Not executed. Honor `Retry-After`, add jitter. |
| 503 | `backend_unavailable`, `rate_limit_unavailable` | Retry with bounded exponential backoff and jitter. |
| 503 | `failover_wait_unavailable` | The write was not sent. Honor `Retry-After`, then retry. |
| 503 | `write_outcome_unknown` | `retryable: false`. Reconcile; do not resubmit automatically. |

## gRPC and embedded

gRPC keeps `msg` as the status message and attaches the code as
`helix-error-code` metadata; the gRPC status follows the class
(`unique_constraint_violation` is `FAILED_PRECONDITION`, `index_backpressure`
is `RESOURCE_EXHAUSTED`). Embedded clients carry the same `error`/`msg` pair.
