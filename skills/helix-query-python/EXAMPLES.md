# Helix Query Authoring - Python Examples

All snippets assume:

```python
from helixdb import (
    BatchCondition,
    Client,
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
    RepeatConfig,
    define_params,
    define_queries,
    g,
    param,
    read_batch,
    register_read,
    register_write,
    sub,
    write_batch,
)
```

## 1. Count Nodes Matching A Label And Predicate

```python
def active_user_count():
    return (
        read_batch()
        .var_as(
            "active_count",
            g().n_with_label("User").where(Predicate.eq("status", "active")).count(),
        )
        .returning(["active_count"])
    )

request = active_user_count().to_dynamic_request(query_name="active_user_count")
```

## 2. Read Users With Runtime Params

```python
find_users_params = define_params({
    "tenant_id": param.string(),
    "limit": param.i64(),
})


def find_users(p=find_users_params):
    return (
        read_batch()
        .var_as(
            "users",
            g()
            .n_with_label("User")
            .where(Predicate.eq("tenantId", p.tenant_id))
            .limit(p.limit)
            .project([
                Projection.property("$id", "id"),
                Projection.property("name"),
                Projection.property("tenantId"),
            ]),
        )
        .returning(["users"])
    )

request = find_users().to_dynamic_request(
    find_users_params,
    {"tenant_id": "acme", "limit": 25},
    query_name="find_users",
)
```

Direct values such as `Predicate.eq("tenantId", "acme")` are literals in the AST. Use params for values that vary per request.

## 3. Execute A Query

```python
client = Client("http://localhost:6969")
response = client.query().dynamic(request).send()
users = response["users"]
```

With Helix Cloud auth:

```python
client = Client("https://helix.example.com", api_key="hx_secret")
response = client.query().dynamic(request).send()
```

## 4. Create A Node

```python
create_user_params = define_params({
    "name": param.string(),
    "tenant_id": param.string(),
})


def create_user(p=create_user_params):
    return (
        write_batch()
        .var_as("user", g().add_n("User", {"name": p.name, "tenantId": p.tenant_id}))
        .returning(["user"])
    )

created = (
    client
    .query()
    .writer_only()
    .should_await_durability(True)
    .dynamic(create_user().to_dynamic_request(create_user_params, {"name": "Alice", "tenant_id": "acme"}, query_name="create_user"))
    .send()
)
```

## 5. Explicit Create Or Update

```python
upsert_user_params = define_params({"user_id": param.string(), "name": param.string()})


def upsert_user(p=upsert_user_params):
    return (
        write_batch()
        .var_as("existing", g().n_with_label("User").where(Predicate.eq("userId", p.user_id)))
        .var_as_if(
            "updated",
            BatchCondition.var_not_empty("existing"),
            g().n(NodeRef.var("existing")).set_property("name", p.name),
        )
        .var_as_if(
            "created",
            BatchCondition.var_empty("existing"),
            g().add_n("User", {"userId": p.user_id, "name": p.name}),
        )
        .returning(["updated", "created"])
    )
```

## 6. Vector Search With Tenant Scope

```python
nearest_documents_params = define_params({
    "tenant_id": param.string(),
    "query_vector": param.array(param.f32()),
    "limit": param.i64(),
})


def nearest_documents(p=nearest_documents_params):
    return (
        read_batch()
        .var_as(
            "hits",
            g()
            .vector_search_nodes_with(
                "Document",
                "embedding",
                p.query_vector.input(),
                p.limit,
                p.tenant_id.input(),
            )
            .project([
                Projection.property("$id", "id"),
                Projection.property("title"),
                Projection.property("$distance", "distance"),
            ]),
        )
        .returning(["hits"])
    )
```

Project `$distance` before navigating off the search hit stream.

## 7. Text Search

```python
search_documents_params = define_params({"tenant_id": param.string(), "query": param.string()})


def search_documents(p=search_documents_params):
    return (
        read_batch()
        .var_as(
            "results",
            g()
            .text_search_nodes_with("Document", "body", p.query.input(), 50, p.tenant_id.input())
            .where(Predicate.eq("published", True))
            .limit(10)
            .project([
                Projection.property("$id", "id"),
                Projection.property("title"),
                Projection.property("$distance", "score"),
            ]),
        )
        .returning(["results"])
    )
```

## 8. Repeat And Branching

```python
friends_params = define_params({"user_ids": param.array(param.i64())})


def friends_and_followers(p=friends_params):
    return (
        read_batch()
        .var_as(
            "network",
            g()
            .n(NodeRef.param("user_ids"))
            .repeat(RepeatConfig.new(sub().out("FOLLOWS")).times(2).emit_all().max_depth(4))
            .union([sub().out("FOLLOWS"), sub().in_("FOLLOWS")])
            .dedup()
            .value_map(["$id", "name"]),
        )
        .returning(["network"])
    )
```

## Edge Endpoint Projection

Use this when an edge list needs stable source/target resource ids. It keeps one
output row per edge and avoids traversing to every endpoint node.

```python
def list_describes_relationships():
    return (
        read_batch()
        .var_as(
            "relationships",
            g()
            .e_with_label("DESCRIBES")
            .project([
                Projection.from_endpoint("resource_id", "from_id"),
                Projection.to_endpoint("resource_id", "to_id"),
                Projection.property("$id", "edge_id"),
                Projection.property("confidence", "confidence"),
            ]),
        )
        .returning(["relationships"])
    )
```

## 9. For Each Param Writes

```python
create_events_params = define_params({"rows": param.array(param.object(param.value()))})


def create_events(p=create_events_params):
    body = write_batch().var_as(
        "created",
        g().add_n(
            "Event",
            {
                "eventId": PropertyInput.param("eventId"),
                "kind": PropertyInput.param("kind"),
                "score": PropertyInput.param("score"),
            },
        ),
    )

    return write_batch().for_each_param("rows", body).returning(["created"])
```

## 10. Query Bundles

```python
queries = define_queries({
    "read": {"find_users": register_read(find_users, find_users_params)},
    "write": {"create_user": register_write(create_user, create_user_params)},
})

# Dynamic request with query_name="find_users" and converted parameters.
request = queries.call.find_users({"tenant_id": "acme", "limit": 25})

# Write queries.json for deploy/runtime workflows that consume bundles.
queries.generate("queries.json")
```

## 11. Stored Routes

```python
client = Client("https://helix.example.com", api_key="hx_secret")
response = client.query().body({"tenant_id": "acme", "limit": 25}).stored("find_users").send()
```

Stored routes post to `/v1/query/{name}`. Dynamic requests post to `/v1/query`.

## 12. Inspect Request JSON In A Test

```python
def test_find_users_request_json():
    body = find_users().to_dynamic_json(
        find_users_params,
        {"tenant_id": "acme", "limit": 25},
        query_name="find_users",
    )
    assert '"query_name":"find_users"' in body
    assert '"parameter_types":{"tenant_id":"String","limit":"I64"}' in body
```
