# Helix Skills Repo Plan

This document turns the current Helix skills strategy into an execution checklist for a public `skills.sh` repository hosted under the `HelixDB` organization.

This repository is the planning and drafting workspace. The hosted skills repository will live separately under `HelixDB`.

## Goal

Ship a public skills repository that helps coding agents:

- write new Helix queries in the Rust DSL
- translate queries from Cypher, Gremlin, and SQL into the Rust DSL
- optimize Helix queries using real Helix storage and query-shape constraints
- run dynamic JSON queries correctly through `POST /v1/query`

The output should be practical, repo-aware, and grounded in real Helix patterns instead of generic graph-database advice.

## Target Outcome

After launch, users should be able to run:

```bash
npx skills add HelixDB/<repo-name>
```

and get a small set of high-signal skills that reliably help agents produce correct Helix query code.

## Product Decisions

### Skill Set

Initial public skills:

- `helix-query-authoring`
- `helix-query-from-cypher`
- `helix-query-from-gremlin`
- `helix-query-from-sql`
- `helix-query-optimize`
- `helix-query-json-dynamic`

Decision for v1:

- do not publish a separate `helix-query-core` skill yet
- keep shared guidance in repository docs and repeat only the essential rules inside each public `SKILL.md`

### Scope Boundaries

In scope:

- Rust DSL stored-query authoring guidance
- migration guidance from Cypher, Gremlin, and SQL
- dynamic endpoint request-shape guidance
- optimization guidance tied to Helix indexes, traversals, and runtime behavior
- benchmark cases and golden examples

Out of scope for v1:

- automatic query conversion tooling
- code generation CLIs
- non-Rust SDK skills
- generic graph modeling advice that is not Helix-specific
- MCP-only skills

### Authoring Principles

- Keep each skill narrow enough that agents can choose it confidently from the description alone.
- Keep `SKILL.md` focused on when to use the skill, how to work, what to avoid, and where to look next.
- Put bulky examples, rosetta tables, and benchmark fixtures in sibling docs.
- Ground every skill in existing Helix code and tests.
- Prefer exact Helix terminology over broad database jargon.

## Source Canon

These are the primary references the skills should cite and draw examples from.

### Helix Docs

- `https://skills.sh/docs`
- `https://opencode.ai/docs/skills`
- `https://docs.helix-db.com/enterprise/introduction`
- `https://docs.helix-db.com/documentation/hql/traversals`
- `https://docs.helix-db.com/documentation/hql/conditionals`
- `https://docs.helix-db.com/documentation/hql/result_ops`
- `https://docs.helix-db.com/documentation/hql/output_values`
- `https://docs.helix-db.com/documentation/hql/vectors`
- `https://docs.helix-db.com/documentation/hql/keyword_search`

### Repo-Local Canonical References

- `docs/source-canon.md`
- `docs/dsl-cheatsheet.md`
- `docs/dynamic-query-examples.md`
- `docs/optimization-checklist.md`
- `examples/authoring-patterns.md`
- `examples/search-patterns.md`
- `examples/optimization-patterns.md`

### Publication Rule

- do not publish machine-local filesystem paths as source pointers
- do not treat app-specific implementations as canonical Helix references
- convert any implementation-derived idea into a generic documented pattern before publishing it here

## Critical Helix Facts The Skills Must Teach

- Stored Rust DSL queries are the normal production path.
- Dynamic inline queries are supported, but they deserialize at request time and are less optimized than stored routes.
- Dynamic queries go to `POST /v1/query`.
- Dynamic query bodies must contain a single inline route object under `query`, not the entire `queries.json` bundle.
- Dynamic `request_type` must be `read` or `write`.
- Dynamic queries do not support `mcp` request type.
- `parameter_types` is required when callers need type-aware coercion, especially `DateTime` and typed arrays.
- Stored routes can inherit parameter typing from router metadata; dynamic routes must provide it explicitly.
- `Bytes` parameters are not representable through the JSON query route.
- Text search in enterprise is property-scoped.
- Vector and text indexes are often tenant-scoped and queries should preserve that scope.
- BM25 patterns may need over-fetch then post-filter then trim.
- Repeat depth in the current DSL patterns is often fixed at compile time.

## Proposed Hosted Repo Layout

```text
/
README.md
skills/
  helix-query-authoring/
    SKILL.md
  helix-query-from-cypher/
    SKILL.md
  helix-query-from-gremlin/
    SKILL.md
  helix-query-from-sql/
    SKILL.md
  helix-query-optimize/
    SKILL.md
  helix-query-json-dynamic/
    SKILL.md
docs/
  dsl-cheatsheet.md
  source-canon.md
  cypher-rosetta.md
  gremlin-rosetta.md
  sql-rosetta.md
  optimization-checklist.md
  dynamic-query-examples.md
examples/
  authoring-patterns.md
  search-patterns.md
  optimization-patterns.md
benchmarks/
  README.md
  manifest.md
  authoring/
  cypher/
  gremlin/
  sql/
  optimize/
  dynamic/
```

## Skill Template Contract

Every skill should include:

- YAML frontmatter with `name` and a very specific `description`
- a short statement of what the skill does
- explicit usage triggers
- a mandatory workflow the agent should follow
- Helix-specific rules and anti-patterns
- links to adjacent docs in the repo
- a small validation checklist

Each `description` should be written for discoverability. It should include the source task phrasing the user is likely to use.

## Recommended Skill Content

### `helix-query-authoring`

Purpose:

- write Rust DSL queries from scratch
- anchor on existing schema and query patterns before inventing new ones

Must teach:

- `read_batch()` and `write_batch()` query shape
- `var_as(...)` and `returning(...)`
- node and edge traversal patterns
- projections, ordering, range, count, dedup, and repeat
- index-aware anchoring
- tenant scoping for vector and text search

Primary sources:

- `docs/dsl-cheatsheet.md`
- `examples/authoring-patterns.md`
- `examples/search-patterns.md`
- `docs/source-canon.md`

### `helix-query-from-cypher`

Purpose:

- translate Cypher patterns into Helix Rust DSL

Must teach:

- `MATCH` to anchored traversal chains
- `WHERE` to `Predicate` and `where_`
- `RETURN` to `project` and `returning`
- relationship patterns to `out`, `in`, `both`, `out_e`, `in_e`
- `MERGE`-like upsert translation to explicit read-then-update/create flows

Primary sources:

- `docs/cypher-rosetta.md`
- `docs/dsl-cheatsheet.md`
- `https://docs.helix-db.com/documentation/hql/traversals`

### `helix-query-from-gremlin`

Purpose:

- translate Gremlin step chains into Helix Rust DSL

Must teach:

- `g.V().hasLabel().has()` to label anchors plus predicates
- step-chain mapping for `out`, `in`, `both`, `outE`, `inE`
- repeat and emit translation
- where Gremlin mental models do not fit Helix directly

Primary sources:

- `docs/gremlin-rosetta.md`
- `docs/dsl-cheatsheet.md`
- `https://docs.helix-db.com/documentation/hql/traversals`

### `helix-query-from-sql`

Purpose:

- help SQL users move from table/join thinking to graph traversal thinking

Must teach:

- start-node selection instead of table-first scans
- joins as traversals
- `WHERE IN` to `Predicate::is_in_param`
- `ORDER BY`, `LIMIT`, and pagination mapping
- when a query should stay property-centric versus traverse the graph

Primary sources:

- `docs/sql-rosetta.md`
- `docs/dsl-cheatsheet.md`
- `https://docs.helix-db.com/documentation/hql/result_ops`

### `helix-query-optimize`

Purpose:

- review or improve query shape and index usage

Must teach:

- choose the narrowest indexed anchor first
- filter before broad traversal
- keep projections explicit
- avoid carrying embeddings unless needed
- use `dedup`, `count`, `first`, `range`, and `limit` deliberately
- use stored routes instead of dynamic when possible
- use read warming correctly

Primary sources:

- `docs/optimization-checklist.md`
- `examples/optimization-patterns.md`
- `examples/search-patterns.md`
- `https://docs.helix-db.com/enterprise/introduction`

### `helix-query-json-dynamic`

Purpose:

- build and validate inline dynamic query payloads for `POST /v1/query`

Must teach:

- exact request envelope
- inline query shape
- `request_type` restrictions
- `parameter_types` rules
- `DateTime` coercion
- typed arrays for vectors
- unsupported `Bytes`
- common malformed-payload mistakes

Primary sources:

- `docs/dynamic-query-examples.md`
- `docs/source-canon.md`
- `https://docs.helix-db.com/enterprise/introduction`

## Shared Supporting Docs

These docs should exist in the hosted repo because they are too large or too specific for `SKILL.md`.

### `docs/dsl-cheatsheet.md`

Should include:

- the basic read and write batch shape
- common traversal builders
- common predicate builders
- result-shaping operations
- index creation helpers
- vector and text search helpers
- repeat patterns
- projection examples

### `docs/source-canon.md`

Should include:

- the canonical public docs and repo-local docs
- what each source category is best for
- rules for avoiding machine-local and app-specific references

### `docs/cypher-rosetta.md`

Should include:

- `MATCH`, `OPTIONAL MATCH`, `WHERE`, `RETURN`, `ORDER BY`, `LIMIT`, `MERGE`, `COUNT`
- direct Helix Rust DSL equivalents or closest safe pattern
- explicit unsupported or lossy translations

### `docs/gremlin-rosetta.md`

Should include:

- `g.V`, `g.E`, `hasLabel`, `has`, `out`, `in`, `both`, `outE`, `inE`, `values`, `valueMap`, `repeat`, `emit`, `dedup`, `limit`, `count`
- Helix equivalents and caveats

### `docs/sql-rosetta.md`

Should include:

- `SELECT`, `WHERE`, `JOIN`, `GROUP BY`, `ORDER BY`, `LIMIT`, `OFFSET`, `IN`, `EXISTS`
- when SQL-style grouping maps poorly to Helix traversal structure

### `docs/optimization-checklist.md`

Should include:

- anchor choice checklist
- index checklist
- projection checklist
- traversal breadth checklist
- text search and vector search checklist
- stored-versus-dynamic decision checklist

### `docs/dynamic-query-examples.md`

Should include:

- minimal read request
- write request envelope guidance
- `DateTime` example with `parameter_types`
- typed array guidance for vector parameters
- failure examples and why they fail

## Example Packs

### `examples/authoring-patterns.md`

Use as the generic CRUD, traversal, and write-branching example pack.

### `examples/search-patterns.md`

Use as the generic BM25, vector, and bounded-expansion example pack.

### `examples/optimization-patterns.md`

Use as the generic before-and-after optimization example pack.

## Benchmark Plan

The benchmark suite should validate whether the skills actually improve agent outputs.

Each benchmark case should contain:

- a prompt
- the expected skill to trigger
- the expected repo files an agent should inspect
- the expected output shape
- one or more gold answers
- a checklist for scoring

Each scoring sheet should cover:

- correct read or write choice
- correct labels, edges, and property names
- correct anchor choice
- correct tenant scope
- correct traversal direction
- correct projection and return shape
- correct dynamic request envelope when relevant
- correct `parameter_types` usage when relevant
- index-awareness where appropriate

## Definitions Of Done

### Repo Done

The hosted repo is done when:

- every public skill is installable through `skills.sh`
- every skill has a valid `SKILL.md`
- supporting docs exist and are linked from the relevant skills
- at least one example pack exists for each major skill area
- benchmark prompts and gold answers exist for every skill
- README explains installation and repo contents

### Skill Done

A skill is done when:

- the frontmatter is valid
- the name matches the directory name
- the description is specific enough for discovery
- the skill includes trigger conditions
- the skill includes a concrete workflow
- the skill includes Helix-specific pitfalls
- the skill points to supporting docs and examples
- the skill has benchmark coverage

## Execution Order

Recommended build order:

1. hosted repo setup
2. README and source canon
3. `helix-query-authoring`
4. `helix-query-json-dynamic`
5. `helix-query-optimize`
6. `helix-query-from-cypher`
7. `helix-query-from-gremlin`
8. `helix-query-from-sql`
9. benchmark suite
10. launch pass and install verification

## Master Checklist

### Phase 1: Hosted Repo Setup

- [ ] Choose the final repository name under `HelixDB`
- [ ] Create the hosted repository under the `HelixDB` organization
- [x] Add a top-level `README.md`
- [x] Add a `skills/` directory
- [x] Add a `docs/` directory
- [x] Add an `examples/` directory
- [x] Add a `benchmarks/` directory
- [ ] Verify the repo is discoverable by `skills.sh`
- [ ] Verify the repo installs locally with `npx skills add HelixDB/<repo-name> --list`

### Phase 2: Core Shared Docs

- [x] Write `docs/source-canon.md`
- [x] Write `docs/dsl-cheatsheet.md`
- [x] Write `docs/optimization-checklist.md`
- [x] Write `docs/dynamic-query-examples.md`
- [x] Link all shared docs from the README
- [x] Verify every doc reflects public Helix behavior and repo-local canonical examples

### Phase 3: Example Packs

- [x] Write `examples/authoring-patterns.md`
- [x] Write `examples/search-patterns.md`
- [x] Write `examples/optimization-patterns.md`
- [x] Keep each example pack generic and self-contained
- [x] Include at least one read example and one write example where applicable
- [x] Include at least one search example where applicable

### Phase 4: `helix-query-authoring`

- [x] Create `skills/helix-query-authoring/SKILL.md`
- [x] Write a precise frontmatter `description`
- [x] Add explicit trigger phrases for “write a Helix query”, “Rust DSL”, and “stored query” tasks
- [x] Add the mandatory first-step workflow to inspect existing labels, properties, edges, and query patterns
- [x] Add the read-versus-write decision rule
- [x] Add the narrowest-index-anchor rule
- [x] Add examples for simple CRUD
- [x] Add examples for traversal queries
- [x] Add examples for search queries
- [x] Add anti-patterns section
- [x] Link to `docs/dsl-cheatsheet.md`
- [x] Link to the example packs

### Phase 5: `helix-query-json-dynamic`

- [x] Create `skills/helix-query-json-dynamic/SKILL.md`
- [x] Add explicit trigger phrases for “dynamic query”, “inline query”, and `/v1/query`
- [x] Document the exact request envelope
- [x] Document that `query` must be a single inline route object, not the full bundle
- [x] Document that `request_type` must be `read` or `write`
- [x] Document that `mcp` is invalid for dynamic queries
- [x] Document `parameter_types` requirements
- [x] Document `DateTime` coercion behavior
- [x] Document typed array expectations for vectors
- [x] Document that `Bytes` is unsupported on this route
- [x] Add malformed-request examples and fixes
- [x] Link to `docs/dynamic-query-examples.md`

### Phase 6: `helix-query-optimize`

- [x] Create `skills/helix-query-optimize/SKILL.md`
- [x] Add explicit trigger phrases for “optimize”, “slow query”, “improve query”, and “index”
- [x] Add an optimization workflow that starts with anchor choice
- [x] Add an index review checklist
- [x] Add projection minimization rules
- [x] Add vector and BM25 search guidance
- [x] Add stored-versus-dynamic guidance
- [x] Add query-warming guidance for reads
- [x] Add canonical optimization examples and before-and-after patterns
- [x] Link to `docs/optimization-checklist.md`

### Phase 7: `helix-query-from-cypher`

- [ ] Create `skills/helix-query-from-cypher/SKILL.md`
- [ ] Add trigger phrases for “Cypher”, “Neo4j”, `MATCH`, and `MERGE`
- [ ] Write `docs/cypher-rosetta.md`
- [ ] Add a translation workflow that first identifies anchors, traversal directions, filters, and outputs
- [ ] Add a mapping table for `MATCH`, `WHERE`, `RETURN`, `ORDER BY`, `LIMIT`, `COUNT`, and `MERGE`
- [ ] Add a section on what does not translate directly
- [ ] Add canonical translation examples
- [ ] Link to `docs/cypher-rosetta.md`

### Phase 8: `helix-query-from-gremlin`

- [ ] Create `skills/helix-query-from-gremlin/SKILL.md`
- [ ] Add trigger phrases for “Gremlin”, “TinkerPop”, `g.V()`, and `repeat`
- [ ] Write `docs/gremlin-rosetta.md`
- [ ] Add a translation workflow that collapses step chains into Helix traversal builders
- [ ] Add a mapping table for `g.V`, `g.E`, `hasLabel`, `has`, `out`, `in`, `both`, `outE`, `inE`, `valueMap`, `repeat`, `emit`, `dedup`, `limit`, and `count`
- [ ] Add canonical translation examples
- [ ] Add caveats where Gremlin step semantics do not map exactly
- [ ] Link to `docs/gremlin-rosetta.md`

### Phase 9: `helix-query-from-sql`

- [ ] Create `skills/helix-query-from-sql/SKILL.md`
- [ ] Add trigger phrases for “SQL”, “SELECT”, “JOIN”, and “WHERE IN”
- [ ] Write `docs/sql-rosetta.md`
- [ ] Add a translation workflow that identifies entities, relationships, filters, ordering, and pagination
- [ ] Add a section on replacing join-first thinking with anchor-first traversal thinking
- [ ] Add mappings for `SELECT`, `WHERE`, `JOIN`, `ORDER BY`, `LIMIT`, `OFFSET`, `IN`, and `EXISTS`
- [ ] Add canonical translation examples
- [ ] Link to `docs/sql-rosetta.md`

### Phase 10: Benchmarks

- [ ] Add `benchmarks/README.md`
- [ ] Add `benchmarks/manifest.md`
- [ ] Add benchmark prompts for authoring
- [ ] Add benchmark prompts for Cypher migration
- [ ] Add benchmark prompts for Gremlin migration
- [ ] Add benchmark prompts for SQL migration
- [ ] Add benchmark prompts for optimization
- [ ] Add benchmark prompts for dynamic JSON execution
- [ ] Add at least one gold answer per benchmark case
- [ ] Add a scoring checklist per benchmark case
- [ ] Run a first benchmark pass with OpenCode
- [ ] Record failures and update the relevant skills

### Phase 11: Launch Readiness

- [ ] Verify every skill directory name matches the `name` field in frontmatter
- [ ] Verify every `description` is specific and searchable
- [ ] Verify all links in `SKILL.md` files resolve within the repo
- [ ] Verify installability with `npx skills add HelixDB/<repo-name> --list`
- [ ] Verify installability with `npx skills add HelixDB/<repo-name> --skill helix-query-authoring`
- [ ] Verify README installation instructions are correct
- [ ] Verify the benchmark manifest matches the shipped skills
- [ ] Cut the initial public release

## Open Items

- [ ] Choose the final repository name
- [ ] Decide whether to add a hidden internal shared-core skill later
- [ ] Decide whether benchmark gold answers should be code-only or code-plus-rationale
- [ ] Decide whether to include agent-specific compatibility notes beyond OpenCode and generic `skills.sh`
- [ ] Decide whether to version example packs independently from skills

## Suggested Next Move

Start with the hosted repo `README.md`, `docs/source-canon.md`, and `skills/helix-query-authoring/SKILL.md` first. Those three pieces will define the tone and working pattern for everything else.
