# Benchmarks

This directory holds prompt sets, gold answers, and scoring notes for the public v3
skills.

Current benchmark groups with prompt coverage:

- `cypher`
- `dynamic`
- `gremlin`
- `optimize`

Planned next benchmark groups:

- `authoring`
- `sql`

The goal is to evaluate whether a skill improves agent output quality and produces
direct v3 requests, not just whether the skill reads well.

Every benchmark case should include:

- a prompt
- the expected skill
- the key behaviors being tested
- a gold translation sketch or gold expectations
- a flat scoring checklist

Gold answers must use the v3 SDK names and the nested direct-request JSON AST, and
must match the contracts in `docs/source-canon.md` (empty returns are `[]`, IDs are
integers, branch on `retryable` rather than the 409 status). Stored routes,
registration, step arrays, and query bundles are failures unless the prompt explicitly
asks to identify invalid legacy guidance. For Cypher and SQL prompts, sending a
supported statement unchanged to `POST /v2/cypher` or `POST /v2/sql` is a correct
answer unless the prompt asks for DSL code.
