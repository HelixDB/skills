---
name: helix-memory-system
description: Design and operate an AI agent memory system on HelixDB using hybrid graph + vector + full-text search. Use when building agent memory, long-term memory, a memory store, recall/"remember" features, episodic/semantic/procedural memory, or memory generation, deduplication, consolidation, updating, forgetting/deletion, and categorisation — not only retrieval. Covers the per-user data model, the modality decision rules (when to use properties vs edges vs vectors vs BM25), and the full write/maintain lifecycle. TypeScript-first (@helixdb/enterprise-ql); a Rust DSL variant is in EXAMPLES.rust.md.
license: MIT
metadata:
  author: HelixDB
  version: 0.1.0
---

# Helix Memory System

Build a durable, per-user agent memory store on Helix that combines **graph relationships**, **vector similarity**, and **BM25 full-text** in one database. This skill is about the whole memory lifecycle — **generation, updating, deletion/forgetting, and categorisation** — with retrieval as the last step, not the only one.

## When To Use

Use this skill when the task is to:

- design the data model for agent / assistant memory, long-term memory, or a "remember what the user told me" feature
- write the queries that **create, deduplicate, reinforce, consolidate, correct, expire, forget, or categorise** memories
- decide which Helix capability (property index, edge, vector, BM25) a given memory operation should use
- build hybrid recall that fuses semantic + keyword + graph context

Do **not** use this skill for generic query syntax questions. For builder/method details defer to `helix-query-typescript` (the default DSL) or `helix-query-rust`, and `helix-query-json-dynamic` (raw `POST /v1/query` payloads). This skill assumes those and focuses on the *memory design* on top of them.

## First Steps

1. Inspect the target repo for any existing `Memory`/`User`/`Category` labels, edges, and indexes; reuse exact casing if present.
2. **Default to the TypeScript DSL** (`@helixdb/enterprise-ql`) so the whole app stays in TypeScript. Use the Rust variant (`EXAMPLES.rust.md`) only if the app/runtime is Rust or you are shipping a stored enterprise route.
3. Reuse the canonical memory model below before inventing new labels. Adapt names, never the shape.
4. Confirm how embeddings are produced: **the application computes embeddings client-side** (calls an embedding API) and passes them in as `F64`/`F32` arrays. Helix does **not** embed text for you on the dynamic-query path — there is no `Embed()`/`SearchV` (that is the stale `.hx` dialect). Keep the embedding **model and dimension fixed** for the life of the index.

## The Memory Model At A Glance

Labels: **`User`** (owner / tenant), **`Memory`** (the unit of memory), **`Category`** (topic taxonomy), **`Entity`** (people/places/things mentioned), **`Session`** (episodic provenance).

Edges: **`OWNS`** (User→Memory), **`IN_CATEGORY`** (Memory→Category), **`MENTIONS`** (Memory→Entity), **`SUPERSEDES`** (Memory→Memory, correction/contradiction), **`RELATES_TO`** (Memory→Memory, association cluster), **`DERIVED_FROM`** (Memory→Session), optional **`PARENT_OF`** (Category→Category).

The fields that make it fast and safe: `Memory.memoryId` (unique), `Memory.userId` (equality index — the tenant key), a **vector index** on `Memory.embedding` and a **text index** on `Memory.content` — both **tenant-scoped by `userId`**. Full spec, types, and the index bootstrap are in `REFERENCE.md`.

## Modality Decision Rules (the core skill)

Pick the mechanism by the *question you are answering*, and use them together:

| Need | Use | Why |
|---|---|---|
| Tenant isolation (`userId`), exact identity (`memoryId`), lifecycle flags (`deletedAt`, `expiresAt`, `validTo`), ordering/filtering (`createdAt`, `salience`) | **Properties + equality index** | O(1) anchors; never scan the whole label. Tenant scope is non-negotiable. |
| Categorisation, entity-centric recall, provenance, contradiction/temporal chains, association clusters, taxonomy | **Graph / edges** | These are *relationships*; you traverse and aggregate over them. |
| "Is this new memory already known?" (dedup); "memories *like* this" | **Vector search** (`Memory.embedding`) | Semantic similarity; tolerant of paraphrase. |
| Exact keyword / proper noun / id / rare-token recall | **BM25 text search** (`Memory.content`) | Embeddings blur names, codes, and exact tokens; BM25 nails them. |

Rule of thumb: **never collapse a memory system to vector-only.** Vectors miss exact names and have no notion of ownership, recency, contradiction, or category. Properties carry identity and lifecycle; edges carry meaning between memories; vector + BM25 are two complementary recall paths you fuse.

Always: scope vector/BM25 searches to the user via `tenantValue = userId`, and filter `deletedAt` out on every read.

## The Memory Lifecycle

Each step links to a complete example in `EXAMPLES.md` (TypeScript) / `EXAMPLES.rust.md` (Rust).

### 1. Generation
1. **Extract** candidate memories from the conversation (LLM, app-side) — atomic, self-contained statements.
2. **Embed** each candidate (app-side) → `F64`/`F32` array.
3. **Deduplicate** before writing. A distance threshold can **not** be a batch condition, so use one of:
   - *read-then-write*: vector-search the nearest existing memory for this user; if `distance < threshold`, **reinforce** it instead of inserting; otherwise create. (Example 2.)
   - *idempotent upsert*: key on a stable `memoryId` (uuid or content hash) and branch with `varAsIf(VarNotEmpty/VarEmpty)` in one write batch — catches exact repeats. (Example 2b.)
4. **Write**: `addN("Memory", …)` with `embedding`, `content`, `kind`, `salience`, and timestamps via `Expr.timestamp()`; link `User -OWNS-> Memory`.
5. **Categorise** immediately (see step 4 below).

### 2. Updating
- **Reinforce on access**: bump `accessCount` (`Expr.prop("accessCount").add(Expr.val(1))`), set `lastAccessedAt = Expr.timestamp()`, raise `salience`. (Example 4.)
- **Consolidate** near-duplicates/related memories with a `RELATES_TO` edge, or rewrite one canonical memory. **If you change `content`, re-embed and overwrite `embedding` in the same write** — content and vector must never drift apart.
- **Correct / contradict**: add `new -SUPERSEDES-> old`, and invalidate the old one (set `validTo` or soft-delete it). Keep the old node for audit unless you have a reason to hard-delete. (Example 5.)

### 3. Deletion / Forgetting
Helix has **no native TTL or decay** — forgetting is explicit write queries the app runs (e.g. on a cron/schedule).
- **Soft-delete** (preferred): set `deletedAt = Expr.timestamp()`. Reads filter `deletedAt IsNull`. Reversible, preserves history. (Example 6.)
- **Decay sweep**: soft-delete memories that are low `salience` **and** stale `lastAccessedAt` **and** low `accessCount`. (Example 7.)
- **Expiry sweep**: hard-delete where `expiresAt < now`. (Example 8.)
- **Hard delete**: `drop()` the node; drop its edges explicitly if your graph is a multigraph (note in `REFERENCE.md`).

### 4. Categorisation
- Set `Memory.kind` ∈ {`episodic`, `semantic`, `procedural`} at generation.
- **Topic**: upsert a `Category` by unique `name` (`varAsIf`), then link `Memory -IN_CATEGORY-> Category`. (Example 3.)
- **Entities**: upsert `Entity` by name and link `Memory -MENTIONS-> Entity` — this is what powers entity-centric multi-hop recall.
- Prefer **edges over array-of-tags** when you will traverse or aggregate by the tag; use an array property only for flat, display-only labels.

### Retrieval (hybrid — last, not first)
Run vector and BM25 as two sub-queries in one read batch, **both tenant-scoped and both filtering `deletedAt IsNull`**, project `$distance` immediately, then **fuse app-side (RRF)** and re-rank by `salience` + recency. Optionally expand via `MENTIONS`/`IN_CATEGORY`/`RELATES_TO` for related context. (Example 9; fusion formula in `REFERENCE.md`.)

## Anti-Patterns

Do not:
- use the `.hx` dialect (`Embed()`, `SearchV`, `SearchBM25`, `AddV`) — the dynamic-query/TS-DSL path passes pre-computed vectors and uses `vectorSearchNodes` / `textSearchNodes`.
- build a vector-only store and call it memory — you lose ownership, recency, contradiction, categories, and exact-name recall.
- forget `tenantValue = userId` on vector/BM25 search, or skip the `deletedAt IsNull` filter on reads (you will leak other users' or forgotten memories).
- read `$distance` after an `out`/`in`/`both` step — project it right after the search.
- expect a TTL — schedule the decay/expiry sweeps yourself.
- try to express a similarity-threshold dedup as a `BatchCondition` — it can only test variable emptiness/size; use read-then-write.
- update `content` without re-embedding.
- return `embedding` arrays in API responses — project only what the caller needs.
- hard-delete by default when soft-delete + `SUPERSEDES` preserves a useful history.

## Validation Checklist

Before finishing:
- read vs write batch is correct (`readBatch()` / `writeBatch()`).
- every search is tenant-scoped (`tenantValue = userId`) and every read filters `deletedAt IsNull`.
- the indexes the queries rely on exist (run the bootstrap from Example 1 first).
- `embedding` dimension and model are consistent across write and search.
- generation deduplicates (read-then-write or idempotent upsert).
- content edits re-embed in the same write.
- timestamps use `Expr.timestamp()`; counters use `Expr.prop(...).add(...)`.
- no `embedding` in projected output unless explicitly required.
- labels/edges/properties match any existing repo casing.

## Reference Files

- `REFERENCE.md` — full data-model spec (labels, properties + types, edges, the complete index bootstrap), the modality cheat-sheet, embedding guidance, the RRF fusion + re-ranking formula, and a TypeScript ↔ Rust API mapping.
- `EXAMPLES.md` — the nine lifecycle scenarios as complete `@helixdb/enterprise-ql` (TypeScript) snippets. **Default.**
- `EXAMPLES.rust.md` — the same nine scenarios in the Rust DSL.
- Adjacent skills: `helix-query-typescript`, `helix-query-rust`, `helix-query-json-dynamic`, `helix-query-optimize`.
