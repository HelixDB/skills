# Helix Rust DSL Cheat Sheet

Quick authoring reference for Helix Rust DSL queries.

## Core Shape

Start with one of these roots:

```rust
read_batch()
write_batch()
```

Common structure:

```rust
read_batch()
    .var_as("result", g()...)
    .returning(["result"])
```

```rust
write_batch()
    .var_as("result", g()...)
    .returning(["result"])
```

## Read Versus Write

Use `read_batch()` for read-only routes.

Use `write_batch()` for any mutation, including:

- `add_n`
- `add_e`
- `set_property`
- `drop`
- `drop_edge_by_id`

## Common Anchors

Prefer the narrowest known starting set:

```rust
g().n(NodeRef::param("node_id"))
g().e(EdgeRef::param("edge_id"))
g().n_with_label("User")
```

Anchor order:

1. node ID or edge ID
2. unique property lookup
3. equality-indexed property lookup
4. scoped label scan
5. broad label scan

## Filtering

Use `where_` for property predicates.

```rust
g().n_with_label("User")
    .where_(Predicate::eq_param("userId", "userId"))
```

Useful predicates:

- `Predicate::eq`
- `Predicate::eq_param`
- `Predicate::gt`, `gte`, `lt`, `lte`
- `Predicate::is_in_param`
- `Predicate::is_null`
- `Predicate::and(vec![...])`
- `Predicate::or(vec![...])`

## Traversal

Node to node:

```rust
g().n(NodeRef::var("user")).out(Some("FOLLOWS"))
g().n(NodeRef::var("entity")).both(Some("RELATED_TO"))
```

Node to edge:

```rust
g().n(NodeRef::param("node_id")).out_e(Some("WORKED_AT"))
g().n(NodeRef::param("node_id")).both_e(Some("RELATED_TO"))
```

Incoming traversal:

```rust
g().n(NodeRef::param("node_id")).in_(Some("FOLLOWS"))
g().n(NodeRef::param("node_id")).in_e(Some("FOLLOWS"))
```

## Projection And Return Shape

Use `project(...)` when the route should return an intentional stable shape.

```rust
g().n_with_label("User").project(vec![
    PropertyProjection::new("$id"),
    PropertyProjection::new("userId"),
    PropertyProjection::new("name"),
])
```

Use `value_map(...)` when returning a loose property map is acceptable.

```rust
g().n_with_label("User").value_map(Some(vec!["$id", "name"]))
```

For vector search, add `$distance` only when needed:

```rust
let projection = vec![
    PropertyProjection::new("$id"),
    PropertyProjection::new("title"),
    PropertyProjection::renamed("$distance", "distance"),
];
```

## Ordering And Pagination

Common operators:

```rust
.order_by("createdAt", Order::Desc)
.order_by_multiple(vec![("updatedAt", Order::Desc), ("entityId", Order::Asc)])
.skip(Expr::param("offset"))
.limit(Expr::param("limit"))
.range(Expr::param("start"), Expr::param("end"))
```

## Mutations

Create a node:

```rust
g().add_n(
    "User",
    vec![
        ("userId", PropertyInput::param("userId")),
        ("name", PropertyInput::param("name")),
    ],
)
```

Create an edge:

```rust
g().n(NodeRef::var("user")).add_e(
    "FOLLOWS",
    NodeRef::var("target"),
    vec![("since", PropertyInput::param("since"))],
)
```

Update properties:

```rust
g().n(NodeRef::var("existing"))
    .set_property("name", PropertyInput::param("name"))
```

Delete:

```rust
g().n(NodeRef::var("target")).drop()
g().drop_edge_by_id(EdgeRef::var("target"))
```

## Conditional Write Flow

For create-or-update behavior, use explicit branching.

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

## Text Search

BM25 text search is property-scoped.

```rust
read_batch()
    .var_as(
        "results",
        g().text_search_nodes_with(
            "Document",
            "body",
            PropertyInput::param("query"),
            Expr::param("limit"),
            Some(PropertyInput::param("tenantId")),
        )
        .project(vec![
            PropertyProjection::new("$id"),
            PropertyProjection::new("title"),
        ]),
    )
    .returning(["results"])
```

## Vector Search

```rust
read_batch()
    .var_as(
        "results",
        g().vector_search_nodes_with(
            "Document",
            "embedding",
            PropertyInput::param("queryVector"),
            Expr::param("limit"),
            Some(PropertyInput::param("tenantId")),
        )
        .project(vec![
            PropertyProjection::new("$id"),
            PropertyProjection::new("title"),
            PropertyProjection::renamed("$distance", "distance"),
        ]),
    )
    .returning(["results"])
```

Guidance:

- keep the vector property out of the projection unless the caller truly needs it
- include `$distance` only when useful
- preserve tenant scope when the vector index is scoped

## Repeat

Repeat is often used with an explicit bounded depth.

```rust
g().n(NodeRef::var("seed"))
    .repeat(
        RepeatConfig::new(sub().both(Some("RELATED_TO")))
            .times(3)
            .emit_all(),
    )
```

## Authoring Heuristics

- inspect the user's local labels, edges, and properties before inventing new ones
- start from the narrowest indexed anchor you can identify
- filter early, traverse second
- keep projections intentional for service-facing routes
- preserve tenant scope for text and vector search
- use `dedup`, `limit`, `range`, and `count` because the route needs them

## See Also

- `docs/source-canon.md`
- `docs/dynamic-query-examples.md`
- `docs/optimization-checklist.md`
- `examples/authoring-patterns.md`
- `examples/search-patterns.md`
