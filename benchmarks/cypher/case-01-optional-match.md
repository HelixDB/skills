# Case 01: Optional Match

## Prompt

Translate this Cypher query into a Helix Rust DSL stored query:

```cypher
MATCH (u:User {userId: $userId})
OPTIONAL MATCH (u)-[:WORKS_AT]->(o:Org)
RETURN u, o
```

## Expected Skill

- `helix-query-from-cypher`

## Focus Areas

- anchored lookup by indexed property
- optional traversal
- preserving the root path when the related node is missing
- returning a deliberate two-binding result shape

## Gold Expectations

- anchor `User` by `userId`
- use `.optional(sub().out(Some("WORKS_AT")))`
- do not rewrite this as a mandatory traversal
- return separate bindings for the user and the optional related result

## Gold Translation Sketch

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId")),
    )
    .var_as(
        "optionalEmployer",
        g().n(NodeRef::var("user"))
            .optional(sub().out(Some("WORKS_AT"))),
    )
    .returning(["user", "optionalEmployer"])
```

## Scoring Checklist

- [ ] Uses `helix-query-from-cypher`
- [ ] Anchors by `userId`
- [ ] Uses `.optional(sub(...))`
- [ ] Does not drop the root path by converting to a mandatory traversal
- [ ] Returns user and optional related result explicitly
