# Helix Query Authoring - Go Examples

All snippets assume:

```go
import helix "github.com/helixdb/helix-db/sdks/go"
```

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
	ID       int64  `json:"$id"`
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

```go
type CreateUserResponse struct {
	User []UserRow `json:"user"`
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

var created CreateUserResponse
err := client.Exec(ctx, CreateUser("Alice", "acme"), &created, helix.WriterOnly(), helix.AwaitDurability(true))
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

## 6. Vector Search With Tenant Scope

```go
func NearestDocuments(tenantID string, queryVector []float32, limit int64) helix.Request {
	q := helix.ReadQuery("nearest_documents")

	tenant := q.ParamString("tenant_id", tenantID)
	vector := q.ParamArray("query_vector", queryVector, helix.ParamTypeF32())
	k := q.ParamI64("limit", limit)
	tenantInput := tenant.Input()

	return q.
		VarAs("hits",
			helix.G().
				VectorSearchNodesWith("Document", "embedding", vector.Input(), k.Bound(), &tenantInput).
				Project(
					helix.ProjectPropAs("$id", "id"),
					helix.ProjectPropAs("title", "title"),
					helix.ProjectPropAs("$distance", "distance"),
				),
		).
		Returning("hits")
}
```

Project `$distance` before navigating off the search hit stream.

## 7. Text Search

```go
func SearchDocuments(tenantID string, query string) helix.Request {
	q := helix.ReadQuery("search_documents")

	tenant := q.ParamString("tenant_id", tenantID)
	text := q.ParamString("query", query)
	tenantInput := tenant.Input()

	return q.
		VarAs("results",
			helix.G().
				TextSearchNodesWith("Document", "body", text.Input(), helix.BoundLiteral(50), &tenantInput).
				Where(helix.PredEq("published", true)).
				Limit(10).
				Project(
					helix.ProjectPropAs("$id", "id"),
					helix.ProjectPropAs("title", "title"),
					helix.ProjectPropAs("$distance", "score"),
				),
		).
		Returning("results")
}
```

## 8. Repeat And Branching

```go
func FriendsAndFollowers(userID int64) helix.Request {
	q := helix.ReadQuery("friends_and_followers")

	start := q.ParamArray("user_ids", []int64{userID}, helix.ParamTypeI64())

	return q.
		VarAs("network",
			helix.G().
				N(helix.NodeParam(start.Name)).
				Repeat(helix.Repeat(helix.Sub().Out("FOLLOWS")).WithTimes(2).EmitAll().WithMaxDepth(4)).
				Union(helix.Sub().Out("FOLLOWS"), helix.Sub().In("FOLLOWS")).
				Dedup().
				ValueMap("$id", "name"),
		).
		Returning("network")
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

Wire format (each tag is a `Bind` step; the terminal is `ProjectBindings`):

```json
{"Bind": "service"}
{"ProjectBindings": {
  "projections": [
    {"kind": "Property", "target": {"Binding": "service"}, "source": "$id", "alias": "service_id"},
    {"kind": "Property", "target": {"Binding": "pod"}, "source": "name", "alias": "pod_name"},
    {"kind": "Coalesce", "refs": [
      {"target": {"Binding": "deployment"}, "source": "$id"},
      {"target": {"Binding": "owner"}, "source": "$id"}
    ], "alias": "workload_id"}
  ],
  "distinct": true
}}
```

## 9. For Each Param Writes

```go
func CreateEvents(rows []map[string]any) helix.Request {
	q := helix.WriteQuery("create_events")

	q.ParamArray("rows", rows, helix.ParamTypeObject())

	body := helix.Write().VarAs("created", helix.G().AddN("Event", helix.Props{
		helix.Prop("eventId", helix.ParamInput("eventId")),
		helix.Prop("kind", helix.ParamInput("kind")),
		helix.Prop("score", helix.ParamInput("score")),
	}))

	return q.ForEachParam("rows", body).Returning("created")
}
```

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

## 11. Caller-Owned Conflict Retry

`Client.Exec` returns HTTP 409 as a `*helix.HelixError` with `StatusCode` set and `helix.ErrConflict` wrapped. It does not retry automatically; retry only when the operation is safe to replay.

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
