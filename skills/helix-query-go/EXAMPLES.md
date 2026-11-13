# Helix Query Authoring - Go Examples

Snippets compile against the Go SDK source on helix-db `main`; everything here
except the noted `main only` calls also exists in the published v0.3.1 module
(`go get github.com/helixdb/helix-db/sdks/go@latest`). They assume:

```go
import helix "github.com/helixdb/helix-db/sdks/go"
```

Every row variable in a response is a JSON array (`[]` when empty), so decode
into slices.

## 1. Count Nodes Matching A Label And Predicate

```go
func ActiveUserCount() helix.Request {
	return helix.ReadQuery("active_user_count").
		VarAs("active_count", helix.G().NWithLabel("User").Where(helix.PredEq("status", "active")).Count()).
		Returning("active_count")
}
```

## 2. Read Users With Inline Params

Declare request-specific values with `q.Param*`. Passing a direct value such as `helix.SourceEq("tenantId", "acme")` or `helix.PredEq("tenantId", "acme")` inlines the literal into the AST instead of parameterizing it.

```go
type UserRow struct {
	ID       int64  `json:"id"` // ProjectPropAs("$id", "id") renames the key
	Name     string `json:"name"`
	TenantID string `json:"tenantId"`
}

type FindUsersResponse struct {
	Users []UserRow `json:"users"`
}

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
				Project(
					helix.ProjectPropAs("$id", "id"),
					helix.ProjectPropAs("name", "name"),
					helix.ProjectPropAs("tenantId", "tenantId"),
				),
		).
		Returning("users")
}
```

Use explicit names in `.Returning(...)` for values that should appear in the response. Zero-arg `.Returning()` is only for intentional empty responses.

## 3. Execute A Query

```go
func ListUsers(ctx context.Context, client *helix.Client, tenantID string, limit int64) (FindUsersResponse, error) {
	var out FindUsersResponse
	err := client.Exec(ctx, FindUsers(tenantID, limit), &out)
	return out, err
}
```

## 4. Create A Node

An unprojected mutation returns only `{"$id": N}` per element, so decode the
created node as an ID row:

```go
type CreatedRow struct {
	ID int64 `json:"$id"`
}

type CreateUserResponse struct {
	User []CreatedRow `json:"user"`
}

func CreateUser(name string, tenantID string) helix.Request {
	q := helix.WriteQuery("create_user")

	nameParam := q.ParamString("name", name)
	tenant := q.ParamString("tenant_id", tenantID)

	return q.
		VarAs("user",
			helix.G().AddN("User", helix.Props{
				helix.Prop("name", nameParam),
				helix.Prop("tenantId", tenant),
			}),
		).
		Returning("user")
}

func ExecuteCreateUser(ctx context.Context, client *helix.Client) (int64, error) {
	var created CreateUserResponse
	if err := client.Exec(ctx, CreateUser("Alice", "acme"), &created, helix.WriterOnly()); err != nil {
		return 0, err
	}
	if len(created.User) == 0 {
		return 0, errors.New("create_user returned no node")
	}
	return created.User[0].ID, nil
}
```

Writes already wait for durability; add `helix.AwaitDurability(false)` only to
trade crash durability for latency.

## 5. Explicit Create Or Update

```go
func UpsertUser(userID string, name string) helix.Request {
	q := helix.WriteQuery("upsert_user")

	id := q.ParamString("user_id", userID)
	nameParam := q.ParamString("name", name)

	return q.
		VarAs("existing", helix.G().NWithLabel("User").Where(helix.PredEq("userId", id))).
		VarAsIf("updated", helix.VarNotEmpty("existing"), helix.G().N(helix.NodeVar("existing")).SetProperty("name", nameParam)).
		VarAsIf("created", helix.VarEmpty("existing"), helix.G().AddN("User", helix.Props{
			helix.Prop("userId", id),
			helix.Prop("name", nameParam),
		})).
		Returning("updated", "created")
}
```

Exactly one of `updated` / `created` is non-empty; the skipped one is `[]`.
Create a unique equality index on the key once,
`helix.G().CreateIndexIfNotExists(helix.NodeUniqueEqualityIndex("User", "userId"))`
(see section 12), so two concurrent upserts cannot both create: the loser fails
with `unique_constraint_violation` (409, `retryable: false`). Re-run the upsert
once on that code; it then takes the update branch.

## 6. Vector Prefiltering Over Traversal Candidates

```go
func NearestDocuments(tenantID string, queryVector []float32, limit int64) helix.Request {
	q := helix.ReadQuery("nearest_documents")

	tenant := q.ParamString("tenant_id", tenantID)
	vector := q.ParamArray("query_vector", queryVector, helix.ParamTypeF32())
	k := q.ParamI64("limit", limit)

	return q.
		VarAs("hits",
			helix.G().
				NWithLabel("Document").
				Where(helix.PredEq("tenantId", tenant)).
				Where(helix.PredEq("published", true)).
				VectorSearchNodesWithin("Document", "embedding", vector, k, tenant).
				Project(
					helix.ProjectPropAs("$id", "id"),
					helix.ProjectPropAs("title", "title"),
					helix.ProjectPropAs("$distance", "distance"),
				),
		).
		Returning("hits")
}
```

The label, tenant, and publication predicates build the exact candidate stream
before vector ranking. Source vector search followed by `Where` can underfill
top-k. Project `$distance` before navigating off the search hit stream.

## 7. Full Text Search Prefiltering Over Traversal Candidates

```go
func SearchDocuments(tenantID string, query string) helix.Request {
	q := helix.ReadQuery("search_documents")

	tenant := q.ParamString("tenant_id", tenantID)
	text := q.ParamString("query", query)

	return q.
		VarAs("results",
			helix.G().
				NWithLabel("Document").
				Where(helix.PredEq("tenantId", tenant)).
				Where(helix.PredEq("published", true)).
				TextSearchNodesWithin("Document", "body", text, helix.BoundLiteral(10), tenant).
				Project(
					helix.ProjectPropAs("$id", "id"),
					helix.ProjectPropAs("title", "title"),
					helix.ProjectPropAs("$score", "score"),
				),
		).
		Returning("results")
}
```

The label, tenant, and publication predicates build the candidate stream
before BM25 ranking. This refills exactly to `k` when enough matching
candidates exist; source text search followed by `Where` does not.

## 8. Repeat And Branching

```go
func FriendsAndFollowers(userID int64) helix.Request {
	q := helix.ReadQuery("friends_and_followers")

	start := q.ParamArray("user_ids", []int64{userID}, helix.ParamTypeI64())

	return q.
		VarAs("network",
			helix.G().
				N(helix.NodeParam(start.Name)).
				Repeat(helix.Repeat(helix.Sub().Out("FOLLOWS")).WithTimes(2).EmitAfter().WithMaxDepth(4)).
				Union(helix.Sub().Out("FOLLOWS"), helix.Sub().In("FOLLOWS")).
				Dedup().
				ValueMap("$id", "name"),
		).
		Returning("network")
}
```

`EmitAfter()` returns the nodes reached at hops 1 and 2 (Gremlin's postfix
`.emit()`). `EmitAll()` would also re-emit each hop's input, duplicating rows.

## Optional Hop (Cypher `OPTIONAL MATCH`)

`Optional(sub)` keeps the input row when `sub` finds nothing, so the current
element would still be the `User`. Bind both sides and read them through
`ProjectBindings`; the `employer` key is absent for users without one.

```go
type UserEmployerRow struct {
	Name     string  `json:"name"`
	Employer *string `json:"employer"` // nil when the key is absent
}

func UsersWithEmployer() helix.Request {
	return helix.ReadQuery("users_with_employer").
		VarAs("rows",
			helix.G().
				NWithLabel("User").
				Bind("user").
				Optional(helix.Sub().Out("WORKS_AT").Bind("employer")).
				ProjectBindings(
					helix.ProjectNamedBinding("user", "name", "name"),
					helix.ProjectNamedBinding("employer", "name", "employer"),
				),
		).
		Returning("rows")
}
```

## Ordered Pagination

```go
func RecentPosts(authorID int64, offset int64, pageSize int64) helix.Request {
	q := helix.ReadQuery("recent_posts")

	author := q.ParamI64("author_id", authorID)
	skip := q.ParamI64("offset", offset)
	size := q.ParamI64("page_size", pageSize)

	return q.
		VarAs("posts",
			helix.G().
				N(helix.NodeParam(author.Name)).
				Out("WROTE").
				Where(helix.PredIsNotNull("publishedAt")).
				OrderBy("publishedAt", helix.OrderDesc).
				Skip(skip).
				Limit(size).
				Project(
					helix.ProjectPropAs("$id", "id"),
					helix.ProjectProp("title"),
					helix.ProjectProp("publishedAt"),
				),
		).
		Returning("posts")
}
```

Rows missing the sort property sort first for `OrderAsc` and last for
`OrderDesc`; the `PredIsNotNull` filter keeps unpublished drafts out entirely.
Use `OrderByMultiple(helix.Ordering{...}, ...)` for tie-breakers.

## Shortest Path

```go
type ConnectionPathResponse struct {
	Path []int64 `json:"path"` // node IDs from source to target; [] when none within maxDepth
}

func ConnectionPath(fromID int64, toID int64) helix.Request {
	q := helix.ReadQuery("connection_path")

	from := q.ParamI64("from_id", fromID)
	to := q.ParamI64("to_id", toID)

	return q.
		VarAs("path",
			helix.G().ShortestPath(helix.NodeParam(from.Name), helix.NodeParam(to.Name), 6,
				helix.ShortestPathOptions{Label: "KNOWS", Direction: helix.ShortestPathBoth}),
		).
		Returning("path")
}
```

## Edge Endpoint Projection

Use this when an edge list needs stable source/target resource ids. It keeps one
output row per edge and avoids traversing to every endpoint node.

```go
func ListDescribesRelationships() helix.Request {
	return helix.ReadQuery("list_describes_relationships").
		VarAs("relationships",
			helix.G().
				EWithLabel("DESCRIBES").
				Project(
					helix.ProjectFromEndpoint("resource_id", "from_id"),
					helix.ProjectToEndpoint("resource_id", "to_id"),
					helix.ProjectPropAs("$id", "edge_id"),
					helix.ProjectPropAs("confidence", "confidence"),
				),
		).
		Returning("relationships")
}
```

## Row Bindings: Multi-Hop Correlation

Use this when one output row must combine values captured at **different hops**
of a single path — `.Project(...)` only sees the final stream. Tag elements with
`.Bind(name)` as you pass them, then assemble rows with
`.ProjectDistinctBindings(...)` (or `.ProjectBindings(...)` to keep duplicates).

```go
func ServiceTopology() helix.Request {
	return helix.ReadQuery("service_topology").
		VarAs("rows",
			helix.G().
				NWithLabel("Service").
				Bind("service").
				Out("ROUTES_TO").Bind("pod").
				Optional(helix.Sub().In("CREATES").Bind("deployment")).
				Union(
					helix.Sub().In("MANAGES").Bind("owner"),
					helix.Sub().Out("ROUTES_TO").Bind("workload"),
				).
				ProjectDistinctBindings(
					helix.ProjectNamedBinding("service", "$id", "service_id"),
					helix.ProjectNamedBinding("pod", "name", "pod_name"),
					helix.ProjectBindingCoalesce([]helix.BindingValueRef{
						helix.NamedBindingValue("deployment", "$id"),
						helix.NamedBindingValue("owner", "$id"),
					}, "workload_id"),
				),
		).
		Returning("rows")
}
```

The binding projection serializes as the nested `project_bindings` operation in a
normal direct request.

## 9. For Each Param Writes

A variable assigned inside a `ForEachParam` body holds only the **last**
iteration's result after the loop, so returning it would report one row. Read
the created nodes back after the loop instead:

```go
func CreateEvents(rows []map[string]any, eventIDs []string) helix.Request {
	q := helix.WriteQuery("create_events")

	q.ParamArray("rows", rows, helix.ParamTypeObject())
	ids := q.ParamArray("event_ids", eventIDs, helix.ParamTypeString())

	body := helix.Write().VarAs("row", helix.G().AddN("Event", helix.Props{
		helix.Prop("eventId", helix.ParamInput("eventId")),
		helix.Prop("kind", helix.ParamInput("kind")),
		helix.Prop("score", helix.ParamInput("score")),
	}))

	return q.
		ForEachParam("rows", body).
		VarAs("created",
			helix.G().
				NWithLabel("Event").
				Where(helix.PredIsIn("eventId", ids)).
				Project(helix.ProjectPropAs("$id", "id"), helix.ProjectProp("eventId")),
		).
		Returning("created")
}
```

The read-back runs in the same write transaction and sees the new nodes. Use
`Count()` instead of `Project(...)` when only the number matters.

## 10. Inspect Request JSON In A Test

```go
func TestFindUsersRequest(t *testing.T) {
	body, err := helix.MarshalRequest(FindUsers("acme", 25))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(body, []byte(`"query_name":"find_users"`)) {
		t.Fatalf("missing query name: %s", body)
	}
}
```

## 11. Caller-Owned Retry

`Client.Exec` never retries. HTTP 409 has two classes, so retry on the code, not
the status: `transaction_conflict`, `request_read_view_changed` and
`stale_index_generation` (409) and `index_backpressure` (429) may succeed when
resent; `unique_constraint_violation`, `index_busy` and `index_build_blocked`
(409, `retryable: false`) fail again. In v0.3.1, `helix.IsConflict(err)` and
`errors.Is(err, helix.ErrConflict)` are true for every 409, so do not gate
retries on them. On `main`, `helix.IsRetryable(err)` replaces the switch below.

```go
import (
	"context"
	"errors"
	"time"

	helix "github.com/helixdb/helix-db/sdks/go"
)

func ExecWithRetry(ctx context.Context, client *helix.Client, reloadAndBuild func(context.Context) (helix.Request, error), out any) error {
	var err error
	for attempt := 0; attempt < 3; attempt++ {
		var request helix.Request
		if request, err = reloadAndBuild(ctx); err != nil {
			return err
		}
		if err = client.Exec(ctx, request, out); err == nil {
			return nil
		}
		var herr *helix.HelixError
		if !errors.As(err, &herr) || herr.Kind != helix.ErrorRemote {
			return err
		}
		switch herr.Code {
		case "transaction_conflict", "request_read_view_changed", "stale_index_generation", "index_backpressure":
		default:
			return err
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(time.Duration(attempt+1) * 50 * time.Millisecond):
		}
	}
	return err
}
```

Rebuild a write from freshly read state when it depends on what it read. A
`408 query_deadline_exceeded`, a 500, or `503
writer_fenced_commit_outcome_unknown` may have committed the write: reconcile by
an application key before resubmitting. On Helix Cloud the gateway's own
`query_timeout` (408) and `write_outcome_unknown` (503) mean the same. The SDK
does not expose `Retry-After`; use a custom HTTP transport when the exact Cloud
delay is required.

## 12. Create An Index And Wait For It

Index DDL returns a receipt immediately and builds in the background. Queries
cannot use the index until its operation succeeds.

```go
import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	helix "github.com/helixdb/helix-db/sdks/go"
)

func CreateUserEmailIndex() helix.Request {
	return helix.WriteQuery("create_user_email_index").
		VarAs("index", helix.G().CreateIndexIfNotExists(helix.NodeUniqueEqualityIndex("User", "email"))).
		Returning("index")
}

func IndexOperation(operationID string) helix.Request {
	return helix.ReadQuery("index_operation").
		VarAs("status", helix.G().GetIndexOperation(operationID)).
		Returning("status")
}

func EnsureUserEmailIndex(ctx context.Context, client *helix.Client) error {
	var created struct {
		Index json.RawMessage `json:"index"`
	}
	if err := client.Exec(ctx, CreateUserEmailIndex(), &created); err != nil {
		return err
	}
	receipt, err := helix.UnmarshalIndexDdlReceipt(created.Index)
	if err != nil {
		return err
	}
	var operationID helix.IndexOperationID
	switch r := receipt.(type) {
	case helix.IndexDdlAlreadyActive:
		return nil
	case helix.IndexDdlAccepted:
		operationID = r.OperationID
	case helix.IndexDdlExistingOperation:
		operationID = r.OperationID
	}
	for {
		var out struct {
			Status json.RawMessage `json:"status"`
		}
		if err := client.Exec(ctx, IndexOperation(string(operationID)), &out); err != nil {
			return err
		}
		status, err := helix.UnmarshalIndexOperationStatus(out.Status)
		if err != nil {
			return err
		}
		switch s := status.(type) { // statuses decode as pointers
		case *helix.IndexOperationSucceeded:
			return nil
		case *helix.IndexOperationBlocked:
			// Fix the data the blocker names, then run RetryIndexOperation in a
			// write query, or AbortIndexOperation to discard the build.
			return fmt.Errorf("index build %s blocked: %s %s", operationID, s.BlockerCode, s.Message)
		case *helix.IndexOperationAborted:
			return errors.New("index build was aborted")
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(500 * time.Millisecond):
		}
	}
}
```

Re-running the same create while the build is in flight returns
`existing_operation` with the same ID. While another lifecycle operation runs
on the index, DDL fails with `index_busy`; while a build is blocked, writes that
would overflow its queue fail with `index_build_blocked`. Both are 409 with
`retryable: false`: resolve the operation first.

## 13. Send Cypher Directly (`main` only)

The server runs Cypher and SQL natively. When the statement fits the supported
profile, send it instead of translating it. v0.3.1 has no `Cypher` method; POST
the same body to `/v2/cypher` over HTTP.

```go
func UserNames(ctx context.Context, client *helix.Client, minAge int64) (*helix.CypherResponse, error) {
	return client.Cypher(ctx, helix.CypherRequest{
		Query:      "MATCH (p:Person) WHERE p.age >= $age RETURN p.name AS name ORDER BY name",
		Parameters: map[string]any{"age": minAge},
		QueryName:  "adult_names",
	})
}
```

The response is `{"columns": ["name"], "rows": [["Ada"], ...]}`. `MERGE`,
variable-length paths, `shortestPath`, `UNION`, subqueries, `FOREACH`, and
vector or text search are rejected (`unsupported_feature`); write those with the
DSL.
