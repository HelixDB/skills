# Helix Query Authoring - Go Reference

Use this reference to confirm published Go SDK v0.3.1 method names and request
patterns. The module path intentionally has no `/v3` suffix:

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

Direct Go values are literals in the inline AST. `helix.SourceEq("id", "foo")` and `helix.PredEq("id", "foo")` embed `"foo"` directly and do not create parameters. For request-specific values, declare a `q.Param*` value and pass the returned ref so the request body has a stable query shape and runtime value metadata:

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
search returns at most `k`, ordered by score descending then entity ID ascending,
with partition-wide statistics; project `$score`. Pass the same tenant partition
used to construct candidates.

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

Filters:

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
rows) or `.ProjectDistinctBindings(...)` (dedups). Constructors
(`sdks/go/dsl.go:622-668`): `helix.Binding(name)` / `helix.CurrentBinding()`
build a `BindingTarget`; `helix.ProjectBinding(target, source, alias)`,
`ProjectNamedBinding`, `ProjectCurrentBinding`, and `ProjectBindingCoalesce`
build `BindingProjection`s; `NamedBindingValue` / `CurrentBindingValue` build
`BindingValueRef`s. `source` accepts stored properties and the virtual fields
`$id`, `$label`, `$from`, `$to`, `$distance`, `$score`. Binding projections
serialize inside the normal direct request.

Writes:

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

Branching and aggregation:

```text
.Repeat(helix.Repeat(helix.Sub().Out("FOLLOWS")).WithTimes(2).EmitAll().WithMaxDepth(4))
.Union(helix.Sub().Out("FOLLOWS"), helix.Sub().In("FOLLOWS"))
.Choose(pred, helix.Sub().Out("A"), helix.Sub().Out("B"))
.Coalesce(helix.Sub().Out("preferred"), helix.Sub().Out("fallback"))
.Optional(helix.Sub().Out("HAS_PROFILE"))
.Group("status")
.GroupCount("status")
.AggregateBy(helix.AggregateMean, "score")
```

`helix.Sub()` is for inline branch traversals. It currently supports `Out`, `In`,
`Both`, `Where`, `Limit`, `Count`, and `Bind` (`sdks/go/dsl.go:1191-1209`) — use
`.Bind` inside a branch to tag the element reached on that arm. Put shared
terminal projections such as `ValueMap`, `Project`, or `ProjectBindings` after
the parent `.Choose`, `.Union`, `.Coalesce`, or `.Optional` step.

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

Source predicates use `SourceEq`, `SourceNeq`, `SourceGt`, `SourceGte`, `SourceLt`,
`SourceLte`, `SourceHasKey`, `SourceStartsWith`, `SourceBetween`, `SourceAnd`, and
`SourceOr` with the same expression promotion rules.

Passing a direct string, number, bool, or `helix.PropertyValue` to a predicate inlines it. Passing a `helix.ParamRef` parameterizes it.

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

## Client

```text
client, err := helix.NewClient("http://localhost:6969")
client, err := helix.NewClient("https://helix.example.com", helix.WithAPIKey("hx_secret"))
client = client.WithAPIKey("hx_secret")
client.ClearAPIKey()
```

`WithAPIKey` / `ClearAPIKey` synchronize access to the stored API key, so `Exec`
can read it safely while other goroutines rotate or clear the key.

Execute:

```text
err := client.Exec(ctx, FindUsers("acme", 25), &out)
err = client.Exec(ctx, CreateUser("Alice", "acme"), &created, helix.WriterOnly(), helix.AwaitDurability(true))
```

Options:

```text
helix.WriterOnly()
helix.WarmOnly()
helix.AwaitDurability(true)
```

`Exec` posts to `/v2/query`, serializes the request internally, and decodes responses with `json.Decoder.UseNumber()`.

Only empty declared returns use inferred shapes. At-most-one empties are JSON
`null`; collection, fold, and mutation empties are `[]`; scalar terminals keep
`0` and `false`; an empty returns list produces `{}`. Populated values retain
their existing representation, including the one-element array for an
at-most-one traversal.

Use slices for both row categories and preserve their decoded state:

```go
type FindUserResponse struct {
	User    []UserRow `json:"user"`    // nil for null; one element when present
	Friends []UserRow `json:"friends"` // non-nil empty slice for []
	Count   int       `json:"count"`
}
```

Do not normalize a nil at-most-one slice to an empty slice before contract
validation. Use `*[]T` or `json.RawMessage` only when the application needs
additional presence tracking.

`helix.WarmOnly()` is read-only. Helix Cloud fans the read out to every eligible
backend and returns `204 No Content` with no query payload after at least one
target succeeds; combine it with `helix.WriterOnly()` to target only the
authoritative writer. The published Go v0.3.1 client accepts only HTTP 200, so
it currently returns a remote `*helix.HelixError` for the Cloud `204`; use
`helix query` or direct HTTP for Cloud warming. Standalone `v0.0.4` warming
returns the normal 200 response.

Prefer `helix.AwaitDurability(true)` on writes: concurrent writers are more likely to hit HTTP 409 write conflicts, and awaiting durability reduces them. It does not eliminate conflicts, so callers still own retry policy and must reload current state before rebuilding a conflicting mutation.

`helix.QueryErrorCode` is an open string type. Remote errors are returned as
`*helix.HelixError` with `Kind: helix.ErrorRemote`, `Code`, `Details`, and
`StatusCode`. Canonical Helix HTTP `error`/`msg` populates `Code` from `error`;
legacy `error`/`code` is also decoded without rejecting unknown future codes.
In v0.3.1, a generic noncanonical `message`/`code` remote body is retained as raw
`Details` but does not populate `Code`; keep status-aware fallback handling and
do not call that generic shape the gateway contract. `helix.IsConflict(err)` and
`errors.Is(err, helix.ErrConflict)` retain HTTP 409 detection; compare `Code`
with `helix.QueryErrorCode("transaction_conflict")` when you need the Helix
classification. Reconcile a `query_timeout` write before resubmitting. Go
v0.3.1 does not expose `Retry-After`; use a custom HTTP transport or direct HTTP
when the exact Cloud delay is required. Never parse `Details`. See
`../../docs/error-handling.md`.

## Published Release Scope

Version v0.3.1 distributes the server query builder and HTTP client. A standard
module install does not include generated native bindings: embedded
constructors return `ErrNativeBindingsUnavailable`, and `Client.Graph` returns
`ErrNativeGraphUnavailable`. The `helixdb_uniffi` build tag is only for callers
that separately generate and link compatible bindings and native libraries.

```text
func ExecWithConflictRetry(ctx context.Context, client *helix.Client, reloadAndBuild func(context.Context) (helix.Request, error), out any) error {
	for attempt := 0; attempt < 3; attempt++ {
		request, err := reloadAndBuild(ctx)
		if err != nil {
			return err
		}
		err = client.Exec(ctx, request, out)
		var helixErr *helix.HelixError
		isTransactionConflict := errors.As(err, &helixErr) && helixErr.Code == helix.QueryErrorCode("transaction_conflict")
		if err == nil || !helix.IsConflict(err) || !isTransactionConflict || attempt == 2 {
			return err
		}
		time.Sleep(time.Duration(attempt+1) * 50 * time.Millisecond)
	}
	return nil
}
```
