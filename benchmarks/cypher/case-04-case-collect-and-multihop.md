# Case 04: Case, Collect, And Multi-Hop

## Prompt

Translate these Cypher tasks into Helix Rust DSL queries:

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

- variable-length paths and `reduce` are rejected natively, so translate both
- bounded multi-hop traversal with explicit emission and target labels
- distinct handling
- best-item selection by property, including missing values

## Gold Expectations

- uses `repeat(RepeatConfig::new(sub().out(Some("FOLLOWS"))).times(2).emit_after())`
  (depths 1 and 2; a `dedup()` inside the body is optional), then
  `has_label("User")` and `dedup()`
- the best score anchors the user in the same batch, then
  `out(Some("HAS_SCORE")).has_label("Score").order_by("value", Order::Desc).limit(1)`
- Helix `Desc` puts scores missing `value` last; a native rewrite
  `ORDER BY s.value DESC LIMIT 1` puts nulls first unless it adds
  `WHERE s.value IS NOT NULL`
- no `choose` to emulate `CASE`

## Gold Translation Sketch

```text
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
                RepeatConfig::new(sub().out(Some("FOLLOWS")).dedup())
                    .times(2)
                    .emit_after(),
            )
            .has_label("User")
            .dedup()
            .project(vec![PropertyProjection::new("$id"), PropertyProjection::new("name")]),
    )
    .returning(["results"])

// best score
read_batch()
    .var_as(
        "user",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId")),
    )
    .var_as(
        "bestScore",
        g().n(NodeRef::var("user"))
            .out(Some("HAS_SCORE"))
            .has_label("Score")
            .order_by("value", Order::Desc)
            .limit(1)
            .project(vec![PropertyProjection::new("$id"), PropertyProjection::new("value")]),
    )
    .returning(["bestScore"])
```

`bestScore` is a list of at most one element (`[]` when the user has no scores).

## Scoring Checklist

- [ ] Uses bounded `repeat(...)` with `emit_after()` for the multi-hop traversal
- [ ] Keeps the `User` / `Score` target labels with `has_label`
- [ ] Uses `dedup()` for `DISTINCT`
- [ ] Defines `user` in the same batch before `NodeRef::var("user")`
- [ ] Expresses best-element selection as `order_by(...).limit(1)` and accounts for missing values
