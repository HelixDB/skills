# HQL → Rust DSL / TypeScript DSL: Worked Migrations

Each scenario: HQL source, then Rust and TypeScript. Rules and contracts: `SKILL.md`; spellings: `REFERENCE.md`.

- **Rust** assumes `use helix_db::dsl::prelude::*;` and shows `read_batch()`/`write_batch()` bodies with explicit
  parameter references. Wrap in `#[query]` for a named callable returning `Result<QueryRequest, QueryError>`
  (call with `?`).
- **TypeScript** assumes `import { ... } from "@helix-db/helix-db";`. Builders return a `ReadBatch`/`WriteBatch`;
  build a request with `builder().toQueryJson(params, values, { queryName: "route_name" })` (or
  `.toQueryJson({ queryName: "route_name" })` with no params).

---

## 1. Read a node by ID

```helixql
QUERY GetUser(user_id: ID) =>
    user <- N<User>(user_id)
    RETURN user
```

```rust
read_batch()
    .var_as("user", g().n(NodeRef::param("user_id")))
    .returning(["user"])
```

```ts
const getUserParams = defineParams({ userId: param.i64() });

function getUser(_ = getUserParams) {
  return readBatch()
    .varAs("user", g().n(NodeRef.param("userId")))
    .returning(["user"]);
}

const body = getUser().toQueryJson(getUserParams, { userId: 42n });
```

> Response: `{"user": [{"$id": 42}]}`, or `{"user": []}` when the node does not exist. Project for properties.

---

## 2. Indexed-property lookup with projection

```helixql
QUERY GetByHandle(handle: String) =>
    user <- N<User>({handle: handle})
    RETURN user::{userID: ::ID, name, handle}
```

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label_where("User", SourcePredicate::eq_param("handle", "handle"))
            .project(vec![
                PropertyProjection::renamed("$id", "userID"),
                PropertyProjection::new("name"),
                PropertyProjection::new("handle"),
            ]),
    )
    .returning(["user"])
```

```ts
const getByHandleParams = defineParams({ handle: param.string() });

function getByHandle(_ = getByHandleParams) {
  return readBatch()
    .varAs(
      "user",
      g()
        .nWithLabelWhere("User", SourcePredicate.eqParam("handle", "handle"))
        .project([
          PropertyProjection.renamed("$id", "userID"),
          PropertyProjection.new("name"),
          PropertyProjection.new("handle"),
        ]),
    )
    .returning(["user"]);
}

const body = getByHandle().toQueryJson(getByHandleParams, { handle: "alice" });
```

---

## 3. Multi-hop traversal with property selection

```helixql
QUERY GetFollowing(user_id: ID) =>
    following <- N<User>(user_id)::Out<Follows>::Out<Follows>
    RETURN following::{name, handle}
```

```rust
read_batch()
    .var_as(
        "following",
        g().n(NodeRef::param("user_id"))
            .out(Some("Follows"))
            .out(Some("Follows"))
            .dedup()
            .value_map(Some(vec!["name", "handle"])),
    )
    .returning(["following"])
```

```ts
const getFollowingParams = defineParams({ userId: param.i64() });

function getFollowing(_ = getFollowingParams) {
  return readBatch()
    .varAs(
      "following",
      g()
        .n(NodeRef.param("userId"))
        .out("Follows")
        .out("Follows")
        .dedup()
        .valueMap(["name", "handle"]),
    )
    .returning(["following"]);
}

const body = getFollowing().toQueryJson(getFollowingParams, { userId: 42n });
```

> HQL does not dedup; add `dedup()` only when distinct results are intended (multi-hop paths repeat nodes).

---

## 4. Edge-object traversal to an endpoint

```helixql
QUERY GetCreator(creation_id: ID) =>
    creator <- E<Creates>(creation_id)::FromN
    RETURN creator
```

```rust
read_batch()
    .var_as("creator", g().e(EdgeRef::param("creation_id")).in_n())
    .returning(["creator"])
```

```ts
const getCreatorParams = defineParams({ creationId: param.i64() });

function getCreator(_ = getCreatorParams) {
  return readBatch()
    .varAs("creator", g().e(EdgeRef.param("creationId")).inN())
    .returning(["creator"]);
}

const body = getCreator().toQueryJson(getCreatorParams, { creationId: 9n });
```

> `From` is the *incoming* side from the edge's perspective, hence `.in_n()`.

---

## 5. Filtered scan with compound predicate, order, and range

```helixql
QUERY ActiveAdults(status: String, min_age: U8) =>
    users <- N<User>::WHERE(AND(_::{status}::EQ(status), _::{age}::GTE(min_age)))::ORDER<Desc>(_::{age})::RANGE(0, 20)
    RETURN users::{name, age, status}
```

```rust
read_batch()
    .var_as(
        "users",
        g().n_with_label("User")
            .where_(Predicate::and(vec![
                Predicate::eq_param("status", "status"),
                Predicate::gte_param("age", "min_age"),
            ]))
            .order_by("age", Order::Desc)
            .range(0, 20)
            .project(vec![
                PropertyProjection::new("name"),
                PropertyProjection::new("age"),
                PropertyProjection::new("status"),
            ]),
    )
    .returning(["users"])
```

```ts
const activeAdultsParams = defineParams({ status: param.string(), minAge: param.i64() });

function activeAdults(_ = activeAdultsParams) {
  return readBatch()
    .varAs(
      "users",
      g()
        .nWithLabel("User")
        .where(
          Predicate.and([
            Predicate.eqParam("status", "status"),
            Predicate.gteParam("age", "minAge"),
          ]),
        )
        .orderBy("age", Order.Desc)
        .range(0, 20)
        .project([
          PropertyProjection.new("name"),
          PropertyProjection.new("age"),
          PropertyProjection.new("status"),
        ]),
    )
    .returning(["users"]);
}

const body = activeAdults().toQueryJson(activeAdultsParams, { status: "active", minAge: 18n });
```

---

## 6. Membership filter (`IS_IN`) and string `CONTAINS`

```helixql
QUERY SearchUsers(statuses: [String], term: String) =>
    users <- N<User>::WHERE(AND(_::{status}::IS_IN(statuses), _::{bio}::CONTAINS(term)))
    RETURN users::{name}
```

```rust
read_batch()
    .var_as(
        "users",
        g().n_with_label("User")
            .where_(Predicate::and(vec![
                Predicate::is_in_param("status", "statuses"),
                Predicate::contains_param("bio", "term"),
            ]))
            .value_map(Some(vec!["name"])),
    )
    .returning(["users"])
```

```ts
const searchUsersParams = defineParams({ statuses: param.array(param.string()), term: param.string() });

function searchUsers(_ = searchUsersParams) {
  return readBatch()
    .varAs(
      "users",
      g()
        .nWithLabel("User")
        .where(
          Predicate.and([
            Predicate.isInParam("status", "statuses"),
            Predicate.containsParam("bio", "term"),
          ]),
        )
        .valueMap(["name"]),
    )
    .returning(["users"]);
}

const body = searchUsers().toQueryJson(searchUsersParams, { statuses: ["active", "pending"], term: "graph" });
```

---

## 7. Group-by counts vs aggregate-by objects

```helixql
QUERY UsersByCountry() =>
    users <- N<User>
    RETURN users::GROUP_BY(country)
```

```rust
read_batch()
    .var_as("users", g().n_with_label("User").group_count("country"))
    .returning(["users"])
```

```ts
function usersByCountry() {
  return readBatch()
    .varAs("users", g().nWithLabel("User").groupCount("country"))
    .returning(["users"]);
}

const body = usersByCountry().toQueryJson();
```

> `AGGREGATE_BY` (full objects) → `group`; `AVG(score)` → `.aggregate_by(AggregateFunction::Mean, "score")`.

---

## 8. Vector search (precomputed vector, tenant-scoped)

```helixql
QUERY FindDocs(vector: [F64], k: I64) =>
    docs <- SearchV<Document>(vector, k)
    RETURN docs::{docID: ::ID, content}
```

```rust
read_batch()
    .var_as(
        "docs",
        g().vector_search_nodes_with(
            "Document",
            "embedding",
            PropertyInput::param("vector"),
            Expr::param("k"),
            Some(PropertyInput::param("tenant_id")),
        )
        .project(vec![
            PropertyProjection::renamed("$id", "docID"),
            PropertyProjection::renamed("$distance", "distance"),
            PropertyProjection::new("content"),
        ]),
    )
    .returning(["docs"])
```

```ts
const findDocsParams = defineParams({
  vector: param.array(param.f64()),
  k: param.i64(),
  tenantId: param.string(),
});

function findDocs(_ = findDocsParams) {
  return readBatch()
    .varAs(
      "docs",
      g()
        .vectorSearchNodesWith(
          "Document",
          "embedding",
          PropertyInput.param("vector"),
          Expr.param("k"),
          PropertyInput.param("tenantId"),
        )
        .project([
          PropertyProjection.renamed("$id", "docID"),
          PropertyProjection.renamed("$distance", "distance"),
          PropertyProjection.new("content"),
        ]),
    )
    .returning(["docs"]);
}

const body = findDocs().toQueryJson(findDocsParams, { vector: [0.1, 0.2, 0.3], k: 10n, tenantId: "acme" });
```

> `_with`/`...With` variants take params; the plain ones take a literal `Vec<f32>`/`number[]`. The vector is
> precomputed (`Embed` is unsupported, §15).

---

## 9. BM25 keyword search

```helixql
QUERY SearchDocs(keywords: String, k: I64) =>
    docs <- SearchBM25<Document>(keywords, k)
    RETURN docs
```

```rust
read_batch()
    .var_as(
        "docs",
        g().text_search_nodes_with(
            "Document",
            "content",
            PropertyInput::param("keywords"),
            Expr::param("k"),
            None::<PropertyInput>,
        ),
    )
    .returning(["docs"])
```

```ts
const searchDocsParams = defineParams({ keywords: param.string(), k: param.i64() });

function searchDocs(_ = searchDocsParams) {
  return readBatch()
    .varAs(
      "docs",
      g().textSearchNodesWith("Document", "content", PropertyInput.param("keywords"), Expr.param("k"), null),
    )
    .returning(["docs"]);
}

const body = searchDocs().toQueryJson(searchDocsParams, { keywords: "machine learning", k: 5n });
```

> `"content"` must be the BM25-indexed property. `None`/`null` tenant when the route is not tenant-scoped.

---

## 10. Create a node, then an edge to it (write batch)

```helixql
QUERY CreateFollow(name: String, target_id: ID) =>
    user <- AddN<User>({name: name})
    edge <- AddE<Follows>::From(user)::To(target_id)
    RETURN user, edge
```

```rust
write_batch()
    .var_as("user", g().add_n("User", vec![("name", PropertyInput::param("name"))]))
    .var_as(
        "edge",
        g().n(NodeRef::var("user"))
            .add_e(
                "Follows",
                NodeRef::param("target_id"),
                Vec::<(&str, PropertyInput)>::new(),
            ),
    )
    .returning(["user", "edge"])
```

```ts
const createFollowParams = defineParams({ name: param.string(), targetId: param.i64() });

function createFollow(_ = createFollowParams) {
  return writeBatch()
    .varAs("user", g().addN("User", { name: PropertyInput.param("name") }))
    .varAs(
      "edge",
      g().n(NodeRef.var("user")).addE("Follows", NodeRef.param("targetId"), {}),
    )
    .returning(["user", "edge"]);
}

const body = createFollow().toQueryJson(createFollowParams, { name: "Alice", targetId: 7n });
```

> Both bindings return `[{"$id": N}]`. A missing `target_id` fails the whole batch; re-running creates a second
> `Follows` edge.

---

## 11. Update properties

```helixql
QUERY RenameUser(user_id: ID, new_name: String) =>
    updated <- N<User>(user_id)::UPDATE({name: new_name})
    RETURN updated
```

```rust
write_batch()
    .var_as(
        "updated",
        g().n(NodeRef::param("user_id")).set_property("name", PropertyInput::param("new_name")),
    )
    .returning(["updated"])
```

```ts
const renameUserParams = defineParams({ userId: param.i64(), newName: param.string() });

function renameUser(_ = renameUserParams) {
  return writeBatch()
    .varAs("updated", g().n(NodeRef.param("userId")).setProperty("name", PropertyInput.param("newName")))
    .returning(["updated"]);
}

const body = renameUser().toQueryJson(renameUserParams, { userId: 42n, newName: "Alicia" });
```

---

## 12. Delete a node

```helixql
QUERY DeleteUser(user_id: ID) =>
    DROP N<User>(user_id)
    RETURN "Removed"
```

```rust
write_batch()
    .var_as("dropped", g().n(NodeRef::param("user_id")).drop())
    .returning(["dropped"])
```

```ts
const deleteUserParams = defineParams({ userId: param.i64() });

function deleteUser(_ = deleteUserParams) {
  return writeBatch()
    .varAs("dropped", g().n(NodeRef.param("userId")).drop())
    .returning(["dropped"]);
}

const body = deleteUser().toQueryJson(deleteUserParams, { userId: 42n });
```

> `RETURN "Removed"` has no form: return the dropped binding, or `.returning(Vec::<&str>::new())` /
> `.returning([])`. Edges only: `g().n(NodeRef::param("user_id")).out_e(Some("Follows")).drop()` /
> `.outE("Follows").drop()` (main).

---

## 13. Iterate an array parameter (`FOR ... IN`)

```helixql
QUERY CreateUsers(users: [{name: String}]) =>
    FOR {name} IN users {
        AddN<User>({name: name})
    }
    RETURN NONE
```

```rust
let body = write_batch()
    .var_as("u", g().add_n("User", vec![("name", PropertyInput::param("name"))]));

write_batch()
    .for_each_param("users", body)
    .returning(Vec::<&str>::new())
```

```ts
const createUsersParams = defineParams({ users: param.array(param.object(param.string())) });

function createUsers(_ = createUsersParams) {
  const body = writeBatch().varAs("u", g().addN("User", { name: PropertyInput.param("name") }));
  return writeBatch().forEachParam("users", body).returning([]);
}

const body = createUsers().toQueryJson(createUsersParams, { users: [{ name: "Alice" }, { name: "Bob" }] });
```

> The body is its own batch reading each element's fields by name. Destructuring over objects (`FOR {name} IN`)
> maps cleanly; an array-of-scalars `FOR name IN` does not map directly.

---

## 14. Relationship-existence filter — UNSUPPORTED as a predicate

```helixql
QUERY UsersWithFollowers() =>
    users <- N<User>::WHERE(EXISTS(_::In<Follows>))
    RETURN users::{name}
```

No predicate form: stage the targets of `Follows` edges and intersect with `.within`, or filter app-side.

```rust
read_batch()
    // every node that is the target of a Follows edge (i.e. has a follower)
    .var_as("followed", g().e_with_label("Follows").out_n().dedup())
    .var_as(
        "users",
        g().n_with_label("User").within("followed").value_map(Some(vec!["name"])),
    )
    .returning(["users"])
```

```ts
function usersWithFollowers() {
  return readBatch()
    .varAs("followed", g().eWithLabel("Follows").outN().dedup())
    .varAs("users", g().nWithLabel("User").within("followed").valueMap(["name"]))
    .returning(["users"]);
}

const body = usersWithFollowers().toQueryJson();
```

> Flag it in the migration. `!EXISTS` uses `.without(var)`; count-based `WHERE`
> (`WHERE(_::In<Follows>::COUNT::GT(100))`) has no predicate form either.

---

## 15. Upsert + inline embedding + reranking — split DSL / app code

```helixql
#[model("openai:text-embedding-ada-002")]
QUERY UpsertAndSearch(content: String, k: I64) =>
    doc <- N<Document>::WHERE(_::{content}::EQ(content))::UpsertV(Embed(content), {content: content})
    hits <- SearchV<Document>(Embed(content), k)::RerankRRF
    RETURN hits
```

`UpsertV` is one write batch; `#[model]`, `Embed(...)` and `::RerankRRF` move to app code.

**App code (outside the DSL):**
1. Embed `content` with your model → `vector` (replaces `Embed` and `#[model]`).
2. After the search returns ranked hits, apply RRF/MMR fusion in the application (replaces `::RerankRRF`).

**DSL request 1 — the upsert (write batch):**

```rust
write_batch()
    .var_as(
        "existing",
        g().n_with_label_where("Document", SourcePredicate::eq_param("content", "content")),
    )
    .var_as_if(
        "updated",
        BatchCondition::VarNotEmpty("existing".to_string()),
        g().n(NodeRef::var("existing"))
            .set_property("embedding", PropertyInput::param("vector")),
    )
    .var_as_if(
        "created",
        BatchCondition::VarEmpty("existing".to_string()),
        g().add_n(
            "Document",
            vec![
                ("content", PropertyInput::param("content")),
                ("embedding", PropertyInput::param("vector")),
            ],
        ),
    )
    .returning(["updated", "created"])
```

```ts
const upsertDocParams = defineParams({ content: param.string(), vector: param.array(param.f64()) });

function upsertDoc(_ = upsertDocParams) {
  return writeBatch()
    .varAs("existing", g().nWithLabelWhere("Document", SourcePredicate.eqParam("content", "content")))
    .varAsIf(
      "updated",
      BatchCondition.varNotEmpty("existing"),
      g().n(NodeRef.var("existing")).setProperty("embedding", PropertyInput.param("vector")),
    )
    .varAsIf(
      "created",
      BatchCondition.varEmpty("existing"),
      g().addN("Document", { content: PropertyInput.param("content"), embedding: PropertyInput.param("vector") }),
    )
    .returning(["updated", "created"]);
}

const upsertBody = upsertDoc().toQueryJson(upsertDocParams, { content: "graph databases", vector: [0.1, 0.2, 0.3] });
```

> Two concurrent upserts can both see `existing` empty; `IndexSpec::node_unique_equality("Document", "content")`
> makes the second fail with `unique_constraint_violation`, then re-run once. Index keys are limited to about
> 64 KiB: for long text, store and look up a hash property (e.g. `contentHash`) instead of `content`.

**DSL request 2 — the similarity search with the app-provided vector:**

```rust
read_batch()
    .var_as(
        "hits",
        g().vector_search_nodes_with(
            "Document",
            "embedding",
            PropertyInput::param("vector"),
            Expr::param("k"),
            None::<PropertyInput>,
        )
        .project(vec![
            PropertyProjection::renamed("$id", "docID"),
            PropertyProjection::renamed("$distance", "distance"),
            PropertyProjection::new("content"),
        ]),
    )
    .returning(["hits"])
```

```ts
const searchSimilarParams = defineParams({ vector: param.array(param.f64()), k: param.i64() });

function searchSimilar(_ = searchSimilarParams) {
  return readBatch()
    .varAs(
      "hits",
      g()
        .vectorSearchNodesWith("Document", "embedding", PropertyInput.param("vector"), Expr.param("k"), null)
        .project([
          PropertyProjection.renamed("$id", "docID"),
          PropertyProjection.renamed("$distance", "distance"),
          PropertyProjection.new("content"),
        ]),
    )
    .returning(["hits"]);
}

const body = searchSimilar().toQueryJson(searchSimilarParams, { vector: [0.1, 0.2, 0.3], k: 10n });
```

> Tell the user which parts moved to app code and why. A strong (default) search sees the vector the upsert just
> committed. Hybrid recall (vector + BM25 + app-side RRF): `helix-memory-system`.

---

## 16. Unweighted shortest path (`ShortestPathBFS`)

```helixql
QUERY Degrees(from_id: ID, to_id: ID) =>
    path <- N<User>(from_id)::ShortestPathBFS<Follows>::To(to_id)
    RETURN path
```

```rust
read_batch()
    .var_as(
        "path",
        g().shortest_path_with(
            NodeRef::param("from_id"),
            NodeRef::param("to_id"),
            Some("Follows"),
            ShortestPathDirection::Out,
            6,
        ),
    )
    .returning(["path"])
```

```ts
const degreesParams = defineParams({ fromId: param.i64(), toId: param.i64() });

function degrees(_ = degreesParams) {
  return readBatch()
    .varAs(
      "path",
      g().shortestPath(NodeRef.param("fromId"), NodeRef.param("toId"), 6, { label: "Follows" }),
    )
    .returning(["path"]);
}

const body = degrees().toQueryJson(degreesParams, { fromId: 1n, toId: 7n });
```

> Response: `{"path": [1, 4, 7]}`, or `{"path": []}`. HQL had no depth bound; pick a positive `max_depth` that
> fits the graph. Undirected: `ShortestPathDirection::Both` / `{ direction: ShortestPathDirection.Both }`; any
> label: `shortest_path(..)` / no `label`.
