# Helix Query Authoring - Go Reference

Use this reference to confirm Go SDK method names and request patterns. Names
are checked against the SDK source on helix-db `main`; the published module is
v0.3.1 (Docker `ghcr.io/helixdb/helixdb:v0.0.16`). APIs newer than v0.3.1 are
marked **main only**. The module path has no `/v3` suffix:

```bash
go get github.com/helixdb/helix-db/sdks/go@latest
```

```text
import helix "github.com/helixdb/helix-db/sdks/go"
```

## Request Shape

```text
type Request interface {
	json.Marshaler
	Validate() error
	// contains unexported methods
}

func ReadQuery(name string) *helix.ReadQueryBuilder
func WriteQuery(name string) *helix.WriteQueryBuilder
func MarshalRequest(req helix.Request) ([]byte, error)
```

`Request` is sealed by the SDK. Application code should construct requests with
`ReadQuery` or `WriteQuery`, not custom implementations.

Primary usage:

```text
func Query(args ...) helix.Request {
	q := helix.ReadQuery("query_name")
	return q.VarAs("result", helix.G()...).Returning("result")
}
```

Pass explicit names to `.Returning(...)` for every response variable that should be decoded. Zero-arg `.Returning()` is valid only for intentional empty responses and serializes as `"returns":[]`.

## Query Builders

Both read and write builders support:

```text
.VarAs(name string, traversal *helix.Traversal)
.VarAsIf(name string, condition helix.BatchCondition, traversal *helix.Traversal)
.Returning(vars ...string) helix.Request
```

`ForEachParam` is available on both builders, but the body type follows the request
kind:

```text
read.ForEachParam(param string, body *helix.ReadBatch)
write.ForEachParam(param string, body *helix.WriteBatch)
```

Read builders reject write traversals during validation. Write builders accept read-only and write traversals.

## Inline Params

```text
q.ParamBool(name string, value bool)
q.ParamI64(name string, value any)
q.ParamF64(name string, value any)
q.ParamF32(name string, value any)
q.ParamString(name string, value string)
q.ParamDateTime(name string, value any)
q.ParamValue(name string, value any)
q.ParamObject(name string, value any, inner ...helix.QueryParamType)
q.ParamArray(name string, value any, inner helix.QueryParamType)
```

Each returns `helix.ParamRef`:

```text
ref.Expr()  // helix.Expr
ref.Input() // helix.PropertyInput
ref.Bound() // helix.StreamBound
```

Direct Go values are literals in the inline AST. `helix.SourceEq("id", "foo")` and `helix.PredEq("id", "foo")` embed `"foo"` directly and do not create parameters. For request-specific values, declare a `q.Param*` value and pass the returned ref so the request body has a stable query shape and runtime value metadata. Bind node/edge IDs as integers (`q.ParamI64`, or `q.ParamArray(..., helix.ParamTypeI64())` with `helix.NodeParam`); a string ID fails at runtime.

```text
id := q.ParamString("id", userID)
helix.G().NWhere(helix.SourceEq("id", id))
helix.G().NWithLabel("User").Where(helix.PredEq("id", id))
```

Parameter type constructors:

```text
helix.ParamTypeBool()
helix.ParamTypeI64()
helix.ParamTypeF64()
helix.ParamTypeF32()
helix.ParamTypeString()
helix.ParamTypeDateTime()
helix.ParamTypeBytes()
helix.ParamTypeValue()
helix.ParamTypeObject()
helix.ParamTypeArray(inner)
```

Dynamic JSON cannot represent bytes values. `ParamTypeBytes()` exists for schema parity, not normal Go runtime values.

## Values And Inputs

Property values are tagged on the wire:

```text
helix.Null()
helix.Bool(true)
helix.I64(42)
helix.DateTimeMillis(1776000000000)
helix.DateTimeFromMillis(1776000000000)
helix.F64(1.5)
helix.F32(1.25)
helix.String("Alice")
helix.Bytes([]byte{1, 2})
helix.I64Array(1, 2, 3)
helix.F64Array(1.0, 2.0)
helix.F32Array(1.0, 2.0)
helix.StringArray("a", "b")
helix.Array(helix.String("a"), helix.I64(7))
helix.Object(map[string]helix.PropertyValue{...})
helix.ObjectFromEntries(helix.Entry("k", "v"))
```

Property inputs are value-or-expression wrappers:

```text
helix.ValueInput(value)
helix.ExprInput(expr)
helix.ParamInput("name")
```

Most mutation/search methods accept normal Go values, `helix.Expr`, or `helix.ParamRef` and convert to the right `PropertyInput` automatically.

## Traversal Sources

```text
helix.G()
helix.Sub()

G().N(helix.NodeID(1))
G().N(helix.NodeIDs(1, 2))
G().N(helix.NodeVar("users"))
G().N(helix.NodeParam("node_ids"))
G().N(helix.AllNodes())
G().NWhere(helix.SourceEq("tenantId", tenant))
G().NWithLabel("User")
G().NWithLabelWhere("User", pred)

G().E(helix.EdgeID(1))
G().E(helix.EdgeIDs(1, 2))
G().E(helix.EdgeVar("edges"))
G().E(helix.EdgeParam("edge_ids"))
G().EWhere(pred)
G().EWithLabel("FOLLOWS")
G().EWithLabelWhere("FOLLOWS", pred)
```

Use `NodeParam` / `EdgeParam` with parameters that carry ids or id arrays, for
example `ids := q.ParamArray("node_ids", []int64{1, 2}, helix.ParamTypeI64())` and
`G().N(helix.NodeParam(ids.Name))`.

Search:

```text
G().VectorSearchNodes(label, property, []float32{1, 0, 0}, 10, tenantValue)
G().VectorSearchNodesWith(label, property, queryVectorInput, kBound, tenantInputPtr)
G().TextSearchNodes(label, property, "graph", 10, tenantValue)
G().TextSearchNodesWith(label, property, queryTextInput, kBound, tenantInputPtr)
G().VectorSearchEdges(...)
G().TextSearchEdges(...)
```

These source methods search the whole selected tenant partition. For an exact
vector or BM25 prefilter, build a node or edge traversal first:

```text
candidateNodes.VectorSearchNodesWithin(label, property, queryVector, k, tenantValue)
candidateNodes.VectorSearchNodesWithinWith(label, property, queryVectorInput, kBound, tenantInputPtr)
candidateEdges.VectorSearchEdgesWithin(...)
candidateEdges.VectorSearchEdgesWithinWith(...)
candidateNodes.TextSearchNodesWithin(label, property, queryText, k, tenantValue)
candidateNodes.TextSearchNodesWithinWith(label, property, queryTextInput, kBound, tenantInputPtr)
candidateEdges.TextSearchEdgesWithin(...)
candidateEdges.TextSearchEdgesWithinWith(...)
```

Restricted vector search enforces exact candidate membership while ranking may
still use approximate index structures; project `$distance`. Restricted BM25
search returns at most `min(unique candidates, k, 800)`, ordered by score
descending then entity ID ascending, with partition-wide statistics; project
`$score`. Pass the same tenant partition used to construct candidates.

Limits: a whole-index vector search returns at most 800 hits. A restricted vector
search fails when `min(k, unique candidates)` exceeds 800 (a larger `k` succeeds
when 800 or fewer candidates exist). More than 1,000,000 unique candidates fails
either restricted search.

Search consistency (**main only**): `helix.ReadQuery("q").WithSearchConsistency(helix.SearchConsistencyEventual)`.
`strong` (default) includes committed but unpublished vector/text work;
`eventual` bounds it and can briefly return hits whose tenant, label or property
has since changed. Writes always search strongly. With v0.3.1, send
`"search_consistency": "eventual"` in a direct HTTP body.

Use `*With` variants for params:

```text
queryVector := q.ParamArray("query_vector", []float32{1, 0, 0}, helix.ParamTypeF32())
limit := q.ParamI64("limit", int64(10))
tenant := q.ParamString("tenant_id", tenantID)
tenantInput := tenant.Input()

G().VectorSearchNodesWith("Document", "embedding", queryVector.Input(), limit.Bound(), &tenantInput)
```

## Traversal Steps

Navigation:

```text
.Out("FOLLOWS") .In("FOLLOWS") .Both("RELATED")
.OutE("FOLLOWS") .InE("FOLLOWS") .BothE("RELATED")
.OutN() .InN() .OtherN()
```

Filters (`.Has` takes literal values only; a `ParamRef` makes the request fail
to serialize, so use `.Where(helix.PredEq("status", ref))`. `.EdgeHas` accepts a
`ParamRef`):

```text
.Has("status", "active")
.HasLabel("User")
.HasKey("externalId")
.Where(helix.PredEq("tenantId", tenant))
.Dedup()
.Within("users")
.Without("blocked")
.EdgeHas("weight", helix.F64(1.0))
.EdgeHasLabel("FOLLOWS")
```

Bounds and variables:

```text
.Limit(10)
.Limit(limitParam)
.Skip(offsetParam)
.Range(start, end)
.As("x") .Store("x") .Select("x") .Inject("x")
.Bind("service")   // tag current element as a row-local binding; enters row mode
```

Ordering:

```text
.OrderBy("createdAt", helix.OrderDesc)
.OrderByMultiple(
    helix.Ordering{Property: "score", Order: helix.OrderDesc},
    helix.Ordering{Property: "name", Order: helix.OrderAsc},
)
```

Rows missing the sort property sort first for `OrderAsc` and last for
`OrderDesc`, the opposite of Cypher and SQL defaults; filter with
`helix.PredIsNotNull(prop)` first when that matters. Put `OrderBy` before any
`Bind`.

Shortest path (unweighted BFS, a source step on `helix.G()`):

```text
helix.G().ShortestPath(helix.NodeVar("from"), helix.NodeVar("to"), 6)
helix.G().ShortestPath(helix.NodeID(1), helix.NodeParam(target.Name), 4,
    helix.ShortestPathOptions{Label: "FOLLOWS", Direction: helix.ShortestPathBoth})
```

It returns one array of node IDs from source to target, such as `[0, 1, 2]`, or
`[]` when no path exists within `maxDepth`. Direction defaults to
`helix.ShortestPathOut`; `maxDepth` must be positive.

Terminals and projection:

```text
.Count()
.Exists()
.ID()
.Label()
.Values("$id", "name")
.ValueMap("$id", "name")
.ValueMapAll()
.Project(
    helix.ProjectPropAs("$id", "id"),
    helix.ProjectFromEndpoint("resource_id", "from_id"),
    helix.ProjectToEndpoint("resource_id", "to_id"),
    helix.ProjectExpr("age2", expr),
)
.EdgeProperties()
```

On edge streams, `helix.ProjectFromEndpoint(prop, alias)` serializes to
`{"source":"$from.<prop>","alias":"<alias>"}` and
`helix.ProjectToEndpoint(prop, alias)` serializes to
`{"source":"$to.<prop>","alias":"<alias>"}`. Use these to return source/target
node properties such as resource ids without traversing from every edge to its
endpoints. Keep `.EdgeProperties()` for full edge maps and the internal `$from`
/ `$to` node ids.

Row bindings (multi-hop correlation):

```text
.ProjectBindings(
    helix.ProjectNamedBinding("service", "$id", "service_id"), // read from a named binding
    helix.ProjectCurrentBinding("$id", "current_id"),          // read from the current element
    helix.ProjectBindingCoalesce([]helix.BindingValueRef{      // first present non-null wins
        helix.NamedBindingValue("deployment", "$id"),
        helix.NamedBindingValue("owner", "$id"),
    }, "workload_id"),
)
.ProjectDistinctBindings(/* same args; dedups identical rows */)
```

`.Project(...)` only sees the final stream. When one output row must combine
values captured at **different hops**, tag elements with `.Bind(name)` as you
pass them, then assemble rows with `.ProjectBindings(...)` (preserves duplicate
rows) or `.ProjectDistinctBindings(...)` (dedups). A binding that a row never
reached (for example inside an empty `Optional`) is left out of that row's
object, so decode those fields as pointers or check presence. After `.Bind`,
`OrderBy`, `Choose`, `Repeat`, `Values`, `ValueMap`, `Project`, `ID`, `Label`
and `EdgeProperties` are rejected (`invalid_after_bind_operation`); finish with
`ProjectBindings`, `Count` or `Exists`. Constructors:
`helix.Binding(name)` / `helix.CurrentBinding()`
build a `BindingTarget`; `helix.ProjectBinding(target, source, alias)`,
`ProjectNamedBinding`, `ProjectCurrentBinding`, and `ProjectBindingCoalesce`
build `BindingProjection`s; `NamedBindingValue` / `CurrentBindingValue` build
`BindingValueRef`s. `source` accepts stored properties and the virtual fields
`$id`, `$label`, `$from`, `$to`, `$distance`, `$score`. Binding projections
serialize inside the normal direct request.

Writes (unprojected mutation output is `{"$id": N}` per element):

```text
.AddN("User", helix.Props{helix.Prop("name", nameParam)})
.AddE("FOLLOWS", helix.NodeVar("target"), helix.Props{helix.Prop("since", sinceParam)})
.SetProperty("name", nameParam)
.RemoveProperty("old")
.Drop()
.DropEdge(helix.NodeID(1))
.DropEdgeLabeled(helix.NodeID(1), "FOLLOWS")
.DropEdgeByID(helix.EdgeID(1))
```

`AddE` creates one edge per (source, target) pair every time it runs; it is not
idempotent, and an empty target fails the whole batch. Guard it with `VarAsIf`
(for example `VarEmpty` on an existing-edge lookup) when re-runs must not
duplicate edges.

Branching and aggregation:

```text
.Repeat(helix.Repeat(helix.Sub().Out("FOLLOWS")).WithTimes(2).EmitAfter().WithMaxDepth(4))
.Union(helix.Sub().Out("FOLLOWS"), helix.Sub().In("FOLLOWS"))
.Choose(pred, helix.Sub().Out("A"), helix.Sub().Out("B"))
.Coalesce(helix.Sub().Out("preferred"), helix.Sub().Out("fallback"))
.Optional(helix.Sub().Out("HAS_PROFILE"))
.Group("status")
.GroupCount("status")
.AggregateBy(helix.AggregateMean, "score")
.Fold() .Unfold() .Path() .SimplePath()
.WithSack(0) .SackSet("p") .SackAdd("p") .SackGet()
```

`helix.Sub()` is for inline branch traversals. It supports `Out`, `In`,
`Both`, `Where`, `Limit`, `Count`, and `Bind` — use
`.Bind` inside a branch to tag the element reached on that arm. Put shared
terminal projections such as `ValueMap`, `Project`, or `ProjectBindings` after
the parent `.Choose`, `.Union`, `.Coalesce`, or `.Optional` step.

Semantics that differ from intuition:

- `Repeat` emit: none returns only the last hop; `EmitAfter()` returns every
  hop's output (Gremlin postfix `.emit()`); `EmitBefore()` every hop's input;
  `EmitAll()` both, so depth-1 rows appear twice. `EmitIf(pred)` emits matching
  hop outputs. Bound every repeat with `WithTimes` or `UntilPred`.
- `Choose(pred, then)` without an else drops rows that fail `pred`.
- `Optional(sub)` keeps the input row (current element unchanged) when `sub` is
  empty; read the optional side through a `Bind` inside `sub` and
  `ProjectBindings`.
- `Fold`, `Unfold`, `Path`, `SimplePath`, `WithSack`, `SackSet`, `SackAdd` and
  `SackGet` execute; they are not no-ops.

Indexes:

```text
.CreateIndexIfNotExists(helix.NodeEqualityIndex("User", "externalId"))
.CreateIndexIfNotExists(helix.NodeUniqueEqualityIndex("User", "email"))
.CreateIndexIfNotExists(helix.NodeRangeIndex("User", "createdAt"))
.CreateIndexIfNotExists(helix.NodeRangeDescIndex("User", "createdAt"))
.CreateIndexIfNotExists(helix.NodeRangeIndexWithDirection("User", "createdAt", helix.RangeIndexDesc))
.CreateIndexIfNotExists(helix.EdgeEqualityIndex("FOLLOWS", "since"))
.CreateIndexIfNotExists(helix.EdgeRangeDescIndex("FOLLOWS", "since"))
.CreateIndexIfNotExists(helix.EdgeRangeIndexWithDirection("FOLLOWS", "since", helix.RangeIndexDesc))
.CreateVectorIndexNodes("Document", "embedding", 1536, helix.VectorDistanceCosine, "tenantId")
.CreateTextIndexNodes("Document", "body", "tenantId")
.DropIndex(helix.NodeRangeIndex("User", "createdAt"))
```

Range indexes default to ascending physical order (`helix.RangeIndexAsc`). Use `helix.RangeIndexDesc` for descending indexes that primarily serve newest-first or high-score-first scans.

Index DDL is asynchronous. The returned variable is a receipt (a scalar, not an
array):

| `kind` | Fields | Next step |
| --- | --- | --- |
| `accepted` | `operation_id`, `index_id`, `generation` | Poll the operation |
| `existing_operation` | `operation_id` | The same build is already in flight; poll it |
| `already_active` | `index_id`, `generation` | Done |

Lifecycle steps (the operation ID is a lowercase UUID string):

```text
helix.G().GetIndexOperation(operationID)    // read
helix.G().RetryIndexOperation(operationID)  // write
helix.G().AbortIndexOperation(operationID)  // write
helix.UnmarshalIndexDdlReceipt(raw)         // -> IndexDdlAccepted | IndexDdlExistingOperation | IndexDdlAlreadyActive
helix.UnmarshalIndexOperationStatus(raw)    // -> *IndexOperationQueued | *Running | *Blocked | *Succeeded | *Aborted (pointers; receipts are values)
```

Poll until `IndexOperationSucceeded`; queries cannot use the index before then.
`IndexOperationBlocked` carries `BlockerCode` (`uniqueness_violation`,
`invalid_source_data`, `oversized_entity`, ...) and does not resume on its own:
fix the data, then `RetryIndexOperation`, or `AbortIndexOperation`. A unique
index rejects duplicate writes with `unique_constraint_violation`; while it
builds, only values already claimed (by an entity the build has scanned, or a
write since the build started) are rejected, and a duplicate of a not-yet-scanned
entity's value blocks the build when the scan reaches it. Related errors: `index_busy` (another lifecycle
operation on the index is running), `index_build_blocked` (a write would
overflow a blocked build's queue; fix and retry or abort the build first).

## Predicates And Expressions

Predicates:

```text
helix.PredEq("status", "active")
helix.PredNeq("status", "deleted")
helix.PredGt("score", helix.F64(0.8))
helix.PredGte("createdAt", sinceParam)
helix.PredLt("age", int64(65))
helix.PredLte("age", int64(65))
helix.PredBetween("age", minParam, int64(65))
helix.PredHasKey("externalId")
helix.PredIsNull("deletedAt")
helix.PredIsNotNull("email")
helix.PredStartsWith("name", "A")
helix.PredEndsWith("name", "b")
helix.PredContains("bio", "graph")
helix.PredIsIn("status", statusesParam)
helix.PredAnd(preds...)
helix.PredOr(preds...)
helix.PredNot(pred)
helix.PredCompare(left, helix.CompareGt, right)
```

Source predicates (`SourcePredicate` is the same type as `Predicate`) use
`SourceEq`, `SourceNeq`, `SourceGt`, `SourceGte`, `SourceLt`, `SourceLte`,
`SourceHasKey`, `SourceStartsWith`, `SourceEndsWith`, `SourceContains`,
`SourceContainsExpr`, `SourceIsIn`, `SourceIsNull`, `SourceIsNotNull`,
`SourceBetween`, `SourceCompare`, `SourceAnd`, `SourceOr`, and `SourceNot`.

Comparison predicates (`Eq`, `Neq`, `Gt`, `Gte`, `Lt`, `Lte`, `Between`, `IsIn`)
take `any`: a direct string, number, bool, or `helix.PropertyValue` is inlined; a
`helix.ParamRef` or `helix.Expr` is parameterized. `StartsWith`, `EndsWith`, and
`Contains` take a Go `string` (always inlined); for a parameterized substring use
`helix.PredContainsExpr("bio", ref.Expr())`. There is no parameterized
prefix/suffix builder in Go.

Expressions:

```text
helix.ExprProp("score")
helix.ExprID()
helix.ExprTimestamp()
helix.ExprDateTime()
helix.ExprVal(helix.F64(1.0))
helix.ExprParam("limit")
helix.ExprProp("score").Add(helix.ExprVal(1))
helix.ExprProp("age").Neg()
helix.ExprCase(branches, elseExprPtr)
```

`ExprCase` is the per-row value choice (Cypher `CASE`), used in
`helix.ProjectExpr` or `SetProperty`:

```text
other := helix.ExprVal("other")
helix.ProjectExpr("tier", helix.ExprCase([]helix.WhenThen{
    {When: helix.PredGte("score", int64(90)), Then: helix.ExprVal("gold")},
    {When: helix.PredGte("score", int64(50)), Then: helix.ExprVal("silver")},
}, &other))
```

## Client

```text
client, err := helix.NewClient("http://localhost:6969")
client, err := helix.NewClient("https://helix.example.com", helix.WithAPIKey("hx_secret"))
client = client.WithAPIKey("hx_secret")
client.ClearAPIKey()
client, err := helix.NewClient(endpoint, helix.WithAPIKey(key), helix.WithDatabaseID(dbID)) // main only
```

`WithAPIKey` / `ClearAPIKey` synchronize access to the stored API key, so `Exec`
can read it safely while other goroutines rotate or clear the key.

Execute:

```text
err := client.Exec(ctx, FindUsers("acme", 25), &out)
err = client.Exec(ctx, CreateUser("Alice", "acme"), &created, helix.WriterOnly())
```

Options:

```text
helix.WriterOnly()             // X-Helix-Require-Writer: true
helix.WarmOnly()               // X-Helix-Warm: true (reads only)
helix.AwaitDurability(false)   // X-Helix-Await-Durable: false (writes only)
```

`Exec` posts to `/v2/query`, serializes the request internally, and decodes responses with `json.Decoder.UseNumber()`.

Writes wait for durability by default. `AwaitDurability(false)` returns once the
write is applied on the writer, so a crash before the WAL upload loses it; it
does not change conflict rates. `AwaitDurability(true)` only restates the
default, and on a read it is `400 invalid_request_option`.

Response shape: one JSON object keyed by the `.Returning(...)` names. Every row
stream is an array, and an empty one is `[]` (single lookups, `Limit(1)` and
skipped `VarAsIf` entries included). `Count()` and `Exists()` stay scalars (`0`,
`false`); index DDL and lifecycle steps return an object. A zero-argument
`.Returning()` produces `{}`. Element streams without a projection return
`{"$id": N}` per element.

```go
type FindUserResponse struct {
	User    []UserRow `json:"user"`    // [] when missing; take User[0] after a length check
	Friends []UserRow `json:"friends"`
	Count   int64     `json:"count"`
}
```

`helix.WarmOnly()` is read-only. Helix Cloud fans the read out to every eligible
backend and returns `204 No Content` with no query payload after at least one
target succeeds; combine it with `helix.WriterOnly()` to target only the
authoritative writer. `Exec` on `main` accepts the `204`; v0.3.1 accepts only
HTTP 200 and returns a remote `*helix.HelixError` for it, so use direct HTTP for
Cloud warming with v0.3.1. A local server returns the normal 200 response.

### Errors

Remote errors are `*helix.HelixError` with `Kind: helix.ErrorRemote`, `Code`
(open-string `helix.QueryErrorCode`, from the body's `error` field), `Details`
(the `msg` diagnostic), and `StatusCode`. On `main` it also has `Retryable
*bool` (the body's `retryable`), and `helix.IsRetryable(err)`,
`helix.IsConflict(err)` (`transaction_conflict` only) and
`helix.IsIndexBackpressure(err)`. In v0.3.1, `Retryable` and `IsRetryable` do
not exist and `IsConflict` / `errors.Is(err, helix.ErrConflict)` are true for
every 409, including `unique_constraint_violation`; branch on `Code`.

| Class | HTTP | `retryable` | A failed write | Codes |
| --- | ---: | --- | --- | --- |
| Invalid request / planning | 400 | absent | committed nothing | `invalid_request`, `invalid_query_json`, `invalid_request_body`, `invalid_request_option`, `unbound_parameter`, `invalid_node_id`, `invalid_after_bind_operation`, `duplicate_*`, other `invalid_*` (not `invalid_query`, `invalid_configuration`, `invalid_index_model`: 500) |
| Not found | 404 | absent | committed nothing | `node_not_found`, `edge_not_found`, `index_not_found`, `index_operation_not_found` |
| Timeout | 408 | absent | may have committed | `query_deadline_exceeded` |
| Retryable conflict | 409 | `true` | committed nothing | `transaction_conflict`, `request_read_view_changed`, `stale_index_generation` |
| Conflict with database state | 409 | `false` | committed nothing | `unique_constraint_violation`, `index_already_exists`, `index_definition_conflict`, `index_busy`, `index_operation_not_abortable`, `index_build_blocked` |
| Index backpressure | 429 | `true` | committed nothing | `index_backpressure` |
| Resource limit | 429 | absent | committed nothing | `query_memory_limit_exceeded` |
| Internal | 500 | absent | may have committed | `storage_error`, `internal_error`, `invalid_query`, ... |
| Unavailable | 503 | absent | committed nothing | `writer_mode_required`, `reader_mode_required`, `database_closed`, `index_lifecycle_unavailable`, `migration_required`, ... |
| Commit outcome unknown | 503 | `false` | may have committed | `writer_fenced_commit_outcome_unknown` |

- Retry the retryable classes unchanged with bounded backoff and jitter;
  rebuild a write from freshly read state when it depends on what it read.
- `unique_constraint_violation`: report a duplicate or pick another key; from an
  upsert's create branch, re-run the upsert once (it then takes the update branch).
- `index_busy` / `index_build_blocked`: resolve the index operation first.
- 408, 500 and `writer_fenced_commit_outcome_unknown`: reconcile (read back by
  an application key) before resubmitting a write.
- Helix Cloud adds gateway codes such as `query_timeout` (408), `rate_limited`
  (429, honor `Retry-After`), `payload_too_large` (413, 2 MiB) and
  `write_outcome_unknown` (503). The SDK does not expose `Retry-After`; use a
  custom HTTP transport when the exact delay matters.
- Never parse `Details`. Full catalog:
  https://docs.helix-db.com/database/helix-db/query-guides/error-handling

### Cypher And SQL (**main only**)

```text
res, err := client.Cypher(ctx, helix.CypherRequest{
    Query:      "MATCH (u:User {email: $email}) RETURN u.name AS name",
    Parameters: map[string]any{"email": email},
    QueryName:  "user_by_email",
})
// res.Columns == ["name"]; res.Rows == [["Ada"]]
res, err = client.SQL(ctx, helix.SQLRequest{
    Query: "SELECT p.name FROM Person p WHERE p.age > ?",
    Args:  []any{30},
})
plan, err := client.ExplainCypher(ctx, helix.CypherRequest{Query: "..."})
```

These post to `POST /v2/cypher`, `/v2/sql` and their `/explain` routes and take
the same `ExecOption`s. With v0.3.1, POST `{"query", "parameters",
"query_name"}` (SQL: `parameters` may be a list for `?`, plus `mappings`) to
those routes over HTTP. A failed statement returns
`{"error": "<category>", "msg", "details": {"detail", "phase", "span"}}`, for
example `unsupported_feature` with `details.detail` `merge`.

## Published Release Scope

Version v0.3.1 distributes the server query builder and HTTP client. A standard
module install does not include generated native bindings: embedded
constructors return `ErrNativeBindingsUnavailable`, and `Client.Graph` returns
`ErrNativeGraphUnavailable`. The `helixdb_uniffi` build tag is only for callers
that separately generate and link compatible bindings and native libraries.

Not in v0.3.1 (source on `main` only): `IsRetryable`, `HelixError.Retryable`,
`IsIndexBackpressure`, `WithDatabaseID`, `WithSearchConsistency`, `Cypher`,
`SQL`, `ExplainCypher`, `ExplainSQL`, and accepting Cloud warm `204`. The retry
loop in `EXAMPLES.md` switches on `Code`, so it compiles against both.
