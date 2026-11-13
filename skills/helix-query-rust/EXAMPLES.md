# Helix Query Authoring — Rust Examples

Scenarios are numbered 1:1 with `../helix-query-typescript/EXAMPLES.md`; either builder
serializes to the same direct JSON request. Snippets assume
`use helix_db::dsl::prelude::*;`. A `#[query]` function returns
`Result<QueryRequest, QueryError>` (add `?`) named after the function; direct
`QueryRequest::read/write` builders serialize `query_name: null` until
`.with_query_name(...)` or `.set_query_name(...)`.

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

The predicates build the exact candidate stream before ranking; source vector search
followed by `where_` can underfill top-k. Project `$distance` before any
`.out`/`.in_`/`.both`.

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
                // (main); 3.0.0 fallback: SKILL.md table
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

This returns exactly `k` hits when enough candidates match; source text search followed
by `where_` does not.

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

One row per edge with source/target resource ids, without traversing to each endpoint.

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

Endpoint sources serialize as `$from.resource_id` and `$to.resource_id`.

---

## Row bindings: multi-hop correlation

One row combining values from **different hops** (`.project(...)` only sees the final
stream). `coalesce` picks the first present non-null reference.

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

Serializes as the nested `project_bindings` operation in a normal direct request; also
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

`newUser` stays the raw `add_n` (`[{"$id": N}]`) because `NodeRef::var` needs a node
stream; a variable ending in `.project(...)` fails at runtime. `add_e` creates one edge per
(post, user) pair every run, and an empty `newUser` target fails the batch.

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

Create `IndexSpec::node_unique_equality("User", "userId")` first (§17); without it two
concurrent upserts can both create. With it the loser fails with
`unique_constraint_violation` (409, `retryable: false`); re-run the upsert once.

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

Parameter names in `body` resolve against each object's fields; `data:
Vec<ParamObject>` records an array-of-object schema. `created` holds only the last
iteration, so read the created nodes back if the caller needs them.

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

Dotted paths are exact-first and scan-only (REFERENCE.md, Nested properties); keep
indexed or searchable fields top-level. Arrays are opaque: no `metadata.tags.0`.

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

`statuses` records as an array-of-string schema, `since` as `"date_time"` (a
`helix_db::DateTime`, serialized as UTC RFC3339).

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

Each variable returns a receipt, not an active index; poll until `succeeded` before
relying on it (polling loop: REFERENCE.md, Index lifecycle). Drop with
`g().drop_index(IndexSpec::...)`. Convenience methods (`create_vector_index_nodes`, etc.)
produce identical wire output.

---

## 18. Warm a read route

Warming sends the *same* query with `.warm_only()` (`X-Helix-Warm: true`):

```rust
use helix_db::Client;

let client = Client::new(Some("http://localhost:6969"))?;

// Cloud returns 204; 3.0.0 raises RemoteError for it (SKILL.md table).
let response = client
    .request_builder::<serde_json::Value>()
    .warm_only()
    .query(user_by_id("u-42".to_string())?)
    .send_bytes()
    .await?;
```

Cloud warms every eligible backend and discards the bodies; `.writer_only().warm_only()`
warms only the writer. A local server warms one process and returns the normal body. A
`WriteBatch` with `X-Helix-Warm: true` is `400 invalid_request_option`.

---

## 19. Handle Structured Remote Errors

```rust
use helix_db::QueryErrorCode; // (main); 3.0.0: parse RemoteError { details }

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

`remote_message()`, `remote_details()` and `raw_response_body()` keep diagnostics without
string parsing; unknown codes stay available through `error_code()`. Error classes:
SKILL.md, Errors.

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

`path` is the ordered node IDs from source to target, or `[]` when none within the depth.
