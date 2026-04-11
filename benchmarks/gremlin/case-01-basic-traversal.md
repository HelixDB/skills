# Case 01: Basic Traversal

## Prompt

Translate this Gremlin traversal into a Helix Rust DSL stored query:

```gremlin
g.V().hasLabel('User').has('userId', userId).out('FOLLOWS').has('status', status).order().by('createdAt', desc).limit(limit).valueMap('userId', 'name', 'status', 'createdAt')
```

## Expected Skill

- `helix-query-from-gremlin`

## Focus Areas

- narrowing the start step
- `hasLabel` and `has` translation
- outgoing traversal
- result shaping with ordering, limit, and `value_map`

## Gold Expectations

- anchor `User` by `userId`
- translate `.out('FOLLOWS')` to `.out(Some("FOLLOWS"))`
- translate `has('status', status)` to `where_(Predicate::eq_param(...))`
- translate ordering and limit explicitly
- use `value_map(...)` for the property-map output

## Gold Translation Sketch

```rust
read_batch()
    .var_as(
        "user",
        g().n_with_label("User")
            .where_(Predicate::eq_param("userId", "userId")),
    )
    .var_as(
        "results",
        g().n(NodeRef::var("user"))
            .out(Some("FOLLOWS"))
            .where_(Predicate::eq_param("status", "status"))
            .order_by("createdAt", Order::Desc)
            .limit(Expr::param("limit"))
            .value_map(Some(vec!["userId", "name", "status", "createdAt"])),
    )
    .returning(["results"])
```

## Scoring Checklist

- [ ] Uses `helix-query-from-gremlin`
- [ ] Narrows the start step instead of leaving a broad `g.V()` shape
- [ ] Preserves the outgoing edge direction
- [ ] Maps filters to explicit predicates
- [ ] Uses deliberate result shaping with ordering, limit, and `value_map`
