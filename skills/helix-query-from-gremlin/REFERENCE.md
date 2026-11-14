# Gremlin To Helix DSL Worked Translations

Rust DSL (`use helix_db::dsl::prelude::*;`) on helix-db `main`. Step mapping and
semantics are in `SKILL.md`.

Gremlin is an imperative chain of traversers. The DSL is a batch of named
traversals (`var_as`) over streams of rows; a row has a current element and
optional row bindings (`bind`).

## Label Filter Plus Outgoing Traversal

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

## Incoming Count From A Known Node

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

## Dedup And Range

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

## Repeat With Postfix Emit

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
            .limit(Expr::param("limit"))
            .project(vec![
                PropertyProjection::new("$id"),
                PropertyProjection::new("entityId"),
            ]),
    )
    .returning(["expanded"])
```

The seed appears when a later hop reaches it again, as in Gremlin. Without the
`project`, `expanded` is a list of `{"$id": N}`.

## Per-Traverser Labels

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

## Group Count

```gremlin
g.V().hasLabel('User').groupCount().by('status')
```

```rust
read_batch()
    .var_as("byStatus", g().n_with_label("User").group_count("status"))
    .returning(["byStatus"])
// {"byStatus": [{"status": "active", "count": 12}, ...]}
```
