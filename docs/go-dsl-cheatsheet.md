# Helix Go SDK Cheat Sheet

Quick reference for dynamic-first HelixDB queries in Go.

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

```go
client, err := helix.NewClient("https://helix.example.com", helix.WithAPIKey("hx_secret"))
var out FindUsersResponse
err = client.Exec(ctx, FindUsers("acme", 25), &out)
```

## Do

- use `helix.ReadQuery("name")` or `helix.WriteQuery("name")`
- declare params inline with `q.ParamString`, `q.ParamI64`, `q.ParamDateTime`, and related helpers
- pass returned `ParamRef` values to predicates, limits, property inputs, and search inputs
- parameterize request-specific values; `SourceEq("id", "foo")` and `PredEq("id", "foo")` inline the literal `"foo"`
- execute with `client.Exec(ctx, request, &out)`
- use `helix.MarshalRequest(req)` only for tests, parity fixtures, or debugging

## Do Not

- do not use `.With(...)`
- do not use `WithQueryName(...)`
- do not use stored-query or bundle workflows for Go v1
- do not call JSON serialization in normal application code
- do not call `.Returning()` with no names unless the response is intentionally empty

## Common Builders

```go
helix.G().NWithLabel("User")
helix.G().NWhere(helix.SourceEq("tenantId", tenant))
helix.G().Out("FOLLOWS").Dedup().Limit(100)
helix.G().Project(helix.ProjectPropAs("$id", "id"), helix.ProjectPropAs("name", "name"))
helix.G().AddN("User", helix.Props{helix.Prop("name", nameParam)})
helix.G().SetProperty("updatedAt", updatedAtParam)
```

## Search

```go
vector := q.ParamArray("query_vector", queryVector, helix.ParamTypeF32())
limit := q.ParamI64("limit", int64(10))
tenant := q.ParamString("tenant_id", tenantID)
tenantInput := tenant.Input()

helix.G().VectorSearchNodesWith("Document", "embedding", vector.Input(), limit.Bound(), &tenantInput)
```

Use `[]float32` for vector parameters. Literal `[]float64` values are accepted and
normalized by the SDK, but dynamic vector params should declare `ParamTypeF32()`.

## Conflicts

`Client.Exec` returns HTTP 409 as a `*helix.HelixError` with `StatusCode` set and `helix.ErrConflict` wrapped. It does not retry automatically; retry in application code only when safe and gate on `helix.IsConflict(err)`.
