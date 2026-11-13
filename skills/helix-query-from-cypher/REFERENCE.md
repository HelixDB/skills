# Cypher To Helix DSL Reference

Rust DSL (`use helix_db::dsl::prelude::*;`) on helix-db `main`. Rules and the
list of constructs that need translation are in `SKILL.md`.

Cypher is row-oriented (each row carries several variables). The DSL is a
stream of current elements plus optional row bindings (`bind`) read by
`project_bindings`. A translation anchors one narrow set (`var_as`), traverses
explicitly with `has_label` on targets, binds only when the result needs more
than one variable, filters with `where_`, and shapes output with `project`,
`project_bindings`, `count`, aggregation and `limit`.

## Mapping Table

| Cypher | Helix Rust DSL | Notes |
| --- | --- | --- |
| `MATCH (u:User)` | `g().n_with_label("User")` | label scan |
| `MATCH (u:User {userId: $userId})` | `g().n_with_label("User").where_(Predicate::eq_param("userId", "userId"))` | index push-down when indexed |
| `(u)-[:FOLLOWS]->(v:User)` | `.out(Some("FOLLOWS")).has_label("User")` | `out` does not filter by node label |
| `(u)<-[:FOLLOWS]-(v)` / `(u)-[:R]-(v)` | `.in_(Some("FOLLOWS"))` / `.both(Some("R"))` | |
| `(u)-[e:FOLLOWS]->()` | `.out_e(Some("FOLLOWS"))` | edge stream; `out_n()`/`in_n()`/`other_n()` back to nodes |
| `WHERE u.status = $status` | `.where_(Predicate::eq_param("status", "status"))` | |
| `>` `>=` `<` `<=` | `gt_param` / `gte_param` / `lt_param` / `lte_param` | e.g. `Predicate::gte_param("age", "minAge")` |
| `IN $statuses` | `Predicate::is_in_param("status", "statuses")` | |
| `IS NULL` | `Predicate::is_null("deletedAt")` | a missing property is null |
| `IS NOT NULL` / `exists(u.email)` | `is_not_null("email")` / `Predicate::has_key("email")` | |
| `STARTS WITH` / `ENDS WITH` / `CONTAINS` | `starts_with` / `ends_with` / `contains` | |
| `AND` / `OR` / `NOT` | `Predicate::and(vec![..])` / `or` / `not` | |
| node ID | integer parameter | |
| `RETURN v.a, v.b` | `.project(vec![PropertyProjection::new("a"), PropertyProjection::new("b")])` | a bare stream returns only `{"$id": N}` |
| `RETURN DISTINCT v` | `.dedup()` | several variables: `project_distinct_bindings` |
| `ORDER BY v.x DESC` | `.order_by("x", Order::Desc)` | missing values first for `Asc`, last for `Desc` |
| `SKIP $o LIMIT $l` | `.skip(Expr::param("o")).limit(Expr::param("l"))` | |
| `MATCH (u)-[:WROTE]->(p:Post) RETURN u.name, p.title` | `.bind("u").out(Some("WROTE")).has_label("Post").bind("p").project_bindings(..)` | [Several variables](#several-variables-per-row) |
| `OPTIONAL MATCH (u)-[:WORKS_AT]->(o:Org)` | `.bind("u").optional(sub().out(Some("WORKS_AT")).has_label("Org").bind("o")).project_bindings(..)` | [OPTIONAL MATCH](#optional-match) |
| `CASE WHEN .. THEN .. ELSE .. END` | `Projection::expr("alias", Expr::case(vec![(pred, expr), ..], Some(else_expr)))` | a value, not `choose` |
| `count(v)` | `.count()` | scalar |
| `RETURN v.k, count(*)` | `.group_count("k")` | `[{"k": .., "count": n}]` |
| `RETURN v.k, collect(v)` | `.group("k")` | `[{"k": .., "count": n, "ids": [..]}]` |
| `sum(v.x)` / `avg` / `min` / `max` over the stream | `.aggregate_by(AggregateFunction::Sum, "x")` (`Mean`, `Min`, `Max`, `Count`) | `[{"x_Sum": f64}]`; `0.0` on empty input |
| `collect(s)` then best by property | `.order_by("value", Order::Desc).limit(1)` | list of at most one |
| `-[:R*1..2]->` | `.repeat(RepeatConfig::new(sub().out(Some("R")).dedup()).times(2).emit_after())` | `*m..n` = `m - 1` plain hops + `times(n - m + 1)` |
| `shortestPath((a)-[:KNOWS*..6]-(b))` | `g().shortest_path_with(NodeRef::var("a"), NodeRef::var("b"), Some("KNOWS"), ShortestPathDirection::Both, 6)` | [shortestPath](#shortestpath) |
| `UNWIND $items AS i` + per-item writes | `write_batch().for_each_param("items", body)` | [UNWIND](#unwind-with-per-item-writes) |
| `DETACH DELETE n` | narrow, then `.drop()` | node `drop()` always removes incident edges |
| `MERGE (u:L {k: $k}) ...` | unique index + read + `var_as_if` | [MERGE](#merge) |
| `MERGE (u)-[:R]->(g)` | read adjacency, `without`, guarded `add_e` | [MERGE](#merge) |
| `timestamp()` | `Expr::timestamp()` | server epoch millis; `Expr::datetime()` for a typed DateTime |

## Match And Traverse

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

Rows without `createdAt` sort last here, first in Cypher.

## Incoming Count

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

## DISTINCT And Pagination

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

Groups without `name` sort first here, last in Cypher.

## Several Variables Per Row

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

After `bind`, `where_`, `has_label`, `out`/`in_`, `optional`, `union`,
`coalesce`, `dedup`, `limit`, `count`, `exists` and `project_bindings` are
allowed. When the sort key belongs to a later variable, keep the statement
native.

## OPTIONAL MATCH

```cypher
MATCH (u:User {userId: $userId})
OPTIONAL MATCH (u)-[:WORKS_AT]->(o:Org)
RETURN u, o
```

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

One row per org, like Cypher; a user with no org yields one row without the
`o_*` keys. A bare `.optional(sub().out(..))` would report the user as the org.

## CASE

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

Use `choose(pred, then, else)` only to branch the traversal itself;
`Some(sub())` as the else passes rows through.

## Aggregation

```cypher
MATCH (u:User) RETURN u.status AS status, count(*) AS users
```

```rust
read_batch()
    .var_as("byStatus", g().n_with_label("User").group_count("status"))
    .returning(["byStatus"])
// {"byStatus": [{"status": "active", "count": 12}, ...]}
```

`aggregate_by(AggregateFunction::Sum, "amount")` over the whole stream returns
`[{"amount_Sum": 12.0}]`.

## MERGE

Node upsert. Create the unique key once and wait until
`get_index_operation(operation_id)` reports `status: "succeeded"`:

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

Both returns are `{"$id": N}` lists; the skipped one is `[]`.

Relationship merge:

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

`missing` is empty when the group is absent or already linked; an absent user
gives `add_e` no source, so nothing is created.

## Variable-Length Paths

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

- `emit_after` emits each hop's output (depths 1..2); `emit_before` emits each
  hop's input; `emit_all` both, repeating every intermediate level.
- `*2..3` = `.out(Some("FOLLOWS"))` then a `times(2)` repeat.
- Always bound with `times` (`max_depth` defaults to 100). `dedup()` in the body
  keeps frontiers small; a final `dedup()` gives `DISTINCT`.

## shortestPath

```rust
g().shortest_path_with(NodeRef::var("a"), NodeRef::var("b"), Some("KNOWS"), ShortestPathDirection::Both, 6)
```

Returns one unweighted shortest path as node IDs (`[0, 1, 2]`), or `[]` when
none exists within `max_depth`. `shortest_path(source, target, max_depth)`
follows any outgoing edge.

## Filter Then Delete

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

`deleted` is `[]`.

## UNWIND With Per-Item Writes

`UNWIND` alone runs natively. `for_each_param` items must be objects; each
object's fields are bound as parameters for one iteration. A variable returned
from inside the body holds only the last iteration.

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
