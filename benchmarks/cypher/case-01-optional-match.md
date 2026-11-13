# Case 01: Optional Match

## Prompt

Run this Cypher query against Helix, or give the Helix Rust DSL query if it has
to be a DSL route:

```cypher
MATCH (u:User {userId: $userId})
OPTIONAL MATCH (u)-[:WORKS_AT]->(o:Org)
RETURN u, o
```

## Expected Skill

- `helix-query-from-cypher`

## Focus Areas

- the statement runs natively
- anchored lookup by indexed property
- optional traversal that keeps the user row without inventing an org
- per-row result with both variables

## Gold Expectations

- runs as is: `POST /v2/cypher` with
  `{"query": ..., "parameters": {"userId": ...}}` (or `helix cypher -e`)
- for the DSL route: anchor `User` by `userId`, `bind("u")`, then
  `.optional(sub().out(Some("WORKS_AT")).has_label("Org").bind("o"))`, then
  `project_bindings` over `u` and `o`
- rejects a bare `.optional(sub().out(..))`: an empty branch passes the user row
  through, reporting the user as the org
- a user without an org yields a row whose `o` fields are absent

## Gold Translation Sketch

```text
POST /v2/cypher
{"query": "MATCH (u:User {userId: $userId}) OPTIONAL MATCH (u)-[:WORKS_AT]->(o:Org) RETURN u, o",
 "parameters": {"userId": "<id>"}}

// DSL route
read_batch()
    .var_as(
        "rows",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId"))
            .bind("u")
            .optional(sub().out(Some("WORKS_AT")).has_label("Org").bind("o"))
            .project_bindings(vec![
                BindingProjection::binding("u", "$id", "u_id"),
                BindingProjection::binding("u", "name", "u_name"),
                BindingProjection::binding("o", "$id", "o_id"),
                BindingProjection::binding("o", "name", "o_name"),
            ]),
    )
    .returning(["rows"])
```

## Scoring Checklist

- [ ] Uses `helix-query-from-cypher`
- [ ] Offers native `POST /v2/cypher` for this supported statement
- [ ] Anchors by `userId`
- [ ] DSL route binds the user and the org and reads them with `project_bindings`
- [ ] Does not use a bare `.optional(sub().out(..))` as the org result
- [ ] Keeps the `Org` label with `has_label`
