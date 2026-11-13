# Helix Query Authoring - Python Reference

Use this reference to confirm Python SDK method names and request patterns.
Install with `pip install helix-db` (import `helixdb`, Python 3.10+). Names are
checked against the SDK source on helix-db `main`; items marked **main only**
are not in the published 0.3.4 package. Server behavior is checked against
Docker `ghcr.io/helixdb/helixdb:v0.0.16`.

```text
from helixdb import (
    AggregateFunction,
    AsyncClient,
    AsyncQueryBuilder,
    AsyncQueryExecutionRequest,
    BatchCondition,
    BindingProjection,
    BindingValueRef,
    Client,
    CompareOp,
    DateTime,
    Disk,
    EdgeRef,
    Expr,
    HelixError,
    IndexDdlAlreadyActive,
    IndexSpec,
    InMemory,
    NodeRef,
    Order,
    Predicate,
    Projection,
    PropertyInput,
    PropertyValue,
    QueryRequest,
    RangeIndexDirection,
    RepeatConfig,
    SearchConsistency,      # main only
    ShortestPathDirection,
    SourcePredicate,
    VectorDistanceMetric,
    define_params,
    g,
    param,
    parse_index_ddl_receipt,
    parse_index_operation_status,
    read_batch,
    sub,
    write_batch,
)
```

## Request Shape

```text
read_batch() -> ReadBatch
write_batch() -> WriteBatch
QueryRequest.read(batch, query_name=None)
QueryRequest.write(batch, query_name=None)
request.with_search_consistency(SearchConsistency.EVENTUAL)   # main only; reads only
```

Batches serialize to the same JSON shape as Rust and TypeScript:

```text
batch.to_json_string()     # raw typed batch JSON
batch.to_query_request(params, values, query_name=..., search_consistency=...)
batch.to_query_json(params, values, query_name=..., search_consistency=...)
```

`search_consistency` (**main only**) is `strong` by default: searches include
committed but unpublished vector/text work. `eventual` includes a bounded amount
of it and can return a hit whose tenant, label or property changed since the
last publication. A write request rejects `eventual`. With 0.3.4, add
`"search_consistency": "eventual"` to the JSON body yourself.

Limits: a request body is at most 16 MiB locally (2 MiB on Helix Cloud) and
JSON nests at most 255 levels.

## Batch Builders

Both read and write batches support:

```text
.var_as(name, traversal)
.var_as_if(name, condition, traversal)
.for_each_param(param_name, body_batch)
.returning(["var", ...])
```

Read batches reject write traversals. Write batches accept read-only and write traversals.

`for_each_param` runs the body once per array element; a variable assigned in
the body holds only the **last** iteration when returned. Read the written rows
back in a follow-up request if you need them all.

Conditions (a skipped `var_as_if` returns `[]`):

```text
BatchCondition.var_not_empty("users")
BatchCondition.var_empty("users")
BatchCondition.var_min_size("users", 10)
BatchCondition.prev_not_empty()
```

## Parameters

```text
params = define_params({
    "tenant_id": param.string(),
    "limit": param.i64(),
    "created_after": param.date_time(),
    "query_vector": param.array(param.f32()),
    "metadata": param.object(param.value()),
})
```

Parameter refs are attributes and items:

```text
params.tenant_id
params["tenant_id"]
```

Use refs directly where accepted:

```text
Predicate.eq("tenantId", params.tenant_id)
g().n(NodeRef.param("node_ids"))     # node_ids: param.array(param.i64()); IDs are integers
g().limit(params.limit)
g().set_property("name", params.name)
```

Schema constructors:

```text
param.bool()
param.i64()
param.f64()
param.f32()
param.string()
param.date_time()
param.bytes()      # schema parity only; dynamic JSON rejects bytes values
param.value()
param.object(inner=None)
param.array(inner)
```

Dynamic datetime values accept `DateTime`, `datetime.datetime`, RFC3339 strings, or epoch millis. They serialize as UTC RFC3339 strings with millisecond precision.

## Values And Inputs

Tagged property values:

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
```

Property inputs:

```text
PropertyInput.value("Alice")
PropertyInput.expr(Expr.prop("score"))
PropertyInput.param("name")
```

Most mutating/search methods accept normal Python values, `PropertyValue`, `PropertyInput`, `Expr`, or `ParamRef` and convert to the correct wrapper.

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
g().n_with_label_where("User", pred)   # use this for indexed lookups

g().e(EdgeRef.id(1))
g().e(EdgeRef.ids([1, 2]))
g().e(EdgeRef.var("edges"))
g().e(EdgeRef.param("edge_ids"))
g().e_where(pred)
g().e_with_label("FOLLOWS")
g().e_with_label_where("FOLLOWS", pred)
```

Search:

```text
g().vector_search_nodes("Document", "embedding", [1.0, 0.0, 0.0], 10, tenant_value="acme")
g().vector_search_nodes_with("Document", "embedding", params.query_vector.input(), params.limit, params.tenant_id.input())
g().text_search_nodes("Document", "body", "graph", 10, tenant_value="acme")
g().text_search_nodes_with("Document", "body", PropertyInput.param("query"), params.limit, PropertyInput.param("tenant_id"))
g().vector_search_edges(...)
g().text_search_edges(...)
g().shortest_path(NodeRef.param("from_id"), NodeRef.param("to_id"), 6, label="FOLLOWS", direction=ShortestPathDirection.BOTH)
```

`shortest_path` is an unweighted BFS. It returns the node IDs on the path,
source first, or `[]` when there is none within `max_depth` or an endpoint is
missing; an endpoint that resolves to several nodes fails the request.

These source methods search the whole selected tenant partition. For an exact
vector or BM25 prefilter, start with a node or edge traversal and use:

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

Restricted vector search enforces exact candidate membership while ranking may
still use approximate index structures; project `$distance`. Restricted BM25
search returns at most `k`, ordered by score descending then entity ID ascending,
with partition-wide statistics; project `$score`. Pass the same tenant partition
used to construct candidates.

Limits: whole-index vector search caps the effective result count at 800. A
restricted vector search fails when `min(k, unique candidates)` exceeds 800;
restricted text returns at most `min(unique candidates, k, 800)`. More than
1,000,000 unique candidates fails either search.

Project `$distance` for vector hits or `$score` for BM25 hits before navigating
away from the hit stream.

## Traversal Steps

Navigation:

```text
.out("FOLLOWS") .in_("FOLLOWS") .both("RELATED")
.out_e("FOLLOWS") .in_e("FOLLOWS") .both_e("RELATED")
.out_n() .in_n() .other_n()
```

Filters:

```text
.has("status", "active")
.has_label("User")
.has_key("externalId")
.where(Predicate.eq("tenantId", params.tenant_id))
.dedup()
.within("users")
.without("blocked")
.edge_has("weight", PropertyValue.f64(1.0))
.edge_has_label("FOLLOWS")
```

Bounds and variables:

```text
.limit(10)
.limit(params.limit)
.skip(params.offset)
.range(0, params.end)
.as_("x") .store("x") .select("x") .inject("x")
```

Terminals and projections (an unprojected element stream returns
`{"$id": N}` per element; project to get properties):

```text
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
```

On edge streams, `Projection.from_endpoint(prop, alias)` serializes to
`{"source":"$from.<prop>","alias":"<alias>"}` and
`Projection.to_endpoint(prop, alias)` serializes to
`{"source":"$to.<prop>","alias":"<alias>"}`. Use these to return source/target
node properties such as resource ids without traversing from every edge to its
endpoints. Keep `.edge_properties()` for full edge maps and the internal `$from`
/ `$to` node ids.

Ordering and aggregation:

```text
.order_by("createdAt", Order.DESC)
.order_by_multiple([("status", Order.ASC), ("createdAt", Order.DESC)])
.group("status")
.group_count("status")
.aggregate_by(AggregateFunction.SUM, "score")   # COUNT, SUM, MIN, MAX, MEAN
```

Rows missing the sort property sort first for `Order.ASC` and last for
`Order.DESC`, the opposite of Cypher/SQL defaults. When their position matters
in a translated `ORDER BY`, query them separately (`Predicate.is_null(...)` /
`Predicate.is_not_null(...)`) and concatenate in the order the source expects.

Branching and repeat:

```text
.repeat(RepeatConfig.new(sub().out("FOLLOWS")).times(2).emit_after().max_depth(4))
.union([sub().out("FOLLOWS"), sub().in_("FOLLOWS")])
.choose(Predicate.eq("tier", "pro"), sub().out("PremiumContent"), sub().out("FreeContent"))
.coalesce([sub().out("PREFERRED_TEAM"), sub().out("PRIMARY_TEAM")])
.optional(sub().out("PROFILE"))
```

- `emit_after()` emits each iteration's output (Gremlin postfix `.emit()`);
  `emit_before()` emits each iteration's input; `emit_all()` emits both, so a
  node reached at depth 1 appears twice. Without an emit, only the final
  iteration's rows are returned.
- `choose` without an else branch drops rows that fail the condition. For a
  per-row value (Cypher `CASE`), use `Expr.case` in a projection.
- `optional(sub)` passes the input row through when the branch is empty, so the
  current element is still the input. For OPTIONAL MATCH semantics, see
  [Row Bindings](#row-bindings).

Reserved steps execute (they are not no-ops):

```text
.fold() .unfold() .path() .simple_path()
.with_sack(PropertyValue.i64(0)) .sack_set("score") .sack_add("score") .sack_get()
```

Mutations:

```text
.add_n("User", {"name": params.name, "tenantId": params.tenant_id})
.add_e("FOLLOWS", NodeRef.var("target"), {"since": params.since})
.set_property("name", params.name)
.remove_property("old")
.drop()
.drop_edge(NodeRef.var("target"))
.drop_edge_labeled(NodeRef.var("target"), "FOLLOWS")
.drop_edge_by_id(EdgeRef.id(123))
```

Indexes:

```text
g().create_index_if_not_exists(IndexSpec.node_unique_equality("User", "userId"))
g().create_index_if_not_exists(IndexSpec.node_range_desc("User", "createdAt"))
g().create_index_if_not_exists(IndexSpec.node_range_with_direction("User", "createdAt", RangeIndexDirection.DESC))
g().create_index_if_not_exists(IndexSpec.edge_range_desc("FOLLOWS", "since"))
g().create_index_if_not_exists(IndexSpec.edge_range_with_direction("FOLLOWS", "since", RangeIndexDirection.DESC))
g().drop_index(IndexSpec.node_range("User", "score"))
g().create_vector_index_nodes("Document", "embedding", 1536, VectorDistanceMetric.COSINE, "tenantId")
g().create_text_index_nodes("Document", "body", "tenantId")
```

Range indexes default to ascending physical order (`RangeIndexDirection.ASC`). Use `RangeIndexDirection.DESC` for descending indexes that primarily serve newest-first or high-score-first scans.

Index DDL is asynchronous. Each call returns a scalar receipt; decode it with
`parse_index_ddl_receipt(response["var"])`:

| Receipt `kind` | Fields | Next step |
| --- | --- | --- |
| `accepted` | `operation_id`, `index_id`, `generation` | Poll `operation_id`. |
| `existing_operation` | `operation_id` | The same build is already in flight; poll it. |
| `already_active` | `index_id`, `generation` | Ready. |

```text
g().get_index_operation(operation_id)     # read batch; decode with parse_index_operation_status
g().retry_index_operation(operation_id)   # write batch; after fixing a blocker
g().abort_index_operation(operation_id)   # write batch; discards a constructing build
```

The status `status` is `queued`, `running`, `blocked`, `succeeded` or `aborted`.
A query cannot use the index until the build succeeds. `blocked` carries
`blocker_code` (`invalid_source_data`, `uniqueness_violation`,
`oversized_entity`, `manifest_limit`, `object_store_configuration_unavailable`,
`invariant_violation`) and does not resume on its own. A unique index rejects
duplicate writes with `unique_constraint_violation` from the moment its build
starts.

## Predicates And Expressions

Predicates:

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
```

`SourcePredicate` is an alias of `Predicate`; the name only marks source
positions (`n_where`, `n_with_label_where`, `e_where`, `e_with_label_where`).
Whether an index is used depends on the label scope and the indexes that exist,
not on the class:

```text
SourcePredicate.eq("tenantId", params.tenant_id)
SourcePredicate.and_([SourcePredicate.eq("tenantId", params.tenant_id), SourcePredicate.eq("status", "active")])
```

Expressions:

```text
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

`Expr.case` is the translation of Cypher/SQL `CASE`: use it inside
`Projection.expr(alias, ...)` or a property input, not `choose`.

Python operators are also available for expressions: `+`, `-`, `*`, `/`, `%`, and unary `-`.

## Client

Synchronous server execution:

```text
client = Client("http://localhost:6969", api_key="hx_secret")
client.with_api_key(None)  # clear
client.base_url
```

Execute a request directly:

```text
client.query(request)
client.execute(request, writer_only=True)
client.execute(request, warm_only=True)           # reads only
client.execute(request, await_durability=False)   # writes only; skip the durability wait
```

Writes wait for durability by default (no header). `await_durability=False`
returns once the write is applied on the writer; a crash before the WAL upload
loses it. It does not reduce conflicts. `await_durability=True` or
`warm_only=True` on the wrong request type is `400 invalid_request_option`.

Native Cypher and SQL (**main only**; with 0.3.4 post the same JSON body to
`/v2/cypher`, `/v2/cypher/explain`, `/v2/sql` or `/v2/sql/explain`):

```text
client.cypher(query, parameters=None, *, query_name=None, timeout=30, **execute_options)
client.explain_cypher(query, parameters=None, *, query_name=None, timeout=30, **execute_options)
client.sql(query, parameters=None, *, mappings=None, query_name=None, timeout=30, **execute_options)
client.explain_sql(...)
# -> {"columns": [...], "rows": [[...], ...]}
```

The client returns parsed JSON and raises `HelixError` for network, remote,
serialization, URL, request, or embedded failures:

| Attribute | Meaning |
| --- | --- |
| `kind` | `Network`, `Remote`, `Serialization`, `InvalidUrl`, `InvalidRequest`, embedded kinds |
| `code` (**main only**) | The body's `error` field (open string; keep unknown codes) |
| `details` | Diagnostic (`msg`); the raw response body in 0.3.4 |
| `status_code` | HTTP status for remote failures |
| `retryable` / `is_retryable()` (**main only**) | The server's `retryable` hint; `is_retryable()` is `True` only when it is `true` |
| `is_index_backpressure()` (**main only**) | `code == "index_backpressure"` |

With 0.3.4 (no `code` / `retryable`), `details` holds the raw remote body;
`json.loads(error.details)` and read `error` and `retryable`. Never parse
the diagnostic text to classify a failure.

Every code has one class, and the class sets the status and `retryable`
(source: `crates/ast/src/error_code.rs`):

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

- Retry `retryable: true` codes with bounded backoff and jitter; rebuild a
  write from freshly read state when it depends on what it read.
- `unique_constraint_violation`: report the duplicate, or re-run an upsert once
  (it then takes the update branch).
- `index_busy`: wait for the running lifecycle operation. `index_build_blocked`:
  fix the blocked build's `blocker_code`, then retry or abort that operation.
- Timeout, internal, commit-outcome-unknown and `Network` failures after a write
  was sent: reconcile (read back by key) before resubmitting.
- Helix Cloud's gateway adds its own codes, such as `query_timeout` (408),
  `rate_limited` (429, honor `Retry-After` through direct HTTP; the SDK does
  not expose headers), `payload_too_large` (413, 2 MiB) and
  `write_outcome_unknown` (503). See
  https://docs.helix-db.com/database/helix-cloud/operate/error-handling.

Cypher/SQL statement failures use
`{"error": "<category>", "msg", "details": {"detail", "phase", "span"}}`;
`unsupported_feature` names the rejected construct in `details.detail`.

A Helix Cloud warm read returns `204 No Content` with no query payload after
fanout. 0.3.4 accepts only 200 and raises a remote `HelixError` for it; `main`
accepts 204. Combine `warm_only=True` with `writer_only=True` to target only
the authoritative writer.

Every returned row stream is a list, and an empty one is `[]`, including an
at-most-one lookup (`n(NodeRef.id(...))`, `limit(1)`) and a skipped
`var_as_if`. Only `count()` (`0`), `exists()` (`False`) and index DDL /
lifecycle operations return scalars; an empty returns list produces `{}`. Type
single-row fields as `list[UserRow]` and take the first element.

Asynchronous server execution:

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
```

`AsyncClient` owns a reusable HTTPX connection pool. The default timeout is
disabled. Close the client with `async with` or `await close()`; closure is
idempotent. Request cancellation closes the response stream and leaves the
client reusable.

Use the asynchronous request builder when header control or raw bytes are
required:

```text
response = await async_client.request_builder() \
    .writer_only() \
    .should_await_durability(False) \
    .query(request) \
    .send()
raw = await async_client.request_builder().query(request).send_bytes()
```

Asynchronous embedded execution requires `helix-db-embedded`:

```text
writer = await AsyncClient.embedded(InMemory("app"))
reader = await AsyncClient.embedded_reader(Disk("./data", "app"))

async with writer:
    response = await writer.query(request)
```

Embedded async requests reject server routing options and per-request client
timeouts; use `asyncio.timeout(...)` for a cancellation boundary. Native graph
loading remains synchronous through `Client.graph(...)`.

## Row Bindings

```text
g().n_with_label("User") \
    .bind("user") \
    .out("FOLLOWS") \
    .bind("friend") \
    .project_distinct_bindings([
        BindingProjection.binding("user", "$id", "user_id"),
        BindingProjection.binding("friend", "$id", "friend_id"),
    ])

# OPTIONAL MATCH (u:User)-[:WORKS_AT]->(c:Company)
g().n_with_label("User") \
    .bind("user") \
    .optional(sub().out("WORKS_AT").has_label("Company").bind("employer")) \
    .project_bindings([
        BindingProjection.binding("user", "name", "name"),
        BindingProjection.binding("employer", "name", "employer"),
    ])
```

A binding that was never set (an empty optional branch) leaves its alias out of
the row. `BindingProjection.coalesce([BindingValueRef.binding(...), ...], alias)`
takes the first bound, non-null value. After a `bind`, `order_by`, `choose`,
`repeat`, `values`, `value_map`, `project`, `id`, `label` and
`edge_properties` are rejected (`invalid_after_bind_operation`); order before
binding and finish with `project_bindings`, `count` or `exists`.

Stored routes, registration, and query bundles are not supported.
