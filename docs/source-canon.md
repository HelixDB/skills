# Source Canon

This repository should use public Helix documentation and repo-local canonical examples as its primary references.

## Working Order

When an agent is writing or reviewing Helix query code, it should use sources in this order:

1. the user's local repo and schema
2. public Helix documentation for semantics and supported behavior
3. this repository's canonical docs in `docs/`
4. this repository's generic examples in `examples/`
5. public skill-format docs for packaging and discovery behavior

## Public Helix References

Use these for product semantics and supported behavior:

- `https://docs.helix-db.com/enterprise/introduction`
- `https://docs.helix-db.com/documentation/hql/traversals`
- `https://docs.helix-db.com/documentation/hql/conditionals`
- `https://docs.helix-db.com/documentation/hql/result_ops`
- `https://docs.helix-db.com/documentation/hql/output_values`
- `https://docs.helix-db.com/documentation/hql/vectors`
- `https://docs.helix-db.com/documentation/hql/keyword_search`

Use these for skill packaging and discovery behavior:

- `https://skills.sh/docs`
- `https://opencode.ai/docs/skills`

## Repo-Local Canonical References

Use these as the main references inside this published skills repo:

- `docs/dsl-cheatsheet.md`
- `docs/dynamic-query-examples.md`
- `docs/optimization-checklist.md`
- `examples/authoring-patterns.md`
- `examples/search-patterns.md`
- `examples/optimization-patterns.md`

These files should be self-contained enough that public skills can point to them directly without sending readers to machine-local paths.

## Rules

- Do not use machine-local filesystem paths as published source pointers.
- Do not treat application-specific implementations as canonical Helix references.
- If a useful idea is learned from an implementation, convert it into a generic documented pattern before publishing it here.
- Prefer generic labels, properties, and edge names in published examples unless a public Helix doc requires a more specific term.
- Use the user's local repo as the authority for their actual schema, naming, and route style.

## Publication Standard

Before publishing a skill or support doc, ask:

1. would this still make sense if the reader had never seen our internal or local repos?
2. does it point to public docs or repo-local docs rather than machine-local files?
3. is it teaching Helix behavior rather than one application's habits?

If the answer is no, rewrite it before shipping.
