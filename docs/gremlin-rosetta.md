# Gremlin To Helix Rosetta

Authoring source for `helix-query-from-gremlin`. Contracts are recorded in
`docs/source-canon.md`; check snippets against the Rust DSL on helix-db `main`
(`use helix_db::dsl::prelude::*;`). Helix has no Gremlin endpoint, so every
traversal is translated. Helix does run Cypher natively (`POST /v2/cypher`); a
Gremlin query that reads naturally as Cypher can be sent that way instead.

## Mental Model

Gremlin is an imperative step chain of traversers. The Helix DSL is a batch of
named traversals (`var_as`) over streams of rows; a row has a current element
and optional row bindings (`bind`). A translation usually:

1. picks the narrowest starting set and binds it with `var_as`
2. translates each step explicitly, keeping `hasLabel` on targets
3. turns `has(...)` into `where_(Predicate::...)`
4. keeps per-traverser labels (`as`/`select`) as row bindings
5. shapes the output with `project`, `value_map`, `project_bindings`, `count`, `limit`

## Mapping Table

| Gremlin | Helix Rust DSL | Notes |
| --- | --- | --- |
| `g.V(id)` | `g().n(NodeRef::param("nodeId"))` | integer ID parameter |
| `g.E(id)` | `g().e(EdgeRef::param("edgeId"))` | prefer node-anchored `out_e`/`in_e`/`both_e` over a bare `g.E()` |
| `g.V().hasLabel('User')` | `g().n_with_label("User")` | |
| `.hasLabel('X')` after a hop | `.has_label("X")` | `out`/`in_`/`both` do not filter by label |
| `.has('userId', userId)` | `.where_(Predicate::eq_param("userId", "userId"))` | |
| `.has('status', within(statuses))` | `.where_(Predicate::is_in_param("status", "statuses"))` | |
| `.has('age', gte(a))` | `.where_(Predicate::gte_param("age", "a"))` | |
| `.out('R')` / `.in('R')` / `.both('R')` | `.out(Some("R"))` / `.in_(Some("R"))` / `.both(Some("R"))` | |
| `.outE('R')` / `.inE('R')` / `.bothE('R')` | `.out_e(Some("R"))` / `.in_e(Some("R"))` / `.both_e(Some("R"))` | |
| `.outV()` / `.inV()` / `.otherV()` | `.out_n()` / `.in_n()` / `.other_n()` | from an edge stream |
| `.valueMap('name', 'status')` | `.value_map(Some(vec!["name", "status"]))` | |
| `.values('name')` | `.values(vec!["name"])` | |
| `.project('a').by('x')` | `.project(vec![Projection::property("x", "a")])` | |
| `.id()` / `.label()` | `.id()` / `.label()` | |
| `.dedup()` / `.count()` | `.dedup()` / `.count()` | |
| `.limit(n)` / `.skip(n)` / `.range(a, b)` | `.limit(..)` / `.skip(..)` / `.range(..)` | `range` is start-inclusive, end-exclusive |
| `.order().by('createdAt', desc)` | `.order_by("createdAt", Order::Desc)` | rows missing the property sort first for `Asc`, last for `Desc` |
| `.repeat(t).times(n)` | `.repeat(RepeatConfig::new(sub()..).times(n))` | last level only |
| `.repeat(t).times(n).emit()` | `.repeat(RepeatConfig::new(sub()..).times(n).emit_after())` | postfix emit: each iteration's output |
| `.emit().repeat(t).times(n)` | `.repeat(RepeatConfig::new(sub()..).times(n + 1).emit_before())` | prefix emit: seed + levels 1..n |
| `.repeat(t).emit(has(..))` | `.emit_if(predicate)` on the config | |
| `.repeat(t).until(p)` | `.until(p)` on the config | stops the whole loop when any new row matches |
| `.as('a') ... .select('a', 'b')` | `.bind("a") ... .bind("b").project_bindings(..)` | per traverser |
| `.aggregate('x') ... .where(without('x'))` | `.as_("x") ... .without("x")` | stream-level variable |
| `.select('x')` of a stored stream | `.select("x")` | replaces the stream with the whole stored stream |
| `.path()` / `.simplePath()` | `.path()` / `.simple_path()` | |
| `.union(a, b)` | `.union(vec![a, b])` | sub-traversals from `sub()` |
| `.coalesce(a, b)` | `.coalesce(vec![a, b])` | first non-empty branch per row |
| `.optional(t)` | `.optional(t)` | empty branch passes the input row through |
| `.choose(p, a, b)` | `.choose(p, a, Some(b))` | |
| `.choose(p, a)` | `.choose(p, a, Some(sub()))` | Helix drops non-matching rows unless the else branch is `sub()` |
| `.groupCount().by('k')` | `.group_count("k")` | `[{"k": v, "count": n}]` |
| `.group().by('k')` | `.group("k")` | `[{"k": v, "count": n, "ids": [..]}]` |
| `.values('x').sum()` / `.mean()` / `.min()` / `.max()` | `.aggregate_by(AggregateFunction::Sum, "x")` (`Mean`, `Min`, `Max`) | `[{"x_Sum": f64}]`; `0.0` on empty input |
| `.fold()` / `.unfold()` | `.fold()` / `.unfold()` | |
| `.withSack(0) ... .sack(sum).by('w') ... .sack()` | `.with_sack(PropertyValue::from(0)) ... .sack_add("w") ... .sack_get()` | top-level only; `sack_set("w")` assigns |
| shortest path | `g().shortest_path_with(src, dst, Some("R"), ShortestPathDirection::Both, max_depth)` | node IDs of one unweighted path, `[]` if none |
| `addV` / `addE('R').to(v)` / `.property(k, v)` / `.drop()` | `add_n` / `add_e("R", v, props)` / `set_property` / `drop` | `add_e` always creates |

Output contracts: every row-stream return is `[]` when empty; only `count`,
`exists` and index operations are scalars; unprojected elements are
`{"$id": N}`.

## Semantics That Differ

- **Emit position.** `emit_after` = Gremlin postfix `emit()`. `emit_before`
  emits each iteration's input, so it needs `times(n + 1)` to match prefix
  `emit()` with `times(n)`. `emit_all` emits both sides of every iteration and
  repeats intermediate levels.
- **`until`.** Helix evaluates the predicate on the whole new frontier and stops
  the loop once any row matches; non-matching rows at that depth are returned
  too. Gremlin stops each traverser on its own. Use bounded `times(n)` with
  `emit_if(..)` and `dedup()` when each branch should stop at a match.
- **`choose` without a false branch** drops rows in Helix and passes them
  through in Gremlin.
- **`select`** on an `as_`/`store` variable is stream-level; per-traverser
  `select` is `bind` + `project_bindings`.
- **`group`/`groupCount`** return a list of objects, not one map.
- **`bind` restrictions.** After `bind`, `order_by`, `choose`, `repeat`,
  `project`, `value_map`, `values`, `id` and `label` are rejected; `bind` and
  `project_bindings` are rejected in a `write_batch`.

## Canonical Examples

### Label Filter Plus Outgoing Traversal

```gremlin
g.V().hasLabel('User').has('userId', userId).out('FOLLOWS').hasLabel('User').has('status', status).order().by('createdAt', desc).limit(limit).valueMap('userId', 'name', 'status', 'createdAt')
```

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
            .has_label("User")
            .where_(Predicate::eq_param("status", "status"))
            .order_by("createdAt", Order::Desc)
            .limit(Expr::param("limit"))
            .value_map(Some(vec!["userId", "name", "status", "createdAt"])),
    )
    .returning(["results"])
```

### Incoming Count From A Known Node

```gremlin
g.V(nodeId).in('FOLLOWS').count()
```

```rust
read_batch()
    .var_as(
        "followerCount",
        g().n(NodeRef::param("nodeId"))
            .in_(Some("FOLLOWS"))
            .count(),
    )
    .returning(["followerCount"])
```

### Dedup And Range

```gremlin
g.V().hasLabel('User').out('MEMBER_OF').dedup().order().by('name', asc).range(start, end).valueMap('groupId', 'name')
```

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

### Repeat With Postfix Emit

```gremlin
g.V().hasLabel('Entity').has('entityId', seedId).repeat(__.both('RELATED_TO')).times(3).emit().dedup().limit(limit)
```

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
                    .emit_after(),
            )
            .dedup()
            .limit(Expr::param("limit")),
    )
    .returning(["expanded"])
```

The seed appears in the output when a later hop reaches it again, as in
Gremlin. `expanded` is a list of `{"$id": N}`; add a `project` for properties.

### Per-Traverser Labels

```gremlin
g.V(userId).as('u').out('WROTE').hasLabel('Post').as('p').select('u', 'p').by('name').by('title')
```

```rust
read_batch()
    .var_as(
        "rows",
        g().n(NodeRef::param("userId"))
            .bind("u")
            .out(Some("WROTE"))
            .has_label("Post")
            .bind("p")
            .project_bindings(vec![
                BindingProjection::binding("u", "name", "u"),
                BindingProjection::binding("p", "title", "p"),
            ]),
    )
    .returning(["rows"])
```

### Group Count

```gremlin
g.V().hasLabel('User').groupCount().by('status')
```

```rust
read_batch()
    .var_as("byStatus", g().n_with_label("User").group_count("status"))
    .returning(["byStatus"])
// {"byStatus": [{"status": "active", "count": 12}, ...]}
```

## No Direct Step

`sideEffect`, `local`, `match`, lambdas and `inject` of literal values have no
DSL step. Split the work into several batch variables, or assemble the result in
the application.

## Translation Checklist

- the start step is the narrowest practical anchor; directions and `hasLabel` targets are kept
- `has` filters became `where_` predicates with parameters
- `repeat` is bounded and its emit mode matches Gremlin's emit position
- per-traverser labels use `bind` + `project_bindings`
- `choose` without a false branch got `Some(sub())`
- response types treat every row stream as a list (`[]` when empty)
