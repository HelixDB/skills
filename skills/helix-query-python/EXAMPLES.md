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
    ShortestPathDirection,
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
users = response["users"]  # always a list; [] when nothing matched
```

A single-row lookup is also a list (`[]` when missing, never `None`):

```python
user_by_id_params = define_params({"user_id": param.i64()})  # node IDs are integers


def user_by_id(p=user_by_id_params):
    return (
        read_batch()
        .var_as(
            "user",
            g().n(NodeRef.param("user_id")).project([Projection.property("$id", "id"), Projection.property("name")]),
        )
        .returning(["user"])
    )


rows = client.query(user_by_id().to_query_request(user_by_id_params, {"user_id": 42}))["user"]
user = rows[0] if rows else None
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
created = client.execute(create_request, writer_only=True)
# {"user": [{"$id": 7}]}: mutations return only IDs unless projected
```

Writes wait for durability by default. Pass `await_durability=False` only to
trade crash durability for latency; it does not reduce conflicts.

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

Exactly one of `updated` / `created` is non-empty; the skipped one is `[]`.
Make the key race-safe with a unique equality index (create it once and wait for
it to succeed, see §14). Two concurrent creates then end with one
`unique_constraint_violation` (`retryable: false`) instead of a duplicate node;
re-running the same upsert once takes the update branch:

```python
from helixdb import HelixError

upsert_request = upsert_user().to_query_request(
    upsert_user_params, {"user_id": "u-1", "name": "Ada"}, query_name="upsert_user"
)
try:
    result = client.query(upsert_request)
except HelixError as error:  # code / is_retryable(): main only; 0.3.4 see §11
    if error.code != "unique_constraint_violation" and not error.is_retryable():
        raise
    result = client.query(upsert_request)
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
            .repeat(RepeatConfig.new(sub().out("FOLLOWS")).times(2).emit_after().max_depth(4))
            .union([sub().out("FOLLOWS"), sub().in_("FOLLOWS")])
            .dedup()
            .value_map(["$id", "name"]),
        )
        .returning(["network"])
    )
```

`emit_after()` returns the nodes reached at depth 1 and 2 (not the seeds).
`emit_all()` would also return the seeds and repeat every intermediate level.

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

    # Do not return "created": it holds only the last iteration's node.
    return write_batch().for_each_param("rows", body)
```

To get every created row, read them back after the write commits:

```python
events_by_id_params = define_params({"event_ids": param.array(param.string())})


def events_by_id(p=events_by_id_params):
    return (
        read_batch()
        .var_as(
            "events",
            g()
            .n_with_label("Event")
            .where(Predicate.is_in_expr("eventId", p.event_ids))
            .project([Projection.property("$id", "id"), Projection.property("eventId")]),
        )
        .returning(["events"])
    )
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

## 11. Handle Errors By Class

```python
import random
import time

from helixdb import HelixError


def run_with_retry(client, request, attempts=5):
    for attempt in range(attempts):
        try:
            return client.query(request)
        except HelixError as error:  # is_retryable(): main only
            # transaction_conflict, request_read_view_changed, stale_index_generation,
            # index_backpressure: the request committed nothing, resend it.
            if not error.is_retryable() or attempt == attempts - 1:
                raise
            time.sleep(min(2.0, 0.05 * 2**attempt) * random.random())
```

Do not retry on the status alone: 409 also carries
`unique_constraint_violation`, `index_busy` and `index_build_blocked`
(`retryable: false`), which fail again until the state changes. Treat
`query_deadline_exceeded` (408), 500s, `writer_fenced_commit_outcome_unknown`
and a `Network` failure after sending a write as an unknown outcome: read back by
key before resubmitting. Helix Cloud's gateway reports its own timeout as
`query_timeout`. `HelixError.code`, `retryable` and `is_retryable()` are
**main only**; with 0.3.4, `json.loads(error.details)` gives the server body
(read its `error` and `retryable`). The SDK does not
expose `Retry-After`; use direct HTTP when the exact Cloud delay is required.

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

## 13. Optional Match With Bindings

```python
def users_with_employer():
    return (
        read_batch()
        .var_as(
            "rows",
            g()
            .n_with_label("User")
            .bind("user")
            .optional(sub().out("WORKS_AT").has_label("Company").bind("employer"))
            .project_bindings([
                BindingProjection.binding("user", "name", "name"),
                BindingProjection.binding("employer", "name", "employer"),
            ]),
        )
        .returning(["rows"])
    )
# {"rows": [{"name": "Ada", "employer": "Acme"}, {"name": "Bob"}]}
```

Without bindings, `.optional(sub().out("WORKS_AT"))` returns the user itself
for users with no employer.

## 14. Create An Index And Wait For It

```python
import time

from helixdb import IndexDdlAlreadyActive, parse_index_ddl_receipt, parse_index_operation_status


def wait_for_index(client, spec, poll_seconds=1.0):
    created = client.query(
        write_batch()
        .var_as("index", g().create_index_if_not_exists(spec))
        .returning(["index"])
        .to_query_request(query_name="create_index")
    )
    receipt = parse_index_ddl_receipt(created["index"])
    if isinstance(receipt, IndexDdlAlreadyActive):
        return
    while True:
        status = parse_index_operation_status(
            client.query(
                read_batch()
                .var_as("op", g().get_index_operation(receipt.operation_id))
                .returning(["op"])
                .to_query_request(query_name="index_operation")
            )["op"]
        )
        if status.status == "succeeded":
            return
        if status.status in ("blocked", "aborted"):
            raise RuntimeError(f"{status.status}: {getattr(status, 'blocker_code', None)}")
        time.sleep(poll_seconds)


wait_for_index(client, IndexSpec.node_unique_equality("User", "userId"))
```

After fixing what a `blocked` operation's `blocker_code` names (for a unique
index, the duplicate values), resume or discard it in a write batch:

```python
def retry_index(operation_id: str):
    return write_batch().var_as("op", g().retry_index_operation(operation_id)).returning(["op"])


def abort_index(operation_id: str):
    return write_batch().var_as("op", g().abort_index_operation(operation_id)).returning(["op"])
```

## 15. Value Choice With `Expr.case`

```python
def user_tiers():
    return (
        read_batch()
        .var_as(
            "users",
            g()
            .n_with_label("User")
            .project([
                Projection.property("name"),
                Projection.expr(
                    "tier",
                    Expr.case([(Predicate.gte("score", 100), Expr.val("gold"))], Expr.val("standard")),
                ),
            ]),
        )
        .returning(["users"])
    )
```

This is Cypher/SQL `CASE`. `choose` without an else branch would drop the
non-matching users instead.

## 16. Shortest Path

```python
path_params = define_params({"from_id": param.i64(), "to_id": param.i64()})


def follow_path(p=path_params):
    return (
        read_batch()
        .var_as(
            "path",
            g().shortest_path(
                NodeRef.param("from_id"),
                NodeRef.param("to_id"),
                6,
                label="FOLLOWS",
                direction=ShortestPathDirection.BOTH,
            ),
        )
        .returning(["path"])
    )
# {"path": [3, 9, 12]} (node IDs, source first) or {"path": []}
```

## 17. Send Cypher Or SQL Directly

```python
import httpx

# helix-db 0.3.4: plain HTTP. On main: client.cypher(query, params) / client.sql(query, params)
rows = httpx.post(
    "http://localhost:6969/v2/sql",
    json={"query": "SELECT p.name AS name FROM Person p WHERE p.age >= ?", "parameters": [30]},
).json()
# {"columns": ["name"], "rows": [["Ada"], ...]}
```

Use this when the statement is inside the Cypher/SQL profile; write the DSL for
`MERGE`, variable-length paths, outer joins, upserts, search, and index
management.

