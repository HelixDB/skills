# Case 04: Case, Collect, And Multi-Hop

## Prompt

Translate these Cypher tasks into Helix Rust DSL stored queries:

```cypher
MATCH (u:User {userId: $userId})-[:FOLLOWS*1..2]->(v:User)
RETURN DISTINCT v
```

```cypher
MATCH (u:User {userId: $userId})-[:HAS_SCORE]->(s:Score)
WITH u, COLLECT(s) AS scores
RETURN reduce(best = null, score IN scores |
  CASE WHEN best IS NULL OR score.value > best.value THEN score ELSE best END
) AS bestScore
```

## Expected Skill

- `helix-query-from-cypher`

## Focus Areas

- bounded multi-hop traversal
- explicit emission behavior
- distinct handling
- best-item selection by property
- choose-style conditional logic

## Gold Expectations

- use `repeat(RepeatConfig::new(...).times(2).emit_after())` for the multi-hop traversal
- use `dedup()` for `DISTINCT`
- if only the best score is required, prefer `order_by(...).limit(1)` instead of forcing collection
- if true collection semantics are required, use the DSL's fold or collect support and `.choose(...)`-style branching rather than inventing Cypher expressions verbatim

## Gold Translation Sketch

```rust
// multi-hop
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
            .dedup(),
    )
    .returning(["results"])

// best score when only the best element is needed
read_batch()
    .var_as(
        "bestScore",
        g().n(NodeRef::var("user"))
            .out(Some("HAS_SCORE"))
            .order_by("value", Order::Desc)
            .limit(1),
    )
    .returning(["bestScore"])
```

## Scoring Checklist

- [ ] Uses bounded `repeat(...)` with `emit_after()` for the multi-hop traversal
- [ ] Uses `dedup()` for `DISTINCT`
- [ ] Does not claim `[:REL*1..2]` is unsupported
- [ ] Recognizes that best-element selection can often be expressed as `order_by(...).limit(1)`
- [ ] Uses `.choose(...)` only when branch logic is truly needed inside the query
