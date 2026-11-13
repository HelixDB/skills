# HelixDB v3 JSON Wire Reference

This reference describes the direct request produced by the published v3 SDKs.
The source of truth is the `helix-ast` crate under
[`HelixDB/helix-db`](https://github.com/HelixDB/helix-db/tree/main/crates/ast).
The published transport schema is
[`openapi.json`](https://docs.helix-db.com/openapi.json); use it for HTTP
headers, status codes, body limits, and the raw-JSON parameter subset.

## Envelope

```json
{
  "request_type": "read",
  "query_name": "optional_diagnostic_name",
  "query": {
    "read": {
      "entries": [
        {
          "query": {
            "name": "users",
            "root": {
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
      ],
      "returns": ["users"]
    }
  }
}
```

| Field | Required | Shape |
|---|---:|---|
| `request_type` | yes | lowercase `"read"` or `"write"` |
| `query_name` | no | non-empty string or `null` |
| `query` | yes | `{ "read": ReadBatch }` or `{ "write": WriteBatch }` |
| `parameters` | no | object of JSON runtime values |
| `parameter_types` | no | object of v3 parameter type descriptors; when present, keys exactly match `parameters` |
| `search_consistency` | no | `"strong"` (default) or `"eventual"`; `eventual` only on read requests |

The batch variant must match `request_type`, and every batch must contain at
least one entry.

## Batches and entries

A batch contains entries in execution order and the variable names to return:

```json
{
  "read": {
    "entries": [
      {
        "query": {
          "name": "users",
          "root": {
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
    ],
    "returns": ["users"]
  }
}
```

`name` is optional in the underlying AST but should be present for normal `varAs`
entries. `condition` is also optional:

```json
{
  "query": {
    "name": "created",
    "condition": { "var_empty": "existing" },
    "root": {
      "add_n": {
        "label": "User",
        "properties": []
      }
    }
  }
}
```

The other entry form repeats a body for each object in a top-level array parameter:

```json
{
  "for_each": {
    "param": "users",
    "body": [
      {
        "query": {
          "name": "created",
          "root": {
            "add_n": {
              "label": "User",
              "properties": []
            }
          }
        }
      }
    ]
  }
}
```

Batch conditions serialize as `{"var_not_empty": "x"}`, `{"var_empty": "x"}`,
`{"var_min_size": ["x", 2]}`, or the unit string `"prev_not_empty"`. A skipped
entry returns `[]`.

A `for_each` body runs once per element and rebinds its names each time, so
returning a name from the body returns only the last iteration's value. Return
something computed after the loop instead.

## Recursive operation encoding

`AstNode` is an externally tagged, `snake_case` enum. A source has no `input`:

```json
{
  "nodes": {
    "reference": { "ids": [0, 1] }
  }
}
```

```json
{
  "nodes_where": {
    "predicate": {
      "eq": {
        "left": { "property": "$label" },
        "right": { "constant": { "string": "User" } }
      }
    }
  }
}
```

Unit variants serialize as plain strings: `"context"` (the input of a
sub-traversal), `"id"`, `"timestamp"`, `"date_time_now"`, `"all"`.

Each following operation wraps the prior node under `input`:

```json
{
  "value_map": {
    "input": {
      "limit": {
        "input": {
          "out": {
            "input": {
              "nodes": {
                "reference": { "var": "user" }
              }
            },
            "label": "FOLLOWS"
          }
        },
        "count": { "literal": 25 }
      }
    },
    "properties": ["$id", "name"]
  }
}
```

### Operation catalog

Fields in `[]` are optional and omitted when unset; every other field is
required. `Sub` is a sub-traversal `{"root": <op>}` whose innermost `input` is
`"context"`. `Bound` is `{"literal": 25}` or `{"expr": <Expr>}`. `Input` is a
`PropertyInput`, `Value` a `PropertyValue`.

Sources (no `input`):

| Variant | Fields | Notes |
|---|---|---|
| `nodes`, `edges` | `reference` | `NodeRef` / `EdgeRef` |
| `nodes_where`, `edges_where` | `predicate` | Label scope is `eq` on `$label`; `n_with_label_where` is `and[eq $label, <pred>]` and is what can use a label-scoped index |
| `vector_search_nodes`, `vector_search_edges` | `label`, `property`, `query_vector: Input`, `k: Bound`, [`tenant_value: Input`] | Hits add `$distance` |
| `text_search_nodes`, `text_search_edges` | `label`, `property`, `query_text: Input`, `k: Bound`, [`tenant_value`] | Hits add `$score` |
| `shortest_path` | `source: NodeRef`, `target: NodeRef`, [`label`], `direction: "out"\|"in"\|"both"`, `max_depth` | Unweighted BFS. Returns the path as an array of node IDs, `[]` when none within `max_depth` |
| `inject` | [`input`], `variable` | Streams a batch variable |

Traversal and filters (all take `input`):

| Variant | Other fields |
|---|---|
| `out`, `in`, `both`, `out_e`, `in_e`, `both_e` | [`label`] |
| `out_n`, `in_n`, `other_n`, `dedup` | none |
| `has` | `property`, `value: Value` |
| `has_label` | `label` |
| `has_key` | `property` |
| `where` | `predicate` |
| `edge_has` | `property`, `value: Input` |
| `edge_has_label` | `label` |
| `within`, `without` | `variable` |
| `limit`, `skip` | `count: Bound` |
| `range` | `start: Bound`, `end: Bound` |
| `as`, `store`, `select`, `bind` | `name` |
| `order_by` | `property`, `order: "asc"\|"desc"` |
| `order_by_multiple` | `orderings: [["name", "asc"], ["age", "desc"]]` |
| `vector_search_nodes_within`, `vector_search_edges_within` | as the source form |
| `text_search_nodes_within`, `text_search_edges_within` | as the source form |

Ordering puts rows missing the property first for `asc` and last for `desc`
(the opposite of Cypher/SQL defaults). `bind` and `project_bindings` are
read-only: a write batch rejects them (`read_only_traversal_in_write_batch`).
After `bind`, `order_by`, `choose`, `repeat`, `values`, `value_map`, `project`,
`id`, `label` and `edge_properties` are rejected; order before binding.

Branching and repetition:

| Variant | Fields | Semantics |
|---|---|---|
| `union` | `input`, `traversals: [Sub]` | Concatenates every branch |
| `coalesce` | `input`, `traversals: [Sub]` | First non-empty branch per row |
| `optional` | `input`, `traversal: Sub` | Branch rows, or the unchanged input row when the branch is empty |
| `choose` | `input`, `condition: Predicate`, `then_traversal: Sub`, [`else_traversal: Sub`] | Without `else_traversal`, rows failing `condition` are dropped. For a per-row value use `Expr` `case` |
| `repeat` | `input`, `config: {traversal: Sub, [times], [until: Predicate], emit, [emit_predicate], max_depth}` | `emit` is required: `"none"` (final frontier only), `"before"`, `"after"` (each iteration's output), `"all"` (both, so depth-1 rows appear twice). `emit_predicate` with `"after"` filters emitted rows. SDKs default `max_depth` to 100 |

Terminals and aggregates (all take `input`):

| Variant | Other fields | Output per row |
|---|---|---|
| `count`, `exists` | none | scalar `N` / `true\|false` |
| `id`, `label` | none | ID / label |
| `values` | `properties: [..]` | property values |
| `value_map` | [`properties`] | object; omit `properties` for all |
| `project` | `projections: [Projection]` | object |
| `edge_properties` | none | object |
| `project_bindings` | `projections: [BindingProjection]`, `distinct: bool` | object; a missing binding or property omits its key |
| `group` | `property` | `{"<property>": v, "count": n, "ids": [..]}` |
| `group_count` | `property` | `{"<property>": v, "count": n}` |
| `aggregate_by` | `function: "count"\|"sum"\|"min"\|"max"\|"mean"`, `property` | `{"<property>_<Function>": f64}`, for example `{"rank_Sum": 6.0}` |
| `fold`, `unfold`, `path`, `simple_path`, `sack_get` | none | Gremlin-style steps; they execute (not no-ops) |
| `with_sack` | `initial: Value` | |
| `sack_set`, `sack_add` | `property` | |

Mutations (write batches only):

| Variant | Fields | Notes |
|---|---|---|
| `add_n` | [`input`], `label`, `properties: [[name, Input], ..]` | Returns `{"$id"}` per node |
| `add_e` | `input`, `label`, `to: NodeRef`, `properties` | One edge per (source, target); never idempotent. An empty `to` fails the batch |
| `set_property` | `input`, `name`, `value: Input` | |
| `remove_property` | `input`, `name` | |
| `drop` | `input` | Drops the current nodes or edges |
| `drop_edge` | `input`, `to: NodeRef` | Edges from the current nodes to `to` |
| `drop_edge_labeled` | `input`, `to: NodeRef`, `label` | |
| `drop_edge_by_id` | [`input`], `edges: EdgeRef` | |

Index DDL and lifecycle (sources):

| Variant | Fields | Batch | Returns |
|---|---|---|---|
| `create_index` | `spec: IndexSpec`, `if_not_exists: bool` | write | receipt |
| `drop_index` | `spec: IndexSpec` | write | receipt |
| `get_index_operation` | `operation_id` | read | status |
| `retry_index_operation` | `operation_id` | write | status |
| `abort_index_operation` | `operation_id` | write | status |

### Restricted (traversal-scoped) search

Restricted vector search enforces exact membership over input IDs, although
approximate index structures may accelerate ranking. The ranked stream receives
`$distance`. The request fails when `min(k, unique candidates)` exceeds 800, so
a larger `k` succeeds only while 800 or fewer candidates exist.

Restricted text search is an exact BM25 prefilter over unique input IDs. It
returns at most `min(unique candidates, k, 800)`, orders by score descending
then entity ID ascending, and keeps tenant-partition BM25 statistics. The
selected input row keeps bindings, path, and sack and receives `$score`.

For both, empty input skips the index; wrong-kind input or more than 1,000,000
unique candidates is a query error. A whole-index vector search caps its
effective result count at 800.

Serialize with an SDK (`to_query_json` / `toQueryJson`) when unsure, and treat
that output as canonical rather than guessing a field.

## Projections

```json
{ "property": { "source": "name", "alias": "name" } }
```

```json
{ "expr": { "alias": "next_age", "expr": { "add": { "left": { "property": "age" }, "right": { "constant": { "i64": 1 } } } } } }
```

Edge streams read endpoint properties with `$from.<prop>` / `$to.<prop>` as
`source`.

`BindingProjection` reads a named binding (`{"binding": "user"}`) or the current
element (`"current"`):

```json
{ "property": { "target": { "binding": "user" }, "source": "name", "alias": "name" } }
```

```json
{ "coalesce": { "refs": [ { "target": { "binding": "nick" }, "source": "name" }, { "target": "current", "source": "name" } ], "alias": "display" } }
```

## Index specs

`IndexSpec` is externally tagged:

| Variant | Fields |
|---|---|
| `node_equality` | `label`, `property`, `unique` (default `false`) |
| `edge_equality` | `label`, `property` |
| `node_range`, `edge_range` | `label`, `property`, `direction` (`"asc"` default, `"desc"`) |
| `node_vector`, `edge_vector` | `label`, `property`, `dimension` (> 0), `metric` (`"cosine"`, `"euclidean"`, `"manhattan"`), [`tenant_property`] |
| `node_text`, `edge_text` | `label`, `property`, [`tenant_property`] |

```json
{
  "create_index": {
    "spec": { "node_equality": { "label": "User", "property": "userId", "unique": true } },
    "if_not_exists": true
  }
}
```

A unique equality index rejects a duplicate write with
`unique_constraint_violation` (`409`, `retryable: false`) from the moment its
build starts; it is the race-safe key for an upsert.

Receipt (`create_index`, `drop_index`), with IDs as decimal strings:

```json
{ "kind": "accepted", "operation_id": "07070707-0707-0707-0707-070707070707", "index_id": "42", "generation": "3" }
```

`kind` is `accepted`, `existing_operation` (only `operation_id`: the same build
is in flight) or `already_active` (`index_id`, `generation`; nothing to wait
for).

Status (`get_index_operation`, `retry_index_operation`, `abort_index_operation`):

```json
{
  "status": "running",
  "operation_id": "07070707-0707-0707-0707-070707070707",
  "index_id": "42",
  "generation": "3",
  "operation_kind": "build",
  "family": "secondary",
  "stage": "scan",
  "attempt": 0,
  "progress": { "entities": "1200", "input_bytes": "0", "output_operations": "0", "output_bytes": "0" }
}
```

`status` is `queued`, `running`, `blocked`, `succeeded` or `aborted`.
`operation_kind` is `build` or `drop`; `family` is `secondary`, `vector` or
`text`. `blocked` adds `blocker_code` (`invalid_source_data`,
`uniqueness_violation`, `oversized_entity`, `manifest_limit`,
`object_store_configuration_unavailable`, `invariant_violation`,
`invalid_legacy_physical`) and an optional `message`; it does not resume until
you fix the cause and send `retry_index_operation`, or discard it with
`abort_index_operation`. Repeating the same `create_index` while it runs
returns `existing_operation` with the same `operation_id`.

## References

`NodeRef` and `EdgeRef` are `snake_case` variants:

```json
{
  "reference": { "var": "alice" }
}
```

```json
{
  "reference": { "ids": [0, 1] }
}
```

```json
{
  "reference": { "param": "user_ids" }
}
```

```json
{
  "reference": "all"
}
```

IDs are unsigned integers. An ID parameter must be a JSON integer or an array
of integers (`"parameter_types": {"user_ids": {"array": "i64"}}`); a string
fails at runtime.

## Values and inputs

`PropertyValue` values are tagged:

```json
{
  "string": "Alice"
}
```

```json
{
  "i64": 25
}
```

```json
{
  "f64_array": [0.1, 0.2, 0.3]
}
```

Other tags: `bool`, `f32`, `date_time` (epoch milliseconds), `i64_array`,
`f32_array`, `string_array`, `array`, `object`; null is the unit string `"null"`.

`PropertyInput` distinguishes a literal value from an expression:

```json
{
  "value": { "string": "Alice" }
}
```

```json
{
  "expr": { "param": "name" }
}
```

Properties on `add_n` and `add_e` are ordered pairs:

```json
{
  "properties": [
    ["name", { "value": { "string": "Alice" } }],
    ["active", { "value": { "bool": true } }]
  ]
}
```

## Predicates

Predicates are expression trees, not positional arrays:

```json
{
  "eq": {
    "left": { "property": "status" },
    "right": { "constant": { "string": "active" } }
  }
}
```

```json
{
  "and": {
    "predicates": [
      {
        "eq": {
          "left": { "property": "$label" },
          "right": { "constant": { "string": "User" } }
        }
      },
      {
        "gte": {
          "left": { "property": "age" },
          "right": { "param": "minimum_age" }
        }
      }
    ]
  }
}
```

Use `constant` for a literal, `param` for a runtime parameter, and `property` for the
current element's property.

Predicate variants: `eq`, `neq`, `gt`, `gte`, `lt`, `lte` (`left`, `right`);
`between` (`value`, `min`, `max`, inclusive); `compare` (`left`,
`op: "eq"|"neq"|"gt"|"gte"|"lt"|"lte"`, `right`); `is_in` (`value`, `values`);
`starts_with` (`value`, `prefix`), `ends_with` (`value`, `suffix`), `contains`
(`value`, `substring`); `has_key`, `is_null`, `is_not_null` (`property`);
`and`, `or` (`predicates`); `not` (`predicate`).

```json
{ "between": { "value": { "property": "age" }, "min": { "constant": { "i64": 18 } }, "max": { "param": "max_age" } } }
```

```json
{ "is_in": { "value": { "property": "status" }, "values": { "param": "statuses" } } }
```

`Expr` variants: `{"property": "p"}`, `{"constant": Value}`, `{"param": "p"}`,
`"id"`, `"timestamp"` (server UTC epoch milliseconds as `i64`),
`"date_time_now"` (typed `date_time`), `add`/`sub`/`mul`/`div`/`mod`
(`left`, `right`), `neg` (`expr`), and `case`:

```json
{
  "case": {
    "when_then": [
      { "when": { "gte": { "left": { "property": "score" }, "right": { "constant": { "i64": 90 } } } }, "then": { "constant": { "string": "high" } } }
    ],
    "else_expr": { "constant": { "string": "low" } }
  }
}
```

A rows-preserving per-row value belongs in `case` inside an `expr`
projection, not in `choose`. Write a server timestamp with
`"value": {"expr": "timestamp"}` (or `"date_time_now"`) in `set_property` or
`add_n` properties.

## Parameter schemas

The raw HTTP scalar schema names are `bool`, `i64`, `f32`, `f64`, `string`,
`date_time`, `value`, and `object`. Arrays use recursive `{ "array": <schema> }` descriptors.
When `parameter_types` is present, its keys must exactly match `parameters`;
typed and untyped values cannot be mixed. Typed `f32`/`f64` accept integer and
floating-point JSON numbers. Values must be finite; `f32` values must fit within
its finite range. Raw bytes cannot be represented on the JSON route.

```json
{
  "parameters": {
    "minimum_age": 18
  },
  "parameter_types": {
    "minimum_age": "i64"
  }
}
```

## Responses

The server returns one top-level member per returned batch name.

```json
{
  "users": [
    { "$id": 0, "name": "Alice" },
    { "$id": 1, "name": "Bob" }
  ]
}
```

- An unprojected node or edge is `{"$id": N}` (plus `$distance` / `$score` for
  search hits).
- Every row-stream return is an array and `[]` when empty, including
  at-most-one lookups and skipped entries. Only `count`, `exists` and index
  DDL / lifecycle results are scalars or objects. `"returns": []` produces `{}`.
- A row with bindings, a visible path or a sack is
  `{"bindings": {...}, "current": {"node": N}, "path": [...], "sack": ...}`;
  end such streams with `project_bindings` for a stable shape.

## HTTP Failure Envelope

```json
{"error":"unique_constraint_violation","msg":"<diagnostic>","retryable":false}
```

`error` is the code; there is no `code` field. `retryable` is present only when
the class settles it. Codes are open strings: keep an unknown one, log it, and
fall back to its status class. Never parse `msg`. A server older than the
current contract may send `{"error": "<diagnostic>", "code": "<code>"}`.

Every code has one class, and the class sets the status and `retryable`
(`crates/ast/src/error_code.rs`):

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

Decisions:

- `retryable: true` → resend the whole request with bounded backoff and
  jitter; rebuild a write from freshly read state if it depends on what it read.
- `unique_constraint_violation` → report the duplicate or choose another key.
  From an upsert's create branch, re-run the upsert once; it now takes the
  update branch.
- `index_busy` → wait for the running operation (`get_index_operation`).
  `index_build_blocked` → fix what the blocked build's `blocker_code` names,
  then `retry_index_operation` (or abort it) before resending the write.
- "May have committed" classes → reconcile by an application key before
  resubmitting; never auto-retry a non-idempotent write.
- An index request with several create/drop/retry/abort entries commits each
  one as it runs; after a later failure, read index state before resending.

Helix Cloud gateway codes (before or around execution): `400
tenant_id_required` / `tenant_id_not_allowed`, `401 unauthorized`, `402
tenant_disabled`, `403 forbidden`, `408 query_timeout` (reconcile writes), `413
payload_too_large` (2 MiB), `429 rate_limited` (honor `Retry-After`), `503
backend_unavailable` / `rate_limit_unavailable` (backoff), `503
failover_wait_unavailable` (not sent; honor `Retry-After`), `503
write_outcome_unknown` (`retryable: false`; reconcile). SDK error objects do not
expose headers, so honor `Retry-After` from direct HTTP.

Cypher and SQL routes report statement failures as
`{"error": "<category>", "msg", "details": {"detail", "phase", "span"}}`:
`syntax_error`, `unsupported_feature`, `type_error`, `argument_error`,
`arithmetic_error`, `parameter_missing`, `entity_not_found`,
`constraint_verification_failed` (400); `resource_limit` (429);
`access_mode_error` (503, send to the writer); `internal_planner_error` (500).

## Validation checklist

- Parse every complete `json` fence.
- Confirm `request_type` and batch variant match.
- Confirm every returned name exists in an entry.
- Confirm response models decode every row return as a list (empty `[]`), and
  unprojected elements as `{"$id"}` only.
- Confirm ID parameters are integers.
- Confirm every non-source operation has the correct nested `input`.
- Confirm all enum tags are `snake_case`.
- Compare hand-written JSON with an SDK serializer for the same query.
- Decode `error`/`msg`/`retryable` failures; branch on `retryable` and keep
  unknown codes.
- Run applicable requests against `ghcr.io/helixdb/helixdb:v0.0.16`.
