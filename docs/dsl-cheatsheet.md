# Helix Rust DSL Cheat Sheet

Quick authoring reference for Helix Rust DSL queries (`helix-db` crate,
`use helix_db::dsl::prelude::*;`). Contracts and the verified release set live in
`docs/source-canon.md`.

## Core Shape

Start with one of these roots:

```text
read_batch()
write_batch()
```

Common structure:

```text
read_batch()
    .var_as("result", g()...)
    .returning(["result"])
```

```text
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
- `create_index_if_not_exists`, `drop_index`, `retry_index_operation`, `abort_index_operation`

## Common Anchors

Prefer the narrowest known starting set:

```text
g().n(NodeRef::param("node_id"))       // node_id is an integer (i64) parameter
g().e(EdgeRef::param("edge_id"))
g().n_with_label_where("User", SourcePredicate::eq("userId", Expr::param("userId")))
g().n_with_label("User")
```

`n_where(pred)` has no label: it scans every node and cannot use label-scoped
indexes. `SourcePredicate` is an alias of `Predicate`.

Anchor order:

1. node ID or edge ID
2. unique property lookup
3. equality-indexed property lookup
4. scoped label scan
5. broad label scan

## Filtering

Use `where_` for property predicates.

```text
g().n_with_label("User")
    .where_(Predicate::eq_param("userId", "userId"))
```

Useful predicates:

- `Predicate::eq`
- `Predicate::eq_param`
- `Predicate::gt`, `gte`, `lt`, `lte`
- `Predicate::is_in_param`
- `Predicate::is_null`
- `Predicate::has_key`
- `Predicate::and(vec![...])`
- `Predicate::or(vec![...])`

Use `Predicate::is_null` for null-style checks.

Use `Predicate::has_key` when you specifically need property-existence semantics.

## Traversal

Node to node:

```text
g().n(NodeRef::var("user")).out(Some("FOLLOWS"))
g().n(NodeRef::var("entity")).both(Some("RELATED_TO"))
```

Node to edge:

```text
g().n(NodeRef::param("node_id")).out_e(Some("WORKED_AT"))
g().n(NodeRef::param("node_id")).both_e(Some("RELATED_TO"))
```

Incoming traversal:

```text
g().n(NodeRef::param("node_id")).in_(Some("FOLLOWS"))
g().n(NodeRef::param("node_id")).in_e(Some("FOLLOWS"))
```

`out`, `in_` and `both` do not filter the target's label. Keep a Cypher target
label with `.has_label("Company")` after the hop.

Optional traversal (Cypher `OPTIONAL MATCH`):

```text
g().n_with_label("User")
    .bind("user")
    .optional(sub().out(Some("WORKS_AT")).has_label("Company").bind("employer"))
    .project_bindings(vec![
        BindingProjection::binding("user", "name", "name"),
        BindingProjection::binding("employer", "name", "employer"),
    ])
```

When the branch is empty, `optional` emits the input row unchanged, so the
current element is still the user. Reading "employer" fields from the current
element would return the user's own data; read them through the `employer`
binding instead. A binding that was never set leaves its key out of the row.
After `bind`, `order_by`, `choose`, `repeat`, `project`, `value_map` and `values`
are rejected.

Traversal branching:

Use `.choose(...)` to pick a traversal per row. Without an else branch it drops
rows that fail the condition. A Cypher `CASE WHEN` is a value, not a traversal:
use `Expr::case(vec![(predicate, expr), ...], Some(else_expr))` inside
`Projection::expr(alias, ...)`.

Shortest path (unweighted BFS, returns node IDs or `[]`):

```text
g().shortest_path_with(NodeRef::param("from"), NodeRef::param("to"), Some("ROUTES_TO"), ShortestPathDirection::Out, 6)
```

## Projection And Return Shape

Use `project(...)` when the route should return an intentional stable shape.

```text
g().n_with_label("User").project(vec![
    PropertyProjection::new("$id"),
    PropertyProjection::new("userId"),
    PropertyProjection::new("name"),
])
```

Use `value_map(...)` when returning a loose property map is acceptable.

```text
g().n_with_label("User").value_map(Some(vec!["$id", "name"]))
```

Return shapes:

| Return | Populated | Empty or skipped `var_as_if` |
| --- | --- | --- |
| Any row stream, including single lookups, folds and mutations | array | `[]` |
| `count()` / `exists()` | integer / bool | `0` / `false` |
| Index DDL or lifecycle | receipt or status object | — |

An unprojected node or edge returns `{"$id": N}`. An empty returns list
produces `{}`. Decode single lookups as `Vec<T>` and take the first element;
there is no `null` (Docker v0.0.13+).

For vector search, add `$distance` only when needed:

```text
let projection = vec![
    PropertyProjection::new("$id"),
    PropertyProjection::new("title"),
    PropertyProjection::renamed("$distance", "distance"),
];
```

## Ordering And Pagination

Common operators:

```text
.order_by("createdAt", Order::Desc)
.order_by_multiple(vec![("updatedAt", Order::Desc), ("entityId", Order::Asc)])
.skip(Expr::param("offset"))
.limit(Expr::param("limit"))
.range(Expr::param("start"), Expr::param("end"))
```

Rows missing the sort property sort first for `Asc` and last for `Desc`, the
opposite of Cypher and SQL. Add `.where_(Predicate::is_not_null("createdAt"))`
before sorting when the placement matters. Edge streams have `order_by` but not
`order_by_multiple`.

When you only need the best element by a property, prefer ordering plus `limit(1)`.

```text
.order_by("score", Order::Desc)
.limit(1)
```

There is no `first()`; use `.limit(1)`. `.fold()` collects a stream into one
folded value and `.unfold()` expands it; both execute (as do `path`,
`simple_path` and the `sack_*` steps).

## Mutations

Create a node:

```text
g().add_n(
    "User",
    vec![
        ("userId", PropertyInput::param("userId")),
        ("name", PropertyInput::param("name")),
    ],
)
```

Create an edge:

```text
g().n(NodeRef::var("user")).add_e(
    "FOLLOWS",
    NodeRef::var("target"),
    vec![("since", PropertyInput::param("since"))],
)
```

Update properties:

```text
g().n(NodeRef::var("existing"))
    .set_property("name", PropertyInput::param("name"))
```

`add_e` always creates one edge per (source, target) pair, so re-running it
duplicates edges, and an empty target fails the whole batch. `NodeRef::var`
must name an unprojected node variable.

Delete:

```text
g().n(NodeRef::var("target")).drop()
g().n(NodeRef::var("user")).out_e(Some("FOLLOWS")).drop()   // edges in a stream (SDK main only)
g().drop_edge_by_id(EdgeRef::var("target"))                  // edges by ID
```

## Conditional Write Flow

For create-or-update behavior, use explicit branching.

```text
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

Use this pattern for Cypher-style `MERGE ... ON CREATE SET ... ON MATCH SET`
flows. Create `IndexSpec::node_unique_equality("User", "userId")` first: then a
concurrent create fails with `unique_constraint_violation` (409, not retryable
unchanged) instead of duplicating, and re-running the upsert once takes the
update branch. Guard `add_e` the same way for `MERGE (a)-[:R]->(b)`.

## Array Expansion And Per-Item Writes

Use `for_each_param(...)` when a write route needs to iterate an array parameter and perform per-item graph work such as `add_e(...)`, `add_n(...)`, or property updates.

This is the main route-level mapping for Cypher patterns like `UNWIND ... FOREACH`.
A variable set inside the body holds only the last iteration's result.

## Indexes

```text
write_batch()
    .var_as("idx", g().create_index_if_not_exists(IndexSpec::node_unique_equality("User", "userId")))
    .returning(["idx"])
```

The result is a receipt (`accepted` with `operation_id`, `existing_operation`,
or `already_active`); the build runs asynchronously. Poll
`g().get_index_operation(operation_id)` in a read batch until `status` is
`succeeded`; on `blocked`, fix the data its `blocker_code` names and run
`retry_index_operation` or `abort_index_operation` in a write batch. There is no
`create_index`; unscoped text/vector convenience builders need `None::<&str>`.

## Text Search

BM25 text search is property-scoped.

```text
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

For exact FTS prefiltering, build candidates first and call `text_search` or
`text_search_with` on the node or edge stream (Rust SDK `main` only; with helix-db
3.0.0 bind the candidate nodes, then `g().text_search_nodes_with(..).within("<var>")`,
which can return fewer than `k`):

```text
g().n_with_label("Document")
    .where_(Predicate::eq_param("tenantId", "tenantId"))
    .where_(Predicate::eq("published", true))
    .text_search_with(
        "Document",
        "body",
        PropertyInput::param("query"),
        Expr::param("limit"),
        Some(PropertyInput::param("tenantId")),
    )
```

Source-level `text_search_nodes[_with]` and `text_search_edges[_with]` search
the whole tenant partition. A later filter is not an exact prefilter and can
return fewer than `k` eligible hits.

## Vector Search

```text
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

For exact vector prefiltering, build candidates first and call `vector_search`
or `vector_search_with` on the node or edge stream:

```text
g().n_with_label("Document")
    .where_(Predicate::eq_param("tenantId", "tenantId"))
    .where_(Predicate::eq("published", true))
    .vector_search_with(
        "Document",
        "embedding",
        PropertyInput::param("queryVector"),
        Expr::param("limit"),
        Some(PropertyInput::param("tenantId")),
    )
```

Source-level `vector_search_nodes[_with]` and `vector_search_edges[_with]`
search the whole tenant partition. A later filter can underfill top-k.

Limits: whole-index vector search returns at most 800 hits; a traversal-scoped
vector search fails when `min(k, unique candidates)` exceeds 800, and text
search returns at most `min(candidates, k, 800)`. More than 1,000,000 unique
candidates fails. Reads default to `SearchConsistency::Strong`;
`.with_search_consistency(SearchConsistency::Eventual)?` on the `QueryRequest`
(SDK `main`; `"search_consistency": "eventual"` over HTTP) skips the
backpressure wait but may return stale matches.

Guidance:

- keep the vector property out of the projection unless the caller truly needs it
- include `$distance` only when useful
- preserve tenant scope when the vector index is scoped

## Repeat

Repeat is often used with an explicit bounded depth.

```text
g().n(NodeRef::var("seed"))
    .repeat(
        RepeatConfig::new(sub().both(Some("RELATED_TO")))
            .times(3)
            .emit_after(),
    )
    .dedup()
```

`emit_after()` emits each hop's output (Cypher `*1..3`, Gremlin postfix
`.emit()`). `emit_before()` emits each hop's input, including the seed.
`emit_all()` does both, so a row reached at depth 1 is emitted twice.

```text
g().n(NodeRef::var("seed"))
    .repeat(
        RepeatConfig::new(sub().out(Some("RELATED_TO")))
            .times(2)
            .emit_after(),
    )
```

## Null, Existence, And Conditional Traversal Notes

- use `Predicate::is_null` for null-oriented filtering
- use `Predicate::has_key` when property existence is the actual question
- use `bind` + `.optional(sub(...).bind(...))` + `project_bindings` for optional traversals
- use `.choose(...)` for traversal-level if/then/else logic and `Expr::case` for per-row values

## Server-Side Time

When a route needs database-generated time values, use `Expr::timestamp()`
(server UTC epoch millis, `i64`) or `Expr::datetime()` (typed datetime) instead
of a client-supplied clock value:

```text
g().add_n("Event", vec![("createdAt", PropertyInput::from(Expr::timestamp()))])
```

Use this for cases like:

- `createdAt`
- `updatedAt`
- Cypher `timestamp()` migrations

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
