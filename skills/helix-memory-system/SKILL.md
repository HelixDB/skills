---
name: helix-memory-system
description: Design and operate an AI agent memory system on the published HelixDB v3 SDKs with hybrid graph plus exact traversal-prefiltered vector and BM25 search. Use when building an app or agent feature that remembers what users tell it (long-term memory, profiles, RAG, recall, extraction, deduplication, consolidation, versioning, forgetting, categorisation, ingestion) on a local or Helix Cloud database. TypeScript-first (`@helix-db/helix-db@3.2.0`); Rust v3 in EXAMPLES.rust.md. For agent memory of a business's own systems and documents without building one, use Helix Foundry (helix-foundry-mcp).
license: MIT
metadata:
  author: HelixDB
  version: 3.1.0
---

# Helix Memory System

Per-tenant agent memory combining **graph**, **vector** and **BM25** in one Helix database.
Helix stores and searches. Extraction, chunking, embedding, relationship classification,
reranking, connector sync, profile summarisation and TTL/decay sweeps are application workers
(unless a managed service provides them); never imply Helix does them.

Not for generic query syntax: use `helix-query-typescript` (default), `helix-query-rust` or
`helix-query-json-dynamic`; `helix-query-optimize` for performance.

- `REFERENCE.md`: full data model, tenant and scope rules, index list, modality cheat-sheet,
  embedding guidance, extractor output shape, adjudication table, evaluation checklist,
  fusion/re-ranking formula, TypeScript ↔ Rust mapping.
- `EXAMPLES.md`: every lifecycle step in `@helix-db/helix-db@3.2.0` TypeScript. **Default.**
- `EXAMPLES.rust.md`: the same in the Rust DSL.

## Setup decisions

1. Inspect the repo's labels, edges, properties, indexes and route style; reuse exact casing.
   Adapt the canonical model's names, not its shape.
2. Use the TypeScript v3 DSL unless the runtime is Rust or the team ships Rust queries. Never the
   deprecated `.hx` dialect (`Embed()`, `SearchV`, `SearchBM25`, `AddV`).
3. **Tenancy.** A partitioned vector or text index takes any property name as its
   `tenant_property`; this skill uses `tenant_id` (keep the repo's name if it has one). Use one
   name for every partitioned index: hybrid recall passes one tenant value to both vector and BM25.
   Put it on every tenant-owned node and edge, and filter every read and write route by it, even
   by `memoryId` or another unique id.
4. **Visibility** is separate from tenancy. `tenant_id` partitions indexes; `userId` (the default
   here), `containerId`, `projectId` or an app ACL decides what recall may return. Only explicitly
   shared records are tenant-wide.
5. **Embeddings.** Default OpenAI `text-embedding-3-small`: 1536-dim `F32`, computed by the app
   and passed as arrays (`param.array(param.f32())`). Helix does not embed on the dynamic-query
   path. Fix model and dimension per vector index. Hash embeddings are for local demos and smoke
   tests only, never production recall or benchmarks.
6. **Indexes build asynchronously.** `createIndexIfNotExists` returns a receipt: `accepted` or
   `existing_operation` (with an `operation_id`), or `already_active`. An index is usable only
   once `getIndexOperation(operation_id)` reports `succeeded`; until then vector and BM25 search
   fail with `index_not_found` and equality lookups scan. A building unique index rejects a write
   only if the value is already claimed (by an entity the build scanned, or a write since it
   started); a duplicate of a not-yet-scanned entity's value is written, and existing duplicates
   block the build (`blocked`, with a `blocker_code`): fix the data, then `retryIndexOperation`.
   Bootstrap and wait at deploy time, not per request (`EXAMPLES.md` §1).

## Model

Labels: `Tenant`, `User`, `UserProfile`, `SourceDocument`, `Chunk`, `Memory`, `Category`,
`Entity`, `Session`, optional `Connector` and `IngestionJob`.

Edges: `OWNS` (Tenant/User→Memory), `HAS_PROFILE` (User→UserProfile), `HAS_CHUNK`
(SourceDocument→Chunk), `EXTRACTED_FROM` (Memory→Chunk or SourceDocument), `IN_CATEGORY`
(Memory→Category), `MENTIONS` (Memory→Entity), `UPDATES` (new Memory→old Memory), `EXTENDS`
(Memory→Memory enrichment), `DERIVES` (inferred Memory→supporting Memory), `RELATES_TO`
(Memory→Memory association), `DERIVED_FROM` (Memory→Session), optional `PARENT_OF`
(Category→Category).

Fields:

- `tenant_id`, equality-indexed where it anchors
- `userId` (or the scope key) on user/container memories, source documents and chunks
- stable ids `memoryId`, `documentId`, `chunkId`, `categoryKey`, `entityKey`, `sessionId`,
  `profileId`: globally unique or tenant-qualified
- lifecycle: `Memory.isLatest`, `validFrom`, `validTo`, `expiresAt`, `deletedAt`
- real-world time, never mixed with lifecycle: `observedAt`, `eventStartAt`, `eventEndAt`,
  `temporalText`, `timezone`
- tenant-partitioned vector/text indexes on `Memory.embedding`/`Memory.content`, optionally
  `Chunk.embedding`/`Chunk.content`

## Pick the mechanism

| Need | Use |
|---|---|
| Tenant isolation, exact identity, lifecycle flags, ordering/filtering (`createdAt`, `salience`) | Properties + equality/range index |
| Categories, entities, provenance, profile ownership, updates/extensions/derivations, associations, taxonomy | Graph edges (traverse, aggregate) |
| Dedup, paraphrase recall, "memories/chunks like this" | Vector search |
| Exact names, ids, rare tokens, commands, file paths, product terms | BM25 (embeddings blur exact tokens) |
| Broad context the model always needs: identity, preferences, recent focus | `UserProfile` + summariser worker |
| Raw documents and citations | `SourceDocument` + `Chunk` (facts don't replace source-grounded RAG) |

Never build a vector-only memory: vectors miss exact names and know nothing of ownership,
recency, contradiction, provenance, profile or category.

**Every recall path** passes the tenant as `tenantValue`, filters user/container visibility,
and keeps only live records: `deletedAt IsNull`, `isLatest = true`, `validTo IsNull`,
`expiresAt` absent or future (checking only `deletedAt` leaks superseded and expired memories).
Build those candidates first, then run traversal-scoped vector/BM25 search so both enforce exact
visibility membership. Enforce in app code whatever a route can't express.

## Application workers

| Worker | Does |
|---|---|
| Ingestion API | Accepts text, chats, files, URLs, connector events, direct memory writes |
| Extractors | PDFs, docs, HTML, images/OCR, audio/video transcripts, code, structured data → text |
| Chunkers | Split by semantic section, message turn, heading, code AST boundary or transcript segment |
| Embedder | 1536-dim `F32` embeddings for memories and chunks before the write |
| Memory generator | Atomic, entity-centric candidate facts from the turn plus context (see Extraction) |
| Relationship classifier | `UPDATES`, `EXTENDS`, `DERIVES`, duplicate or standalone |
| Profile summariser | `UserProfile.staticSummary` and `dynamicSummary` from latest memories |
| Forgetting jobs | Expiry, decay, stale-profile and connector-deletion sweeps |
| Retrieval service | Query rewrite, vector + BM25 over memories/chunks, fuse, rerank, graph-expand, pack with citations |

## Lifecycle

Each step has a full example in `EXAMPLES.md` and `EXAMPLES.rust.md`.

### 1. Ingest and generate

1. Accept a `SourceDocument`, conversation/session, direct memory write or connector update.
2. Extract and chunk app-side unless the input is already an atomic memory; embed each
   memory/chunk app-side.
3. Extract atomic, self-contained, entity-centric facts ("Alex prefers morning meetings", not
   "prefers morning meetings"). Classify `kind`: `fact`, `preference`, `episode`, `procedure`
   or app equivalents.
4. Deduplicate before writing: read-then-write for semantic dedup (a similarity threshold can't
   be a `BatchCondition`, which tests only variable emptiness/size); idempotent upsert for exact
   repeats.
5. Write `Memory` with `tenant_id`, `memoryId`, `content`, `embedding`, `kind`, `salience`,
   `isLatest: true` and lifecycle timestamps; link ownership and provenance; categorise and
   entity-link immediately.

### Extraction needs context

Give the extractor the current user message, the previous assistant message (it often defines
what a short answer means), a bounded recent window, recalled active memories and entities, the
current date/time, and the scope (`tenant_id` plus `userId`/`containerId`/`projectId`/ACL).
Resolve pronouns, ellipsis and short answers before deciding to store; a brief answer to a
memory-bearing follow-up becomes a self-contained memory.

Output, for deterministic writes: `shouldStore`, self-contained `content`, `kind`, `confidence`,
`salience`, `entities`, `source` pointers, `scope`, optional temporal fields, and a relationship
(`new`, `duplicate`, `EXTENDS`, `UPDATES`, `DERIVES`). Never let one vector-distance threshold
decide: gather exact, vector and BM25 candidates and adjudicate in app code.

```text
Existing memory: User is planning a trip to Japan with Maya.
Assistant: When are you going?   User: next April
→ User is planning a trip to Japan with Maya next April. EXTENDS the trip memory; MENTIONS Maya, Japan.
Assistant: What do you want to do there?   User: mostly food, temples, and trains
→ User wants their Japan trip with Maya to focus on food, temples, and trains. EXTENDS; category travel/preferences.
User later: actually we're going in May instead
→ User is planning a trip to Japan with Maya in May. UPDATES the next-April memory and invalidates it.
```

### 2. Update and version

- **Reinforce on access:** bump `accessCount`, `lastAccessedAt` and bounded `salience`.
- **Correct:** create a new memory, link `new -UPDATES-> old`, set old `isLatest = false` and
  `validTo`; optionally `deletedAt` to hide it from normal recall.
- **Extend:** `new -EXTENDS-> existing` when it enriches without replacing.
- **Derive:** `DERIVES` edges to supporting memories; mark it inferred, with confidence.
- Changing `content` re-embeds in the same write; content and vector never drift.
- A changed fact invalidates the old record even when both facts refer to past or future dates.

Remote errors are `{"error": "<code>", "msg": "..."}`; branch on `error`, never on `msg`:

| `error` | Do |
| --- | --- |
| `transaction_conflict` (409) | Expected: versioning is read-then-write across concurrent sessions. Reload state, rebuild the mutation, replay with bounded backoff only if idempotent or otherwise safe. Writes already wait for durability by default (only `shouldAwaitDurability(false)` / `x-helix-await-durable: false` skips it), and durability does not prevent conflicts |
| `unique_constraint_violation` | The key exists: treat as a duplicate and reinforce |
| `index_not_found` (404) | An index is missing or still building |
| `index_backpressure` (429) | Back off and retry |

### 3. Forget

Helix has no native TTL or decay; forgetting is explicit writes the app runs.

- **Soft-delete** (preferred; reversible, auditable): `deletedAt = Expr.datetime()`, filtered
  from reads.
- **Invalidate a version:** `isLatest = false`, `validTo = Expr.datetime()`.
- **Expiry sweep:** hide or hard-delete where `expiresAt < now`.
- **Decay sweep:** hide weak, stale, rarely accessed episodic memories.
- **Hard delete** only when policy requires: `drop()` removes the node and its incident edges;
  `dropEdgeById` for surgical edge cleanup on multigraph-sensitive paths.

### 4. Categorise and link entities

- `Category` and `Entity` nodes carry `tenant_id` and a unique `categoryKey`/`entityKey` such as
  `${tenant_id}:${normalisedName}`; never global by display name.
- Use edges, not arrays, for what you traverse, aggregate or recall by; nested object metadata for
  display/audit fields; keep frequently filtered fields top-level.

### 5. Maintain profiles

One `UserProfile` per user/container: `profileId`, `tenant_id`, `userId`, `staticSummary`
(identity, stable preferences, background), `dynamicSummary` (current projects, recent context,
temporary goals, open tasks), `updatedAt`. Update asynchronously after writes and deletions;
keep generation deterministic enough to test.

### Retrieve

1. Fetch the `UserProfile`.
2. Vector + BM25 over current `Memory`, scoped and freshness-filtered as above.
3. Optionally vector + BM25 over `Chunk` for RAG and citations, with the same scope unless
   documents are intentionally shared.
4. Fuse app-side with RRF; re-rank by salience, recency, relationship type and optional
   cross-encoder score.
5. Expand top memories through `MENTIONS`, `IN_CATEGORY`, `EXTENDS`, `UPDATES`, `RELATES_TO`,
   bounded by depth and tenant filters.
6. Pack context with source/citation metadata. Project `$distance`/`$score` right after the
   search, never after an `out`/`in`/`both` step. Never return `embedding` unless explicitly
   required.

## Run it on Helix Cloud

Same queries locally and on Cloud; only the path differs:

| Who runs it | Path | Credential |
| --- | --- | --- |
| Memory service in production | SDK against the database's gateway URL (`connectionEndpoint` in `helix database get tenant:<id> --json`): `Client.server(url).withApiKey(key)`, plus `.withDatabaseId(id)` for the TypeScript SDK on a shared gateway | Application database key from `helix database create` or `helix database key create --database tenant:<id> --access read-write`, in the app's secret store |
| Developer or agent at a shell | `helix query tenant:<id> --file request.json --json` (backend broker; no key) | The user's `helix auth login` session |
| Agent over MCP | `helix_execute_read_query`, or `helix_prepare_write_query` + `helix_execute_write_query` (helix-query-mcp) | The user's OAuth sign-in, or a service credential with `query-read`/`query-write` |

The database key stays in the application: never give it to the CLI or an MCP client, never
commit it. Bootstrap indexes once per database from a deploy step (any path), and check the
active set with `helix database indexes tenant:<id> --json` or `helix_list_database_indexes`.

## Before finishing

- `readBatch()` for reads, `writeBatch()` for writes.
- Timestamps use one convention: typed DateTime via `Expr.datetime()` and `param.dateTime()`.
- Response shapes: at-most-one fields allow `null`; collection/fold/mutation empties stay `[]`;
  scalar `0` or `false` stays scalar.
- Promised citations or RAG over raw context → `SourceDocument`/`Chunk` exist. Promised always-on
  personalization → profile jobs exist.
- Evaluation covers `REFERENCE.md`'s Evaluation Checklist: tenant and user/container isolation,
  stale suppression, contextual follow-ups, exact-token recall, temporal corrections, deletion,
  profile rebuilds, latency, token budget.
