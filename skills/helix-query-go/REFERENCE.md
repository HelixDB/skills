# Helix Query Authoring - Go Reference

Method names follow the SDK source on helix-db `main`; `(main)` marks APIs
missing from v0.3.1 (see the table in `SKILL.md`).

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

`Request` is sealed; build requests with `ReadQuery` / `WriteQuery`, not custom
implementations.

## Query Builders

```text
.VarAs(name string, traversal *helix.Traversal)
.VarAsIf(name string, condition helix.BatchCondition, traversal *helix.Traversal)
.Returning(vars ...string) helix.Request
read.ForEachParam(param string, body *helix.ReadBatch)
write.ForEachParam(param string, body *helix.WriteBatch)
```

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

ID params: `q.ParamI64`, or `q.ParamArray(..., helix.ParamTypeI64())` with
`helix.NodeParam`.

```text
id := q.ParamString("id", userID)
helix.G().NWhere(helix.SourceEq("id", id))
helix.G().NWithLabel("User").Where(helix.PredEq("id", id))
```

Parameter types:

```text
helix.ParamTypeBool()
helix.ParamTypeI64()
helix.ParamTypeF64()
helix.ParamTypeF32()
helix.ParamTypeString()
helix.ParamTypeDateTime()
helix.ParamTypeBytes()     // schema parity only: dynamic JSON cannot carry bytes
helix.ParamTypeValue()
helix.ParamTypeObject()
helix.ParamTypeArray(inner)
```

## Values And Inputs

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

helix.ValueInput(value)
helix.ExprInput(expr)
helix.ParamInput("name")
```

Property values are tagged on the wire. Most mutation/search methods accept Go
values, `helix.Expr` or `helix.ParamRef` and convert to `PropertyInput`.

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

`NodeParam` / `EdgeParam` take a param holding ids:
`ids := q.ParamArray("node_ids", []int64{1, 2}, helix.ParamTypeI64())`, then
`G().N(helix.NodeParam(ids.Name))`.

## Search

```text
G().VectorSearchNodes(label, property, []float32{1, 0, 0}, 10, tenantValue)
G().VectorSearchNodesWith(label, property, queryVectorInput, kBound, tenantInputPtr)
G().TextSearchNodes(label, property, "graph", 10, tenantValue)
G().TextSearchNodesWith(label, property, queryTextInput, kBound, tenantInputPtr)
G().VectorSearchEdges(...)
G().TextSearchEdges(...)

candidateNodes.VectorSearchNodesWithin(label, property, queryVector, k, tenantValue)
candidateNodes.VectorSearchNodesWithinWith(label, property, queryVectorInput, kBound, tenantInputPtr)
candidateEdges.VectorSearchEdgesWithin(...)
candidateEdges.VectorSearchEdgesWithinWith(...)
candidateNodes.TextSearchNodesWithin(label, property, queryText, k, tenantValue)
candidateNodes.TextSearchNodesWithinWith(label, property, queryTextInput, kBound, tenantInputPtr)
candidateEdges.TextSearchEdgesWithin(...)
candidateEdges.TextSearchEdgesWithinWith(...)
```

`*With` variants take params:

```text
queryVector := q.ParamArray("query_vector", []float32{1, 0, 0}, helix.ParamTypeF32())
limit := q.ParamI64("limit", int64(10))
tenant := q.ParamString("tenant_id", tenantID)
tenantInput := tenant.Input()

G().VectorSearchNodesWith("Document", "embedding", queryVector.Input(), limit.Bound(), &tenantInput)
```

- Restricted (`*Within`) vector search enforces exact candidate membership;
  ranking may still use approximate index structures. A `k` above 800 succeeds
  when 800 or fewer candidates exist.
- Restricted BM25 returns at most `min(unique candidates, k, 800)`, ordered by
  score descending then entity ID ascending, with partition-wide statistics.
- Search consistency (main):
  `helix.ReadQuery("q").WithSearchConsistency(helix.SearchConsistencyEventual)`.
  `strong` (default) includes committed but unpublished vector/text work;
  `eventual` bounds it and can briefly return hits whose tenant, label or
  property has since changed. Writes always search strongly.

## Traversal Steps

```text
.Out("FOLLOWS") .In("FOLLOWS") .Both("RELATED")
.OutE("FOLLOWS") .InE("FOLLOWS") .BothE("RELATED")
.OutN() .InN() .OtherN()

.Has("status", "active")            // literals only
.HasLabel("User")
.HasKey("externalId")
.Where(helix.PredEq("tenantId", tenant))
.Dedup()
.Within("users")
.Without("blocked")
.EdgeHas("weight", helix.F64(1.0))  // accepts a ParamRef
.EdgeHasLabel("FOLLOWS")

.Limit(10)
.Limit(limitParam)
.Skip(offsetParam)
.Range(start, end)
.As("x") .Store("x") .Select("x") .Inject("x")
.Bind("service")   // row-local binding; enters row mode

.OrderBy("createdAt", helix.OrderDesc)
.OrderByMultiple(
    helix.Ordering{Property: "score", Order: helix.OrderDesc},
    helix.Ordering{Property: "name", Order: helix.OrderAsc},
)
```

Filter with `helix.PredIsNotNull(prop)` before `OrderBy` when missing values
must not lead.

### Shortest Path

Unweighted BFS, a source step on `helix.G()`:

```text
helix.G().ShortestPath(helix.NodeVar("from"), helix.NodeVar("to"), 6)
helix.G().ShortestPath(helix.NodeID(1), helix.NodeParam(target.Name), 4,
    helix.ShortestPathOptions{Label: "FOLLOWS", Direction: helix.ShortestPathBoth})
```

Returns one array of node IDs from source to target (`[0, 1, 2]`), or `[]` when
no path exists within `maxDepth`. Direction defaults to `helix.ShortestPathOut`;
`maxDepth` must be positive.

### Terminals And Projection

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

`ProjectFromEndpoint(prop, alias)` serializes to
`{"source":"$from.<prop>","alias":"<alias>"}`; `ProjectToEndpoint` to
`{"source":"$to.<prop>","alias":"<alias>"}`.

### Row Bindings

```text
.ProjectBindings(
    helix.ProjectNamedBinding("service", "$id", "service_id"), // named binding
    helix.ProjectCurrentBinding("$id", "current_id"),          // current element
    helix.ProjectBindingCoalesce([]helix.BindingValueRef{      // first present non-null
        helix.NamedBindingValue("deployment", "$id"),
        helix.NamedBindingValue("owner", "$id"),
    }, "workload_id"),
)
.ProjectDistinctBindings(/* same args; dedups identical rows */)
```

- `.Project(...)` sees only the final stream; to combine values from different
  hops, `.Bind(name)` along the path and finish with `.ProjectBindings(...)`
  (keeps duplicates) or `.ProjectDistinctBindings(...)`.
- A binding a row never reached is absent from its object: decode as pointers.
- After `.Bind`, `EdgeProperties` is also rejected
  (`invalid_after_bind_operation`); finish with `ProjectBindings`, `Count` or
  `Exists`.
- Constructors: `helix.Binding(name)` / `helix.CurrentBinding()` →
  `BindingTarget`; `helix.ProjectBinding(target, source, alias)`,
  `ProjectNamedBinding`, `ProjectCurrentBinding`, `ProjectBindingCoalesce` →
  `BindingProjection`; `NamedBindingValue` / `CurrentBindingValue` →
  `BindingValueRef`. `source` accepts stored properties and `$id`, `$label`,
  `$from`, `$to`, `$distance`, `$score`.

### Writes

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

`AddE` creates one edge per (source, target) pair on every run (not
idempotent); an empty target fails the whole batch. Guard re-runs with
`VarAsIf` (e.g. `VarEmpty` on an existing-edge lookup).

### Branching And Aggregation

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

- `Repeat` emit: none returns only the last hop; `EmitAfter()` = Gremlin
  postfix `.emit()`; `EmitBefore()` each hop's input; `EmitIf(pred)` matching
  hop outputs. Bound every repeat with `WithTimes` or `UntilPred`.
- `.Bind` inside a branch tags the element reached on that arm.

### Indexes

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

Range indexes default to ascending (`helix.RangeIndexAsc`); use
`helix.RangeIndexDesc` for newest-first or high-score-first scans.

The DDL variable is a receipt object:

| `kind` | Fields | Next step |
| --- | --- | --- |
| `accepted` | `operation_id`, `index_id`, `generation` | Poll the operation |
| `existing_operation` | `operation_id` | Same build in flight; poll it |
| `already_active` | `index_id`, `generation` | Done |

```text
helix.G().GetIndexOperation(operationID)    // read; ID is a lowercase UUID string
helix.G().RetryIndexOperation(operationID)  // write
helix.G().AbortIndexOperation(operationID)  // write
helix.UnmarshalIndexDdlReceipt(raw)         // -> IndexDdlAccepted | IndexDdlExistingOperation | IndexDdlAlreadyActive
helix.UnmarshalIndexOperationStatus(raw)    // -> *IndexOperationQueued | *Running | *Blocked | *Succeeded | *Aborted (pointers; receipts are values)
```

- `IndexOperationBlocked.BlockerCode`: `uniqueness_violation`,
  `invalid_source_data`, `oversized_entity`, ...; it does not resume on its own.
- A unique index rejects duplicate writes with `unique_constraint_violation`.
  While it builds, only values already claimed (by a scanned entity or a write
  since the build started) are rejected; a duplicate of a not-yet-scanned
  entity's value blocks the build when the scan reaches it.
- `index_busy`: another lifecycle operation on the index is running.
  `index_build_blocked`: a write would overflow a blocked build's queue; retry
  or abort the build first.

## Predicates And Expressions

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
helix.PredContainsExpr("bio", ref.Expr())
helix.PredIsIn("status", statusesParam)
helix.PredAnd(preds...)
helix.PredOr(preds...)
helix.PredNot(pred)
helix.PredCompare(left, helix.CompareGt, right)
```

- Source predicates (`SourcePredicate` = `Predicate`): `SourceEq`, `SourceNeq`,
  `SourceGt`, `SourceGte`, `SourceLt`, `SourceLte`, `SourceHasKey`,
  `SourceStartsWith`, `SourceEndsWith`, `SourceContains`, `SourceContainsExpr`,
  `SourceIsIn`, `SourceIsNull`, `SourceIsNotNull`, `SourceBetween`,
  `SourceCompare`, `SourceAnd`, `SourceOr`, `SourceNot`.
- `Eq`, `Neq`, `Gt`, `Gte`, `Lt`, `Lte`, `Between`, `IsIn` take `any`: a Go
  string, number, bool or `helix.PropertyValue` is inlined; a `helix.ParamRef`
  or `helix.Expr` is parameterized. `StartsWith`, `EndsWith`, `Contains` take a
  Go `string`. No parameterized prefix/suffix builder exists in Go.

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

`ExprCase` (Cypher `CASE`) goes in `helix.ProjectExpr` or `SetProperty`:

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
client, err := helix.NewClient(endpoint, helix.WithAPIKey(key), helix.WithDatabaseID(dbID)) // (main)

helix.WriterOnly()             // X-Helix-Require-Writer: true
helix.WarmOnly()               // X-Helix-Warm: true (reads only)
helix.AwaitDurability(false)   // X-Helix-Await-Durable: false (writes only)
```

- `WithAPIKey` / `ClearAPIKey` are synchronized, so `Exec` is safe while other
  goroutines rotate the key.
- `Exec` posts to `/v2/query` and decodes with `json.Decoder.UseNumber()`.
- `AwaitDurability(false)` returns once the write is applied on the writer;
  `AwaitDurability(true)` restates the default.
- Response: one JSON object keyed by the `.Returning(...)` names; index DDL and
  lifecycle steps return an object.
- `WarmOnly()` on Helix Cloud fans the read out to every eligible backend and
  returns `204 No Content` with no payload once one target succeeds; add
  `WriterOnly()` to target only the authoritative writer. A local server
  returns the normal 200.

```go
type FindUserResponse struct {
	User    []UserRow `json:"user"`    // [] when missing; take User[0] after a length check
	Friends []UserRow `json:"friends"`
	Count   int64     `json:"count"`
}
```

## Errors

`*helix.HelixError`: `Kind: helix.ErrorRemote`, `Code` (open-string
`helix.QueryErrorCode`, body `error`), `Details` (`msg`), `StatusCode`;
(main) `Retryable *bool` (body `retryable`), `helix.IsRetryable(err)`,
`helix.IsConflict(err)` (`transaction_conflict` only),
`helix.IsIndexBackpressure(err)`.

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

- Retry retryable classes with bounded backoff and jitter; rebuild a write from
  freshly read state when it depends on what it read.
- `unique_constraint_violation`: report a duplicate or pick another key; from an
  upsert's create branch, re-run the upsert once.
- `index_busy` / `index_build_blocked`: resolve the index operation first.
- Helix Cloud gateway codes: `query_timeout` (408), `rate_limited` (429, honor
  `Retry-After`), `payload_too_large` (413, 2 MiB), `write_outcome_unknown`
  (503). The SDK does not expose `Retry-After`; use a custom HTTP transport when
  the exact delay matters.

## Cypher And SQL (main)

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

- Same `ExecOption`s as `Exec`. Over HTTP, SQL `parameters` may be a list for
  `?`, plus `mappings`.
- A failed statement returns
  `{"error": "<category>", "msg", "details": {"detail", "phase", "span"}}`, e.g.
  `unsupported_feature` with `details.detail` `merge`.
