# Helix Go SDK Cheat Sheet

Quick reference for direct HelixDB v3 queries in Go. Release set and shared
contracts: `source-canon.md`.

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

Every row variable is a JSON array; an empty one is `[]`, single-node lookups
included, so decode slices and take `[0]` after a length check. `Count()` (`0`),
`Exists()` (`false`) and index DDL / lifecycle steps are scalars. Unprojected
elements (mutation output too) are `{"$id": N}`. A zero-argument `.Returning()`
produces `{}`. Writes wait for durability by default; `helix.AwaitDurability(false)`
skips the wait (it does not reduce conflicts, and `true` on a read is a 400).

## Do

- use `helix.ReadQuery("name")` or `helix.WriteQuery("name")`
- declare params inline with `q.ParamString`, `q.ParamI64`, `q.ParamDateTime`, and related helpers
- pass returned `ParamRef` values to predicates, limits, property inputs, and search inputs
- parameterize request-specific values; `SourceEq("id", "foo")` and `PredEq("id", "foo")` inline the literal `"foo"`
- execute with `client.Exec(ctx, request, &out)`
- use `helix.MarshalRequest(req)` only for tests, parity fixtures, or debugging

## Do Not

- do not use `.With(...)`
- do not use `WithQueryName(...)` on `ReadQuery` / `WriteQuery` builders
- do not pass a `ParamRef` to `.Has(...)` (fails to serialize) or to `PredStartsWith` / `PredEndsWith` / `PredContains` (they take `string`); use `.Where(helix.PredEq(...))` or `PredContainsExpr`
- do not bind node IDs as strings; use `q.ParamI64` / `ParamTypeI64()`
- do not use stored-query or bundle workflows in the v3 SDK
- do not call JSON serialization in normal application code
- do not call `.Returning()` with no names unless the `{}` response is intentional

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

Missing sort values come first for `OrderAsc` and last for `OrderDesc`.
`Optional` keeps the input row when the branch is empty; read the optional side
through bindings. Index DDL returns a receipt (`accepted` / `existing_operation`
/ `already_active`); poll `GetIndexOperation(id)` until `succeeded`, and on
`blocked` fix the data then `RetryIndexOperation` or `AbortIndexOperation`.

## Search

```text
vector := q.ParamArray("query_vector", queryVector, helix.ParamTypeF32())
limit := q.ParamI64("limit", int64(10))
tenant := q.ParamString("tenant_id", tenantID)
tenantInput := tenant.Input()

helix.G().VectorSearchNodesWith("Document", "embedding", vector.Input(), limit.Bound(), &tenantInput)
```

Use `[]float32` for vector parameters. Literal `[]float64` values are accepted and
normalized by the SDK, but dynamic vector params should declare `ParamTypeF32()`.

Prefiltered vector search fails when `min(k, unique candidates)` exceeds 800;
more than 1,000,000 unique candidates fails. `WithSearchConsistency` is on
`main` only; with v0.3.1 send `"search_consistency"` over HTTP.

## Errors

`Client.Exec` returns query failures as `*helix.HelixError` with open-string
`Code` (body `error`), diagnostic `Details`, and `StatusCode`. Branch on `Code`:
`transaction_conflict`, `request_read_view_changed`, `stale_index_generation`
and `index_backpressure` may be retried unchanged; `unique_constraint_violation`,
`index_busy` and `index_build_blocked` (also 409) may not. In v0.3.1,
`helix.IsConflict(err)` / `helix.ErrConflict` match every 409, so never gate a
retry on them; on `main`, use `helix.IsRetryable(err)`. A 408
`query_deadline_exceeded`, 500, or 503 `writer_fenced_commit_outcome_unknown`
may have committed a write: reconcile first. Do not parse `Details`. See
`error-handling.md`.

## Cypher And SQL

The server runs them natively at `POST /v2/cypher`, `/v2/sql` and their
`/explain` routes. `client.Cypher` / `client.SQL` exist on `main` only; with
v0.3.1 POST `{"query", "parameters", "query_name"}` over HTTP. Hand-write the DSL
for `MERGE`, variable-length paths, `shortestPath`, `UNION`, subqueries,
`FOREACH`, and search.
