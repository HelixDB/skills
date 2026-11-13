# v3 Authoring Patterns

Generic Rust SDK examples (`helix-db` crate; see `docs/source-canon.md` for the
verified release set). Each builder produces a direct `QueryRequest`; there is
no route registration or bundle generation.

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

Why it is a good baseline:

- starts from a narrow, label-scoped anchor that an equality index on `User.userId` can serve
- uses explicit projection
- returns a stable named result: `[]` when no user matches, a one-element array otherwise

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

Why it is a good baseline:

- makes read-versus-write intent obvious
- does not invent unsupported `MERGE` semantics
- keeps the control flow visible and atomic in one write batch

Back `userId` with `IndexSpec::node_unique_equality("User", "userId")`. Without
it, two concurrent requests can both see `existing` empty and create duplicates.
With it, the second create fails with `unique_constraint_violation` (409,
`retryable: false`); re-running the upsert once then takes the update branch.
Do not treat that 409 like `transaction_conflict` in a generic retry loop.

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

Why it is a good baseline:

- loads the starting node explicitly
- controls traversal breadth
- uses a lightweight returned shape
