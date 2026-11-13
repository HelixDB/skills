# Case 03: Unwind, Delete, And Null Semantics

## Prompt

Run or translate these Cypher tasks for Helix (Rust DSL where a DSL route is
needed):

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

- which statement runs natively (the delete) and which must be translated
  (`FOREACH` and `MERGE` are rejected)
- array expansion for per-item writes
- relationship MERGE without duplicate edges or failed batches
- null checks and filter-then-delete

## Gold Expectations

- the delete runs natively on `POST /v2/cypher`; as a DSL route it narrows with
  `Predicate::is_null("deletedAt")` (a missing property counts as null) and calls
  `drop()`, which always removes incident edges
- the membership task uses `for_each_param("memberships", body)`; each object's
  `userId` and `groupId` fields are parameters inside the body
- the body creates the edge only when both nodes exist and the edge does not:
  read `u`'s `MEMBER_OF` targets, keep the group `without` them, and guard
  `add_e` with `var_as_if(VarNotEmpty(..))`
- does not use a bare `add_e`: it duplicates edges on re-runs, and an empty
  group fails the whole batch

## Gold Translation Sketch

```text
// array-driven relationship merge
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

// filter then delete (or send the Cypher natively)
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

- [ ] Sends or offers the delete natively
- [ ] Uses `for_each_param(...)` for the `UNWIND` + `FOREACH` translation
- [ ] Checks for an existing edge before `add_e`
- [ ] Guards against a missing group so the batch cannot fail
- [ ] Uses `Predicate::is_null` for the null check and `drop()` after filtering
