# Benchmarks

This directory holds prompt sets, gold answers, and scoring notes for the public v3
skills.

Current benchmark groups with prompt coverage:

- `cypher`
- `gremlin`

Planned next benchmark groups:

- `authoring`
- `dynamic`
- `optimize`
- `sql`

The goal is to evaluate whether a skill improves agent output quality and produces
direct v3 requests, not just whether the skill reads well.

Every benchmark case should include:

- a prompt
- the expected skill
- the key behaviors being tested
- a gold translation sketch or gold expectations
- a flat scoring checklist

Gold answers must use the forthcoming v3 SDK names and the nested direct-request JSON
AST. Stored routes, registration, step arrays, and query bundles are failures unless
the prompt explicitly asks to identify invalid legacy guidance.
