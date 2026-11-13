# Helix Go SDK Cheat Sheet

Quick reference for direct HelixDB v3 queries in Go. Release set, published
package gaps and shared contracts (empty `[]` returns, `{"$id"}` elements,
durability, ordering, `Optional`, index receipts, search limits):
`source-canon.md`. Errors: `error-handling.md`.

```bash
go get github.com/helixdb/helix-db/sdks/go@latest   # published v0.3.1
```

```go
import helix "github.com/helixdb/helix-db/sdks/go" // no /v3 suffix
```

## Core Shape

```go
func FindUsers(tenantID string, limit int64) helix.Request {
	q := helix.ReadQuery("find_users")
	tenant := q.ParamString("tenant_id", tenantID)
	maxRows := q.ParamI64("limit", limit)

	return q.
		VarAs("users", helix.G().NWithLabel("User").Where(helix.PredEq("tenantId", tenant)).Limit(maxRows).ValueMap("$id", "name")).
		Returning("users")
}
```

## Execute

```text
client, err := helix.NewClient("https://helix.example.com", helix.WithAPIKey("hx_secret"))
var out FindUsersResponse
err = client.Exec(ctx, FindUsers("acme", 25), &out)
```

Decode row variables as slices and take `[0]` after a length check. A
zero-argument `.Returning()` produces `{}`.

## Do

- use `helix.ReadQuery("name")` or `helix.WriteQuery("name")`
- declare params inline (`q.ParamString`, `q.ParamI64`, `q.ParamDateTime`, ...)
  and pass the returned `ParamRef` to predicates, limits, property inputs and
  search inputs; `SourceEq("id", "foo")` / `PredEq("id", "foo")` inline `"foo"`
- execute with `client.Exec(ctx, request, &out)`
- use `helix.MarshalRequest(req)` only for tests, parity fixtures or debugging

## Do Not

- use `.With(...)`, or `WithQueryName(...)` on `ReadQuery` / `WriteQuery` builders
- pass a `ParamRef` to `.Has(...)` (fails to serialize) or to `PredStartsWith` /
  `PredEndsWith` / `PredContains` (they take `string`); use
  `.Where(helix.PredEq(...))` or `PredContainsExpr`
- bind node IDs as strings; use `q.ParamI64` / `ParamTypeI64()`
- use stored-query or bundle workflows in the v3 SDK
- call JSON serialization in normal application code
- call `.Returning()` with no names unless the `{}` response is intentional

## Common Builders

```text
helix.G().NWithLabel("User")
helix.G().NWhere(helix.SourceEq("tenantId", tenant))
helix.G().Out("FOLLOWS").Dedup().Limit(100)
helix.G().Project(helix.ProjectPropAs("$id", "id"), helix.ProjectPropAs("name", "name"))
helix.G().AddN("User", helix.Props{helix.Prop("name", nameParam)})
helix.G().SetProperty("updatedAt", updatedAtParam)
helix.G().NWithLabel("Post").OrderBy("createdAt", helix.OrderDesc).Limit(20)
helix.G().ShortestPath(helix.NodeVar("from"), helix.NodeVar("to"), 6)   // [] or node IDs
helix.G().NWithLabel("User").Bind("u").Optional(helix.Sub().Out("WORKS_AT").Bind("c")).
	ProjectBindings(helix.ProjectNamedBinding("u", "name", "name"), helix.ProjectNamedBinding("c", "name", "employer"))
helix.G().CreateIndexIfNotExists(helix.NodeUniqueEqualityIndex("User", "email")) // async: poll GetIndexOperation
```

On a `blocked` index build, fix the data, then `RetryIndexOperation` or
`AbortIndexOperation`.

## Search

```text
vector := q.ParamArray("query_vector", queryVector, helix.ParamTypeF32())
limit := q.ParamI64("limit", int64(10))
tenant := q.ParamString("tenant_id", tenantID)
tenantInput := tenant.Input()

helix.G().VectorSearchNodesWith("Document", "embedding", vector.Input(), limit.Bound(), &tenantInput)
```

Use `[]float32` for vector parameters. Literal `[]float64` values are normalized
by the SDK, but dynamic vector params should declare `ParamTypeF32()`.
`WithSearchConsistency` is `main` only; with v0.3.1 send `"search_consistency"`
over HTTP.

## Errors

`Client.Exec` returns `*helix.HelixError` with open-string `Code` (body
`error`), diagnostic `Details` and `StatusCode`. Branch on `Code`, never on
`Details`. v0.3.1 `helix.IsConflict(err)` / `helix.ErrConflict` match every
409, so never gate a retry on them; on `main`, use `helix.IsRetryable(err)`.

## Cypher And SQL

Native at `POST /v2/cypher`, `/v2/sql` and their `/explain` routes.
`client.Cypher` / `client.SQL` are `main` only; with v0.3.1 POST
`{"query", "parameters", "query_name"}` over HTTP. Hand-write the DSL for
`MERGE`, variable-length paths, `shortestPath`, `UNION`, subqueries, `FOREACH`
and search.
