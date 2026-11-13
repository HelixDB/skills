# Helix Query Authoring — TypeScript Examples

Scenarios are numbered 1:1 with `../helix-query-rust/EXAMPLES.md`; either builder
serializes to the same direct JSON request. Snippets assume
`import { ... } from "@helix-db/helix-db";`. Send with
`await Client.server(url).query<R>(builder().toQueryRequest(params, values, { queryName: "route_name" })).send()`;
`toQueryJson` shows the exact `POST /v2/query` body.

---

## 1. Count nodes matching label + predicate

```ts
function activeUserCount() {
  return readBatch()
    .varAs("active_count", g().nWithLabel("User").where(Predicate.eq("status", "active")).count())
    .returning(["active_count"]);
}

const body = activeUserCount().toQueryJson(); // no parameters
```

---

## 2. Read node by indexed property with projection

Literal form:

```ts
function userByIdLiteral() {
  return readBatch()
    .varAs(
      "user",
      g()
        .nWithLabelWhere("User", SourcePredicate.eq("userId", "u-42"))
        .project([
          PropertyProjection.renamed("$id", "id"),
          PropertyProjection.new("userId"),
          PropertyProjection.new("name"),
        ]),
    )
    .returning(["user"]);
}
```

Parameterized form (preferred):

```ts
const userByIdParams = defineParams({ userId: param.string() });

function userById(p = userByIdParams) {
  return readBatch()
    .varAs(
      "user",
      g()
        .nWithLabel("User")
        .where(Predicate.eqParam("userId", "userId"))
        .project([PropertyProjection.renamed("$id", "id"), PropertyProjection.new("name")]),
    )
    .returning(["user"]);
}

const body = userById().toQueryJson(userByIdParams, { userId: "u-42" });
```

---

## 3. Multi-hop traversal with `dedup` + `limit`

```ts
const fofParams = defineParams({ userId: param.array(param.i64()) });

function friendsOfFriends(p = fofParams) {
  return readBatch()
    .varAs(
      "fof",
      g()
        .n(NodeRef.param("userId"))
        .out("FOLLOWS")
        .out("FOLLOWS")
        .dedup()
        .limit(50)
        .values(["$id", "name"]),
    )
    .returning(["fof"]);
}

const body = friendsOfFriends().toQueryJson(fofParams, { userId: [1n, 2n] });
```

---

## 4. Vector prefiltering over traversal candidates

```ts
const nearestParams = defineParams({
  tenantId: param.string(),
  queryVector: param.array(param.f32()),
  k: param.i64(),
});

function nearestDocuments(p = nearestParams) {
  return readBatch()
    .varAs(
      "hits",
      g()
        .nWithLabel("Document")
        .where(Predicate.eqParam("tenantId", "tenantId"))
        .where(Predicate.eq("published", true))
        .vectorSearchWith(
          "Document",
          "embedding",
          PropertyInput.param("queryVector"),
          Expr.param("k"),
          PropertyInput.param("tenantId"),
        )
        .project([
          PropertyProjection.renamed("$id", "id"),
          PropertyProjection.new("title"),
          PropertyProjection.renamed("$distance", "distance"),
        ]),
    )
    .returning(["hits"]);
}
```

The predicates build the exact candidate stream before ranking; source vector search
followed by `where` can underfill top-k. Project `$distance` before any
`.out`/`.in`/`.both`.

---

## 5. Full Text Search prefiltering over traversal candidates

```ts
const docSearchParams = defineParams({ tenantId: param.string(), q: param.string() });

function documentSearch(p = docSearchParams) {
  return readBatch()
    .varAs(
      "results",
      g()
        .nWithLabel("Document")
        .where(Predicate.eqParam("tenantId", "tenantId"))
        .where(Predicate.eq("published", true))
        .textSearchWith("Document", "body", PropertyInput.param("q"), 10, PropertyInput.param("tenantId"))
        .project([
          PropertyProjection.renamed("$id", "id"),
          PropertyProjection.new("title"),
          PropertyProjection.renamed("$score", "score"),
        ]),
    )
    .returning(["results"]);
}
```

This returns exactly `k` hits when enough candidates match; source text search followed
by `where` does not.

---

## 6. `repeat` traversal with `until` + `emitAfter`

```ts
const chainParams = defineParams({ startId: param.array(param.i64()) });

function managementChain(p = chainParams) {
  return readBatch()
    .varAs(
      "chain",
      g()
        .n(NodeRef.param("startId"))
        .repeat(
          RepeatConfig.new(sub().out("REPORTS_TO"))
            .until(Predicate.eq("title", "CEO"))
            .emitAfter()
            .maxDepth(10),
        )
        .project([
          PropertyProjection.renamed("$id", "id"),
          PropertyProjection.new("name"),
          PropertyProjection.new("title"),
        ]),
    )
    .returning(["chain"]);
}
```

---

## 7. `union` of two sub-traversals

```ts
const networkParams = defineParams({ userId: param.array(param.i64()) });

function userNetwork(p = networkParams) {
  return readBatch()
    .varAs(
      "network",
      g()
        .n(NodeRef.param("userId"))
        .union([sub().out("FOLLOWS"), sub().in("FOLLOWS")])
        .dedup()
        .values(["$id", "name"]),
    )
    .returning(["network"]);
}
```

---

## 8. `choose` (conditional traversal)

```ts
const contentParams = defineParams({ userId: param.array(param.i64()) });

function userContent(p = contentParams) {
  return readBatch()
    .varAs(
      "content",
      g()
        .n(NodeRef.param("userId"))
        .choose(Predicate.eq("tier", "premium"), sub().out("HAS_PREMIUM"), sub().out("HAS_FREE"))
        .limit(20)
        .valueMap(["$id", "title"]),
    )
    .returning(["content"]);
}
```

Without the else branch, non-`premium` users would be dropped. For a per-row value use
`Expr.case` (§10).

---

## 9. `coalesce` (fallback traversal)

```ts
const teamParams = defineParams({ userId: param.array(param.i64()) });

function preferredTeam(p = teamParams) {
  return readBatch()
    .varAs(
      "team",
      g()
        .n(NodeRef.param("userId"))
        .coalesce([sub().out("PREFERRED_TEAM"), sub().out("PRIMARY_TEAM"), sub().out("MEMBER_OF").limit(1)])
        .values(["$id", "name"]),
    )
    .returning(["team"]);
}
```

---

## 10. `project` with `Expr.case` (computed field)

```ts
function usersWithBucket() {
  return readBatch()
    .varAs(
      "users",
      g()
        .nWithLabel("User")
        .project([
          Projection.property("$id", "id"),
          Projection.property("score", "score"),
          Projection.expr(
            "bucket",
            Expr.case(
              [
                [Predicate.gte("score", 1000), Expr.val("high")],
                [Predicate.gte("score", 100), Expr.val("mid")],
              ],
              Expr.val("low"),
            ),
          ),
        ]),
    )
    .returning(["users"]);
}
```

---

## 11. Aggregation: `groupCount` and `aggregateBy`

```ts
function usersByStatus() {
  return readBatch()
    .varAs("by_status", g().nWithLabel("User").groupCount("status"))
    .returning(["by_status"]);
}

function totalRevenue() {
  return readBatch()
    .varAs("revenue", g().nWithLabel("Order").aggregateBy(AggregateFunction.Sum, "price"))
    .returning(["revenue"]);
}
```

---

## Edge Endpoint Projection

One row per edge with source/target resource ids, without traversing to each endpoint.

```ts
function listDescribesRelationships() {
  return readBatch()
    .varAs(
      "relationships",
      g()
        .eWithLabel("DESCRIBES")
        .project([
          Projection.fromEndpoint("resource_id", "from_id"),
          Projection.toEndpoint("resource_id", "to_id"),
          Projection.property("$id", "edge_id"),
          Projection.property("confidence", "confidence"),
        ]),
    )
    .returning(["relationships"]);
}
```

Endpoint sources serialize as `$from.resource_id` and `$to.resource_id`.

---

## Row bindings: multi-hop correlation

One row combining values from **different hops** (`.project(...)` only sees the final
stream). `coalesce` picks the first present non-null reference.

```ts
function serviceTopology() {
  return readBatch()
    .varAs(
      "rows",
      g()
        .nWithLabel("Service")
        .bind("service")
        .out("ROUTES_TO").bind("pod")
        .optional(sub().in("CREATES").bind("deployment"))
        .union([
          sub().in("MANAGES").bind("owner"),
          sub().out("ROUTES_TO").bind("workload"),
        ])
        .projectDistinctBindings([
          BindingProjection.binding("service", "$id", "service_id"),
          BindingProjection.binding("pod", "name", "pod_name"),
          BindingProjection.coalesce([
            BindingProjection.bindingRef("deployment", "$id"),
            BindingProjection.bindingRef("owner", "$id"),
          ], "workload_id"),
        ]),
    )
    .returning(["rows"]);
}
```

Part of a normal direct request; also available in the Python v3 SDK.

---

## 12. Write: `addN` + `addE` in one batch with cross-entry `Var` reference

```ts
const createUserParams = defineParams({
  userId: param.string(),
  name: param.string(),
  postId: param.array(param.i64()),
});

function createUserAndLinkPost(p = createUserParams) {
  return writeBatch()
    // Keep the variable a node stream: NodeRef.var() needs nodes, not a projection.
    .varAs(
      "newUser",
      g().addN("User", {
        userId: PropertyInput.param("userId"),
        name: PropertyInput.param("name"),
        createdAt: PropertyInput.expr(Expr.timestamp()),
      }),
    )
    .varAs("link", g().n(NodeRef.param("postId")).addE("CREATED_BY", NodeRef.var("newUser"), {}))
    // Project in a separate entry for the response.
    .varAs(
      "user",
      g()
        .n(NodeRef.var("newUser"))
        .project([PropertyProjection.renamed("$id", "id"), PropertyProjection.new("name")]),
    )
    .returning(["user", "link"]);
}

type CreateUserResponse = {
  user: { id: number; name: string }[];
  link: { $id: number }[]; // unprojected edges return only their ID
};
```

`addE` creates one edge per (source, target) pair every run; an empty target stream fails
the whole batch.

---

## 13. Write: upsert via `varAsIf`

```ts
const upsertParams = defineParams({ userId: param.string(), name: param.string() });

function upsertUser(p = upsertParams) {
  return writeBatch()
    .varAs("existing", g().nWithLabel("User").where(Predicate.eqParam("userId", "userId")))
    .varAsIf(
      "updated",
      BatchCondition.varNotEmpty("existing"),
      g().n(NodeRef.var("existing")).setProperty("name", PropertyInput.param("name")),
    )
    .varAsIf(
      "created",
      BatchCondition.varEmpty("existing"),
      g().addN("User", { userId: PropertyInput.param("userId"), name: PropertyInput.param("name") }),
    )
    .returning(["updated", "created"]);
}
```

Both entries are `{ "$id": number }[]`; the branch that did not run returns `[]`. Create
`IndexSpec.nodeUniqueEquality("User", "userId")` (§17) so concurrent upserts cannot both
create; the loser fails with `unique_constraint_violation`; re-run the upsert once.

---

## 14. Write: `forEachParam` over an array of objects

```ts
const bulkParams = defineParams({ data: param.array(param.object(param.value())) });

function bulkCreateUsers(p = bulkParams) {
  const body = writeBatch().varAs(
    "created",
    g().addN("User", {
      externalId: PropertyInput.param("externalId"),
      embedding: PropertyInput.param("embedding"),
    }),
  );
  return writeBatch().forEachParam("data", body).returning(["created"]);
}
```

Parameter names in `body` resolve against each object's fields.
`param.array(param.object(param.value()))` matches Rust
`QueryParamType::Array(Box::new(QueryParamType::Object))`. `created` holds only the last
iteration.

---

## 15. Nested object properties + dotted paths

```ts
function createUserWithMetadata() {
  return writeBatch()
    .varAs(
      "user",
      g()
        .addN("User", {
          userId: "u-42",
          metadata: {
            externalID: "crm-42",
            score: 20,
            tags: ["trial", 7],
          },
        })
        .valueMap(["userId", "metadata.externalID"]),
    )
    .returning(["user"]);
}

function usersByExternalId() {
  return readBatch()
    .varAs(
      "users",
      g()
        .nWithLabel("User")
        .where(Predicate.eq("metadata.externalID", "crm-42"))
        .project([
          PropertyProjection.new("userId"),
          PropertyProjection.renamed("metadata.externalID", "external_id"),
        ]),
    )
    .returning(["users"]);
}
```

Dotted paths are exact-first and scan-only (REFERENCE.md, Nested properties); keep
indexed or searchable fields top-level. Arrays are opaque: no `metadata.tags.0`.

---

## 16. Typed-array parameter + `DateTime` parameter

```ts
const filteredParams = defineParams({
  statuses: param.array(param.string()),
  since: param.dateTime(),
});

function usersFiltered(p = filteredParams) {
  return readBatch()
    .varAs(
      "users",
      g()
        .nWithLabel("User")
        .where(Predicate.and([Predicate.isInParam("status", "statuses"), Predicate.gteParam("createdAt", "since")]))
        .values(["$id", "status", "createdAt"]),
    )
    .returning(["users"]);
}

const body = usersFiltered().toQueryJson(filteredParams, {
  statuses: ["active", "pending"],
  since: DateTime.parseRfc3339("2026-04-05T10:00:00Z"),
});
```

`statuses` records as an array-of-string schema, `since` as `"date_time"` (UTC RFC3339,
milliseconds).

---

## 17. Write: index management

```ts
function bootstrapIndexes() {
  return writeBatch()
    .varAs("idx_userId", g().createIndexIfNotExists(IndexSpec.nodeUniqueEquality("User", "userId")))
    .varAs(
      "idx_embedding",
      g().createIndexIfNotExists(
        IndexSpec.nodeVector(
          "Document",
          "embedding",
          1536,
          VectorDistanceMetric.Cosine,
          "tenantId",
        ),
      ),
    )
    .varAs("idx_body", g().createIndexIfNotExists(IndexSpec.nodeText("Document", "body", "tenantId")))
    .returning(["idx_userId", "idx_embedding", "idx_body"]);
}
```

Drop with `g().dropIndex(IndexSpec....)`. Convenience methods (`createVectorIndexNodes`,
etc.) produce identical wire output; prefer `createIndexIfNotExists` + `IndexSpec`. Each
entry returns a receipt; wait for the build before relying on the index:

```ts
async function waitForIndex(client: Client, receiptValue: unknown): Promise<void> {
  const receipt = parseIndexDdlReceipt(receiptValue);
  if (receipt.kind === "already_active") return;
  const operationId = receipt.operation_id;
  const statusRequest = readBatch()
    .varAs("status", g().getIndexOperation(operationId))
    .returning(["status"])
    .toQueryRequest({ queryName: "index_operation_status" });
  for (;;) {
    const { status } = await client.query<{ status: unknown }>(statusRequest).send();
    const operation = parseIndexOperationStatus(status);
    if (operation.status === "succeeded") return;
    if (operation.status === "aborted") throw new Error(`index operation ${operationId} aborted`);
    if (operation.status === "blocked") {
      // Fix what blocker_code names (e.g. duplicate values for uniqueness_violation), then
      // run writeBatch().varAs("retry", g().retryIndexOperation(operationId)), or abort with
      // g().abortIndexOperation(operationId).
      throw new Error(`index build blocked: ${operation.blocker_code} ${operation.message ?? ""}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

const created = await client
  .query<Record<string, unknown>>(bootstrapIndexes().toQueryRequest({ queryName: "bootstrap_indexes" }))
  .send();
for (const receipt of Object.values(created)) await waitForIndex(client, receipt);
```

Repeating the create while the build runs returns `existing_operation` with the same
`operation_id`.

---

## 18. Warm a read route

Warming sends the *same* query with `.warmOnly()` (`X-Helix-Warm: true`):

```ts
import { Client } from "@helix-db/helix-db";

const client = new Client("http://localhost:6969");
const request = userById().toQueryRequest(userByIdParams, { userId: "u-42" });

// Helix Cloud returns 204 after a successful warm and send() resolves
// undefined; a local server returns the normal 200 body.
await client.requestBuilder<void>().warmOnly().query(request).send();
```

Cloud warms every eligible backend and discards the bodies; `.writerOnly().warmOnly()`
warms only the writer. A `WriteBatch` with `X-Helix-Warm: true` is
`400 invalid_request_option`.

---

## 19. Handle Structured Remote Errors

```ts
import { Client, HelixError, QueryRequest } from "@helix-db/helix-db";

async function sendWithRetry<R>(client: Client, request: QueryRequest, attempts = 4): Promise<R> {
  for (let attempt = 1; ; attempt++) {
    try {
      return await client.query<R>(request).send();
    } catch (cause) {
      // Only "retryable": true (transaction_conflict, request_read_view_changed,
      // stale_index_generation, index_backpressure) may succeed unchanged.
      if (!(cause instanceof HelixError) || !cause.isRetryable() || attempt >= attempts) throw cause;
      await new Promise((resolve) => setTimeout(resolve, 50 * 2 ** attempt + Math.random() * 50));
    }
  }
}

try {
  const request = upsertUser().toQueryRequest(upsertParams, { userId: "u-42", name: "Ada" }, { queryName: "upsert_user" });
  await sendWithRetry(client, request);
} catch (cause) {
  if (!(cause instanceof HelixError)) throw cause;
  if (cause.code === "unique_constraint_violation") {
    // 409 with retryable: false. Resending unchanged fails again: report the duplicate,
    // or re-run an upsert once so it takes the update branch.
  } else if (cause.statusCode === 408 || cause.statusCode === 500 || cause.code === "writer_fenced_commit_outcome_unknown") {
    // The write may have committed. Read it back by its key before resubmitting.
  } else {
    throw cause;
  }
}
```

Never retry on `isConflict()` (3.2.0: true for every 409). A write that depends on what it
read re-reads state on each attempt. Use `serverMessage`, `serverDetails` and `rawBody` for
diagnostics, preserve unfamiliar `code` strings, and never classify errors by parsing text.

---

## Shortest path

```ts
const pathParams = defineParams({ from: param.i64(), to: param.i64() });

function introductionPath(p = pathParams) {
  return readBatch()
    .varAs(
      "path",
      g().shortestPath(NodeRef.param("from"), NodeRef.param("to"), 6, {
        label: "KNOWS",
        direction: ShortestPathDirection.Both,
      }),
    )
    .returning(["path"]);
}

const body = introductionPath().toQueryJson(pathParams, { from: 1n, to: 42n });
// response: { path: [1, 7, 42] } (node IDs, source first), or { path: [] }
```

---

## Cypher or SQL instead of the DSL

Send supported statements natively (SKILL.md, Cypher and SQL):

```ts
// (main)
const result = await client.cypher(
  "MATCH (u:User) OPTIONAL MATCH (u)-[:WORKS_AT]->(c:Company) RETURN u.name AS name, c.name AS employer",
);
// { columns: ["name", "employer"], rows: [["Ada", "Acme"], ["Bob", null]] }

// 3.2.0: same route over HTTP
const response = await fetch(`${baseUrl}/v2/cypher`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query: "MATCH (u:User {userId: $id}) RETURN u.name AS name", parameters: { id: "u-42" } }),
});
```

`POST /v2/sql` takes `{ query, parameters, mappings, query_name }` (`parameters` may be a
list binding each `?` in order). Both routes have an `/explain` variant that plans without
executing.
