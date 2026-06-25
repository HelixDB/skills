# Helix Query Authoring - Python Reference

Use this reference to confirm Python SDK method names and request patterns. Import from `helixdb`:

```python
from helixdb import (
    AggregateFunction,
    BatchCondition,
    Client,
    CompareOp,
    DateTime,
    EdgeRef,
    Expr,
    IndexSpec,
    NodeRef,
    Order,
    Predicate,
    Projection,
    PropertyInput,
    PropertyValue,
    RangeIndexDirection,
    RepeatConfig,
    SourcePredicate,
    define_params,
    g,
    param,
    read_batch,
    sub,
    write_batch,
)
```

## Request Shape

```python
read_batch() -> ReadBatch
write_batch() -> WriteBatch
DynamicQueryRequest.read(batch, query_name=None)
DynamicQueryRequest.write(batch, query_name=None)
```

Batches serialize to the same JSON shape as Rust and TypeScript:

```python
batch.to_json_string()      # raw {queries, returns} batch JSON
batch.to_dynamic_request()  # dynamic request object
batch.to_dynamic_json()     # request JSON string for POST /v1/query
```

## Batch Builders

Both read and write batches support:

```python
.var_as(name, traversal)
.var_as_if(name, condition, traversal)
.for_each_param(param_name, body_batch)
.returning(["var", ...])
```

Read batches reject write traversals. Write batches accept read-only and write traversals.

Conditions:

```python
BatchCondition.var_not_empty("users")
BatchCondition.var_empty("users")
BatchCondition.var_min_size("users", 10)
BatchCondition.prev_not_empty()
```

## Parameters

```python
params = define_params({
    "tenant_id": param.string(),
    "limit": param.i64(),
    "created_after": param.date_time(),
    "query_vector": param.array(param.f32()),
    "metadata": param.object(param.value()),
})
```

Parameter refs are attributes and items:

```python
params.tenant_id
params["tenant_id"]
```

Use refs directly where accepted:

```python
Predicate.eq("tenantId", params.tenant_id)
g().n(NodeRef.param("node_ids"))
g().limit(params.limit)
g().set_property("name", params.name)
```

Schema constructors:

```python
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

```python
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

```python
PropertyInput.value("Alice")
PropertyInput.expr(Expr.prop("score"))
PropertyInput.param("name")
```

Most mutating/search methods accept normal Python values, `PropertyValue`, `PropertyInput`, `Expr`, or `ParamRef` and convert to the correct wrapper.

## Traversal Sources

```python
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

```python
g().vector_search_nodes("Document", "embedding", [1.0, 0.0, 0.0], 10, tenant_value="acme")
g().vector_search_nodes_with("Document", "embedding", params.query_vector.input(), params.limit, params.tenant_id.input())
g().text_search_nodes("Document", "body", "graph", 10, tenant_value="acme")
g().text_search_nodes_with("Document", "body", PropertyInput.param("query"), params.limit, PropertyInput.param("tenant_id"))
g().vector_search_edges(...)
g().text_search_edges(...)
```

Project `$distance` before navigating away from a vector/text hit stream.

## Traversal Steps

Navigation:

```python
.out("FOLLOWS") .in_("FOLLOWS") .both("RELATED")
.out_e("FOLLOWS") .in_e("FOLLOWS") .both_e("RELATED")
.out_n() .in_n() .other_n()
```

Filters:

```python
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

```python
.limit(10)
.limit(params.limit)
.skip(params.offset)
.range(0, params.end)
.as_("x") .store("x") .select("x") .inject("x")
```

Terminals and projections:

```python
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

```python
.order_by("createdAt", Order.DESC)
.order_by_multiple([("status", Order.ASC), ("createdAt", Order.DESC)])
.group("status")
.group_count("status")
.aggregate_by(AggregateFunction.SUM, "score")
```

Branching and repeat:

```python
.repeat(RepeatConfig.new(sub().out("FOLLOWS")).times(2).emit_all().max_depth(4))
.union([sub().out("FOLLOWS"), sub().in_("FOLLOWS")])
.choose(Predicate.eq("tier", "pro"), sub().out("PremiumContent"), sub().out("FreeContent"))
.coalesce([sub().out("PREFERRED_TEAM"), sub().out("PRIMARY_TEAM")])
.optional(sub().out("PROFILE"))
```

Mutations:

```python
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

```python
g().create_index_if_not_exists(IndexSpec.node_unique_equality("User", "userId"))
g().create_index_if_not_exists(IndexSpec.node_range_desc("User", "createdAt"))
g().create_index_if_not_exists(IndexSpec.node_range_with_direction("User", "createdAt", RangeIndexDirection.DESC))
g().create_index_if_not_exists(IndexSpec.edge_range_desc("FOLLOWS", "since"))
g().create_index_if_not_exists(IndexSpec.edge_range_with_direction("FOLLOWS", "since", RangeIndexDirection.DESC))
g().drop_index(IndexSpec.node_range("User", "score"))
g().create_vector_index_nodes("Document", "embedding", "tenantId")
g().create_text_index_nodes("Document", "body", "tenantId")
```

Range indexes default to ascending physical order (`RangeIndexDirection.ASC`). Use `RangeIndexDirection.DESC` for descending indexes that primarily serve newest-first or high-score-first scans.

## Predicates And Expressions

Predicates:

```python
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

```python
SourcePredicate.eq("$label", "User")
SourcePredicate.and_([SourcePredicate.eq("$label", "User"), SourcePredicate.eq("tenantId", params.tenant_id)])
```

Expressions:

```python
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

```python
client = Client("http://localhost:6969", api_key="hx_secret")
client.with_api_key(None)  # clear
client.base_url
```

Request builder:

```python
client.query().dynamic(request).send()
client.query().body({"tenant_id": "acme"}).stored("find_users").send()
client.query().writer_only().dynamic(request).send()
client.query().warm_only().dynamic(request).send()
client.query().should_await_durability(True).dynamic(request).send()
```

`send()` returns parsed JSON on HTTP 200, returns `None` for an empty 200 body, and raises `HelixError` with `kind` in `Network`, `Remote`, `Serialization`, or `InvalidUrl` otherwise.

## Bundles

```python
queries = define_queries({
    "read": {"find_users": register_read(find_users, params)},
    "write": {"add_user": register_write(add_user, add_user_params)},
})

queries.call.find_users({"tenant_id": "acme", "limit": 25})
bundle = queries.build_query_bundle()
queries.generate("queries.json")
```

Route names must be unique across read and write routes. The Python SDK serializes and reads **only** `QUERY_BUNDLE_VERSION = 4`. The Rust, TypeScript, and Go SDKs are at v5 (they read both v4 and v5); a v5 bundle — for example one using row bindings, which Python does not support — will not deserialize in the Python SDK.
