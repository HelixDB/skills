# Helix Query Authoring — Rust Examples

Each numbered scenario corresponds 1:1 with `../helix-query-typescript/EXAMPLES.md` and `../helix-query-json-dynamic/EXAMPLES.md`. When moving between the Rust DSL, TypeScript DSL, and inline JSON, open the same scenario in each file.

All snippets assume `use helix_db::dsl::prelude::*;`.

Calling a public `#[register]` function returns a `DynamicQueryRequest` whose top-level `query_name` is the Rust function name. Direct `DynamicQueryRequest::read/write` builders serialize `query_name: null` until `.with_query_name(...)` or `.set_query_name(...)` is used.

---

## 1. Count nodes matching label + predicate

```rust
#[register]
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
#[register]
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
#[register]
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
#[register]
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

## 4. Vector search with tenant + distance in projection

```rust
#[register]
pub fn nearest_documents(
    tenantId: String,
    queryVector: Vec<f64>,
    k: i64,
) -> ReadBatch {
    let _ = (&tenantId, &queryVector, &k);
    read_batch()
        .var_as(
            "hits",
            g().vector_search_nodes_with(
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

Project `$distance` before any `.out`/`.in_`/`.both` — traversal off the hit stream drops the distance metadata.

---

## 5. BM25 text search with post-filter

```rust
#[register]
pub fn document_search(
    tenantId: String,
    q: String,
) -> ReadBatch {
    let _ = (&tenantId, &q);
    read_batch()
        .var_as(
            "results",
            g().text_search_nodes_with(
                "Document",
                "body",
                PropertyInput::param("q"),
                50usize,
                Some(PropertyInput::param("tenantId")),
            )
            .where_(Predicate::eq("published", true))
            .limit(10usize)
            .project(vec![
                PropertyProjection::renamed("$id", "id"),
                PropertyProjection::new("title"),
                PropertyProjection::renamed("$distance", "score"),
            ]),
        )
        .returning(["results"])
}
```

---

## 6. `Repeat` traversal with `until` + `emit_after`

```rust
#[register]
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
#[register]
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
#[register]
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
#[register]
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
#[register]
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
#[register]
pub fn users_by_status() -> ReadBatch {
    read_batch()
        .var_as(
            "by_status",
            g().n_with_label("User").group_count("status"),
        )
        .returning(["by_status"])
}

#[register]
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
#[register]
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

Wire format:

```json
{"Project": [
  {"source": "$from.resource_id", "alias": "from_id"},
  {"source": "$to.resource_id", "alias": "to_id"},
  {"source": "$id", "alias": "edge_id"},
  {"source": "confidence", "alias": "confidence"}
]}
```

---

## Row bindings: multi-hop correlation

Use this when a single output row must combine values captured at **different
hops** of one path — `.project(...)` only sees the final stream. Tag elements
with `.bind(name)` as you pass them, then assemble rows with
`.project_distinct_bindings(...)` (or `.project_bindings(...)` to keep
duplicates). `coalesce` picks the first present non-null reference.

```rust
#[register]
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

Wire format (each tag is a `Bind` step; the terminal is `ProjectBindings`):

```json
{"Bind": "service"}
{"ProjectBindings": {
  "projections": [
    {"kind": "Property", "target": {"Binding": "service"}, "source": "$id", "alias": "service_id"},
    {"kind": "Property", "target": {"Binding": "pod"}, "source": "name", "alias": "pod_name"},
    {"kind": "Coalesce", "refs": [
      {"target": {"Binding": "deployment"}, "source": "$id"},
      {"target": {"Binding": "owner"}, "source": "$id"}
    ], "alias": "workload_id"}
  ],
  "distinct": true
}}
```

This emits a **v5** query bundle. Not available in the Python SDK yet — use
another SDK or hand-write the JSON for binding queries from Python.

---

## 12. Write: `add_n` + `add_e` in one batch with cross-entry `Var` reference

```rust
#[register]
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
            )
            .project(vec![PropertyProjection::renamed("$id", "id")]),
        )
        .var_as(
            "link",
            g().n(NodeRef::param("postId"))
                .add_e::<&str, PropertyInput>("CREATED_BY", NodeRef::var("newUser"), vec![]),
        )
        .returning(["newUser", "link"])
}
```

---

## 13. Write: upsert via `var_as_if`

```rust
#[register]
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

---

## 14. Write: `for_each_param` over an array of objects

```rust
#[register]
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
    write_batch()
        .for_each_param("data", body)
        .returning(["created"])
}
```

Inside `body`, the parameter names resolve against each object's fields. Registering with `data: Vec<ParamObject>` makes the macro record `QueryParamType::Array(Box::new(QueryParamType::Object))`, which is exactly `{"Array": "Object"}` on the wire.

---

## 15. Nested object properties + dotted paths

```rust
#[register]
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

#[register]
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

Dotted property lookup is exact-first and scan-only in V1. Keep indexed/searchable fields top-level; use nested objects for metadata you can scan or project. Arrays are opaque, so there is no `metadata.tags.0` syntax.

---

## 16. Typed-array parameter + `DateTime` parameter

```rust
#[register]
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

The macro records `statuses` as `{"Array": "String"}` and `since` as `"DateTime"`. On the client, pass any RFC3339 string or epoch-millis integer; the wrapper normalizes to UTC RFC3339 before serializing.

---

## 17. Write: index management

```rust
#[register]
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

Drop an index with `g().drop_index(IndexSpec::...)`. The convenience methods (`create_vector_index_nodes`, etc.) are available but produce identical wire output — prefer `create_index_if_not_exists` + `IndexSpec` for consistency with the dynamic JSON reference.

---

## 18. Warm a read route

Warming uses the *same* query; `.warm_only()` sets the `X-Helix-Warm: true` header on the client. Build the request and let callers decide to warm:

```rust
use helix_db::Client;

let client = Client::new(Some("https://helix.example.com"))?.with_api_key(Some(&api_key));

// .warm_only() sets X-Helix-Warm: true. A successful warm returns 204 No Content; writes reject warming.
let _: serde_json::Value = client
    .query()
    .warm_only()
    .dynamic(user_by_id("u-42".to_string())?)
    .send()
    .await?;
```

Warming is strictly read-only; a `WriteBatch` with `X-Helix-Warm: true` is rejected by the gateway.
