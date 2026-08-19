# Helix Query Authoring - Python Examples

All snippets assume:

```python
from helixdb import (
    AsyncClient,
    BatchCondition,
    BindingProjection,
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
    g,
    param,
    read_batch,
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

request = active_user_count().to_query_request(query_name="active_user_count")
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

request = find_users().to_query_request(
    find_users_params,
    {"tenant_id": "acme", "limit": 25},
    query_name="find_users",
)
```

Direct values such as `Predicate.eq("tenantId", "acme")` are literals in the AST. Use params for values that vary per request.

## 3. Execute A Query

```python
client = Client("http://localhost:6969")
response = client.query(request)
users = response["users"]
```

With Helix Cloud auth:

```python
client = Client("https://helix.example.com", api_key="hx_secret")
response = client.query(request)
```

## 3a. Execute Concurrent Queries Asynchronously

Reuse one client so its HTTPX connection pool serves every request:

```python
import asyncio


async def fetch_users_twice():
    async with AsyncClient("https://helix.example.com", api_key="hx_secret") as client:
        return await asyncio.gather(
            client.query(request),
            client.query(request, timeout=2.0),
        )


responses = asyncio.run(fetch_users_twice())
```

For embedded execution, also install `helix-db-embedded` and await the native
writer or reader constructor:

```python
from helixdb import InMemory


async def query_embedded():
    client = await AsyncClient.embedded(InMemory("app"))
    async with client:
        return await client.query(request)
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

create_request = create_user().to_query_request(
    create_user_params,
    {"name": "Alice", "tenant_id": "acme"},
    query_name="create_user",
)
created = client.execute(
    create_request,
    writer_only=True,
    await_durability=True,
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

## 6. Vector Prefiltering Over Traversal Candidates

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
            .n_with_label("Document")
            .where(Predicate.eq("tenantId", p.tenant_id))
            .where(Predicate.eq("published", True))
            .vector_search_with(
                "Document",
                "embedding",
                p.query_vector,
                p.limit,
                p.tenant_id,
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

The label, tenant, and publication predicates build the exact candidate stream
before vector ranking. Source vector search followed by `where` can underfill
top-k. Project `$distance` before navigating off the search hit stream.

## 7. Full Text Search Prefiltering Over Traversal Candidates

```python
search_documents_params = define_params({"tenant_id": param.string(), "query": param.string()})


def search_documents(p=search_documents_params):
    return (
        read_batch()
        .var_as(
            "results",
            g()
            .n_with_label("Document")
            .where(Predicate.eq("tenantId", p.tenant_id))
            .where(Predicate.eq("published", True))
            .text_search_with("Document", "body", p.query, 10, p.tenant_id)
            .project([
                Projection.property("$id", "id"),
                Projection.property("title"),
                Projection.property("$score", "score"),
            ]),
        )
        .returning(["results"])
    )
```

The label, tenant, and publication predicates build the candidate stream
before BM25 ranking. This refills exactly to `k` when enough matching
candidates exist; source text search followed by `where` does not.

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

## 10. Correlated Row Bindings

```python
def user_friend_pairs():
    return (
        read_batch()
        .var_as(
            "pairs",
            g()
            .n_with_label("User")
            .bind("user")
            .out("FOLLOWS")
            .bind("friend")
            .project_distinct_bindings([
                BindingProjection.binding("user", "$id", "user_id"),
                BindingProjection.binding("friend", "$id", "friend_id"),
            ]),
        )
        .returning(["pairs"])
    )
```

The v3 Python SDK does not expose stored routes or query bundles.

## 11. Handle Stable Error Codes

```python
from helixdb import HelixError

try:
    response = client.query(request)
except HelixError as error:
    if error.code == "transaction_conflict" and error.status_code == 409:
        # Retry with bounded backoff only when the request is safe to replay.
        pass
    else:
        raise
```

Use `error.kind` to distinguish transport from remote/embedded failures and `error.details` for diagnostics. Preserve unfamiliar `error.code` strings and never classify failures by parsing `details`.

## 12. Inspect Request JSON In A Test

```python
def test_find_users_request_json():
    body = find_users().to_query_json(
        find_users_params,
        {"tenant_id": "acme", "limit": 25},
        query_name="find_users",
    )
    assert '"query_name":"find_users"' in body
    assert '"parameter_types":{"tenant_id":"string","limit":"i64"}' in body
```
