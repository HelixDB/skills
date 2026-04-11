# Case 02: Merge And Timestamps

## Prompt

Translate this Cypher query into a Helix Rust DSL stored query:

```cypher
MERGE (u:User {userId: $userId})
ON CREATE SET u.name = $name, u.createdAt = timestamp(), u.updatedAt = timestamp()
ON MATCH SET u.name = $name, u.updatedAt = timestamp()
RETURN u
```

## Expected Skill

- `helix-query-from-cypher`

## Focus Areas

- upsert-style branching
- create versus update branches
- server-side timestamps
- explicit write route choice

## Gold Expectations

- use `write_batch()`
- load an `existing` binding first
- use `var_as_if` with `BatchCondition::VarEmpty` and `BatchCondition::VarNotEmpty`
- assign branch-specific fields in the create and update paths
- use the server-side timestamp helper rather than a client-supplied parameter for `createdAt` and `updatedAt`

## Gold Translation Sketch

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
        // update name and updatedAt using the server-side timestamp helper
        g().n(NodeRef::var("existing")),
    )
    .var_as_if(
        "created",
        BatchCondition::VarEmpty("existing".to_string()),
        // create node and set createdAt and updatedAt using the server-side timestamp helper
        g().add_n("User", vec![]),
    )
    .returning(["updated", "created"])
```

## Scoring Checklist

- [ ] Uses `write_batch()`
- [ ] Loads an existing binding first
- [ ] Uses `var_as_if` branching
- [ ] Separates create-path assignments from update-path assignments
- [ ] Uses server-side timestamps instead of client-supplied time params
