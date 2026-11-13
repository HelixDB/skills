# Case 02: Merge And Timestamps

## Prompt

Translate this Cypher query into a Helix Rust DSL query:

```cypher
MERGE (u:User {userId: $userId})
ON CREATE SET u.name = $name, u.createdAt = timestamp(), u.updatedAt = timestamp()
ON MATCH SET u.name = $name, u.updatedAt = timestamp()
RETURN u
```

## Expected Skill

- `helix-query-from-cypher`

## Focus Areas

- recognizing that `MERGE` and `timestamp()` are outside the native profile
- upsert branching in one write batch
- a unique key so concurrent creates cannot duplicate
- server-side timestamps

## Gold Expectations

- notes that `/v2/cypher` rejects `MERGE` (`unsupported_feature`, `merge`), so
  this one is translated
- recommends a unique equality index on `User.userId`
  (`IndexSpec::node_unique_equality`) created once and waited on until active
- uses `write_batch()` with an `existing` read, then `var_as_if` on
  `BatchCondition::VarNotEmpty` (update) and `BatchCondition::VarEmpty` (create)
- assigns branch-specific fields, with `Expr::timestamp()` rather than
  client-supplied time parameters
- on `409 unique_constraint_violation` (`retryable: false`), re-runs the upsert
  once instead of retrying the same create

## Gold Translation Sketch

```text
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

## Scoring Checklist

- [ ] Uses `write_batch()`
- [ ] Loads an existing binding first
- [ ] Uses `var_as_if` branching
- [ ] Separates create-path assignments from update-path assignments
- [ ] Uses `Expr::timestamp()` instead of client-supplied time params
- [ ] Recommends a unique index on the merge key
