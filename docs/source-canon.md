# Source Canon

This repository should use public Helix documentation and repo-local canonical examples as its primary references. The SDK, error-transport, CLI-auth, HTTP/OpenAPI, and planner guidance was last reviewed against `HelixDB/helix-db` main at `5ec14e5f8cf059aa03f42917d560b3cded09fb26`.

## Verified release boundaries

On 2026-09-28, the published package artifacts were Rust 3.0.0, TypeScript 3.2.0,
Python 0.3.4, and Go v0.3.1. TypeScript 3.1.0 and later expose structured remote
errors (`HelixError.code`, `statusCode`, `serverMessage`, `retryable`) and accept
Cloud warm success 204; 3.2.0 adds `withDatabaseId`. The published Rust, Python,
and Go packages accept HTTP 200 but still reject Cloud warm success 204. A
main-branch implementation is not evidence that the same behavior has shipped in
a package version. Use direct HTTP for Cloud warming from those SDKs, since the
released CLI's `--warm` flag is local-only.

The published Docker image `ghcr.io/helixdb/helixdb:v0.0.6` supports Linux amd64
and arm64 and is the default of the released CLI 3.3.0, which saves it as the
`tag` of new local blocks in `helix.toml`. Native-volume persistence, typed
`f32`/`f64` JSON parameters (including integer JSON values), normalized
responses, and standalone warming were verified against the released arm64
image. Existing projects retain their saved tag; set `tag = "v0.0.6"` to upgrade.

Planner source links describe the current main-branch model. Verify the deployed
engine's version and actual plan before promising that a specific optimization
is present in an older image.

## Working Order

When an agent is writing or reviewing Helix query code, it should use sources in this order:

1. the user's local repo and schema
2. this repository's canonical docs in `docs/`
3. this repository's generic examples in `examples/`
4. public Helix documentation for product semantics and public behavior
5. the v3 SDK source on `HelixDB/helix-db` `main` for exact public names
6. public skill-format docs for packaging and discovery behavior

This ordering is intentional. The skills track the published Rust 3.0.0,
TypeScript 3.2.0, Python 0.3.4, and Go 0.3.1 SDK lines. Public documentation is
the behavior contract; use the SDK source to confirm exact identifiers rather
than guessing from an older release.

## Public Helix References

Use these for product semantics and supported behavior:

- `https://docs.helix-db.com/database/helix-db/start-here/quickstart`
- `https://docs.helix-db.com/database/helix-db/start-here/local-development/local-server`
- `https://docs.helix-db.com/database/helix-db/start-here/sdk-setup/rust-project-setup`
- `https://docs.helix-db.com/database/helix-db/start-here/sdk-setup/typescript-project-setup`
- `https://docs.helix-db.com/database/helix-db/start-here/sdk-setup/go-project-setup`
- `https://docs.helix-db.com/database/helix-db/start-here/sdk-setup/python-project-setup`
- `https://docs.helix-db.com/database/helix-cloud/connect/mcp`
- `https://docs.helix-db.com/database/helix-db/core-concepts/overview`
- `https://docs.helix-db.com/database/helix-db/query-guides/writing-data`
- `https://docs.helix-db.com/database/helix-db/query-guides/reading-data`
- `https://docs.helix-db.com/database/helix-db/query-guides/traversals`
- `https://docs.helix-db.com/database/helix-db/query-guides/filtering`
- `https://docs.helix-db.com/database/helix-db/query-guides/projections`
- `https://docs.helix-db.com/database/helix-db/query-guides/secondary-indexes`
- `https://docs.helix-db.com/database/helix-db/query-guides/vector-indexes`
- `https://docs.helix-db.com/database/helix-db/query-guides/text-indexes`
- `https://docs.helix-db.com/database/helix-db/query-guides/advanced`
- `https://docs.helix-db.com/database/helix-db/query-guides/parameters`
- `https://docs.helix-db.com/database/helix-db/query-guides/http-api`
- `https://docs.helix-db.com/database/helix-cloud/operate/error-handling`
- `https://docs.helix-db.com/database/helix-cloud/operate/limits`
- `https://docs.helix-db.com/database/helix-db/query-guides/traversals`
- `https://docs.helix-db.com/database/helix-db/query-guides/filtering`
- `https://docs.helix-db.com/database/helix-db/query-guides/advanced`
- `https://docs.helix-db.com/database/helix-db/query-guides/projections`
- `https://docs.helix-db.com/database/helix-db/query-guides/vector-indexes`
- `https://docs.helix-db.com/database/helix-db/query-guides/text-indexes`

Use these for skill packaging and discovery behavior:

- `https://skills.sh/docs`
- `https://opencode.ai/docs/skills`

Use these `main` branches for exact v3 SDK identifiers:

- `https://github.com/HelixDB/helix-db/tree/main/sdks/rust`
- `https://github.com/HelixDB/helix-db/tree/main/sdks/typescript`
- `https://github.com/HelixDB/helix-db/tree/main/sdks/go`
- `https://github.com/HelixDB/helix-db/tree/main/sdks/python`

## Repo-Local Canonical References

Use these as the main references inside this published skills repo:

- `docs/dsl-cheatsheet.md`
- `docs/go-dsl-cheatsheet.md`
- `docs/cypher-rosetta.md`
- `docs/gremlin-rosetta.md`
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
- Keep installation commands unpinned and verify registry availability before claiming that an SDK is published.
- Do not use a feature branch in a published source link. The coordinated repositories are consumed from `main`.
- Prefer generic labels, properties, and edge names in published examples unless a public Helix doc requires a more specific term.
- Use the user's local repo as the authority for their actual schema, naming, and route style.

## Publication Standard

Before publishing a skill or support doc, ask:

1. would this still make sense if the reader had never seen our internal or local repos?
2. does it point to public docs or repo-local docs rather than machine-local files?
3. is it teaching Helix behavior rather than one application's habits?

If the answer is no, rewrite it before shipping.
