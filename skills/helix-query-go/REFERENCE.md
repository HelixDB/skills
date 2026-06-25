# Helix Query Authoring - Go Reference

Use this reference to confirm Go SDK method names and request patterns. Import the module as:

```go
import helix "github.com/helixdb/helix-db/sdks/go"
```

## Request Shape

```go
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

```go
func Query(args ...) helix.Request {
	q := helix.ReadQuery("query_name")
	return q.VarAs("result", helix.G()...).Returning("result")
}
```

Pass explicit names to `.Returning(...)` for every response variable that should be decoded. Zero-arg `.Returning()` is valid only for intentional empty responses and serializes as `"returns":[]`.

## Query Builders

Both read and write builders support:

```go
.VarAs(name string, traversal *helix.Traversal)
.VarAsIf(name string, condition helix.BatchCondition, traversal *helix.Traversal)
.Returning(vars ...string) helix.Request
```

`ForEachParam` is available on both builders, but the body type follows the request
kind:

```go
read.ForEachParam(param string, body *helix.ReadBatch)
write.ForEachParam(param string, body *helix.WriteBatch)
```

Read builders reject write traversals during validation. Write builders accept read-only and write traversals.

## Inline Params

```go
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

```go
ref.Expr()  // helix.Expr
ref.Input() // helix.PropertyInput
ref.Bound() // helix.StreamBound
```

Direct Go values are literals in the inline AST. `helix.SourceEq("id", "foo")` and `helix.PredEq("id", "foo")` embed `"foo"` directly and do not create parameters. For request-specific values, declare a `q.Param*` value and pass the returned ref so the request body has a stable query shape and runtime value metadata:

```go
id := q.ParamString("id", userID)
helix.G().NWhere(helix.SourceEq("id", id))
helix.G().NWithLabel("User").Where(helix.PredEq("id", id))
```

Parameter type constructors:

```go
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

```go
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

```go
helix.ValueInput(value)
helix.ExprInput(expr)
helix.ParamInput("name")
```

Most mutation/search methods accept normal Go values, `helix.Expr`, or `helix.ParamRef` and convert to the right `PropertyInput` automatically.

## Traversal Sources

```go
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

```go
G().VectorSearchNodes(label, property, []float32{1, 0, 0}, 10, tenantValue)
G().VectorSearchNodesWith(label, property, queryVectorInput, kBound, tenantInputPtr)
G().TextSearchNodes(label, property, "graph", 10, tenantValue)
G().TextSearchNodesWith(label, property, queryTextInput, kBound, tenantInputPtr)
G().VectorSearchEdges(...)
G().TextSearchEdges(...)
```

Use `*With` variants for params:

```go
queryVector := q.ParamArray("query_vector", []float32{1, 0, 0}, helix.ParamTypeF32())
limit := q.ParamI64("limit", int64(10))
tenant := q.ParamString("tenant_id", tenantID)
tenantInput := tenant.Input()

G().VectorSearchNodesWith("Document", "embedding", queryVector.Input(), limit.Bound(), &tenantInput)
```

## Traversal Steps

Navigation:

```go
.Out("FOLLOWS") .In("FOLLOWS") .Both("RELATED")
.OutE("FOLLOWS") .InE("FOLLOWS") .BothE("RELATED")
.OutN() .InN() .OtherN()
```

Filters:

```go
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

```go
.Limit(10)
.Limit(limitParam)
.Skip(offsetParam)
.Range(start, end)
.As("x") .Store("x") .Select("x") .Inject("x")
.Bind("service")   // tag current element as a row-local binding; enters row mode
```

Terminals and projection:

```go
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

```go
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
`$id`, `$label`, `$from`, `$to`, `$distance`, `$score`. Emits a **v5** bundle.

Writes:

```go
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

```go
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

```go
.CreateIndexIfNotExists(helix.NodeEqualityIndex("User", "externalId"))
.CreateIndexIfNotExists(helix.NodeUniqueEqualityIndex("User", "email"))
.CreateIndexIfNotExists(helix.NodeRangeIndex("User", "createdAt"))
.CreateIndexIfNotExists(helix.NodeRangeDescIndex("User", "createdAt"))
.CreateIndexIfNotExists(helix.NodeRangeIndexWithDirection("User", "createdAt", helix.RangeIndexDesc))
.CreateIndexIfNotExists(helix.EdgeEqualityIndex("FOLLOWS", "since"))
.CreateIndexIfNotExists(helix.EdgeRangeDescIndex("FOLLOWS", "since"))
.CreateIndexIfNotExists(helix.EdgeRangeIndexWithDirection("FOLLOWS", "since", helix.RangeIndexDesc))
.CreateVectorIndexNodes("Document", "embedding", "tenantId")
.CreateTextIndexNodes("Document", "body", "tenantId")
.DropIndex(helix.NodeRangeIndex("User", "createdAt"))
```

Range indexes default to ascending physical order (`helix.RangeIndexAsc`). Use `helix.RangeIndexDesc` for descending indexes that primarily serve newest-first or high-score-first scans.

## Predicates And Expressions

Predicates:

```go
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

```go
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

```go
client, err := helix.NewClient("http://localhost:6969")
client, err := helix.NewClient("https://helix.example.com", helix.WithAPIKey("hx_secret"))
client = client.WithAPIKey("hx_secret")
client.ClearAPIKey()
```

`WithAPIKey` / `ClearAPIKey` synchronize access to the stored API key, so `Exec`
can read it safely while other goroutines rotate or clear the key.

Execute:

```go
err := client.Exec(ctx, FindUsers("acme", 25), &out)
err = client.Exec(ctx, CreateUser("Alice", "acme"), &created, helix.WriterOnly(), helix.AwaitDurability(true))
```

Options:

```go
helix.WriterOnly()
helix.WarmOnly()
helix.AwaitDurability(true)
```

`Exec` posts to `/v1/query`, serializes the request internally, and decodes responses with `json.Decoder.UseNumber()`.

Prefer `helix.AwaitDurability(true)` on writes: concurrent writers are more likely to hit HTTP 409 write conflicts, and awaiting durability reduces them. It does not eliminate conflicts, so callers still own retry policy.

Remote errors are returned as `*helix.HelixError` with `Kind: helix.ErrorRemote`, `Details`, and `StatusCode` set. `helix.IsConflict(err)` and `errors.Is(err, helix.ErrConflict)` detect HTTP 409 conflicts. The SDK does not retry conflicts automatically; callers should retry only when the operation is safe to replay.

```go
func ExecWithConflictRetry(ctx context.Context, client *helix.Client, build func() helix.Request, out any) error {
	for attempt := 0; attempt < 3; attempt++ {
		err := client.Exec(ctx, build(), out)
		if err == nil || !helix.IsConflict(err) || attempt == 2 {
			return err
		}
		time.Sleep(time.Duration(attempt+1) * 50 * time.Millisecond)
	}
	return nil
}
```
