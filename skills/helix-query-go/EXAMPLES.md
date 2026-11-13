# Helix Query Authoring - Go Examples

Snippets follow the SDK source on `main`; `(main)` marks calls missing from
v0.3.1. They assume `import helix "github.com/helixdb/helix-db/sdks/go"`.

## 1. Count Nodes Matching A Label And Predicate

```go
func ActiveUserCount() helix.Request {
	return helix.ReadQuery("active_user_count").
		VarAs("active_count", helix.G().NWithLabel("User").Where(helix.PredEq("status", "active")).Count()).
		Returning("active_count")
}
```

## 2. Read Users With Inline Params

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

## 3. Execute A Query

```go
func ListUsers(ctx context.Context, client *helix.Client, tenantID string, limit int64) (FindUsersResponse, error) {
	var out FindUsersResponse
	err := client.Exec(ctx, FindUsers(tenantID, limit), &out)
	return out, err
}
```

## 4. Create A Node

Unprojected mutation output is `{"$id": N}`:

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
Create the key's unique index once
(`helix.G().CreateIndexIfNotExists(helix.NodeUniqueEqualityIndex("User", "userId"))`,
§17); a concurrent duplicate create then fails with
`unique_constraint_violation` (409, `retryable: false`). Re-run the upsert once
on that code; it takes the update branch.

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

Prefiltered search fills exactly to `k` when enough candidates match.

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

`EmitAfter()` returns the nodes reached at hops 1 and 2.

## 9. Optional Hop (Cypher `OPTIONAL MATCH`)

The `employer` key is absent for users without one.

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

## 10. Ordered Pagination

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

`PredIsNotNull` keeps unpublished drafts out. Tie-breakers:
`OrderByMultiple(helix.Ordering{...}, ...)`.

## 11. Shortest Path

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

## 12. Edge Endpoint Projection

One output row per edge, with source/target resource ids:

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

## 13. Row Bindings: Multi-Hop Correlation

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

It serializes as a nested `project_bindings` operation in a normal direct
request.

## 14. For Each Param Writes

A variable assigned inside a `ForEachParam` body holds only the **last**
iteration's result after the loop; read the created nodes back instead:

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
`Count()` when only the number matters.

## 15. Inspect Request JSON In A Test

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

## 16. Caller-Owned Retry

The `Code` switch compiles against v0.3.1 and `main`; on `main`,
`helix.IsRetryable(err)` can replace it.

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

On a may-have-committed failure (408 `query_deadline_exceeded`, 500, 503
`writer_fenced_commit_outcome_unknown`; Cloud `query_timeout`,
`write_outcome_unknown`), reconcile by an application key before resubmitting.

## 17. Create An Index And Wait For It

Queries cannot use the index until its operation succeeds.

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

Re-running the create while the build is in flight returns
`existing_operation` with the same ID.

## 18. Send Cypher Directly (main)

```go
func UserNames(ctx context.Context, client *helix.Client, minAge int64) (*helix.CypherResponse, error) {
	return client.Cypher(ctx, helix.CypherRequest{
		Query:      "MATCH (p:Person) WHERE p.age >= $age RETURN p.name AS name ORDER BY name",
		Parameters: map[string]any{"age": minAge},
		QueryName:  "adult_names",
	})
}
```

Response: `{"columns": ["name"], "rows": [["Ada"], ...]}`. Rejected constructs
fail with `unsupported_feature`; write those with the DSL.
