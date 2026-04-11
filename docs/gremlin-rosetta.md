# Gremlin To Helix Rosetta

Use this document to translate Gremlin traversals into Helix Rust DSL queries.

## Mental Model Shift

Gremlin is an imperative step chain.

Helix Rust DSL is a batch-oriented query builder with explicit bindings and explicit result shaping.

A good translation usually looks like this:

1. pick the narrowest starting set
2. bind it with `var_as`
3. translate each traversal step explicitly
4. turn `has(...)` and similar filters into `where_(Predicate::...)`
5. shape the final output intentionally with `project`, `value_map`, `count`, `dedup`, `limit`, `range`, or `skip`

## Translation Workflow

When translating a Gremlin traversal:

1. identify the start step such as `g.V(id)`, `g.V()`, or `g.E()`
2. identify label filters and property filters
3. identify edge directions and edge labels
4. identify result-shaping steps like `dedup`, `count`, `limit`, `range`, or `order`
5. identify Gremlin features that are not a direct one-to-one mapping

## Mapping Table

| Gremlin | Helix Rust DSL | Notes |
| --- | --- | --- |
| `g.V(id)` | `g().n(NodeRef::param("node_id"))` | node-id anchor |
| `g.E()` | prefer edge-ID anchoring or node-anchored `out_e` / `in_e` / `both_e` | broad all-edge scans are usually a weak translation |
| `g.V().hasLabel("User")` | `g().n_with_label("User")` | label anchor |
| `.has("userId", userId)` | `.where_(Predicate::eq_param("userId", "userId"))` | exact-match property filter |
| `.has("status", within(statuses))` | `.where_(Predicate::is_in_param("status", "statuses"))` | membership filter |
| `.out("FOLLOWS")` | `.out(Some("FOLLOWS"))` | outgoing node traversal |
| `.in("FOLLOWS")` | `.in_(Some("FOLLOWS"))` | incoming node traversal |
| `.both("RELATED_TO")` | `.both(Some("RELATED_TO"))` | two-way traversal |
| `.outE("FOLLOWS")` | `.out_e(Some("FOLLOWS"))` | outgoing edge traversal |
| `.inE("FOLLOWS")` | `.in_e(Some("FOLLOWS"))` | incoming edge traversal |
| `.valueMap("name", "status")` | `.value_map(Some(vec!["name", "status"]))` | property-map result |
| `.values("name")` | project or value-map that field explicitly | Helix usually returns object-shaped route results |
| `.dedup()` | `.dedup()` | duplicate elimination |
| `.count()` | `.count()` | count current stream |
| `.limit(n)` | `.limit(Expr::param("limit"))` or `.limit(n)` | row limiting |
| `.range(start, end)` | `.range(Expr::param("start"), Expr::param("end"))` | inclusive start, exclusive end style paging |
| `.order().by("createdAt", desc)` | `.order_by("createdAt", Order::Desc)` | explicit ordering |
| `.emit()` | `.emit_all()` inside `RepeatConfig` | usually paired with bounded repeat |
| `.repeat(__.both("RELATED_TO")).times(3).emit()` | `.repeat(RepeatConfig::new(sub().both(Some("RELATED_TO"))).times(3).emit_all())` | bounded repeat traversal |

## Special Note On `g.E()`

Bare `g.E()` is often a weak translation target.

In Helix, prefer one of these instead:

1. edge ID anchor if you already know the edge
2. node-anchored edge traversal with `out_e`, `in_e`, or `both_e`
3. a local edge-root selection form if the target codebase already uses one explicitly

Do not default to broad all-edge scans if the original traversal can be re-anchored more narrowly.

## Canonical Examples

### Label Filter Plus Outgoing Traversal

Gremlin:

```gremlin
g.V().hasLabel('User').has('userId', userId).out('FOLLOWS').has('status', status).order().by('createdAt', desc).limit(limit).valueMap('userId', 'name', 'status', 'createdAt')
```

Helix Rust DSL:

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

### Incoming Count From A Known Node

Gremlin:

```gremlin
g.V(nodeId).in('FOLLOWS').count()
```

Helix Rust DSL:

```rust
read_batch()
    .var_as(
        "followerCount",
        g().n(NodeRef::param("node_id"))
            .in_(Some("FOLLOWS"))
            .count(),
    )
    .returning(["followerCount"])
```

### Dedup And Range

Gremlin:

```gremlin
g.V().hasLabel('User').out('MEMBER_OF').dedup().order().by('name', asc).range(start, end).valueMap('groupId', 'name')
```

Helix Rust DSL:

```rust
read_batch()
    .var_as(
        "groups",
        g().n_with_label("User")
            .out(Some("MEMBER_OF"))
            .dedup()
            .order_by("name", Order::Asc)
            .range(Expr::param("start"), Expr::param("end"))
            .value_map(Some(vec!["groupId", "name"])),
    )
    .returning(["groups"])
```

### Repeat With Emit

Gremlin:

```gremlin
g.V().hasLabel('Entity').has('entityId', seedId).repeat(__.both('RELATED_TO')).times(3).emit().dedup().limit(limit)
```

Helix Rust DSL:

```rust
read_batch()
    .var_as(
        "seed",
        g().n_with_label("Entity")
            .where_(Predicate::eq_param("entityId", "seedId")),
    )
    .var_as(
        "expanded",
        g().n(NodeRef::var("seed"))
            .repeat(
                RepeatConfig::new(sub().both(Some("RELATED_TO")))
                    .times(3)
                    .emit_all(),
            )
            .without("seed")
            .dedup()
            .limit(Expr::param("limit")),
    )
    .returning(["expanded"])
```

## What Does Not Translate Directly

These need care instead of literal translation:

- `path()`
- `select(...)`
- `project(...)` in Gremlin's map-building sense
- `coalesce(...)`
- `choose(...)`
- `union(...)`
- `group()` and `groupCount()`
- `sideEffect(...)`
- `sack(...)`
- `local(...)`
- arbitrary unbounded repeat logic

Typical Helix replacements:

- split complex traversals into multiple explicit bindings
- return multiple named bindings instead of a Gremlin path object
- assemble some response shapes in the service layer rather than forcing one query to emulate Gremlin exactly
- use bounded `repeat(...)` instead of open-ended traversal semantics

## Translation Checklist

Before finishing a Gremlin translation:

- verify the start step became the narrowest practical Helix anchor
- verify `hasLabel` and `has` became explicit label and predicate logic
- verify edge direction was preserved correctly
- verify result-shaping steps like `dedup`, `count`, `limit`, `range`, and ordering map to deliberate Helix operators
- verify `values` or `valueMap` became an intentional Helix result shape
- verify `repeat` was translated with an explicit bound
- verify path-building or side-effect-heavy Gremlin steps were translated semantically, not literally

## See Also

- `docs/dsl-cheatsheet.md`
- `examples/authoring-patterns.md`
- `examples/search-patterns.md`
- `https://docs.helix-db.com/documentation/hql/traversals`
- `https://docs.helix-db.com/documentation/hql/conditionals`
- `https://docs.helix-db.com/documentation/hql/result_ops`
