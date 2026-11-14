# Case 02: Repeat And Range

## Prompt

Translate this Gremlin traversal into a Helix Rust DSL query:

```gremlin
g.V().hasLabel('Entity').has('entityId', seedId).repeat(__.both('RELATED_TO')).times(3).emit().dedup().range(start, end)
```

## Expected Skill

- `helix-query-from-gremlin`

## Focus Areas

- bounded repeat
- emit semantics
- deduplication
- range-based pagination

## Gold Expectations

- anchor `Entity` by `entityId`
- use bounded `repeat(...)`, not "unsupported"
- postfix `emit()` → `.emit_after()` (each iteration's output), not
  `.emit_all()`, which also emits the seed and repeats intermediate levels
- no `.without("seed")`: Gremlin emits the seed when a later hop reaches it
- use `dedup()` and `range(...)` explicitly

## Gold Translation Sketch

```text
read_batch()
    .var_as(
        "seed",
        g().n_with_label("Entity")
            .where_(Predicate::eq_param("entityId", "seedId")),
    )
    .var_as(
        "results",
        g().n(NodeRef::var("seed"))
            .repeat(
                RepeatConfig::new(sub().both(Some("RELATED_TO")))
                    .times(3)
                    .emit_after(),
            )
            .dedup()
            .range(Expr::param("start"), Expr::param("end")),
    )
    .returning(["results"])
```

## Scoring Checklist

- [ ] Uses bounded `repeat(...)`
- [ ] Preserves the two-way traversal direction
- [ ] Uses `emit_after()` for the postfix `emit()`
- [ ] Uses `dedup()`
- [ ] Uses `range(...)` for the windowing step
