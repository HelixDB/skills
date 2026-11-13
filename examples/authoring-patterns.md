# v3 Authoring Patterns

Generic Rust SDK (`helix-db`; release set in `docs/source-canon.md`) examples.
Each builder produces a direct `QueryRequest`; no route registration or bundles.

## Read By Indexed Identifier

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label_where(
            "User",
            SourcePredicate::eq("userId", "known-id"),
        )
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("userId"),
                PropertyProjection::new("name"),
            ]),
    )
    .returning(["user"])
```

- narrow, label-scoped anchor an equality index on `User.userId` can serve
- explicit projection
- stable named result: `[]` when no user matches, else a one-element array

## Create Or Update With Explicit Branching

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

- explicit read-versus-write intent, no invented `MERGE` semantics
- visible control flow, atomic in one write batch

Back `userId` with `IndexSpec::node_unique_equality("User", "userId")`, or two
concurrent requests can both see `existing` empty and create duplicates. With
it, the second create fails with `unique_constraint_violation` (409,
`retryable: false`): re-run the upsert once (it takes the update branch); do not
retry it like `transaction_conflict`.

## Traverse From One Known Node

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId")),
    )
    .var_as(
        "followers",
        g().n(NodeRef::var("user"))
            .in_(Some("FOLLOWS"))
            .dedup()
            .limit(Expr::param("limit"))
            .value_map(Some(vec!["$id", "userId", "name"])),
    )
    .returning(["followers"])
```

- explicit starting node
- bounded traversal breadth
- lightweight returned shape
