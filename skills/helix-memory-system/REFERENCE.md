# Helix Memory System — Reference

The data model, indexes, modality cheat-sheet, embedding rules, fusion formula, and the TypeScript ↔ Rust API mapping. Authoring rules are in `SKILL.md`; runnable queries are in `EXAMPLES.md` (TS) / `EXAMPLES.rust.md`.

## Data Model

Helix is schema-on-write for labels and properties (they exist the first time you write them) but **indexes are explicit** — create them once (Example 1) before relying on them.

### Labels

**`User`** — the owner / tenant.

| Property | Type | Index | Notes |
|---|---|---|---|
| `userId` | String | unique equality | Tenant key. The value passed as `tenantValue` in searches. |
| `name` | String | — | Optional display name. |
| `createdAt` | DateTime (epoch millis) | — | `Expr.timestamp()` at insert. |

**`Memory`** — the unit of memory.

| Property | Type | Index | Notes |
|---|---|---|---|
| `memoryId` | String | unique equality | App-generated stable id (uuid or content hash). The upsert/lookup anchor. |
| `userId` | String | equality | Tenant key, denormalised onto the node so the vector/text indexes can be tenant-scoped and reads can filter by owner. |
| `content` | String | **text (BM25), tenant_property `userId`** | The human-readable memory text. |
| `embedding` | F64Array / F32Array | **vector, tenant_property `userId`** | Client-computed embedding of `content`. Fixed dimension. |
| `kind` | String | — | `episodic` \| `semantic` \| `procedural`. |
| `salience` | F64 | — | Importance 0..1; drives re-ranking and decay. |
| `createdAt` | DateTime | — | Insert time. |
| `updatedAt` | DateTime | — | Last content/embedding change. |
| `lastAccessedAt` | DateTime | — | Bumped on reinforcement. |
| `accessCount` | I64 | — | Bumped on reinforcement. |
| `validFrom` / `validTo` | DateTime | — | Temporal validity; `validTo` set when superseded/invalidated. |
| `expiresAt` | DateTime | — | Optional TTL target for the expiry sweep. |
| `deletedAt` | DateTime | — | Soft-delete tombstone. Absent/null ⇒ live. **Every read filters `deletedAt IsNull`.** |
| `sourceSessionId` | String | — | Optional provenance pointer. |

**`Category`** — topic taxonomy. `name` (String, unique equality), `description` (String, optional).

**`Entity`** — people/places/things mentioned. `name` (String, equality), `entityType` (String, optional).

**`Session`** — episodic provenance. `sessionId` (String, unique equality), `startedAt` (DateTime).

### Edges

| Edge | From → To | Properties | Purpose |
|---|---|---|---|
| `OWNS` | User → Memory | — | Ownership; lets you list/scope a user's memories via the graph. |
| `IN_CATEGORY` | Memory → Category | `confidence` (F64, opt) | Topic categorisation. |
| `MENTIONS` | Memory → Entity | `role` (String, opt) | Entity-centric recall and multi-hop expansion. |
| `SUPERSEDES` | Memory → Memory | `reason` (String, opt), `at` (DateTime) | Correction/contradiction; `new` supersedes `old`. |
| `RELATES_TO` | Memory → Memory | `kind` (String, opt) | Association / consolidation cluster. |
| `DERIVED_FROM` | Memory → Session | — | Provenance to the originating session. |
| `PARENT_OF` | Category → Category | — | Optional hierarchical taxonomy. |

### Index Bootstrap (run once)

Create these from a **write** batch before generation/retrieval (full query in Example 1):

- `IndexSpec.nodeUniqueEquality("User", "userId")`
- `IndexSpec.nodeUniqueEquality("Memory", "memoryId")`
- `IndexSpec.nodeEquality("Memory", "userId")`
- `createVectorIndexNodes("Memory", "embedding", "userId")`  → `IndexSpec.nodeVector("Memory","embedding","userId")`
- `createTextIndexNodes("Memory", "content", "userId")`  → `IndexSpec.nodeText("Memory","content","userId")`
- `IndexSpec.nodeUniqueEquality("Category", "name")`
- `IndexSpec.nodeEquality("Entity", "name")`
- `IndexSpec.nodeUniqueEquality("Session", "sessionId")`

The `tenant_property` ("userId") on the vector and text indexes is what makes per-user isolation a single-argument concern at query time: pass `tenantValue = userId` and the search only sees that user's partition.

## Modality Cheat-Sheet

| Question | Mechanism | Builder |
|---|---|---|
| Which user? Which exact memory? Is it deleted/expired/valid? | property + equality index | `nWithLabelWhere("Memory", SourcePredicate.eq("userId", p.userId))`, `where(Predicate.isNull("deletedAt"))` |
| What category/entity/session/contradiction relates these? | edges | `out("IN_CATEGORY")`, `out("MENTIONS")`, `out("SUPERSEDES")`, `in("OWNS")` |
| What is semantically similar / already known? | vector | `vectorSearchNodesWith("Memory","embedding", p.embedding, p.k, p.userId)` |
| What contains this exact word/name/id? | BM25 text | `textSearchNodesWith("Memory","content", p.q, p.k, p.userId)` |
| Ordering / recency / top-k by importance | property + `orderBy` | `orderBy("salience", Order.Desc)`, `orderBy("lastAccessedAt", Order.Desc)` |

`$distance` (smaller = closer for both vector and BM25) is only available **immediately after** the search step and survives `where`/filter steps, but is **dropped by `out`/`in`/`both`**. Project it before any traversal.

## Embedding Guidance

- Embeddings are produced **by the application** (OpenAI, Gemini, local model, …) and passed as a numeric array parameter (`param.array(param.f64())`). There is no server-side `Embed()` on the dynamic-query/TS-DSL path.
- Keep the **same model and dimension** for writes and searches over the life of an index. Changing models requires re-embedding every memory and rebuilding the vector index.
- Embed the same text you store in `content` (or a normalised form of it) so dedup distances are meaningful.
- For **stored Rust enterprise routes** you may instead configure a server-side embedding model via `#[model("openai:text-embedding-3-small")]` on the query; that is an enterprise-stored-route feature, not available to dynamic JSON/TS calls. Default to client-side embeddings.

## Hybrid Fusion & Re-Ranking (app-side)

Helix returns the vector hits and the BM25 hits as two separate result sets; **fuse them in application code.**

**Reciprocal Rank Fusion (RRF)** — robust, score-scale-free:

```
rrf_score(memory) = Σ_lists  1 / (k + rank_in_list)        # k ≈ 60, rank is 1-based
```

Take the union of memoryIds across the vector list and the BM25 list, sum each memory's reciprocal rank from every list it appears in, sort descending.

**Final re-rank** blends recall with memory health:

```
final = w_rrf * rrf_score
      + w_sal * salience
      + w_rec * recency_decay(lastAccessedAt)        # e.g. exp(-age_days / halflife)
```

Typical weights `w_rrf=1.0, w_sal=0.3, w_rec=0.2` — tune per app. Then optionally graph-expand the top results via `MENTIONS`/`RELATES_TO` for additional context, deduplicating against what you already have.

## TypeScript ↔ Rust API Mapping

| TypeScript (`@helixdb/enterprise-ql`) | Rust DSL | Notes |
|---|---|---|
| `readBatch()` / `writeBatch()` | `read_batch()` / `write_batch()` | |
| `g()` | `g()` | empty traversal source |
| `.varAs(name, t)` / `.varAsIf(name, cond, t)` | `.var_as(...)` / `.var_as_if(...)` | branch on `BatchCondition` |
| `BatchCondition.varEmpty/varNotEmpty(name)` | `BatchCondition::VarEmpty/VarNotEmpty(name)` | only tests emptiness/size — not a value threshold |
| `.nWithLabelWhere("Memory", SourcePredicate.eq("userId", p.userId))` | `.n_with_label_where(...)` / `g().n_with_label("Memory").where_(Predicate::eq_param(...))` | indexed anchor |
| `.where(Predicate.isNull("deletedAt"))` | `.where_(Predicate::is_null(...))` | post-source filter |
| `.vectorSearchNodesWith(label, prop, p.vec, p.k, p.userId)` | `.vector_search_nodes_with(label, prop, PropertyInput::param("vec"), Expr::param("k"), Some(PropertyInput::param("userId")))` | tenant arg last |
| `.textSearchNodesWith(label, prop, p.q, p.k, p.userId)` | `.text_search_nodes_with(...)` | BM25 |
| `.addN("Memory", { … })` | `.add_n("Memory", vec![("k", …)])` | TS takes an object map |
| `.addE("OWNS", NodeRef.var("mem"), {})` | `.add_e("OWNS", NodeRef::var("mem"), vec![])` | |
| `.setProperty("lastAccessedAt", Expr.timestamp())` | `.set_property("lastAccessedAt", PropertyInput::Expr(Expr::Timestamp))` | server UTC millis |
| `Expr.prop("accessCount").add(Expr.val(1))` | `Expr::prop("accessCount").add(Expr::val(1))` | increment |
| `.drop()` / `.dropEdge(NodeRef.var("x"))` | `.drop()` / `.drop_edge(NodeRef::var("x"))` | |
| `createVectorIndexNodes / createTextIndexNodes / createIndexIfNotExists(IndexSpec.*)` | `create_vector_index_nodes / create_text_index_nodes / create_index(IndexSpec::*)` | bootstrap |
| `param.string()/i64()/f64()/array(param.f64())/object()/dateTime()`, `defineParams`, `.toDynamicJson(params, values)` | `#[register] fn(...)`, `DynamicQueryRequest::{read,write}(batch)...` | parameterisation + transport |
