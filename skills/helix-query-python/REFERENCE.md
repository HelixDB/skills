# Helix Query Authoring - Python Reference

Use this reference to confirm published Python SDK method names and request
patterns. The package is `helix-db` and the import is `helixdb`.

```text
from helixdb import (
    AggregateFunction,
    AsyncClient,
    AsyncQueryBuilder,
    AsyncQueryExecutionRequest,
    BatchCondition,
    BindingProjection,
    Client,
    CompareOp,
    DateTime,
    Disk,
    EdgeRef,
    Expr,
    IndexSpec,
    InMemory,
    NodeRef,
    Order,
    Predicate,
    Projection,
    PropertyInput,
    PropertyValue,
    RangeIndexDirection,
    RepeatConfig,
    SourcePredicate,
    VectorDistanceMetric,
    define_params,
    g,
    param,
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
```

Batches serialize to the same JSON shape as Rust and TypeScript:

```text
batch.to_json_string()     # raw typed batch JSON
batch.to_query_request()   # direct QueryRequest object
batch.to_query_json()      # request JSON string for POST /v2/query
```

## Batch Builders

Both read and write batches support:

```text
.var_as(name, traversal)
.var_as_if(name, condition, traversal)
.for_each_param(param_name, body_batch)
.returning(["var", ...])
```

Read batches reject write traversals. Write batches accept read-only and write traversals.

Conditions:

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
g().n(NodeRef.param("node_ids"))
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
g().n_where(SourcePredicate.eq("tenantId", params.tenant_id))
g().n_with_label("User")
g().n_with_label_where("User", pred)

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
```

These source methods search the whole selected tenant partition. For an exact
BM25 prefilter, start with a node or edge traversal and use:

```text
candidate_nodes.text_search("Document", "body", "graph", 10, "acme")
candidate_nodes.text_search_with("Document", "body", params.query, params.limit, params.tenant_id)
candidate_edges.text_search(...)
candidate_edges.text_search_with(...)
```

Restricted search deduplicates input IDs and returns at most `k`, ordered by
score descending then entity ID ascending. BM25 statistics remain global to
the tenant partition. The selected row keeps bindings, path, and sack, and
receives `$score`. Empty input skips the index. Wrong-kind input or more than
1,000,000 unique candidates is a query error. Pass the same tenant partition
used to construct candidates.

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

Terminals and projections:

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
.aggregate_by(AggregateFunction.SUM, "score")
```

Branching and repeat:

```text
.repeat(RepeatConfig.new(sub().out("FOLLOWS")).times(2).emit_all().max_depth(4))
.union([sub().out("FOLLOWS"), sub().in_("FOLLOWS")])
.choose(Predicate.eq("tier", "pro"), sub().out("PremiumContent"), sub().out("FreeContent"))
.coalesce([sub().out("PREFERRED_TEAM"), sub().out("PRIMARY_TEAM")])
.optional(sub().out("PROFILE"))
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

Source predicates are the index-eligible source-side subset:

```text
SourcePredicate.eq("$label", "User")
SourcePredicate.and_([SourcePredicate.eq("$label", "User"), SourcePredicate.eq("tenantId", params.tenant_id)])
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
client.execute(request, warm_only=True)
client.execute(request, await_durability=True)
```

The client returns parsed JSON and raises `HelixError` for network, remote,
serialization, URL, or request failures. A Helix Cloud warm read returns
`204 No Content` with no query payload after fanout; standalone `v0.0.3`
warming returns the normal response. Combine `warm_only=True` with
`writer_only=True` to warm only the authoritative writer.

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
    response = await async_client.execute(request, writer_only=True, await_durability=True)
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
    .should_await_durability(True) \
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
```

Stored routes, registration, and query bundles are not supported.
