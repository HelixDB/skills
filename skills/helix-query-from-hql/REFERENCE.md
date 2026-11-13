# HQL → Rust DSL / TypeScript DSL Mapping Catalog

Per-feature lookup for migrating HQL into the Rust DSL (crate `helix-db`, import `helix_db`) and the TypeScript
DSL (`@helix-db/helix-db`); Go and Python spellings below. Builder signatures: the `helix-query-rust` /
`helix-query-typescript` skills. Runtime contracts, version gaps, errors and verification: `SKILL.md`.

Source: [`crates/ast`](https://github.com/HelixDB/helix-db/tree/main/crates/ast),
[`sdks/rust`](https://github.com/HelixDB/helix-db/tree/main/sdks/rust),
[`sdks/typescript`](https://github.com/HelixDB/helix-db/tree/main/sdks/typescript).

**NONE** means no DSL form; see `SKILL.md` § Unsupported.

## Spelling differences (most translation mistakes)

| Concept | Rust DSL | TypeScript DSL |
| --- | --- | --- |
| Casing | `snake_case` (`n_with_label`, `value_map`, `order_by`) | `camelCase` (`nWithLabel`, `valueMap`, `orderBy`) |
| Incoming traversal | `.in_(Some("X"))` (`in` is a keyword) | `.in("X")` |
| Filter step | `.where_(pred)` | `.where(pred)` |
| Static constructors | `::` path: `Predicate::eq`, `NodeRef::id` | `.` member: `Predicate.eq`, `NodeRef.id` |
| Edge/traversal label | `Some("FOLLOWS")` / `None::<&str>` | `"FOLLOWS"` / `null` |
| Property lists | `vec!["a","b"]` / `Some(vec![...])` / `None::<Vec<&str>>` | `["a","b"]` / `null` |
| Write properties | `vec![("name","Alice")]` | `{ name: "Alice" }` or `[["name","Alice"]]` |
| Integers in params (incl. IDs) | native `i64` | `number` or `bigint` (`1n`; `bigint` above 2^53) |
| Direct request | `#[query] fn foo(..) -> ReadBatch`, called as `foo(..)?` (returns `Result<QueryRequest, QueryError>`) | `defineParams(...)` + `batch.toQueryRequest(...)` |

## Go and Python spellings

Same AST, different spelling. Builder names: `helix-query-go`, `helix-query-python`.

| Concept | Rust | TypeScript | Go | Python |
| --- | --- | --- | --- | --- |
| Entry | `g()`, `read_batch()` | `g()`, `readBatch()` | `helix.G()`, `helix.ReadQuery("name")` | `g()`, `read_batch()` |
| Casing | `n_with_label_where` | `nWithLabelWhere` | `NWithLabelWhere` | `n_with_label_where` |
| Incoming / filter | `.in_(Some("E"))`, `.where_(..)` | `.in("E")`, `.where(..)` | `.In("E")`, `.Where(..)` | `.in_("E")`, `.where(..)` |
| ID param | `NodeRef::param("id")` | `NodeRef.param("id")` + `param.i64()` | `helix.NodeParam("id")` + `q.ParamI64("id", v)` | `NodeRef.param("id")` + `param.i64()` |

Install: `go get github.com/helixdb/helix-db/sdks/go@latest` (import `helix "github.com/helixdb/helix-db/sdks/go"`,
no `/v3`); `pip install helix-db` (import `helixdb`).

## Query declaration & parameters

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `QUERY Foo(p: ID) =>` (read) | `#[query] pub fn foo(p: i64) -> ReadBatch { read_batch()... }` | `const fooParams = defineParams({ p: param.i64() }); function foo(_ = fooParams) { return readBatch()... }` | `ID` → `i64` / `param.i64()`. |
| `QUERY Foo(..) =>` (write) | `#[query] pub fn foo(..) -> WriteBatch { write_batch()... }` | `function foo(...) { return writeBatch()... }` | Rust typestate / TS types reject a write op in a read batch. |
| `name: String, age: U8, vec: [F64]` | `name: String, age: i64, vec: Vec<f64>` | `param.string()`, `param.i64()`, `param.array(param.f64())` | All integer widths → `i64`. |
| Parameter in a predicate | `Predicate::eq_param("status","status")` | `Predicate.eqParam("status","status")` | Pass the parameter **name**. |
| `binding <- expr` | `.var_as("binding", expr)` | `.varAs("binding", expr)` | |
| `RETURN a` / `RETURN a, b` | `.returning(["a"])` / `.returning(["a","b"])` | same | One top-level response field per binding. |
| `RETURN NONE` | `.returning(Vec::<&str>::new())` | `.returning([])` | Response `{}`. |
| `RETURN "ok"` (literal) | **NONE**: return a binding | **NONE** | Bind the value first if needed. |

## Sources / anchors

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `N<T>(id)` | `g().n(NodeRef::id(id))` | `g().n(NodeRef.id(id))` | Narrowest anchor. HQL UUIDs become an indexed property (e.g. `externalId`). |
| `N<T>(id)` from a param | `g().n(NodeRef::param("user_id"))` | `g().n(NodeRef.param("userId"))` | |
| `N<T>` (all of a label) | `g().n_with_label("User")` | `g().nWithLabel("User")` | |
| `N<T>({field: value})` (indexed) | `g().n_with_label_where("T", SourcePredicate::eq_param("field", "field"))` | `g().nWithLabelWhere("T", SourcePredicate.eqParam("field", "field"))` | `.eq("field", value)` for a constant. |
| `E<T>(id)` | `g().e(EdgeRef::id(id))` | `g().e(EdgeRef.id(id))` | |
| `E<T>` by indexed property | `g().e_with_label_where("T", SourcePredicate::eq(..))` | `g().eWithLabelWhere("T", SourcePredicate.eq(..))` | Label-scoped, like nodes. |
| `V<T>(id)` | `g().n(NodeRef::id(id))` | `g().n(NodeRef.id(id))` | No separate vector source; similarity lookup is under Search. |

## Traversals

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `::Out<E>` | `.out(Some("E"))` | `.out("E")` | `None::<&str>`/`null` = any label. |
| `::In<E>` | `.in_(Some("E"))` | `.in("E")` | |
| (undirected) | `.both(Some("E"))` | `.both("E")` | HQL has no `Both`; use only for genuinely symmetric data. |
| `::OutE<E>` / `::InE<E>` | `.out_e(Some("E"))` / `.in_e(..)` | `.outE("E")` / `.inE(..)` | Edge objects. |
| `::FromN` (edge → source) | `.in_n()` | `.inN()` | |
| `::ToN` (edge → target) | `.out_n()` | `.outN()` | |
| `::FromV` / `::ToV` | `$from` / `$to` via `.edge_properties()` | `.edgeProperties()` | Endpoint ids in the edge property map. |
| anonymous `_::...` | `sub()...` | `sub()...` | Only inside `union`/`choose`/`coalesce`/`optional`; **not** inside `where_`. |

## Filters & predicates

`Predicate` tests properties of the current element only, never a sub-traversal.

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `::WHERE(_::{f}::EQ(v))` | `.where_(Predicate::eq("f", v))` | `.where(Predicate.eq("f", v))` | |
| `::EQ` / `::NEQ` | `Predicate::eq` / `::neq` | `Predicate.eq` / `.neq` | |
| `::GT/::GTE/::LT/::LTE` | `Predicate::gt`/`gte`/`lt`/`lte` | `Predicate.gt`/`gte`/`lt`/`lte` | Numeric/string compare. |
| (parameterized compare) | `Predicate::eq_param`/`gt_param`/… | `Predicate.eqParam`/`gtParam`/… | Use for query parameters. |
| `::CONTAINS(substr)` | `Predicate::contains("f", s)` | `Predicate.contains("f", s)` | Substring. |
| `::IS_IN([..])` | `Predicate::is_in("f", vals)` / `is_in_param` | `Predicate.isIn` / `.isInParam` | |
| `EXISTS(_::{f})` (property) | `Predicate::has_key("f")` | `Predicate.hasKey("f")` | Property, not relationship. |
| `!EXISTS(_::{f})` / null check | `Predicate::is_null("f")` / `is_not_null` | `Predicate.isNull` / `.isNotNull` | |
| `AND(a, b)` / `OR(a, b)` | `Predicate::and(vec![..])` / `::or(..)` | `Predicate.and([..])` / `.or([..])` | |
| `!cond` | `Predicate::not(Box::new(..))` | `Predicate.not(..)` | |
| `::INTERSECT(_::..)` | `.within("var")` | `.within("var")` | Stage the other set in a `var_as` first. |
| (set difference) | `.without("var")` | `.without("var")` | For `!EXISTS`-style relationship exclusion. |
| `EXISTS(traversal)` as a returned boolean | `.exists()` terminal | `.exists()` | Own binding only, not a `WHERE` predicate. |

## Aggregation, ordering, pagination

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `::COUNT` | `.count()` | `.count()` | |
| `::GROUP_BY(p)` | `.group_count("p")` | `.groupCount("p")` | Count summaries. |
| `::AGGREGATE_BY(p)` | `.group("p")` | `.group("p")` | Full grouped objects. |
| `MIN/MAX/SUM/AVG/COUNT(coll)` | `.aggregate_by(AggregateFunction::Min/Max/Sum/Mean/Count, "p")` | `.aggregateBy(AggregateFunction.Min/…, "p")` | `AVG` → `Mean`. |
| `::ORDER<Asc>(_::{f})` / `<Desc>` | `.order_by("f", Order::Asc)` / `Order::Desc` | `.orderBy("f", Order.Asc)` / `Order.Desc` | |
| `::RANGE(a, b)` | `.range(a, b)` | `.range(a, b)` | Inclusive start, exclusive end, as in HQL. |
| (limit / page size) | `.limit(n)` / `.skip(n)` | `.limit(n)` / `.skip(n)` | `n` accepts `Expr::param(..)` / a `ParamRef`. |
| `::FIRST` | `.limit(1)` | `.limit(1)` | HQL gives an object; `.limit(1)` gives a one-element array or `[]`. Unwrap client-side. |

## Projections

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `::{a, b}` | `.project(vec![PropertyProjection::new("a"), PropertyProjection::new("b")])` | `.project([PropertyProjection.new("a"), PropertyProjection.new("b")])` | Stable shape; prefer for service routes. |
| `::{a, b}` (loose map) | `.value_map(Some(vec!["a","b"]))` | `.valueMap(["a","b"])` | |
| all properties (no projection / spread `..`) | `.value_map(None::<Vec<&str>>)` | `.valueMap(null)` | No spread operator. |
| `::{new: old}` | `PropertyProjection::renamed("old","new")` | `PropertyProjection.renamed("old","new")` | **(source, alias)**. |
| `::ID` / `::{id: ::ID}` | `"$id"` in a projection/value_map, or `.id()` | `"$id"`, or `.id()` | e.g. `PropertyProjection::renamed("$id","id")`. |
| computed `::{total: ...}` | `ExprProjection::new("total", Expr::prop("price").mul(Expr::prop("qty")))` | `ExprProjection.new("total", Expr.prop("price").mul(Expr.prop("qty")))` | `+ - * / %` and negation only. |
| `::!{a, b}` (exclusion) | **NONE**: list the fields to keep | **NONE** | |
| `user::|u|{ posts: ... }` (nested closure) | **NONE** | **NONE** | Return the related set as a separate `var_as` binding; join client-side. |

## Writes

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `AddN<T>({props})` | `g().add_n("T", vec![("name","Alice")])` | `g().addN("T", { name: "Alice" })` | TS also takes `[["name","Alice"]]`. |
| `AddN<T>` (empty) | `g().add_n("T", Vec::<(&str, PropertyInput)>::new())` | `g().addN("T")` | |
| `AddE<T>::From(a)::To(b)` | `g().n(NodeRef::var("a")).add_e("T", NodeRef::var("b"), Vec::<(&str, PropertyInput)>::new())` | `g().n(NodeRef.var("a")).addE("T", NodeRef.var("b"), {})` | Step on **From**; **To** is arg 2. |
| `AddE<T>({props})::From(a)::To(b)` | `.add_e("T", NodeRef::var("b"), vec![("since", since)])` | `.addE("T", NodeRef.var("b"), { since })` | |
| `::UPDATE({f: v})` | `.set_property("f", v)` | `.setProperty("f", v)` | One call per field; omitted fields unchanged. |
| (remove a property) | `.remove_property("f")` | `.removeProperty("f")` | No HQL form. |
| `DROP N<T>(id)` | `g().n(NodeRef::id(id)).drop()` | `g().n(NodeRef.id(id)).drop()` | Also removes the node's edges. |
| `UpsertN<T>({key: k}, {props})` | one `write_batch()`: `.var_as("existing", g().n_with_label_where("T", SourcePredicate::eq_param("key","key")))`, `.var_as_if("updated", BatchCondition::VarNotEmpty("existing".into()), g().n(NodeRef::var("existing")).set_property(..))`, `.var_as_if("created", BatchCondition::VarEmpty("existing".into()), g().add_n("T", ..))` | same with `varAsIf`, `BatchCondition.varNotEmpty("existing")` / `.varEmpty("existing")` | Unique index on `key`; see `SKILL.md`. |
| `UpsertE<T>::From(a)::To(b)` | stage `existing` as `g().n(NodeRef::var("a")).out(Some("T")).within("b")`, then `var_as_if(VarEmpty("existing"), g().n(NodeRef::var("a")).add_e("T", NodeRef::var("b"), ..))` | same with `varAsIf` | Creates the edge only when `a` is not already linked to `b`. |
| `DROP N<T>::OutE<E>` (edges only) | `g().n(NodeRef::param("id")).out_e(Some("E")).drop()` (main) | `g().n(NodeRef.param("id")).outE("E").drop()` | Drops exactly the traversed edges. Avoid `.drop_edge(to)`: it drops *all* edges to a target. |

## Search

Plain variants take concrete values; for runtime params use the `_with` / `...With` variants (`SKILL.md`).

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `SearchV<T>(vector, k)` | `g().vector_search_nodes("T","embedding", vec_f32, k, None)` | `g().vectorSearchNodes("T","embedding", vector, k, null)` | Precomputed vector; `"embedding"` = the indexed vector property. |
| `SearchV<T>` on an edge index | `g().vector_search_edges(..)` | `g().vectorSearchEdges(..)` | |
| `SearchBM25<T>(text, k)` | `g().text_search_nodes("T","body", text, k, None)` | `g().textSearchNodes("T","body", text, k, null)` | `"body"` = the BM25-indexed property. Edges: `text_search_edges`. |
| tenant-scoped search | last arg `Some(PropertyValue::from("acme"))` | last arg `"acme"` | Dropping the tenant changes results. |
| `SearchV<T>(Embed(text), k)` | **NONE**: embed in app code | **NONE** | |

## Schema & indexes

The query DSL declares no schema. Index DDL is asynchronous (receipts and polling: `SKILL.md`).

| HQL schema feature | DSL equivalent | Notes |
| --- | --- | --- |
| `N::User { name: String, ... }` | none | Labels/properties come from data and queries. Keep the schema as documentation. |
| `INDEX field: T` | `g().create_index_if_not_exists(IndexSpec::node_equality("User","field"))` in a **write batch** | Run once at setup. |
| `UNIQUE INDEX field: T` | `IndexSpec::node_unique_equality("User","field")` / `IndexSpec.nodeUniqueEquality` | Race-safe upsert key. Existing duplicates block the build. |
| vector index (for `SearchV`) | `g().create_vector_index_nodes("Doc", "embedding", NonZeroUsize::new(1536).expect("non-zero dimension"), VectorDistanceMetric::Cosine, None::<&str>)` / `g().createVectorIndexNodes("Doc", "embedding", 1536, VectorDistanceMetric.Cosine)` | Dimension and metric required; tenant property optional. |
| BM25 index (for `SearchBM25`) | `g().create_text_index_nodes("Doc","body", None::<&str>)` / `g().createTextIndexNodes("Doc","body")` | A bare `None` cannot infer the tenant-property type (E0282). |
| `DEFAULT 0` / `DEFAULT "draft"` | **NONE** | Include the value in `add_n`. |
| `DEFAULT NOW` | `Expr::timestamp()` / `Expr::datetime()` as the `add_n` value | |
| `DEFAULT NONE` | **NONE**: omit the property | Null is implicit. |

## Control flow

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `FOR x IN <array param> { ... }` | `.for_each_param("arr", body_batch)` | `.forEachParam("arr", body)` | Only over a passed-in array parameter. |
| `FOR {a, b} IN arr { ... }` | reference fields by name inside the body | same | The body batch reads each element's fields by name. |
| nested `FOR` | nest `for_each_param` bodies | nest `forEachParam` bodies | |

## Shortest paths

| HQL | Rust DSL | TypeScript DSL | Notes |
| --- | --- | --- | --- |
| `ShortestPathBFS` (out, any label) | `g().shortest_path(NodeRef::param("from"), NodeRef::param("to"), 6)` | `g().shortestPath(NodeRef.param("from"), NodeRef.param("to"), 6)` | Unweighted BFS. |
| `ShortestPathBFS<E>` (labeled / undirected) | `g().shortest_path_with(src, dst, Some("E"), ShortestPathDirection::Both, 6)` | `g().shortestPath(src, dst, 6, { label: "E", direction: ShortestPathDirection.Both })` | Direction `Out` (default), `In`, `Both`. |
| `ShortestPathDijkstras` / `ShortestPathAStar` | **NONE** | **NONE** | Weighted. |

Go: `helix.G().ShortestPath(src, dst, maxDepth, helix.ShortestPathOptions{Label: "E", Direction: helix.ShortestPathBoth})`.
Python: `g().shortest_path(src, dst, max_depth, label="E", direction=ShortestPathDirection.BOTH)`.
