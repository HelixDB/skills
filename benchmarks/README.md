# Benchmarks

Prompt sets, gold answers and scoring notes for the public v3 skills. They test
whether a skill improves agent output and produces direct v3 requests, not
whether it reads well.

Groups with prompts: `cypher`, `dynamic`, `gremlin`, `optimize`. Planned:
`authoring`, `sql`.

Each case has a prompt, the expected skill, the behaviors tested, a gold
translation sketch or expectations, and a flat scoring checklist.

Gold answers use v3 SDK names and the nested direct-request JSON AST, and match
`docs/source-canon.md` (empty returns are `[]`, IDs are integers, branch on
`retryable`, not the 409 status). Stored routes, registration, step arrays and
query bundles fail unless the prompt asks to identify invalid legacy guidance.
For Cypher and SQL prompts, sending a supported statement unchanged to
`POST /v2/cypher` or `POST /v2/sql` is correct unless the prompt asks for DSL code.
