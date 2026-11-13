# Helix Query Authoring — Rust Examples

Each numbered scenario corresponds 1:1 with `../helix-query-typescript/EXAMPLES.md`.
When moving between Rust and TypeScript, open the same scenario in each file, then
serialize either builder for the canonical direct JSON request.

All snippets assume `use helix_db::dsl::prelude::*;`.

Calling a public `#[query]` function returns `Result<QueryRequest, QueryError>`
(add `?`); the request's top-level `query_name` is the Rust function name.
Inside the body each argument is rebound as `Expr::param("<name>")`. Direct
`QueryRequest::read/write` builders serialize `query_name: null` until
`.with_query_name(...)` or `.set_query_name(...)` is used.

Every stream return is an array, `[]` when empty, including single lookups; an
unprojected element is `{"$id": N}`.

---

## 1. Count nodes matching label + predicate

```rust
#[query]
pub fn active_user_count() -> ReadBatch {
    read_batch()
        .var_as(
            "active_count",
            g().n_with_label("User")
                .where_(Predicate::eq("status", "active"))
                .count(),
        )
        .returning(["active_count"])
}
```

---

## 2. Read node by indexed property with projection

Literal form:

```rust
#[query]
pub fn user_by_id_literal() -> ReadBatch {
    read_batch()
        .var_as(
            "user",
            g().n_with_label_where(
                "User",
                SourcePredicate::eq("userId", "u-42"),
            )
            .project(vec![
                PropertyProjection::renamed("$id", "id"),
                PropertyProjection::new("userId"),
                PropertyProjection::new("name"),
            ]),
        )
        .returning(["user"])
}
```

Parameterized form (preferred):

```rust
#[query]
pub fn user_by_id(userId: String) -> ReadBatch {
    let _ = &userId;
    read_batch()
        .var_as(
            "user",
            g().n_with_label("User")
                .where_(Predicate::eq_param("userId", "userId"))
                .project(vec![
                    PropertyProjection::renamed("$id", "id"),
                    PropertyProjection::new("name"),
                ]),
        )
        .returning(["user"])
}
```

---

## 3. Multi-hop traversal with `dedup` + `limit`

```rust
#[query]
pub fn friends_of_friends(userId: Vec<i64>) -> ReadBatch {
    let _ = &userId;
    read_batch()
        .var_as(
            "fof",
            g().n(NodeRef::param("userId"))
                .out(Some("FOLLOWS"))
                .out(Some("FOLLOWS"))
                .dedup()
                .limit(50usize)
                .values(vec!["$id", "name"]),
        )
        .returning(["fof"])
}
```

---

## 4. Vector prefiltering over traversal candidates

```rust
#[query]
pub fn nearest_documents(
    tenantId: String,
    queryVector: Vec<f32>,
    k: i64,
) -> ReadBatch {
    let _ = (&tenantId, &queryVector, &k);
    read_batch()
        .var_as(
            "hits",
            g().n_with_label("Document")
                .where_(Predicate::eq_param("tenantId", "tenantId"))
                .where_(Predicate::eq("published", true))
                .vector_search_with(
                    "Document",
                    "embedding",
                    PropertyInput::param("queryVector"),
                    Expr::param("k"),
                    Some(PropertyInput::param("tenantId")),
                )
                .project(vec![
                    PropertyProjection::renamed("$id", "id"),
                    PropertyProjection::new("title"),
                    PropertyProjection::renamed("$distance", "distance"),
                ]),
        )
        .returning(["hits"])
}
```

The label, tenant, and publication predicates build the exact candidate stream
before vector ranking. Source vector search followed by `where_` can underfill
top-k. Project `$distance` before any `.out`/`.in_`/`.both`.

---

## 5. Full Text Search prefiltering over traversal candidates

```rust
#[query]
pub fn document_search(
    tenantId: String,
    q: String,
) -> ReadBatch {
    let _ = (&tenantId, &q);
    read_batch()
        .var_as(
            "results",
            g().n_with_label("Document")
                .where_(Predicate::eq_param("tenantId", "tenantId"))
                .where_(Predicate::eq("published", true))
                .text_search_with(
                    "Document",
                    "body",
                    PropertyInput::param("q"),
                    10usize,
                    Some(PropertyInput::param("tenantId")),
                )
                .project(vec![
                    PropertyProjection::renamed("$id", "id"),
                    PropertyProjection::new("title"),
                    PropertyProjection::renamed("$score", "score"),
                ]),
        )
        .returning(["results"])
}
```

The label, tenant, and publication predicates build the candidate stream
before BM25 ranking. This refills exactly to `k` when enough matching
candidates exist; source text search followed by `where_` does not.

---

## 6. `Repeat` traversal with `until` + `emit_after`

```rust
#[query]
pub fn management_chain(startId: Vec<i64>) -> ReadBatch {
    let _ = &startId;
    read_batch()
        .var_as(
            "chain",
            g().n(NodeRef::param("startId"))
                .repeat(
                    RepeatConfig::new(sub().out(Some("REPORTS_TO")))
                        .until(Predicate::eq("title", "CEO"))
                        .emit_after()
                        .max_depth(10),
                )
                .project(vec![
                    PropertyProjection::renamed("$id", "id"),
                    PropertyProjection::new("name"),
                    PropertyProjection::new("title"),
                ]),
        )
        .returning(["chain"])
}
```

---

## 7. `Union` of two sub-traversals

```rust
#[query]
pub fn user_network(userId: Vec<i64>) -> ReadBatch {
    let _ = &userId;
    read_batch()
        .var_as(
            "network",
            g().n(NodeRef::param("userId"))
                .union(vec![
                    sub().out(Some("FOLLOWS")),
                    sub().in_(Some("FOLLOWS")),
                ])
                .dedup()
                .values(vec!["$id", "name"]),
        )
        .returning(["network"])
}
```

---

## 8. `Choose` (conditional traversal)

```rust
#[query]
pub fn user_content(userId: Vec<i64>) -> ReadBatch {
    let _ = &userId;
    read_batch()
        .var_as(
            "content",
            g().n(NodeRef::param("userId"))
                .choose(
                    Predicate::eq("tier", "premium"),
                    sub().out(Some("HAS_PREMIUM")),
                    Some(sub().out(Some("HAS_FREE"))),
                )
                .limit(20usize)
                .value_map(Some(vec!["$id", "title"])),
        )
        .returning(["content"])
}
```

---

## 9. `Coalesce` (fallback traversal)

```rust
#[query]
pub fn preferred_team(userId: Vec<i64>) -> ReadBatch {
    let _ = &userId;
    read_batch()
        .var_as(
            "team",
            g().n(NodeRef::param("userId"))
                .coalesce(vec![
                    sub().out(Some("PREFERRED_TEAM")),
                    sub().out(Some("PRIMARY_TEAM")),
                    sub().out(Some("MEMBER_OF")).limit(1usize),
                ])
                .values(vec!["$id", "name"]),
        )
        .returning(["team"])
}
```

---

## 10. `Project` with `Expr::case` (computed field)

```rust
#[query]
pub fn users_with_bucket() -> ReadBatch {
    read_batch()
        .var_as(
            "users",
            g().n_with_label("User").project(vec![
                Projection::property("$id", "id"),
                Projection::property("score", "score"),
                Projection::expr(
                    "bucket",
                    Expr::case(
                        vec![
                            (
                                Predicate::gte("score", 1000i64),
                                Expr::val("high"),
                            ),
                            (
                                Predicate::gte("score", 100i64),
                                Expr::val("mid"),
                            ),
                        ],
                        Some(Expr::val("low")),
                    ),
                ),
            ]),
        )
        .returning(["users"])
}
```

---

## 11. Aggregation: `group_count` and `aggregate_by`

```rust
#[query]
pub fn users_by_status() -> ReadBatch {
    read_batch()
        .var_as(
            "by_status",
            g().n_with_label("User").group_count("status"),
        )
        .returning(["by_status"])
}

#[query]
pub fn total_revenue() -> ReadBatch {
    read_batch()
        .var_as(
            "revenue",
            g().n_with_label("Order")
                .aggregate_by(AggregateFunction::Sum, "price"),
        )
        .returning(["revenue"])
}
```

---

## Edge Endpoint Projection

Use this when an edge list needs stable source/target resource ids. It keeps one
output row per edge and avoids traversing to every endpoint node.

```rust
#[query]
pub fn list_describes_relationships() -> ReadBatch {
    read_batch()
        .var_as(
            "relationships",
            g().e_with_label("DESCRIBES").project(vec![
                Projection::from_endpoint("resource_id", "from_id"),
                Projection::to_endpoint("resource_id", "to_id"),
                Projection::property("$id", "edge_id"),
                Projection::property("confidence", "confidence"),
            ]),
        )
        .returning(["relationships"])
}
```

The direct request nests this projection under the `project` root. Endpoint
helpers serialize their sources as `$from.resource_id` and `$to.resource_id`.

---

## Row bindings: multi-hop correlation

Use this when a single output row must combine values captured at **different
hops** of one path — `.project(...)` only sees the final stream. Tag elements
with `.bind(name)` as you pass them, then assemble rows with
`.project_distinct_bindings(...)` (or `.project_bindings(...)` to keep
duplicates). `coalesce` picks the first present non-null reference.

```rust
#[query]
pub fn service_topology() -> ReadBatch {
    read_batch()
        .var_as(
            "rows",
            g().n_with_label("Service")
                .bind("service")
                .out(Some("ROUTES_TO")).bind("pod")
                .optional(sub().in_(Some("CREATES")).bind("deployment"))
                .union(vec![
                    sub().in_(Some("MANAGES")).bind("owner"),
                    sub().out(Some("ROUTES_TO")).bind("workload"),
                ])
                .project_distinct_bindings(vec![
                    BindingProjection::binding("service", "$id", "service_id"),
                    BindingProjection::binding("pod", "name", "pod_name"),
                    BindingProjection::coalesce(
                        vec![
                            BindingValueRef::binding("deployment", "$id"),
                            BindingValueRef::binding("owner", "$id"),
                        ],
                        "workload_id",
                    ),
                ]),
        )
        .returning(["rows"])
}
```

The binding projection serializes as the nested `project_bindings` operation in a
normal direct request.

This binding projection is part of a normal direct request and is also
available in the Python v3 SDK.

---

## 12. Write: `add_n` + `add_e` in one batch with cross-entry `Var` reference

```rust
#[query]
pub fn create_user_and_link_post(
    userId: String,
    name: String,
    postId: Vec<i64>,
) -> WriteBatch {
    let _ = (&userId, &name, &postId);
    write_batch()
        .var_as(
            "newUser",
            g().add_n(
                "User",
                vec![
                    ("userId", PropertyInput::param("userId")),
                    ("name", PropertyInput::param("name")),
                    ("createdAt", PropertyInput::from(Expr::timestamp())),
                ],
            ),
        )
        .var_as(
            "link",
            g().n(NodeRef::param("postId"))
                .add_e::<&str, PropertyInput>("CREATED_BY", NodeRef::var("newUser"), vec![]),
        )
        .returning(["newUser", "link"])
}
```

`NodeRef::var("newUser")` needs a node stream, so `newUser` stays the raw
`add_n` (it returns `[{"$id": N}]`). A variable ending in `.project(...)` is not a
node stream and fails at runtime. `add_e` creates one edge per (post, user) pair
every time it runs, and an empty `newUser` target fails the batch.

---

## 13. Write: upsert via `var_as_if`

```rust
#[query]
pub fn upsert_user(userId: String, name: String) -> WriteBatch {
    let _ = (&userId, &name);
    write_batch()
        .var_as(
            "existing",
            g().n_with_label("User")
                .where_(Predicate::eq_param("userId", "userId")),
        )
        .var_as_if(
            "updated",
            BatchCondition::VarNotEmpty("existing".to_string()),
            g().n(NodeRef::var("existing"))
                .set_property("name", PropertyInput::param("name")),
        )
        .var_as_if(
            "created",
            BatchCondition::VarEmpty("existing".to_string()),
            g().add_n(
                "User",
                vec![
                    ("userId", PropertyInput::param("userId")),
                    ("name", PropertyInput::param("name")),
                ],
            ),
        )
        .returning(["updated", "created"])
}
```

Create `IndexSpec::node_unique_equality("User", "userId")` first (example 17).
Without it, two concurrent upserts can both take the create branch and
duplicate the user; with it, the loser fails with `unique_constraint_violation`
(409, `retryable: false`) and re-running the upsert once takes the update
branch.

---

## 14. Write: `for_each_param` over an array of objects

```rust
#[query]
pub fn bulk_create_users(data: Vec<ParamObject>) -> WriteBatch {
    let _ = &data;
    let body = write_batch().var_as(
        "created",
        g().add_n(
            "User",
            vec![
                ("externalId", PropertyInput::param("externalId")),
                ("embedding", PropertyInput::param("embedding")),
            ],
        ),
    );
    write_batch().for_each_param("data", body)
}
```

Inside `body`, the parameter names resolve against each object's fields. A
`data: Vec<ParamObject>` argument makes `#[query]` record a structured
array-of-object parameter schema. A variable set in `body` holds only the last
iteration's result, so returning `created` would report one node, not all of
them; read the created nodes back afterwards if the caller needs them.

---

## 15. Nested object properties + dotted paths

```rust
#[query]
pub fn create_user_with_metadata() -> WriteBatch {
    let metadata = PropertyValue::object(vec![
        ("externalID", PropertyValue::from("crm-42")),
        ("score", PropertyValue::from(20i64)),
        (
            "tags",
            PropertyValue::array(vec![
                PropertyValue::from("trial"),
                PropertyValue::from(7i64),
            ]),
        ),
    ]);

    write_batch()
        .var_as(
            "user",
            g().add_n(
                "User",
                vec![
                    ("userId", PropertyInput::from("u-42")),
                    ("metadata", PropertyInput::from(metadata)),
                ],
            )
            .value_map(Some(vec!["userId", "metadata.externalID"])),
        )
        .returning(["user"])
}

#[query]
pub fn users_by_external_id() -> ReadBatch {
    read_batch()
        .var_as(
            "users",
            g().n_with_label("User")
                .where_(Predicate::eq("metadata.externalID", "crm-42"))
                .project(vec![
                    PropertyProjection::new("userId"),
                    PropertyProjection::renamed("metadata.externalID", "external_id"),
                ]),
        )
        .returning(["users"])
}
```

Dotted property lookup is exact-first and scan-only in the current runtime. Keep indexed/searchable fields top-level; use nested objects for metadata you can scan or project. Arrays are opaque, so there is no `metadata.tags.0` syntax.

---

## 16. Typed-array parameter + `DateTime` parameter

```rust
#[query]
pub fn users_filtered(
    statuses: Vec<String>,
    since: DateTime,
) -> ReadBatch {
    let _ = (&statuses, &since);
    read_batch()
        .var_as(
            "users",
            g().n_with_label("User")
                .where_(Predicate::and(vec![
                    Predicate::is_in_param("status", "statuses"),
                    Predicate::gte_param("createdAt", "since"),
                ]))
                .values(vec!["$id", "status", "createdAt"]),
        )
        .returning(["users"])
}
```

The macro records `statuses` as an array-of-string schema and `since` as
`"date_time"`. `since` is a `helix_db::DateTime`: build it with
`DateTime::from_millis(ms)` or `DateTime::parse_rfc3339("2026-01-01T00:00:00Z")?`;
the wrapper serializes it as UTC RFC3339.

---

## 17. Write: index management

```rust
#[query]
pub fn bootstrap_indexes() -> WriteBatch {
    write_batch()
        .var_as(
            "idx_userId",
            g().create_index_if_not_exists(IndexSpec::node_unique_equality("User", "userId")),
        )
        .var_as(
            "idx_embedding",
            g().create_index_if_not_exists(IndexSpec::node_vector(
                "Document",
                "embedding",
                std::num::NonZeroUsize::new(1536).expect("non-zero dimension"),
                VectorDistanceMetric::Cosine,
                Some("tenantId"),
            )),
        )
        .var_as(
            "idx_body",
            g().create_index_if_not_exists(IndexSpec::node_text(
                "Document",
                "body",
                Some("tenantId"),
            )),
        )
        .returning(["idx_userId", "idx_embedding", "idx_body"])
}
```

Each variable returns a receipt, not an active index:
`{"kind": "accepted", "operation_id", "index_id", "generation"}`,
`{"kind": "existing_operation", "operation_id"}` or
`{"kind": "already_active", "index_id", "generation"}`. Builds run in the
background; poll `g().get_index_operation(operation_id)` until its `status` is
`succeeded` before relying on the index, and handle `blocked` with
`retry_index_operation` / `abort_index_operation` (see `REFERENCE.md`, Index
lifecycle). Drop an index with `g().drop_index(IndexSpec::...)`. The convenience
methods (`create_vector_index_nodes`, etc.) produce identical wire output;
`create_text_index_nodes("Doc", "body", None::<&str>)` needs the turbofish for an
unscoped index.

---

## 18. Warm a read route

Warming uses the *same* query; `.warm_only()` sets the `X-Helix-Warm: true` header on the client. Build the request and let callers decide to warm:

```rust
use helix_db::Client;

let client = Client::new(Some("http://localhost:6969"))?;

// Helix Cloud returns 204 after a successful warm. helix-db 3.0.0 accepts only
// 200 and raises RemoteError for it; `main` accepts 204. With 3.0.0, warm Cloud
// through direct HTTP.
let response = client
    .request_builder::<serde_json::Value>()
    .warm_only()
    .query(user_by_id("u-42".to_string())?)
    .send_bytes()
    .await?;
```

Helix Cloud fans the read out to every eligible backend and discards the result
bodies. Chain `.writer_only().warm_only()` to warm only the authoritative
writer. A local server warms one process and returns the normal query body.
Warming is strictly read-only; a `WriteBatch` with `X-Helix-Warm: true` is
rejected with `400 invalid_request_option` before execution.

---

## 19. Handle Structured Remote Errors

```rust
use helix_db::QueryErrorCode;

match client.query::<serde_json::Value>(request).send().await {
    Ok(response) => Ok(response),
    // transaction_conflict, request_read_view_changed, stale_index_generation,
    // index_backpressure: resend the whole request with bounded backoff + jitter.
    Err(error) if error.is_retryable() => Err(error),
    // 409 with retryable: false. Resending unchanged fails again.
    Err(error)
        if error.error_code() == Some(QueryErrorCode::UniqueConstraintViolation.as_str()) =>
    {
        Err(error)
    }
    Err(error) => Err(error),
}
```

Branch on `is_retryable()` / `retryable()`, not on the 409 status:
`unique_constraint_violation`, `index_busy` and `index_build_blocked` are 409s
that are **not** retryable. `is_conflict()` means `transaction_conflict` only.
A `query_deadline_exceeded` (408), a 500, or
`writer_fenced_commit_outcome_unknown` (503) may follow a committed write:
reconcile before resubmitting. `remote_message()`, `remote_details()`, and
`raw_response_body()` keep diagnostics without string parsing; unknown codes
stay available through `error_code()`.

These helpers are on `main`. In helix-db 3.0.0, `HelixError::RemoteError {
details }` holds the raw body: parse it with `serde_json` and read `error` and
`retryable`. The SDK does not expose `Retry-After`; use direct HTTP when the
exact Cloud delay matters.

---

## Shortest path

```rust
#[query]
pub fn route(fromId: i64, toId: i64) -> ReadBatch {
    let _ = (&fromId, &toId);
    read_batch()
        .var_as(
            "path",
            g().shortest_path_with(
                NodeRef::param("fromId"),
                NodeRef::param("toId"),
                Some("ROUTES_TO"),
                ShortestPathDirection::Out,
                6,
            ),
        )
        .returning(["path"])
}
```

Unweighted BFS: `path` is the ordered node IDs from source to target, or `[]`
when there is no path within the depth.
