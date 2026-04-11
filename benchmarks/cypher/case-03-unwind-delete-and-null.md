# Case 03: Unwind, Delete, And Null Semantics

## Prompt

Translate these Cypher tasks into Helix Rust DSL stored queries:

```cypher
UNWIND $memberships AS membership
MATCH (u:User {userId: membership.userId})
MATCH (g:Group {groupId: membership.groupId})
FOREACH (_ IN [1] | MERGE (u)-[:MEMBER_OF]->(g))
```

```cypher
MATCH (u:User)
WHERE u.deletedAt IS NULL
DETACH DELETE u
```

## Expected Skill

- `helix-query-from-cypher`

## Focus Areas

- array expansion for per-item writes
- relationship creation per element
- null checks
- filter then delete

## Gold Expectations

- use `for_each_param(...)` for the array-expansion flow
- perform per-item node lookups and edge writes inside that iteration
- use `Predicate::is_null("deletedAt")` for the delete filter
- call `drop()` after narrowing the target set

## Gold Translation Sketch

```rust
// array-driven relationship creation
write_batch()
    .for_each_param("memberships", /* per-item lookup and add_e(...) work */)

// filter then delete
write_batch()
    .var_as(
        "targets",
        g().n_with_label("User")
            .where_(Predicate::is_null("deletedAt")),
    )
    .var_as("deleted", g().n(NodeRef::var("targets")).drop())
    .returning(["deleted"])
```

## Scoring Checklist

- [ ] Uses `for_each_param(...)` for the `UNWIND` translation
- [ ] Performs per-item graph work rather than trying to fake array expansion with a scalar traversal
- [ ] Uses `Predicate::is_null` for the null check
- [ ] Filters before deleting
- [ ] Uses `drop()` for the delete path
