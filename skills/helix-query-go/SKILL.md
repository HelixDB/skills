---
name: helix-query-go
description: Write and revise HelixDB queries with the Go SDK. Use when building dynamic Helix queries in Go with normal functions returning helix.Request, ReadQuery/WriteQuery, inline params, traversal builders, projections, indexes, BM25 text search, vector search, and client.Exec. Dynamic-first; do not use stored-query or bundle workflows for Go v1.
license: MIT
metadata:
  author: HelixDB
  version: 0.1.2
---

# Helix Query Authoring - Go

Write HelixDB Go SDK queries that are schema-aware, dynamic-first, and easy for application engineers to call. The Go module is `github.com/helixdb/helix-db/sdks/go`, imported as `helix`.

The primary Go workflow is different from Rust and TypeScript bundles: write ordinary Go functions that return `helix.Request`, declare parameters inline on the query builder, and execute with `client.Exec(ctx, request, &out)`.

## When To Use

Use this skill when the task is to:

- write a new Helix query in Go
- revise an existing Go query function
- add traversal, projection, pagination, BM25 text search, or vector search in Go
- use inline parameters such as `q.ParamString`, `q.ParamI64`, or `q.ParamDateTime`
- execute dynamic requests with `client.Exec(ctx, req, &out)`
- debug Go request JSON with `helix.MarshalRequest(req)`

Do not use this skill for Rust `#[register]`, TypeScript `defineQueries`, bundle generation, or hand-written dynamic JSON. Use `helix-query-rust`, `helix-query-typescript`, or `helix-query-json-dynamic` for those tasks.

## First Steps

Before writing code:

1. Inspect the local repo for labels, edge labels, properties, response structs, and existing query functions.
2. Reuse exact casing, such as `tenantId`, `externalId`, `FOLLOWS`, or `Document`.
3. Decide whether the query is read-only or write-capable.
4. Start from the narrowest practical anchor: ID, indexed property, scoped label, then broad scan.
5. Open `REFERENCE.md` for method names before inventing a builder.

## Core Rules

### 1. Return `helix.Request`

Use normal Go functions as the public query API:

```go
func FindUsers(tenantID string, limit int64) helix.Request {
	q := helix.ReadQuery("find_users")

	tenant := q.ParamString("tenant_id", tenantID)
	maxRows := q.ParamI64("limit", limit)

	return q.
		VarAs("users",
			helix.G().
				NWithLabel("User").
				Where(helix.PredEq("tenantId", tenant)).
				Limit(maxRows).
				ValueMap("$id", "name", "tenantId"),
		).
		Returning("users")
}
```

### 2. Set Query Names At Construction

- Read query: `helix.ReadQuery("find_users")`
- Write query: `helix.WriteQuery("create_user")`
- Unnamed dynamic request: `helix.ReadQuery("")`, which serializes `query_name: null`

Do not use `WithQueryName(...)` in Go v1.

### 3. Declare Params Inline

Use the `q.Param*` methods before returning:

```go
tenant := q.ParamString("tenant_id", tenantID)
limit := q.ParamI64("limit", limitValue)
since := q.ParamDateTime("created_after", sinceValue)
```

Parameter refs can be passed to predicates, bounds, property inputs, and search inputs where supported.

Important: direct Go values are inlined into the serialized AST. `helix.SourceEq("id", "foo")` and `helix.PredEq("id", "foo")` embed the string literal `"foo"`; they do not create runtime parameters and can miss server-cache hits across otherwise identical requests. For request-specific values, declare a builder parameter and pass the returned `ParamRef`:

```go
id := q.ParamString("id", userID)
helix.G().NWhere(helix.SourceEq("id", id))
```

For vector search request parameters, prefer `q.ParamArray("query_vector", values, helix.ParamTypeF32())` with `[]float32`; Helix vector values normalize to float32.

Do not add a `.With(...)` step. The runtime values and `parameter_types` metadata are inserted by the inline param methods.

### 4. Return Explicit Variables

Always pass explicit response variable names to `.Returning(...)` when rows should be decoded:

```go
return q.VarAs("users", traversal).Returning("users")
```

Use zero-arg `.Returning()` only for intentional empty responses. The SDK serializes it as `"returns":[]`, but explicit names are clearer and avoid mismatched response structs.

### 5. Execute With `Client.Exec`

```go
client, err := helix.NewClient("https://helix.example.com", helix.WithAPIKey("hx_secret"))
if err != nil {
	return err
}

var out FindUsersResponse
err = client.Exec(ctx, FindUsers("acme", 25), &out)
```

Use options only for transport behavior:

```go
err = client.Exec(ctx, CreateUser("Alice", "acme"), &created,
	helix.WriterOnly(),
	helix.AwaitDurability(true),
)
```

Prefer `helix.AwaitDurability(true)` on writes. Under concurrent writers, not awaiting durability raises the chance of HTTP 409 write conflicts; awaiting it reduces them. Leaving it off is fine for low-concurrency or read paths. Either way, `Client.Exec` does not retry HTTP 409 conflicts. Application code owns retry policy and idempotency. Remote errors carry `StatusCode`, and `helix.IsConflict(err)` or `errors.Is(err, helix.ErrConflict)` detects 409 conflicts without parsing error text.

### 6. Keep JSON Conversion Secondary

Use `helix.MarshalRequest(req)` only for tests, parity fixtures, or debugging. Do not make application code call `ToJSON`, `ToJSONString`, or equivalent helpers.

### 7. Respect Sub-Traversal Limits

`helix.Sub()` is for branch bodies inside `Repeat`, `Union`, `Choose`, `Coalesce`, and `Optional`. It currently supports walk/filter/bound operations such as `Out`, `In`, `Both`, `Where`, `Limit`, and `Count`. Put shared terminal projections like `ValueMap` or `Project` after the parent branch step.

For edge endpoint properties, prefer edge-stream `.Project(...)` with
`helix.ProjectFromEndpoint(prop, alias)` / `helix.ProjectToEndpoint(prop, alias)`
instead of traversing to every endpoint first. Keep `.EdgeProperties()` for full
edge maps and internal `$from` / `$to` node ids.

### 8. Avoid Go v1 Non-Goals

Do not use stored-query registration, query bundles, `defineQueries`, `registerRead`, `registerWrite`, or Rust-style `#[register]` patterns in Go v1.

## Validation Checklist

Before finishing:

- verify read queries use `ReadQuery` and writes use `WriteQuery`
- verify write traversals are not placed in read queries
- verify request-specific values use `q.Param*` refs instead of direct literals in predicates, source predicates, limits, inputs, or search arguments
- verify response structs match `.Returning(...)` names and projected fields
- verify vector/text search preserves tenant scope where the index is scoped
- verify conflict retries, if any, are explicit in application code and gated by `helix.IsConflict(err)`
- run `go test ./...` in the Go module when editing SDK or query code

## Companion Files

- `REFERENCE.md` - Go builder catalog and signatures.
- `EXAMPLES.md` - canonical Go query functions for reads, writes, search, branching, and execution.
