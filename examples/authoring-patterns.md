# Authoring Patterns

Generic Helix Rust DSL examples for new query authoring.

## Read By Indexed Identifier

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
    .returning(["user"])
```

Why it is a good baseline:

- starts from a narrow anchor
- uses explicit projection
- returns a stable named result

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
- keeps the control flow visible

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
