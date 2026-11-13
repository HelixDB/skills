# Cypher To Helix Rosetta

Authoring source for `helix-query-from-cypher`. Contracts are recorded in
`docs/source-canon.md`; check the snippets against the Rust DSL on helix-db
`main` (`use helix_db::dsl::prelude::*;`).

## Native First

The server runs a profile of openCypher (`POST /v2/cypher`,
`/v2/cypher/explain`) and SQL translated into it (`POST /v2/sql`,
`/v2/sql/explain`), Docker v0.0.13+ and Helix Cloud. Body
`{"query", "parameters", "query_name"}` (SQL adds `mappings` and positional
`parameters`); response `{"columns", "rows"}`. Send supported statements as
they are; translate only:

- constructs rejected with `unsupported_feature`: `MERGE`, variable-length
  relationships, `shortestPath`/`allShortestPaths`, `UNION`, `CALL` and
  `EXISTS`/`COUNT`/`COLLECT` subqueries, map projections, list and pattern
  comprehensions, pattern predicates, `any`/`all`/`none`/`single`, `FOREACH`,
  `LOAD CSV`, schema commands, multiple or mutated labels, and functions
  outside the profile (`timestamp`, `date`, `datetime`, `reduce`, `round`,
  `sqrt`, `split`, `replace`, `startNode`, `endNode`, ...)
- work only the DSL does: vector and text search, index management, typed
  parameters, conditional write batches (`var_as_if`), `for_each_param`

Public references: https://docs.helix-db.com/database/helix-db/query-guides/cypher,
https://docs.helix-db.com/database/helix-db/query-guides/sql

## Mental Model

Cypher is row-oriented: each row carries several variables. The Helix DSL is
traversal-oriented: a stream of current elements, plus optional row bindings
(`bind`) read by `project_bindings`. A translation usually:

1. anchors one narrow set (`var_as`)
2. traverses explicitly, keeping target labels with `has_label`
3. binds per-row variables only when the result needs more than one of them
4. filters with `where_`
5. shapes the output with `project`, `project_bindings`, `count`, aggregation, `limit`

## Mapping Table

| Cypher | Helix Rust DSL | Notes |
| --- | --- | --- |
| `MATCH (u:User)` | `g().n_with_label("User")` | label scan |
| `MATCH (u:User {userId: $userId})` | `g().n_with_label("User").where_(Predicate::eq_param("userId", "userId"))` | index push-down when indexed |
| `(u)-[:FOLLOWS]->(v:User)` | `.out(Some("FOLLOWS")).has_label("User")` | `out` does not filter by node label |
| `(u)<-[:FOLLOWS]-(v)` | `.in_(Some("FOLLOWS"))` | |
| `(u)-[:R]-(v)` | `.both(Some("R"))` | |
| `(u)-[e:FOLLOWS]->()` | `.out_e(Some("FOLLOWS"))` | edge stream; `out_n()`/`in_n()`/`other_n()` back to nodes |
| `MATCH (u)-[:WROTE]->(p:Post) RETURN u.name, p.title` | `.bind("u").out(Some("WROTE")).has_label("Post").bind("p").project_bindings(..)` | see [Several variables](#several-variables-per-row) |
| `OPTIONAL MATCH (u)-[:WORKS_AT]->(o:Org)` | `.bind("u").optional(sub().out(Some("WORKS_AT")).has_label("Org").bind("o")).project_bindings(..)` | see [OPTIONAL MATCH](#optional-match) |
| `-[:R*1..2]->` | `.repeat(RepeatConfig::new(sub().out(Some("R")).dedup()).times(2).emit_after())` | bounded; `*m..n` = `m - 1` plain hops + `times(n - m + 1)` |
| `shortestPath((a)-[:KNOWS*..6]-(b))` | `g().shortest_path_with(NodeRef::var("a"), NodeRef::var("b"), Some("KNOWS"), ShortestPathDirection::Both, 6)` | one unweighted path as node IDs; `[]` if none |
| `WHERE u.status = $status` | `.where_(Predicate::eq_param("status", "status"))` | |
| `WHERE u.age >= $minAge` | `.where_(Predicate::gte_param("age", "minAge"))` | |
| `WHERE u.status IN $statuses` | `.where_(Predicate::is_in_param("status", "statuses"))` | |
| `WHERE u.deletedAt IS NULL` | `.where_(Predicate::is_null("deletedAt"))` | a missing property is null |
| `WHERE exists(u.email)` | `.where_(Predicate::has_key("email"))` or `is_not_null("email")` | |
| `RETURN v.a, v.b` | `.project(vec![PropertyProjection::new("a"), PropertyProjection::new("b")])` | a bare stream returns only `{"$id": N}` |
| `RETURN DISTINCT v` | `.dedup()` | several variables: `project_distinct_bindings` |
| `ORDER BY v.x DESC` | `.order_by("x", Order::Desc)` | missing values first for `Asc`, last for `Desc` (Cypher: last for `ASC`, first for `DESC`) |
| `SKIP $o LIMIT $l` | `.skip(Expr::param("o")).limit(Expr::param("l"))` | |
| `CASE WHEN .. THEN .. ELSE .. END` | `Projection::expr("alias", Expr::case(vec![(pred, expr), ..], Some(else_expr)))` | a value, not `choose` |
| `count(v)` | `.count()` | scalar |
| `RETURN v.k, count(*)` | `.group_count("k")` | `[{"k": .., "count": n}]` |
| `RETURN v.k, collect(v)` | `.group("k")` | `[{"k": .., "count": n, "ids": [..]}]` |
| `sum(v.x)` / `avg` / `min` / `max` over the stream | `.aggregate_by(AggregateFunction::Sum, "x")` (`Mean`, `Min`, `Max`, `Count`) | `[{"x_Sum": f64}]`; `0.0` on empty input |
| `collect(s)` then best by property | `.order_by("value", Order::Desc).limit(1)` | |
| `UNWIND $items AS i` + per-item writes | `write_batch().for_each_param("items", body)` | items are objects; fields become params |
| `DETACH DELETE n` | narrow, then `.drop()` | node `drop()` always removes incident edges |
| `MERGE (u:L {k: $k}) ...` | unique index + read + `var_as_if` | see [MERGE](#merge) |
| `MERGE (u)-[:R]->(g)` | read adjacency, `without`, guarded `add_e` | see [MERGE](#merge) |
| `timestamp()` | `Expr::timestamp()` | server epoch millis; `Expr::datetime()` for a typed DateTime |

Output contracts: every row-stream return is `[]` when empty (including single
lookups and skipped `var_as_if` branches); only `count`, `exists` and index
operations are scalars. Node and edge IDs are integers.

## Canonical Examples

### Match And Traverse

```cypher
MATCH (u:User {userId: $userId})-[:FOLLOWS]->(v:User)
WHERE v.status = $status
RETURN v.userId, v.name, v.createdAt
ORDER BY v.createdAt DESC
LIMIT $limit
```

Native as is. As a DSL route:

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId")),
    )
    .var_as(
        "results",
        g().n(NodeRef::var("user"))
            .out(Some("FOLLOWS"))
            .has_label("User")
            .where_(Predicate::eq_param("status", "status"))
            .order_by("createdAt", Order::Desc)
            .limit(Expr::param("limit"))
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("userId"),
                PropertyProjection::new("name"),
                PropertyProjection::new("createdAt"),
            ]),
    )
    .returning(["results"])
```

Rows without `createdAt` sort last here and first in Cypher.

### Incoming Count

```cypher
MATCH (:User {userId: $userId})<-[:FOLLOWS]-(f:User)
RETURN count(f) AS followerCount
```

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId")),
    )
    .var_as(
        "followerCount",
        g().n(NodeRef::var("user"))
            .in_(Some("FOLLOWS"))
            .has_label("User")
            .count(),
    )
    .returning(["followerCount"])
```

### DISTINCT And Pagination

```cypher
MATCH (u:User)-[:MEMBER_OF]->(g:Group)
RETURN DISTINCT g.groupId, g.name
ORDER BY g.name ASC
SKIP $offset
LIMIT $limit
```

```rust
read_batch()
    .var_as(
        "groups",
        g().n_with_label("User")
            .out(Some("MEMBER_OF"))
            .has_label("Group")
            .dedup()
            .order_by("name", Order::Asc)
            .skip(Expr::param("offset"))
            .limit(Expr::param("limit"))
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("groupId"),
                PropertyProjection::new("name"),
            ]),
    )
    .returning(["groups"])
```

Groups without `name` sort first here and last in Cypher.

### Several Variables Per Row

```cypher
MATCH (u:User)-[:WROTE]->(p:Post)
WHERE p.published = true
RETURN u.name AS author, p.title AS title
LIMIT 50
```

```rust
read_batch()
    .var_as(
        "rows",
        g().n_with_label("User")
            .bind("u")
            .out(Some("WROTE"))
            .has_label("Post")
            .where_(Predicate::eq("published", true))
            .bind("p")
            .limit(50)
            .project_bindings(vec![
                BindingProjection::binding("u", "name", "author"),
                BindingProjection::binding("p", "title", "title"),
            ]),
    )
    .returning(["rows"])
```

After `bind`, the planner rejects `order_by`, `choose`, `repeat`, `project`,
`value_map`, `values`, `id`, `label` and `edge_properties`
(`invalid_after_bind_operation`). Sort before the first `bind`; when the sort key
belongs to a later variable, keep the statement native. `bind` and
`project_bindings` are rejected in a `write_batch`.

### OPTIONAL MATCH

```cypher
MATCH (u:User {userId: $userId})
OPTIONAL MATCH (u)-[:WORKS_AT]->(o:Org)
RETURN u, o
```

`optional(sub)` emits the input row unchanged when the branch is empty, so
`.optional(sub().out(..))` alone makes the user stand in for the missing org.
Bind both sides:

```rust
read_batch()
    .var_as(
        "rows",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId"))
            .bind("u")
            .optional(sub().out(Some("WORKS_AT")).has_label("Org").bind("o"))
            .project_bindings(vec![
                BindingProjection::binding("u", "$id", "u_id"),
                BindingProjection::binding("u", "name", "u_name"),
                BindingProjection::binding("o", "$id", "o_id"),
                BindingProjection::binding("o", "name", "o_name"),
            ]),
    )
    .returning(["rows"])
```

One row per org, like Cypher. A user with no org yields one row without the
`o_*` keys. Conditions from `OPTIONAL MATCH ... WHERE` go inside the
sub-traversal.

### CASE

```cypher
MATCH (u:User)
RETURN u.name AS name,
       CASE WHEN u.score >= 90 THEN 'gold' WHEN u.score >= 50 THEN 'silver' ELSE 'bronze' END AS tier
```

```rust
read_batch()
    .var_as(
        "users",
        g().n_with_label("User").project(vec![
            Projection::property("name", "name"),
            Projection::expr(
                "tier",
                Expr::case(
                    vec![
                        (Predicate::gte("score", 90), Expr::val("gold")),
                        (Predicate::gte("score", 50), Expr::val("silver")),
                    ],
                    Some(Expr::val("bronze")),
                ),
            ),
        ]),
    )
    .returning(["users"])
```

`choose(pred, then, None)` drops rows that fail `pred`; use it only to branch
the traversal itself, with an else branch (`Some(sub())` passes rows through).

### Aggregation

```cypher
MATCH (u:User) RETURN u.status AS status, count(*) AS users
```

```rust
read_batch()
    .var_as("byStatus", g().n_with_label("User").group_count("status"))
    .returning(["byStatus"])
// {"byStatus": [{"status": "active", "count": 12}, ...]}
```

`aggregate_by(AggregateFunction::Sum, "amount")` aggregates the whole stream to
`[{"amount_Sum": 12.0}]`. Per-group sums and averages have no DSL step; keep
those native or aggregate in the application.

### MERGE

Node upsert. Create the unique key once and wait until its build succeeds
(`get_index_operation(operation_id)` reports `status: "succeeded"`):

```rust
write_batch()
    .var_as(
        "index",
        g().create_index_if_not_exists(IndexSpec::node_unique_equality("User", "userId")),
    )
    .returning(["index"])
```

```cypher
MERGE (u:User {userId: $userId})
ON CREATE SET u.name = $name, u.createdAt = timestamp(), u.updatedAt = timestamp()
ON MATCH SET u.name = $name, u.updatedAt = timestamp()
RETURN u
```

```rust
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
            .set_property("name", PropertyInput::param("name"))
            .set_property("updatedAt", Expr::timestamp()),
    )
    .var_as_if(
        "created",
        BatchCondition::VarEmpty("existing".to_string()),
        g().add_n(
            "User",
            vec![
                ("userId", PropertyInput::param("userId")),
                ("name", PropertyInput::param("name")),
                ("createdAt", PropertyInput::from(Expr::timestamp())),
                ("updatedAt", PropertyInput::from(Expr::timestamp())),
            ],
        ),
    )
    .returning(["updated", "created"])
```

Both returns are `{"$id": N}` lists; the skipped one is `[]`. A concurrent
create of the same key fails with `409 unique_constraint_violation`
(`retryable: false`); re-run the upsert once and it takes the update branch.

Relationship merge. `add_e` always creates one edge per (source, target) pair,
and an empty target fails the whole batch:

```cypher
MATCH (u:User {userId: $userId}), (g:Group {groupId: $groupId})
MERGE (u)-[:MEMBER_OF]->(g)
```

```rust
write_batch()
    .var_as("u", g().n_with_label("User").where_(Predicate::eq_param("userId", "userId")))
    .var_as("grp", g().n_with_label("Group").where_(Predicate::eq_param("groupId", "groupId")))
    .var_as("linked", g().n(NodeRef::var("u")).out(Some("MEMBER_OF")))
    .var_as("missing", g().n(NodeRef::var("grp")).without("linked"))
    .var_as_if(
        "created",
        BatchCondition::VarNotEmpty("missing".to_string()),
        g().n(NodeRef::var("u"))
            .add_e("MEMBER_OF", NodeRef::var("missing"), Vec::<(&str, PropertyInput)>::new()),
    )
    .returning(["created"])
```

`missing` is empty when the group is absent or already linked; when the user is
absent, `add_e` has no source and creates nothing. Edges have no unique index,
so this check is not race-safe on its own.

### Variable-Length Paths

```cypher
MATCH (u:User {userId: $userId})-[:FOLLOWS*1..2]->(v:User)
RETURN DISTINCT v.userId, v.name
```

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId")),
    )
    .var_as(
        "results",
        g().n(NodeRef::var("user"))
            .repeat(
                RepeatConfig::new(sub().out(Some("FOLLOWS")).dedup())
                    .times(2)
                    .emit_after(),
            )
            .has_label("User")
            .dedup()
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("userId"),
                PropertyProjection::new("name"),
            ]),
    )
    .returning(["results"])
```

`emit_after` emits each hop's output (depths 1..2). `emit_before` emits each
hop's input and `emit_all` both, so `emit_all` repeats every intermediate level.
`*2..3` is `.out(Some("FOLLOWS"))` followed by a `times(2)` repeat.

### Filter Then Delete

```cypher
MATCH (u:User) WHERE u.status = $status DETACH DELETE u
```

Native as is. As a DSL route:

```rust
write_batch()
    .var_as(
        "targets",
        g().n_with_label("User")
            .where_(Predicate::eq_param("status", "status")),
    )
    .var_as("deleted", g().n(NodeRef::var("targets")).drop())
    .returning(["deleted"])
```

`deleted` is `[]`. Node `drop()` is always a detach delete.

### UNWIND With Per-Item Writes

```rust
// parameters: {"memberships": [{"userId": "u1", "groupId": "g1"}, ...]}
write_batch().for_each_param(
    "memberships",
    write_batch()
        .var_as("u", g().n_with_label("User").where_(Predicate::eq_param("userId", "userId")))
        .var_as("grp", g().n_with_label("Group").where_(Predicate::eq_param("groupId", "groupId")))
        .var_as("linked", g().n(NodeRef::var("u")).out(Some("MEMBER_OF")))
        .var_as("missing", g().n(NodeRef::var("grp")).without("linked"))
        .var_as_if(
            "created",
            BatchCondition::VarNotEmpty("missing".to_string()),
            g().n(NodeRef::var("u"))
                .add_e("MEMBER_OF", NodeRef::var("missing"), Vec::<(&str, PropertyInput)>::new()),
        ),
)
```

Each object's fields are bound as parameters for one iteration. A variable
returned from inside the body holds only the last iteration's value.

## Translation Checklist

- the statement was sent natively unless a listed construct or DSL-only need forced a translation
- anchors are narrow; directions and target labels are kept
- several variables per row use `bind` + `project_bindings`, sorted before the first `bind`
- `OPTIONAL MATCH` binds both sides; `CASE` is `Expr::case`
- missing-value ordering was handled
- `MERGE` uses a unique key and `var_as_if`; relationship merges check the edge first
- variable-length paths are bounded `repeat` with `emit_after`
- response types treat every row stream as a list
