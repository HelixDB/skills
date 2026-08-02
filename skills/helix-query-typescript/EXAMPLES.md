# Helix Query Authoring — TypeScript Examples

Each numbered scenario corresponds 1:1 with `../helix-query-rust/EXAMPLES.md`.
When moving between TypeScript and Rust, open the same scenario in each file, then
serialize either builder for the canonical direct JSON request.

All snippets assume `import { ... } from "@helix-db/helix-db";`. Query
builders are plain functions returning a `ReadBatch` or `WriteBatch`. Build a
direct request with
`builder().toQueryRequest(params, values, { queryName: "route_name" })` and
execute it with `await Client.server(url).query<R>(request).send()`. Use
`toQueryJson` to inspect the exact `POST /v2/query` body.

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

## 4. Vector search with tenant + distance in projection

```ts
const nearestParams = defineParams({
  tenantId: param.string(),
  queryVector: param.array(param.f64()),
  k: param.i64(),
});

function nearestDocuments(p = nearestParams) {
  return readBatch()
    .varAs(
      "hits",
      g()
        .vectorSearchNodesWith(
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

Project `$distance` before any `.out`/`.in`/`.both` — traversal off the hit stream drops the distance metadata.

---

## 5. BM25 text search with post-filter

```ts
const docSearchParams = defineParams({ tenantId: param.string(), q: param.string() });

function documentSearch(p = docSearchParams) {
  return readBatch()
    .varAs(
      "results",
      g()
        .textSearchNodesWith("Document", "body", PropertyInput.param("q"), 50, PropertyInput.param("tenantId"))
        .where(Predicate.eq("published", true))
        .limit(10)
        .project([
          PropertyProjection.renamed("$id", "id"),
          PropertyProjection.new("title"),
          PropertyProjection.renamed("$score", "score"),
        ]),
    )
    .returning(["results"]);
}
```

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

Use this when an edge list needs stable source/target resource ids. It keeps one
output row per edge and avoids traversing to every endpoint node.

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

The direct request nests this projection under the `project` root. Endpoint
helpers serialize their sources as `$from.resource_id` and `$to.resource_id`.

---

## Row bindings: multi-hop correlation

Use this when one output row must combine values captured at **different hops**
of a single path — `.project(...)` only sees the final stream. Tag elements with
`.bind(name)` as you pass them, then assemble rows with
`.projectDistinctBindings(...)` (or `.projectBindings(...)` to keep duplicates).
`coalesce` picks the first present non-null reference.

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

This binding projection is part of a normal direct request and is
available in the Python v3 SDK.

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
    .varAs(
      "newUser",
      g()
        .addN("User", {
          userId: PropertyInput.param("userId"),
          name: PropertyInput.param("name"),
          createdAt: PropertyInput.expr(Expr.timestamp()),
        })
        .project([PropertyProjection.renamed("$id", "id")]),
    )
    .varAs("link", g().n(NodeRef.param("postId")).addE("CREATED_BY", NodeRef.var("newUser"), {}))
    .returning(["newUser", "link"]);
}
```

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

Inside `body`, parameter names resolve against each object's fields.
`param.array(param.object(param.value()))` records a structured array-of-object
schema matching Rust `QueryParamType::Array(Box::new(QueryParamType::Object))`.

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

Dotted property lookup is exact-first and scan-only in the current runtime. Keep indexed/searchable fields top-level; use nested objects for metadata you can scan or project. Arrays are opaque, so there is no `metadata.tags.0` syntax.

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

`statuses` records as an array-of-string schema and `since` as
`"date_time"`. Pass a `DateTime`; the request normalizes to UTC RFC3339 with
millisecond precision before serializing.

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

Drop an index with `g().dropIndex(IndexSpec....)`. The convenience methods (`createVectorIndexNodes`, etc.) produce identical wire output — prefer `createIndexIfNotExists` + `IndexSpec` for consistency with the dynamic JSON reference.

---

## 18. Warm a read route

Warming uses the *same* query; `.warmOnly()` sets the `X-Helix-Warm: true` header on the client. Build the request and let callers decide to warm:

```ts
import { Client } from "@helix-db/helix-db";

const client = new Client("https://helix.example.com").withApiKey(apiKey);
const request = userById().toQueryRequest(userByIdParams, { userId: "u-42" });

// .warmOnly() sets X-Helix-Warm: true. Writes reject warming.
await client.requestBuilder().warmOnly().query(request).send();
```

Warming is strictly read-only; a `WriteBatch` with `X-Helix-Warm: true` is rejected by the gateway.

---

The v3 SDK does not expose stored routes, registration, or query-bundle APIs.
