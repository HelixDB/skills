# Cypher To Helix Rosetta

Use this document to translate Cypher queries into Helix Rust DSL queries.

## Mental Model Shift

Cypher is row-oriented and pattern-oriented.

Helix Rust DSL is batch-oriented and traversal-oriented.

That means a good translation usually looks like this:

1. choose one narrow anchor
2. bind it with `var_as`
3. traverse explicitly with `out`, `in_`, `both`, `out_e`, `in_e`, or `both_e`
4. apply `where_` predicates deliberately
5. shape the result explicitly with `project`, `value_map`, `count`, `limit`, `range`, or `dedup`

## Translation Workflow

When translating a Cypher query:

1. identify the first practical anchor
2. identify edge directions and edge labels
3. extract property filters and parameter names
4. decide whether the route is read or write
5. map the return shape intentionally
6. handle non-1:1 Cypher features explicitly rather than pretending they translate directly

## Mapping Table

| Cypher | Helix Rust DSL | Notes |
| --- | --- | --- |
| `MATCH (u:User)` | `g().n_with_label("User")` | label anchor |
| `MATCH (u:User {userId: $userId})` | `g().n_with_label("User").where_(Predicate::eq_param("userId", "userId"))` | label plus indexed property filter |
| `MATCH (u)-[:FOLLOWS]->(v)` | `g().n(NodeRef::var("user")).out(Some("FOLLOWS"))` | outgoing node traversal |
| `MATCH (u)<-[:FOLLOWS]-(v)` | `g().n(NodeRef::var("user")).in_(Some("FOLLOWS"))` | incoming node traversal |
| `MATCH (u)-[e:FOLLOWS]->(v)` | `g().n(NodeRef::var("user")).out_e(Some("FOLLOWS"))` | edge traversal |
| `WHERE u.status = $status` | `where_(Predicate::eq_param("status", "status"))` | exact match |
| `WHERE u.age >= $minAge` | `where_(Predicate::gte_param("age", "minAge"))` | numeric comparison |
| `WHERE u.status IN $statuses` | `where_(Predicate::is_in_param("status", "statuses"))` | set membership |
| `RETURN u` | `project(...)` or `value_map(...)` | prefer explicit projection |
| `RETURN count(u)` | `.count()` | count the current stream |
| `RETURN DISTINCT u` | `.dedup()` | remove duplicates before returning |
| `ORDER BY u.updatedAt DESC` | `.order_by("updatedAt", Order::Desc)` | explicit ordering |
| `SKIP $offset LIMIT $limit` | `.skip(Expr::param("offset")).limit(Expr::param("limit"))` | pagination |
| `LIMIT $limit` | `.limit(Expr::param("limit"))` | limit current stream |
| `MERGE (...)` | explicit read then `var_as_if` update/create flow | not a direct one-step translation |

## Canonical Examples

### Match And Traverse

Cypher:

```cypher
MATCH (u:User {userId: $userId})-[:FOLLOWS]->(v:User)
WHERE v.status = $status
RETURN v
ORDER BY v.createdAt DESC
LIMIT $limit
```

Helix Rust DSL:

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
            .where_(Predicate::eq_param("status", "status"))
            .order_by("createdAt", Order::Desc)
            .limit(Expr::param("limit"))
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("userId"),
                PropertyProjection::new("name"),
                PropertyProjection::new("status"),
                PropertyProjection::new("createdAt"),
            ]),
    )
    .returning(["results"])
```

### Incoming Count

Cypher:

```cypher
MATCH (:User {userId: $userId})<-[:FOLLOWS]-(f:User)
RETURN count(f) AS followerCount
```

Helix Rust DSL:

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
            .count(),
    )
    .returning(["followerCount"])
```

### DISTINCT And Pagination

Cypher:

```cypher
MATCH (u:User)-[:MEMBER_OF]->(g:Group)
RETURN DISTINCT g
ORDER BY g.name ASC
SKIP $offset
LIMIT $limit
```

Helix Rust DSL:

```rust
read_batch()
    .var_as(
        "groups",
        g().n_with_label("User")
            .out(Some("MEMBER_OF"))
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

### MERGE-Like Upsert

Cypher:

```cypher
MERGE (u:User {userId: $userId})
SET u.name = $name
RETURN u
```

Helix Rust DSL:

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
```

### OPTIONAL MATCH Caveat

Cypher:

```cypher
MATCH (u:User {userId: $userId})
OPTIONAL MATCH (u)-[:WORKS_AT]->(o:Org)
RETURN u, o
```

Helix Rust DSL usually becomes separate bindings:

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId"))
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("userId"),
                PropertyProjection::new("name"),
            ]),
    )
    .var_as(
        "employers",
        g().n(NodeRef::var("user"))
            .out(Some("WORKS_AT"))
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("orgId"),
                PropertyProjection::new("name"),
            ]),
    )
    .returning(["user", "employers"])
```

This is not the same as Cypher's row-preserving null extension. For complex `OPTIONAL MATCH` cases, expect to assemble the final response shape in the service layer or split the logic into multiple bindings.

## What Does Not Translate Directly

These need care instead of literal translation:

- `OPTIONAL MATCH`
- `MERGE`
- variable-length relationship patterns like `[:REL*1..3]`
- path objects such as `p = (...)`
- `RETURN *`
- pattern comprehensions and collection-heavy Cypher expressions

Typical Helix replacements:

- `OPTIONAL MATCH`: separate bindings and explicit response assembly
- `MERGE`: read first, then branch with `var_as_if`
- variable-length patterns: bounded `repeat(...)`
- `RETURN *`: explicit `project(...)` or `value_map(...)`

## Translation Checklist

Before finishing a Cypher translation:

- verify the first anchor is the narrowest practical starting set
- verify edge direction was translated correctly
- verify `WHERE` filters became explicit `Predicate` calls
- verify `RETURN` became an intentional projection or aggregation
- verify `ORDER BY`, `SKIP`, and `LIMIT` map to explicit result operators
- verify `MERGE` and `OPTIONAL MATCH` were handled as semantic translations, not string replacements

## See Also

- `docs/dsl-cheatsheet.md`
- `examples/authoring-patterns.md`
- `examples/search-patterns.md`
- `https://docs.helix-db.com/documentation/hql/traversals`
- `https://docs.helix-db.com/documentation/hql/conditionals`
- `https://docs.helix-db.com/documentation/hql/result_ops`
