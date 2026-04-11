# Cypher To Helix Rosetta

Use this document to translate Cypher queries into Helix Rust DSL queries.

## Mental Model Shift

Cypher is row-oriented and pattern-oriented.

Helix Rust DSL is batch-oriented and traversal-oriented.

That means a good translation usually looks like this:

1. choose one narrow anchor
2. bind it with `var_as`
3. traverse explicitly with `out`, `in_`, `both`, `out_e`, `in_e`, `both_e`, `optional`, or `repeat`
4. apply `where_` predicates deliberately
5. branch explicitly with `choose` or `var_as_if` when the Cypher query branches
6. shape the result explicitly with `project`, `value_map`, `count`, `limit`, `range`, `skip`, or `dedup`

## Translation Workflow

When translating a Cypher query:

1. identify the first practical anchor
2. identify edge directions, edge labels, and hop depth
3. extract property filters, null or existence checks, and parameter names
4. decide whether the route is read or write
5. identify optional branches, per-element writes, or conditional branches
6. map the return shape intentionally
7. handle complex Cypher features semantically rather than pretending every clause is a one-token rewrite

## Mapping Table

| Cypher | Helix Rust DSL | Notes |
| --- | --- | --- |
| `MATCH (u:User)` | `g().n_with_label("User")` | label anchor |
| `MATCH (u:User {userId: $userId})` | `g().n_with_label("User").where_(Predicate::eq_param("userId", "userId"))` | label plus indexed property filter |
| `OPTIONAL MATCH (u)-[:WORKS_AT]->(o)` | `.optional(sub().out(Some("WORKS_AT")))` | optional traversal without dropping the root path |
| `MATCH (u)-[:FOLLOWS]->(v)` | `g().n(NodeRef::var("user")).out(Some("FOLLOWS"))` | outgoing node traversal |
| `MATCH (u)<-[:FOLLOWS]-(v)` | `g().n(NodeRef::var("user")).in_(Some("FOLLOWS"))` | incoming node traversal |
| `MATCH (u)-[e:FOLLOWS]->(v)` | `g().n(NodeRef::var("user")).out_e(Some("FOLLOWS"))` | edge traversal |
| `MATCH (u)-[:REL*1..2]->(v)` | `.repeat(RepeatConfig::new(sub().out(Some("REL"))).times(2).emit_after())` | bounded multi-hop traversal |
| `WHERE u.status = $status` | `where_(Predicate::eq_param("status", "status"))` | exact match |
| `WHERE u.age >= $minAge` | `where_(Predicate::gte_param("age", "minAge"))` | numeric comparison |
| `WHERE u.status IN $statuses` | `where_(Predicate::is_in_param("status", "statuses"))` | set membership |
| `WHERE u.deletedAt IS NULL` | `where_(Predicate::is_null("deletedAt"))` | null check |
| `WHERE exists(u.email)` | `where_(Predicate::has_key("email"))` | property existence check |
| `RETURN u` | `project(...)` or `value_map(...)` | prefer explicit projection |
| `RETURN count(u)` | `.count()` | count the current stream |
| `RETURN DISTINCT u` | `.dedup()` | remove duplicates before returning |
| `ORDER BY u.updatedAt DESC` | `.order_by("updatedAt", Order::Desc)` | explicit ordering |
| `SKIP $offset LIMIT $limit` | `.skip(Expr::param("offset")).limit(Expr::param("limit"))` | pagination |
| `LIMIT $limit` | `.limit(Expr::param("limit"))` | limit current stream |
| `CASE WHEN ... THEN ... ELSE ... END` | `.choose(...)` | traversal-level conditional branching |
| `COLLECT(x)` plus best-item selection | `.order_by(...).limit(1)` or fold or collect support | use the simpler path when only the best item is needed |
| `UNWIND $items AS item FOREACH (...)` | `for_each_param("items", ...)` | per-element write expansion |
| `DETACH DELETE` | filter with `where_` or `has`, then `drop()` | delete after narrowing the target set |
| `MERGE (...) ON CREATE SET ... ON MATCH SET ...` | explicit read then `var_as_if` update/create flow | semantic upsert mapping |
| `timestamp()` | server-side timestamp helper | use database-generated time values |

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

In the create and update branches, use the server-side timestamp helper from your current Helix build for fields like `createdAt` and `updatedAt` when the Cypher query used `timestamp()` or branch-specific time assignments.

### OPTIONAL MATCH

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
        "optionalEmployer",
        g().n(NodeRef::var("user"))
            .optional(sub().out(Some("WORKS_AT"))),
    )
    .returning(["user", "optionalEmployer"])
```

Use `optional(sub(...))` when the traversal should not eliminate the root path just because the related node or edge is missing.

### Multi-Hop Traversal

Cypher:

```cypher
MATCH (u:User {userId: $userId})-[:FOLLOWS*1..2]->(v:User)
RETURN DISTINCT v
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
            .repeat(
                RepeatConfig::new(sub().out(Some("FOLLOWS")))
                    .times(2)
                    .emit_after(),
            )
            .dedup()
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("userId"),
                PropertyProjection::new("name"),
            ]),
    )
    .returning(["results"])
```

### Filter Then Delete

Cypher:

```cypher
MATCH (u:User)
WHERE u.status = $status
DETACH DELETE u
```

Helix Rust DSL:

```rust
write_batch()
    .var_as(
        "targets",
        g().n_with_label("User")
            .where_(Predicate::eq_param("status", "status")),
    )
    .var_as(
        "deleted",
        g().n(NodeRef::var("targets")).drop(),
    )
    .returning(["deleted"])
```

## Additional Supported Patterns

### `CASE WHEN`

Use `.choose(...)` when the Cypher query branches traversal behavior or result selection inside the query.

### `COLLECT(...)` Plus Best-Item Selection

If the Cypher query only needs the best element by a property after collection, the simplest Helix translation is usually:

1. order the stream explicitly
2. `limit(1)`

If the query truly needs to materialize an array first, use the fold or collect support available in your current Helix build.

### `UNWIND` Plus `FOREACH`

Use `for_each_param(...)` when a write route should iterate an array parameter and run graph work such as `add_e(...)` for each element.

### `IS NULL` And Property Existence

Use:

- `Predicate::is_null` for null-style checks
- `Predicate::has_key` when the question is property existence

### Server-Side Timestamps

Use the server-side timestamp helper from your current Helix build when translating Cypher `timestamp()` usage or branch-specific create and update timestamps.

## What Does Not Translate Directly

These need care instead of literal translation:

- `MERGE`
- path objects such as `p = (...)`
- `RETURN *`
- pattern comprehensions and collection-heavy Cypher expressions

`MERGE` is supported semantically, but it is still not a one-token rewrite. Translate it into explicit read-first branching.

Typical Helix replacements:

- `MERGE`: read first, then branch with `var_as_if`
- variable-length patterns: bounded `repeat(...)` plus `emit_after()` when you need per-hop emission
- `RETURN *`: explicit `project(...)` or `value_map(...)`

## Translation Checklist

Before finishing a Cypher translation:

- verify the first anchor is the narrowest practical starting set
- verify edge direction was translated correctly
- verify `WHERE` filters became explicit `Predicate` calls
- verify optional traversals use `optional(sub(...))` when required
- verify multi-hop traversal uses bounded `repeat(...)` with explicit emission behavior
- verify `RETURN` became an intentional projection or aggregation
- verify `ORDER BY`, `SKIP`, and `LIMIT` map to explicit result operators
- verify `CASE WHEN`, `UNWIND`, `FOREACH`, delete, and timestamp logic were mapped to Helix-native constructs when present
- verify `MERGE` was handled semantically, not as a string replacement

## See Also

- `docs/dsl-cheatsheet.md`
- `examples/authoring-patterns.md`
- `examples/search-patterns.md`
- `https://docs.helix-db.com/documentation/hql/traversals`
- `https://docs.helix-db.com/documentation/hql/conditionals`
- `https://docs.helix-db.com/documentation/hql/result_ops`
