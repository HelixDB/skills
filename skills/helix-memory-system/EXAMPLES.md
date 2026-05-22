# Helix Memory System — TypeScript Examples

Complete, runnable `@helixdb/enterprise-ql` snippets for the full memory lifecycle. This is the **default** path so the whole app stays in TypeScript. The Rust equivalents are in `EXAMPLES.rust.md`. The data model and index bootstrap are in `REFERENCE.md`.

Each query function is plain; call it and `.toDynamicJson(params, values)` to get the body for `POST /v1/query` (or `helix query dev --json '<body>'`). Send the resulting string straight to the gateway.

```ts
import {
  g, readBatch, writeBatch, defineParams, param,
  NodeRef, SourcePredicate, Predicate, Expr, CompareOp,
  IndexSpec, Projection, BatchCondition,
} from "@helixdb/enterprise-ql";
```

Throughout: `EMBED_DIM`-length vectors are produced by the app's embedding call; `userId` is always passed as the search `tenantValue`; every read filters `deletedAt IsNull`.

---

## 1. Bootstrap indexes (run once)

```ts
function bootstrapMemoryIndexes() {
  return writeBatch()
    .varAs("userId",     g().createIndexIfNotExists(IndexSpec.nodeUniqueEquality("User", "userId")))
    .varAs("memoryId",   g().createIndexIfNotExists(IndexSpec.nodeUniqueEquality("Memory", "memoryId")))
    .varAs("memUserId",  g().createIndexIfNotExists(IndexSpec.nodeEquality("Memory", "userId")))
    .varAs("memVector",  g().createVectorIndexNodes("Memory", "embedding", "userId"))
    .varAs("memText",    g().createTextIndexNodes("Memory", "content", "userId"))
    .varAs("catName",    g().createIndexIfNotExists(IndexSpec.nodeUniqueEquality("Category", "name")))
    .varAs("entName",    g().createIndexIfNotExists(IndexSpec.nodeEquality("Entity", "name")))
    .varAs("sessId",     g().createIndexIfNotExists(IndexSpec.nodeUniqueEquality("Session", "sessionId")))
    .returning(["memVector", "memText"]);
}

// const body = bootstrapMemoryIndexes().toDynamicJson(); // no params
```

---

## 2. Generation — read-then-write dedup

A similarity threshold can't be a batch condition, so the app reads the nearest neighbour first, then decides.

**2a. Read nearest existing memory for this user.**

```ts
const nearestParams = defineParams({
  userId: param.string(),
  embedding: param.array(param.f64()),
});

function nearestMemory(p = nearestParams) {
  return readBatch()
    .varAs(
      "nearest",
      g()
        .vectorSearchNodesWith("Memory", "embedding", p.embedding, 1, p.userId)
        .where(Predicate.isNull("deletedAt"))
        .project([
          Projection.property("memoryId", "memoryId"),
          Projection.property("$distance", "distance"),
        ]),
    )
    .returning(["nearest"]);
}

// App logic:
//   const { nearest } = await runQuery(nearestMemory().toDynamicJson(nearestParams, { userId, embedding }));
//   if (nearest[0] && nearest[0].distance < DEDUP_THRESHOLD) reinforce(nearest[0].memoryId);
//   else createMemory(...);
```

**2b. Create a new memory + ownership edge** (when no near-duplicate exists).

```ts
const createParams = defineParams({
  userId: param.string(),
  memoryId: param.string(),
  content: param.string(),
  embedding: param.array(param.f64()),
  kind: param.string(),
  salience: param.f64(),
  sessionId: param.string(),
});

function createMemory(p = createParams) {
  return writeBatch()
    .varAs("user", g().nWithLabelWhere("User", SourcePredicate.eq("userId", p.userId)))
    .varAs(
      "mem",
      g().addN("Memory", {
        memoryId: p.memoryId,
        userId: p.userId,
        content: p.content,
        embedding: p.embedding,
        kind: p.kind,
        salience: p.salience,
        accessCount: 0,
        createdAt: Expr.timestamp(),
        updatedAt: Expr.timestamp(),
        lastAccessedAt: Expr.timestamp(),
        sourceSessionId: p.sessionId,
      }),
    )
    .varAs("own", g().n(NodeRef.var("user")).addE("OWNS", NodeRef.var("mem"), {}))
    .returning(["mem"]);
}
```

**2c. Idempotent upsert by `memoryId`** (single batch — catches exact repeats without a read round-trip).

```ts
const upsertParams = defineParams({
  userId: param.string(),
  memoryId: param.string(),
  content: param.string(),
  embedding: param.array(param.f64()),
  kind: param.string(),
  salience: param.f64(),
});

function upsertMemory(p = upsertParams) {
  return writeBatch()
    .varAs("existing", g().nWithLabelWhere("Memory", SourcePredicate.eq("memoryId", p.memoryId)))
    .varAsIf(
      "updated",
      BatchCondition.varNotEmpty("existing"),
      g()
        .n(NodeRef.var("existing"))
        .setProperty("content", p.content)
        .setProperty("embedding", p.embedding)   // re-embed alongside content
        .setProperty("updatedAt", Expr.timestamp()),
    )
    .varAsIf(
      "created",
      BatchCondition.varEmpty("existing"),
      g().addN("Memory", {
        memoryId: p.memoryId,
        userId: p.userId,
        content: p.content,
        embedding: p.embedding,
        kind: p.kind,
        salience: p.salience,
        accessCount: 0,
        createdAt: Expr.timestamp(),
        updatedAt: Expr.timestamp(),
        lastAccessedAt: Expr.timestamp(),
      }),
    )
    .returning(["updated", "created"]);
}
```

> `BatchCondition` is imported from `@helixdb/enterprise-ql`.

---

## 3. Categorisation — upsert + link (topic, entity, kind)

Upsert the `Category` by unique `name`, then link the memory to whichever variable got populated. Same shape works for `Entity`/`MENTIONS`.

```ts
const categoriseParams = defineParams({
  memoryId: param.string(),
  category: param.string(),
  entity: param.string(),
  kind: param.string(),
});

function categoriseMemory(p = categoriseParams) {
  return writeBatch()
    .varAs("mem", g().nWithLabelWhere("Memory", SourcePredicate.eq("memoryId", p.memoryId)).setProperty("kind", p.kind))
    // --- Category upsert ---
    .varAs("cat", g().nWithLabelWhere("Category", SourcePredicate.eq("name", p.category)))
    .varAsIf("catNew", BatchCondition.varEmpty("cat"), g().addN("Category", { name: p.category }))
    .varAsIf("linkCat",    BatchCondition.varNotEmpty("cat"),    g().n(NodeRef.var("mem")).addE("IN_CATEGORY", NodeRef.var("cat"), {}))
    .varAsIf("linkCatNew", BatchCondition.varNotEmpty("catNew"), g().n(NodeRef.var("mem")).addE("IN_CATEGORY", NodeRef.var("catNew"), {}))
    // --- Entity upsert ---
    .varAs("ent", g().nWithLabelWhere("Entity", SourcePredicate.eq("name", p.entity)))
    .varAsIf("entNew", BatchCondition.varEmpty("ent"), g().addN("Entity", { name: p.entity }))
    .varAsIf("mentions",    BatchCondition.varNotEmpty("ent"),    g().n(NodeRef.var("mem")).addE("MENTIONS", NodeRef.var("ent"), {}))
    .varAsIf("mentionsNew", BatchCondition.varNotEmpty("entNew"), g().n(NodeRef.var("mem")).addE("MENTIONS", NodeRef.var("entNew"), {}))
    .returning(["mem"]);
}
```

---

## 4. Updating — reinforce on access

```ts
const reinforceParams = defineParams({ memoryId: param.string() });

function reinforceMemory(p = reinforceParams) {
  return writeBatch()
    .varAs(
      "mem",
      g()
        .nWithLabelWhere("Memory", SourcePredicate.eq("memoryId", p.memoryId))
        .setProperty("lastAccessedAt", Expr.timestamp())
        .setProperty("accessCount", Expr.prop("accessCount").add(Expr.val(1)))
        .setProperty("salience", Expr.prop("salience").add(Expr.val(0.1))),
    )
    .returning(["mem"]);
}
```

---

## 5. Correct / supersede — new memory invalidates an old one

```ts
const supersedeParams = defineParams({
  newId: param.string(),
  oldId: param.string(),
  reason: param.string(),
});

function supersedeMemory(p = supersedeParams) {
  return writeBatch()
    .varAs("old", g().nWithLabelWhere("Memory", SourcePredicate.eq("memoryId", p.oldId)))
    .varAs("new", g().nWithLabelWhere("Memory", SourcePredicate.eq("memoryId", p.newId)))
    .varAs("link", g().n(NodeRef.var("new")).addE("SUPERSEDES", NodeRef.var("old"), { reason: p.reason, at: Expr.timestamp() }))
    .varAs("invalidate", g().n(NodeRef.var("old")).setProperty("validTo", Expr.timestamp()))
    .returning(["link", "invalidate"]);
}
```

> Keeps the old memory for audit. To also hide it from recall, add `.setProperty("deletedAt", Expr.timestamp())` to the `invalidate` traversal.

---

## 6. Soft-delete (forget, reversibly)

```ts
const softDeleteParams = defineParams({ memoryId: param.string() });

function softDeleteMemory(p = softDeleteParams) {
  return writeBatch()
    .varAs("mem", g().nWithLabelWhere("Memory", SourcePredicate.eq("memoryId", p.memoryId)).setProperty("deletedAt", Expr.timestamp()))
    .returning(["mem"]);
}
```

---

## 7. Decay sweep — soft-delete weak, stale, rarely-used memories

Anchor on the user's index, then filter. Run on a schedule.

```ts
const decayParams = defineParams({
  userId: param.string(),
  cutoff: param.dateTime(),       // e.g. now - 30 days
  minSalience: param.f64(),       // e.g. 0.2
  minAccess: param.i64(),         // e.g. 2
});

function decaySweep(p = decayParams) {
  return writeBatch()
    .varAs(
      "decayed",
      g()
        .nWithLabelWhere("Memory", SourcePredicate.eq("userId", p.userId))
        .where(
          Predicate.and([
            Predicate.isNull("deletedAt"),
            Predicate.compare(Expr.prop("lastAccessedAt"), CompareOp.Lt, Expr.param("cutoff")),
            Predicate.compare(Expr.prop("salience"), CompareOp.Lt, Expr.param("minSalience")),
            Predicate.compare(Expr.prop("accessCount"), CompareOp.Lt, Expr.param("minAccess")),
          ]),
        )
        .setProperty("deletedAt", Expr.timestamp()),
    )
    .returning(["decayed"]);
}
```

---

## 8. Expiry sweep — hard-delete past `expiresAt`

```ts
const expiryParams = defineParams({
  userId: param.string(),
  now: param.dateTime(),
});

function expirySweep(p = expiryParams) {
  return writeBatch()
    .varAs(
      "expired",
      g()
        .nWithLabelWhere("Memory", SourcePredicate.eq("userId", p.userId))
        .where(
          Predicate.and([
            Predicate.isNotNull("expiresAt"),
            Predicate.compare(Expr.prop("expiresAt"), CompareOp.Lt, Expr.param("now")),
          ]),
        )
        .drop(),
    )
    .returning(["expired"]);
}
```

> `drop()` removes the node. If your deployment is a multigraph and you need to guarantee no dangling edges, traverse and `dropEdgeById(...)` the incident edges first; otherwise prefer the soft-delete in Example 6.

---

## 9. Hybrid retrieval — vector + BM25, fused app-side, then graph-expanded

**9a. Two recall paths in one read batch**, both tenant-scoped, both filtering deleted.

```ts
const recallParams = defineParams({
  userId: param.string(),
  embedding: param.array(param.f64()),
  query: param.string(),
  k: param.i64(),
});

function hybridRecall(p = recallParams) {
  return readBatch()
    .varAs(
      "semantic",
      g()
        .vectorSearchNodesWith("Memory", "embedding", p.embedding, p.k, p.userId)
        .where(Predicate.isNull("deletedAt"))
        .project([
          Projection.property("memoryId", "memoryId"),
          Projection.property("content", "content"),
          Projection.property("kind", "kind"),
          Projection.property("salience", "salience"),
          Projection.property("lastAccessedAt", "lastAccessedAt"),
          Projection.property("$distance", "distance"),
        ]),
    )
    .varAs(
      "keyword",
      g()
        .textSearchNodesWith("Memory", "content", p.query, p.k, p.userId)
        .where(Predicate.isNull("deletedAt"))
        .project([
          Projection.property("memoryId", "memoryId"),
          Projection.property("content", "content"),
          Projection.property("kind", "kind"),
          Projection.property("salience", "salience"),
          Projection.property("lastAccessedAt", "lastAccessedAt"),
          Projection.property("$distance", "score"),
        ]),
    )
    .returning(["semantic", "keyword"]);
}
```

**9b. Fuse with RRF + re-rank (app-side).**

```ts
type Hit = { memoryId: string; content: string; salience: number; lastAccessedAt: number };

function fuse(semantic: Hit[], keyword: Hit[], k = 60): Hit[] {
  const score = new Map<string, { hit: Hit; s: number }>();
  const add = (list: Hit[]) =>
    list.forEach((hit, i) => {
      const cur = score.get(hit.memoryId) ?? { hit, s: 0 };
      cur.s += 1 / (k + i + 1);                  // reciprocal rank, 1-based
      score.set(hit.memoryId, cur);
    });
  add(semantic);
  add(keyword);

  const now = Date.now();
  const HALFLIFE_MS = 30 * 24 * 3600 * 1000;
  return [...score.values()]
    .map(({ hit, s }) => {
      const ageDays = (now - hit.lastAccessedAt) / 86_400_000;
      const recency = Math.exp((-Math.LN2 * (now - hit.lastAccessedAt)) / HALFLIFE_MS);
      const final = 1.0 * s + 0.3 * hit.salience + 0.2 * recency;
      return { hit, final };
    })
    .sort((a, b) => b.final - a.final)
    .map((x) => x.hit);
}
```

**9c. Optional graph expansion** — pull memories that mention the same entities, scoped to the user and not deleted.

```ts
const expandParams = defineParams({
  memoryId: param.string(),
  userId: param.string(),
});

function expandViaEntities(p = expandParams) {
  return readBatch()
    .varAs(
      "related",
      g()
        .nWithLabelWhere("Memory", SourcePredicate.eq("memoryId", p.memoryId))
        .out("MENTIONS")
        .in("MENTIONS")
        .dedup()
        .where(
          Predicate.and([
            Predicate.isNull("deletedAt"),
            Predicate.compare(Expr.prop("userId"), CompareOp.Eq, Expr.param("userId")),
          ]),
        )
        .limit(10)
        .project([
          Projection.property("memoryId", "memoryId"),
          Projection.property("content", "content"),
        ]),
    )
    .returning(["related"]);
}
```

> The expansion returns the seed memory itself (it mentions its own entities); filter it out by `memoryId` in app code, or add a `Predicate.neq("memoryId", …)` once parameterised comparison for inequality is needed.
