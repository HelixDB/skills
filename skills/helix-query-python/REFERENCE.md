# Helix Query Authoring - Python Reference

Names follow the SDK source on helix-db `main`; `(main)` marks APIs missing from
PyPI `helix-db` 0.3.4 (see the table in `SKILL.md`).

```text
from helixdb import (
    AggregateFunction, AsyncClient, AsyncQueryBuilder, AsyncQueryExecutionRequest,
    BatchCondition, BindingProjection, BindingValueRef, Client, CompareOp, DateTime,
    Disk, EdgeRef, Expr, HelixError, IndexDdlAlreadyActive, IndexSpec, InMemory,
    NodeRef, Order, Predicate, Projection, PropertyInput, PropertyValue, QueryRequest,
    RangeIndexDirection, RepeatConfig,
    SearchConsistency,      # (main)
    ShortestPathDirection, SourcePredicate, VectorDistanceMetric, define_params, g,
    param, parse_index_ddl_receipt, parse_index_operation_status, read_batch, sub,
    write_batch,
)
```

## Requests

```text
read_batch() -> ReadBatch
write_batch() -> WriteBatch
QueryRequest.read(batch, query_name=None)
QueryRequest.write(batch, query_name=None)
request.with_search_consistency(SearchConsistency.EVENTUAL)   # (main); reads only, writes reject eventual

batch.to_json_string()     # raw typed batch JSON
batch.to_query_request(params, values, query_name=..., search_consistency=...)
batch.to_query_json(params, values, query_name=..., search_consistency=...)
```

Batches serialize to the same JSON as Rust and TypeScript. Limits: body 16 MiB
locally (`invalid_request_body`; Helix Cloud 2 MiB, `413 payload_too_large`),
JSON nesting 255 levels (`invalid_query_json`).

## Batch Builders

Read and write batches:

```text
.var_as(name, traversal)
.var_as_if(name, condition, traversal)    # skipped -> []
.for_each_param(param_name, body_batch)
.returning(["var", ...])

BatchCondition.var_not_empty("users")
BatchCondition.var_empty("users")
BatchCondition.var_min_size("users", 10)
BatchCondition.prev_not_empty()
```

`for_each_param` runs the body once per array element; a body variable returns
only the **last** iteration. Read written rows back in a follow-up request.

## Parameters

```text
params = define_params({
    "tenant_id": param.string(),
    "limit": param.i64(),
    "created_after": param.date_time(),
    "query_vector": param.array(param.f32()),
    "metadata": param.object(param.value()),
})

params.tenant_id
params["tenant_id"]

Predicate.eq("tenantId", params.tenant_id)
g().n(NodeRef.param("node_ids"))     # node_ids: param.array(param.i64())
g().limit(params.limit)
g().set_property("name", params.name)
```

Schema constructors: `param.bool()`, `param.i64()`, `param.f64()`,
`param.f32()`, `param.string()`, `param.date_time()`, `param.bytes()` (schema
parity only; dynamic JSON rejects bytes values), `param.value()`,
`param.object(inner=None)`, `param.array(inner)`.

Datetime values accept `DateTime`, `datetime.datetime`, RFC3339 strings or epoch
millis, and serialize as UTC RFC3339 with millisecond precision.

## Values And Inputs

```text
PropertyValue.null()
PropertyValue.bool(True)
PropertyValue.i64(42)
PropertyValue.date_time(DateTime.from_millis(1776000000000))
PropertyValue.f64(1.5)
PropertyValue.f32(1.25)
PropertyValue.string("Alice")
PropertyValue.bytes(b"abc")
PropertyValue.i64_array([1, 2, 3])
PropertyValue.f64_array([1.0, 2.0])
PropertyValue.f32_array([1.0, 2.0])
PropertyValue.string_array(["a", "b"])
PropertyValue.array(["a", 7])
PropertyValue.object({"k": "v"})

PropertyInput.value("Alice")
PropertyInput.expr(Expr.prop("score"))
PropertyInput.param("name")
```

Most mutating/search methods accept plain Python values, `PropertyValue`,
`PropertyInput`, `Expr` or `ParamRef` and wrap them.

## Traversal Sources

```text
g()
sub()

g().n(NodeRef.id(1))
g().n(NodeRef.ids([1, 2]))
g().n(NodeRef.var("users"))
g().n(NodeRef.param("node_ids"))
g().n(NodeRef.all())
g().n_where(SourcePredicate.eq("tenantId", params.tenant_id))   # unlabeled: cannot use a label-scoped index
g().n_with_label("User")
g().n_with_label_where("User", pred)   # indexed lookups

g().e(EdgeRef.id(1))
g().e(EdgeRef.ids([1, 2]))
g().e(EdgeRef.var("edges"))
g().e(EdgeRef.param("edge_ids"))
g().e_where(pred)
g().e_with_label("FOLLOWS")
g().e_with_label_where("FOLLOWS", pred)
```

Whole-partition search and shortest path:

```text
g().vector_search_nodes("Document", "embedding", [1.0, 0.0, 0.0], 10, tenant_value="acme")
g().vector_search_nodes_with("Document", "embedding", params.query_vector.input(), params.limit, params.tenant_id.input())
g().text_search_nodes("Document", "body", "graph", 10, tenant_value="acme")
g().text_search_nodes_with("Document", "body", PropertyInput.param("query"), params.limit, PropertyInput.param("tenant_id"))
g().vector_search_edges(...)
g().text_search_edges(...)
g().shortest_path(NodeRef.param("from_id"), NodeRef.param("to_id"), 6, label="FOLLOWS", direction=ShortestPathDirection.BOTH)
```

`shortest_path(source, target, max_depth, label=None,
direction=ShortestPathDirection.OUT)` is an unweighted BFS returning the path's
node IDs, source first, or `[]` when none is within `max_depth` or an endpoint
is missing. An endpoint resolving to several nodes fails the request.

Traversal-scoped (prefiltered) search:

```text
candidate_nodes.vector_search("Document", "embedding", [1.0, 0.0, 0.0], 10, "acme")
candidate_nodes.vector_search_with("Document", "embedding", params.query_vector, params.limit, params.tenant_id)
candidate_edges.vector_search(...)
candidate_edges.vector_search_with(...)
candidate_nodes.text_search("Document", "body", "graph", 10, "acme")
candidate_nodes.text_search_with("Document", "body", params.query, params.limit, params.tenant_id)
candidate_edges.text_search(...)
candidate_edges.text_search_with(...)
```

Restricted vector search enforces exact candidate membership; ranking may still
use approximate index structures. Restricted BM25 returns at most `k`, ordered
by score descending then entity ID ascending, with partition-wide statistics.

## Traversal Steps

```text
# navigation
.out("FOLLOWS") .in_("FOLLOWS") .both("RELATED")
.out_e("FOLLOWS") .in_e("FOLLOWS") .both_e("RELATED")
.out_n() .in_n() .other_n()

# filters
.has("status", "active")
.has_label("User")
.has_key("externalId")
.where(Predicate.eq("tenantId", params.tenant_id))
.dedup()
.within("users")
.without("blocked")
.edge_has("weight", PropertyValue.f64(1.0))
.edge_has_label("FOLLOWS")

# bounds and variables
.limit(10)
.limit(params.limit)
.skip(params.offset)
.range(0, params.end)
.as_("x") .store("x") .select("x") .inject("x")

# terminals and projections
.count()
.exists()
.id()
.label()
.values(["name", "tier"])
.value_map(["$id", "name"])
.value_map(None)  # all properties
.project([
    Projection.property("$id", "id"),
    Projection.from_endpoint("resource_id", "from_id"),
    Projection.to_endpoint("resource_id", "to_id"),
    Projection.expr("score_plus_one", Expr.prop("score").add(Expr.val(1))),
])
.edge_properties()

# ordering and aggregation
.order_by("createdAt", Order.DESC)
.order_by_multiple([("status", Order.ASC), ("createdAt", Order.DESC)])
.group("status")
.group_count("status")
.aggregate_by(AggregateFunction.SUM, "score")   # COUNT, SUM, MIN, MAX, MEAN

# branching and repeat
.repeat(RepeatConfig.new(sub().out("FOLLOWS")).times(2).emit_after().max_depth(4))
.union([sub().out("FOLLOWS"), sub().in_("FOLLOWS")])
.choose(Predicate.eq("tier", "pro"), sub().out("PremiumContent"), sub().out("FreeContent"))
.coalesce([sub().out("PREFERRED_TEAM"), sub().out("PRIMARY_TEAM")])
.optional(sub().out("PROFILE"))

# reserved steps
.fold() .unfold() .path() .simple_path()
.with_sack(PropertyValue.i64(0)) .sack_set("score") .sack_add("score") .sack_get()

# mutations
.add_n("User", {"name": params.name, "tenantId": params.tenant_id})
.add_e("FOLLOWS", NodeRef.var("target"), {"since": params.since})
.set_property("name", params.name)
.remove_property("old")
.drop()
.drop_edge(NodeRef.var("target"))
.drop_edge_labeled(NodeRef.var("target"), "FOLLOWS")
.drop_edge_by_id(EdgeRef.id(123))
```

On edge streams, `Projection.from_endpoint(prop, alias)` serializes to
`{"source":"$from.<prop>","alias":"<alias>"}` and `to_endpoint` to
`{"source":"$to.<prop>","alias":"<alias>"}`. `.edge_properties()` returns full
edge maps with the internal `$from` / `$to` node ids.

## Indexes

```text
g().create_index_if_not_exists(IndexSpec.node_unique_equality("User", "userId"))
g().create_index_if_not_exists(IndexSpec.node_range_desc("User", "createdAt"))
g().create_index_if_not_exists(IndexSpec.node_range_with_direction("User", "createdAt", RangeIndexDirection.DESC))
g().create_index_if_not_exists(IndexSpec.edge_range_desc("FOLLOWS", "since"))
g().create_index_if_not_exists(IndexSpec.edge_range_with_direction("FOLLOWS", "since", RangeIndexDirection.DESC))
g().drop_index(IndexSpec.node_range("User", "score"))
g().create_vector_index_nodes("Document", "embedding", 1536, VectorDistanceMetric.COSINE, "tenantId")
g().create_text_index_nodes("Document", "body", "tenantId")

g().get_index_operation(operation_id)     # read batch; decode with parse_index_operation_status
g().retry_index_operation(operation_id)   # write batch; after fixing a blocker
g().abort_index_operation(operation_id)   # write batch; discards a constructing build
```

Range indexes default to `RangeIndexDirection.ASC`; use `DESC` for indexes that
mainly serve newest-first or high-score-first scans.

DDL returns a scalar receipt; decode with `parse_index_ddl_receipt(response["var"])`:

| Receipt `kind` | Fields | Next step |
| --- | --- | --- |
| `accepted` | `operation_id`, `index_id`, `generation` | Poll `operation_id`. |
| `existing_operation` | `operation_id` | Same build already in flight; poll it. |
| `already_active` | `index_id`, `generation` | Ready. |

Operation `status`: `queued`, `running`, `blocked`, `succeeded`, `aborted`.
`blocked` carries `blocker_code` (`invalid_source_data`, `uniqueness_violation`,
`oversized_entity`, `manifest_limit`, `object_store_configuration_unavailable`,
`invariant_violation`). A unique index rejects duplicate writes with
`unique_constraint_violation`; while it builds, only values already claimed (by
an entity the build has scanned, or a write since the build started) are
rejected, and a duplicate of a not-yet-scanned entity's value blocks the build
when the scan reaches it.

## Predicates And Expressions

```text
Predicate.eq("status", "active")
Predicate.neq("status", "deleted")
Predicate.gt("score", 10)
Predicate.gte("createdAt", params.created_after)
Predicate.lt("score", 100)
Predicate.lte("score", 100)
Predicate.between("score", 10, 20)
Predicate.has_key("email")
Predicate.is_null("deletedAt")
Predicate.is_not_null("email")
Predicate.starts_with("name", "Al")
Predicate.ends_with("email", "@example.com")
Predicate.contains("bio", "graph")
Predicate.is_in("status", ["active", "trial"])
Predicate.is_in_expr("status", params.statuses)
Predicate.and_([p1, p2])
Predicate.or_([p1, p2])
Predicate.not_(p1)
Predicate.compare(Expr.prop("score"), CompareOp.GT, Expr.val(10))

SourcePredicate.eq("tenantId", params.tenant_id)
SourcePredicate.and_([SourcePredicate.eq("tenantId", params.tenant_id), SourcePredicate.eq("status", "active")])

Expr.prop("score")
Expr.val(1)
Expr.id()
Expr.timestamp()
Expr.date_time_now()
Expr.param("limit")
Expr.prop("score").add(Expr.val(1))
Expr.prop("score").neg()
Expr.case([(Predicate.eq("tier", "pro"), Expr.val("paid"))], Expr.val("free"))
```

`SourcePredicate` is an alias of `Predicate` that marks source positions
(`n_where`, `n_with_label_where`, `e_where`, `e_with_label_where`); index use
depends on label scope and existing indexes, not the class. Expressions also
support `+`, `-`, `*`, `/`, `%` and unary `-`.

## Client

```text
client = Client("http://localhost:6969", api_key="hx_secret")
client.with_api_key(None)  # clear
client.base_url

client.query(request)
client.execute(request, writer_only=True)
client.execute(request, warm_only=True)           # reads only
client.execute(request, await_durability=False)   # writes only

# (main)
client.cypher(query, parameters=None, *, query_name=None, timeout=30, **execute_options)
client.explain_cypher(query, parameters=None, *, query_name=None, timeout=30, **execute_options)
client.sql(query, parameters=None, *, mappings=None, query_name=None, timeout=30, **execute_options)
client.explain_sql(...)
# -> {"columns": [...], "rows": [[...], ...]}
```

The client returns parsed JSON and raises `HelixError` for network, remote,
serialization, URL, request or embedded failures:

| Attribute | Meaning |
| --- | --- |
| `kind` | `Network`, `Remote`, `Serialization`, `InvalidUrl`, `InvalidRequest`, embedded kinds |
| `code` (main) | The body's `error` field (open string; keep unknown codes) |
| `details` | Diagnostic (`msg`); the raw response body in 0.3.4 |
| `status_code` | HTTP status for remote failures |
| `retryable` / `is_retryable()` (main) | The server's `retryable` hint; `is_retryable()` is `True` only when it is `true` |
| `is_index_backpressure()` (main) | `code == "index_backpressure"` |

| Class | HTTP | `retryable` | A failed write | Codes |
| --- | ---: | --- | --- | --- |
| Invalid request | 400 | absent | committed nothing | `invalid_request`, `invalid_query_json` (malformed, unknown field, nesting > 255), `invalid_request_body` (unreadable, > 16 MiB), `invalid_request_option`, `invalid_node_id`, `unbound_parameter`, `active_text_mutation_limit_exceeded`, `invalid_index_source_data`, `invalid_secondary_index_value`, `unsupported_unique_index_value_type`, `invalid_vector_dimension`, `invalid_vector_component`, ... |
| Planning | 400 | absent | committed nothing | `invalid_after_bind_operation`, `read_only_traversal_in_write_batch`, `duplicate_projection_alias`, `invalid_search_result_count`, `invalid_repeat_count`, `invalid_shortest_path_count`, ... |
| Not found | 404 | absent | committed nothing | `node_not_found`, `edge_not_found`, `index_not_found`, `index_operation_not_found` |
| Timeout | 408 | absent | may have committed | `query_deadline_exceeded` |
| Retryable conflict | 409 | `true` | committed nothing | `transaction_conflict`, `request_read_view_changed`, `stale_index_generation` |
| Conflict with database state | 409 | `false` | committed nothing | `unique_constraint_violation`, `index_already_exists`, `index_definition_conflict`, `index_busy`, `index_operation_not_abortable`, `index_build_blocked` |
| Index backpressure | 429 | `true` | committed nothing | `index_backpressure` |
| Resource limit | 429 | absent | committed nothing | `query_memory_limit_exceeded` |
| Internal | 500 | absent | may have committed | `storage_error`, `internal_error`, ... |
| Unavailable | 503 | absent | committed nothing | `writer_mode_required`, `reader_mode_required`, `database_closed`, `index_lifecycle_unavailable`, `migration_required`, ... |
| Commit outcome unknown | 503 | `false` | may have committed | `writer_fenced_commit_outcome_unknown` |

Full catalog: https://docs.helix-db.com/database/helix-db/query-guides/error-handling.
Helix Cloud gateway codes (`query_timeout` 408, `rate_limited` 429,
`payload_too_large` 413, `write_outcome_unknown` 503):
https://docs.helix-db.com/database/helix-cloud/operate/error-handling; honor
`Retry-After` through direct HTTP.

Cypher/SQL statement failures return
`{"error": "<category>", "msg", "details": {"detail", "phase", "span"}}`;
`unsupported_feature` names the rejected construct in `details.detail`.

## Async Client

```text
import httpx

async_client = AsyncClient(
    "http://localhost:6969",
    api_key="hx_secret",
    timeout=None,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
)

async with async_client:
    response = await async_client.query(request)
    response = await async_client.query(request, timeout=2.0)
    response = await async_client.execute(request, writer_only=True)

# header control or raw bytes
response = await async_client.request_builder() \
    .writer_only() \
    .should_await_durability(False) \
    .query(request) \
    .send()
raw = await async_client.request_builder().query(request).send_bytes()

# embedded (requires helix-db-embedded)
writer = await AsyncClient.embedded(InMemory("app"))
reader = await AsyncClient.embedded_reader(Disk("./data", "app"))

async with writer:
    response = await writer.query(request)
```

`AsyncClient` owns a reusable HTTPX pool with no default timeout. Close it with
`async with` or `await close()` (idempotent). Cancellation closes the response
stream and leaves the client reusable. Embedded requests reject server routing
options and per-request timeouts; use `asyncio.timeout(...)`. Native graph
loading stays synchronous through `Client.graph(...)`.

## Row Bindings

```text
.bind("user")
.project_bindings([BindingProjection.binding("user", "name", "name"), ...])
.project_distinct_bindings([BindingProjection.binding("user", "$id", "user_id"), ...])
BindingProjection.coalesce([BindingValueRef.binding(...), ...], alias)   # first bound, non-null value
```

Examples: `EXAMPLES.md` §10 (pairs) and §13 (OPTIONAL MATCH).
