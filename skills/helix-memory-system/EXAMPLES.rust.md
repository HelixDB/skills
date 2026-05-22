# Helix Memory System — Rust Examples

The same nine lifecycle scenarios as `EXAMPLES.md`, in the Rust DSL. **Use this only when the app/runtime is Rust or you are shipping a stored enterprise route.** TypeScript is the default for memory apps.

Each query is a `#[register]` function: its parameters are bound by name, and calling it yields a `DynamicQueryRequest` you can send to `POST /v1/query`. The same builders also serialize for stored query bundles. Data model and indexes are in `REFERENCE.md`.

```rust
use helix_db::dsl::prelude::*;
```

Conventions mirror the TS examples: anchor on an indexed property, scope every search with `Some(PropertyInput::param("userId"))`, and filter `deletedAt IsNull` on every read. Edge timestamps use `Expr::Timestamp` to keep edge property vectors well-typed (avoids empty-`vec![]` inference).

---

## 1. Bootstrap indexes (run once)

```rust
#[register]
fn bootstrap_memory_indexes() {
    write_batch()
        .var_as("userId",    g().create_index_if_not_exists(IndexSpec::node_unique_equality("User", "userId")))
        .var_as("memoryId",  g().create_index_if_not_exists(IndexSpec::node_unique_equality("Memory", "memoryId")))
        .var_as("memUserId", g().create_index_if_not_exists(IndexSpec::node_equality("Memory", "userId")))
        .var_as("memVector", g().create_vector_index_nodes("Memory", "embedding", Some("userId")))
        .var_as("memText",   g().create_text_index_nodes("Memory", "content", Some("userId")))
        .var_as("catName",   g().create_index_if_not_exists(IndexSpec::node_unique_equality("Category", "name")))
        .var_as("entName",   g().create_index_if_not_exists(IndexSpec::node_equality("Entity", "name")))
        .var_as("sessId",    g().create_index_if_not_exists(IndexSpec::node_unique_equality("Session", "sessionId")))
        .returning(["memVector", "memText"])
}
```

---

## 2. Generation — read-then-write dedup

**2a. Read nearest existing memory.**

```rust
#[register]
fn nearest_memory(userId: String, embedding: Vec<f64>) {
    read_batch()
        .var_as(
            "nearest",
            g().vector_search_nodes_with(
                "Memory",
                "embedding",
                PropertyInput::param("embedding"),
                1usize,
                Some(PropertyInput::param("userId")),
            )
            .where_(Predicate::is_null("deletedAt"))
            .project(vec![
                PropertyProjection::new("memoryId"),
                PropertyProjection::renamed("$distance", "distance"),
            ]),
        )
        .returning(["nearest"])
}
// App: if nearest[0].distance < DEDUP_THRESHOLD -> reinforce; else create.
```

**2b. Create a new memory + ownership edge.**

```rust
#[register]
fn create_memory(
    userId: String,
    memoryId: String,
    content: String,
    embedding: Vec<f64>,
    kind: String,
    salience: f64,
    sessionId: String,
) {
    write_batch()
        .var_as("user", g().n_with_label("User").where_(Predicate::eq_param("userId", "userId")))
        .var_as(
            "mem",
            g().add_n(
                "Memory",
                vec![
                    ("memoryId", PropertyInput::param("memoryId")),
                    ("userId", PropertyInput::param("userId")),
                    ("content", PropertyInput::param("content")),
                    ("embedding", PropertyInput::param("embedding")),
                    ("kind", PropertyInput::param("kind")),
                    ("salience", PropertyInput::param("salience")),
                    ("accessCount", PropertyInput::from(0i64)),
                    ("createdAt", PropertyInput::Expr(Expr::Timestamp)),
                    ("updatedAt", PropertyInput::Expr(Expr::Timestamp)),
                    ("lastAccessedAt", PropertyInput::Expr(Expr::Timestamp)),
                    ("sourceSessionId", PropertyInput::param("sessionId")),
                ],
            ),
        )
        .var_as(
            "own",
            g().n(NodeRef::var("user")).add_e(
                "OWNS",
                NodeRef::var("mem"),
                vec![("createdAt", PropertyInput::Expr(Expr::Timestamp))],
            ),
        )
        .returning(["mem"])
}
```

**2c. Idempotent upsert by `memoryId`.**

```rust
#[register]
fn upsert_memory(
    userId: String,
    memoryId: String,
    content: String,
    embedding: Vec<f64>,
    kind: String,
    salience: f64,
) {
    write_batch()
        .var_as("existing", g().n_with_label("Memory").where_(Predicate::eq_param("memoryId", "memoryId")))
        .var_as_if(
            "updated",
            BatchCondition::VarNotEmpty("existing".to_string()),
            g().n(NodeRef::var("existing"))
                .set_property("content", PropertyInput::param("content"))
                .set_property("embedding", PropertyInput::param("embedding")) // re-embed with content
                .set_property("updatedAt", Expr::timestamp()),
        )
        .var_as_if(
            "created",
            BatchCondition::VarEmpty("existing".to_string()),
            g().add_n(
                "Memory",
                vec![
                    ("memoryId", PropertyInput::param("memoryId")),
                    ("userId", PropertyInput::param("userId")),
                    ("content", PropertyInput::param("content")),
                    ("embedding", PropertyInput::param("embedding")),
                    ("kind", PropertyInput::param("kind")),
                    ("salience", PropertyInput::param("salience")),
                    ("accessCount", PropertyInput::from(0i64)),
                    ("createdAt", PropertyInput::Expr(Expr::Timestamp)),
                    ("updatedAt", PropertyInput::Expr(Expr::Timestamp)),
                    ("lastAccessedAt", PropertyInput::Expr(Expr::Timestamp)),
                ],
            ),
        )
        .returning(["updated", "created"])
}
```

---

## 3. Categorisation — upsert + link

```rust
#[register]
fn categorise_memory(memoryId: String, category: String, entity: String, kind: String) {
    write_batch()
        .var_as(
            "mem",
            g().n_with_label("Memory")
                .where_(Predicate::eq_param("memoryId", "memoryId"))
                .set_property("kind", PropertyInput::param("kind")),
        )
        // Category upsert
        .var_as("cat", g().n_with_label("Category").where_(Predicate::eq_param("name", "category")))
        .var_as_if(
            "catNew",
            BatchCondition::VarEmpty("cat".to_string()),
            g().add_n("Category", vec![("name", PropertyInput::param("category"))]),
        )
        .var_as_if(
            "linkCat",
            BatchCondition::VarNotEmpty("cat".to_string()),
            g().n(NodeRef::var("mem")).add_e("IN_CATEGORY", NodeRef::var("cat"), vec![("at", PropertyInput::Expr(Expr::Timestamp))]),
        )
        .var_as_if(
            "linkCatNew",
            BatchCondition::VarNotEmpty("catNew".to_string()),
            g().n(NodeRef::var("mem")).add_e("IN_CATEGORY", NodeRef::var("catNew"), vec![("at", PropertyInput::Expr(Expr::Timestamp))]),
        )
        // Entity upsert
        .var_as("ent", g().n_with_label("Entity").where_(Predicate::eq_param("name", "entity")))
        .var_as_if(
            "entNew",
            BatchCondition::VarEmpty("ent".to_string()),
            g().add_n("Entity", vec![("name", PropertyInput::param("entity"))]),
        )
        .var_as_if(
            "mentions",
            BatchCondition::VarNotEmpty("ent".to_string()),
            g().n(NodeRef::var("mem")).add_e("MENTIONS", NodeRef::var("ent"), vec![("at", PropertyInput::Expr(Expr::Timestamp))]),
        )
        .var_as_if(
            "mentionsNew",
            BatchCondition::VarNotEmpty("entNew".to_string()),
            g().n(NodeRef::var("mem")).add_e("MENTIONS", NodeRef::var("entNew"), vec![("at", PropertyInput::Expr(Expr::Timestamp))]),
        )
        .returning(["mem"])
}
```

---

## 4. Updating — reinforce on access

```rust
#[register]
fn reinforce_memory(memoryId: String) {
    write_batch()
        .var_as(
            "mem",
            g().n_with_label("Memory")
                .where_(Predicate::eq_param("memoryId", "memoryId"))
                .set_property("lastAccessedAt", Expr::timestamp())
                .set_property("accessCount", Expr::prop("accessCount").add(Expr::val(1i64)))
                .set_property("salience", Expr::prop("salience").add(Expr::val(0.1f64))),
        )
        .returning(["mem"])
}
```

---

## 5. Correct / supersede

```rust
#[register]
fn supersede_memory(newId: String, oldId: String, reason: String) {
    write_batch()
        .var_as("old", g().n_with_label("Memory").where_(Predicate::eq_param("memoryId", "oldId")))
        .var_as("new", g().n_with_label("Memory").where_(Predicate::eq_param("memoryId", "newId")))
        .var_as(
            "link",
            g().n(NodeRef::var("new")).add_e(
                "SUPERSEDES",
                NodeRef::var("old"),
                vec![("reason", PropertyInput::param("reason")), ("at", PropertyInput::Expr(Expr::Timestamp))],
            ),
        )
        .var_as("invalidate", g().n(NodeRef::var("old")).set_property("validTo", Expr::timestamp()))
        .returning(["link", "invalidate"])
}
```

---

## 6. Soft-delete

```rust
#[register]
fn soft_delete_memory(memoryId: String) {
    write_batch()
        .var_as(
            "mem",
            g().n_with_label("Memory")
                .where_(Predicate::eq_param("memoryId", "memoryId"))
                .set_property("deletedAt", Expr::timestamp()),
        )
        .returning(["mem"])
}
```

---

## 7. Decay sweep

```rust
#[register]
fn decay_sweep(userId: String, cutoff: i64, minSalience: f64, minAccess: i64) {
    write_batch()
        .var_as(
            "decayed",
            g().n_with_label("Memory")
                .where_(Predicate::eq_param("userId", "userId"))
                .where_(Predicate::and(vec![
                    Predicate::is_null("deletedAt"),
                    Predicate::lt_param("lastAccessedAt", "cutoff"),
                    Predicate::lt_param("salience", "minSalience"),
                    Predicate::lt_param("accessCount", "minAccess"),
                ]))
                .set_property("deletedAt", Expr::timestamp()),
        )
        .returning(["decayed"])
}
```

---

## 8. Expiry sweep (hard delete)

```rust
#[register]
fn expiry_sweep(userId: String, now: i64) {
    write_batch()
        .var_as(
            "expired",
            g().n_with_label("Memory")
                .where_(Predicate::eq_param("userId", "userId"))
                .where_(Predicate::and(vec![
                    Predicate::is_not_null("expiresAt"),
                    Predicate::lt_param("expiresAt", "now"),
                ]))
                .drop(),
        )
        .returning(["expired"])
}
// drop() removes the node and its edges. For multigraph precision use drop_edge_by_id first.
```

---

## 9. Hybrid retrieval

**9a. Vector + BM25 in one read batch.**

```rust
#[register]
fn hybrid_recall(userId: String, embedding: Vec<f64>, query: String, k: i64) {
    read_batch()
        .var_as(
            "semantic",
            g().vector_search_nodes_with(
                "Memory",
                "embedding",
                PropertyInput::param("embedding"),
                Expr::param("k"),
                Some(PropertyInput::param("userId")),
            )
            .where_(Predicate::is_null("deletedAt"))
            .project(vec![
                PropertyProjection::new("memoryId"),
                PropertyProjection::new("content"),
                PropertyProjection::new("kind"),
                PropertyProjection::new("salience"),
                PropertyProjection::new("lastAccessedAt"),
                PropertyProjection::renamed("$distance", "distance"),
            ]),
        )
        .var_as(
            "keyword",
            g().text_search_nodes_with(
                "Memory",
                "content",
                PropertyInput::param("query"),
                Expr::param("k"),
                Some(PropertyInput::param("userId")),
            )
            .where_(Predicate::is_null("deletedAt"))
            .project(vec![
                PropertyProjection::new("memoryId"),
                PropertyProjection::new("content"),
                PropertyProjection::new("kind"),
                PropertyProjection::new("salience"),
                PropertyProjection::new("lastAccessedAt"),
                PropertyProjection::renamed("$distance", "score"),
            ]),
        )
        .returning(["semantic", "keyword"])
}
```

**9b. Fuse with RRF + re-rank** — done in application code; see the formula in `REFERENCE.md` and the TS implementation in `EXAMPLES.md` §9b.

**9c. Graph expansion via shared entities.**

```rust
#[register]
fn expand_via_entities(memoryId: String, userId: String) {
    read_batch()
        .var_as(
            "related",
            g().n_with_label("Memory")
                .where_(Predicate::eq_param("memoryId", "memoryId"))
                .out(Some("MENTIONS"))
                .in_(Some("MENTIONS"))
                .dedup()
                .where_(Predicate::and(vec![
                    Predicate::is_null("deletedAt"),
                    Predicate::eq_param("userId", "userId"),
                ]))
                .limit(10usize)
                .project(vec![
                    PropertyProjection::new("memoryId"),
                    PropertyProjection::new("content"),
                ]),
        )
        .returning(["related"])
}
```
