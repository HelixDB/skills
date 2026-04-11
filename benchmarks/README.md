# Benchmarks

This directory will hold prompt sets, gold answers, and scoring notes for each public skill.

Current benchmark groups with prompt coverage:

- `cypher`
- `gremlin`

Planned next benchmark groups:

- `authoring`
- `dynamic`
- `optimize`
- `sql`

The goal is to evaluate whether a skill improves agent output quality, not just whether the skill reads well.

Every benchmark case should include:

- a prompt
- the expected skill
- the key behaviors being tested
- a gold translation sketch or gold expectations
- a flat scoring checklist
