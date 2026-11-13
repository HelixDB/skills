---
name: helix-cli
description: Drive the HelixDB v3 `helix` CLI (3.7.0) for local Docker/Podman instances and WorkOS-session Helix Cloud discovery, resource management, query, shell, cypher, doctor, status and logs. Use for helix init/add/start/stop/query/shell/cypher/doctor/explorer/auth/workspace/project/cluster/database/service-credential/api/skills and helix.toml. Run it with --json in agent sessions. Cloud login is interactive and WorkOS-only, so the user runs `helix auth login`; never supply API keys or service credentials as a CLI login. Defer query-body authoring to helix-query-* skills.
license: MIT
metadata:
  author: HelixDB
  version: 5.0.0
---

# Helix CLI

Use the CLI as a runtime and control-plane client. It does not compile `.hx` files, deploy query
bundles, push source, or sync gateway metadata. `REFERENCE.md` has every command and flag;
`EXAMPLES.md` has end-to-end sessions.

## Run it as an agent

- Pass the global `--json` on every command. It never prompts, prints only the result as compact
  JSON on stdout, and reports a failure on stderr as
  `{"error": {"message", "context"?, "caused_by"?, "hint"?, "candidates"?: [{"id", "name"}]}}`.
  A runtime failure exits 1; a usage error (bad flag or argument) exits 2.
- When stdin or stderr is not a terminal, or under `--json`, the CLI cannot prompt. A
  command that would have shown a picker fails instead and lists `candidates`: re-run with one of
  them (`--workspace`, `--project`, `--database`, an instance name, or a typed `tenant:<id>` /
  `cluster:<id>`). Never guess between candidates; ask the user.
- Destructive commands (`delete`, `prune`, `project delete`, `database delete`,
  `database key revoke`, `service-credential revoke`) need `--yes` without a terminal. `--yes` is
  per command, not global. Pass it only after the user confirmed that exact action.
- `--quiet` prints errors and the final result only; `-v`/`--verbose` adds timings. Neither
  combines with `--json`.
- `helix chef`, `helix skills install` and `helix skills list` are interactive and refuse `--json`.

## Choose the execution boundary

- Local `[local.<name>]`: Docker/Podman, auth-disabled local `/v2/query` on the instance port.
- Cloud `[enterprise.<name>]` or a typed `tenant:<id>` / `cluster:<id>`: the backend query broker,
  authenticated by the user's WorkOS session, never a direct gateway request.
- Application gateway access (SDK or HTTP from the user's app): outside the CLI; uses an explicitly
  created database key.

## Local image and storage

The CLI 3.7.0 default image is `ghcr.io/helixdb/helixdb:v0.0.16`. `helix init` writes that
`tag` into `[local.<name>]`. An older project may still pin an older `tag` (such as `v0.0.5`): that
image lacks `/v2/cypher` and `/v2/diagnostics`, so `helix cypher` and `helix doctor` fail against
it. Update the `tag` to `v0.0.16` when the user upgrades; do not add pins to older tags. Override for
one run with `helix start --image-version <tag|sha256:...>` and `--pull always|missing|never`; add
`--persist` to save the resolved settings.

The server listens on container port 8080 (`/healthz`, `/readyz`, `/v2/query`, `/v2/cypher`); the
CLI publishes host port 6969 by default and waits for `/healthz`.

Memory storage is the default and loses data on stop/restart. `--disk` runs a CLI-managed
SeaweedFS sidecar with a named volume; data written by older MinIO-based CLIs is not readable by it
(the old volume is left until `helix prune`). `--storage-uri s3://bucket/prefix` uses an external
S3-compatible store with credentials from the standard AWS environment variables or the
project-root `.env`, never `helix.toml`. Direct `docker run` persistence uses `HELIX_DATA_DIR`
instead (see `EXAMPLES.md`).

## Cloud authentication

`helix auth login` needs an interactive terminal and fails under an agent ("logging in needs an
interactive terminal"). Do not run it yourself: ask the user to run `helix auth login` (or
`helix auth login github|google|microsoft|sso|password`) in their own terminal, then check with
`helix auth status --json`.

The session is a WorkOS session stored in `~/.helix/credentials` (mode 0600; `$HELIX_HOME`
overrides `~/.helix`). Never ask for or set a Cloud API key, legacy admin/user key, service
credential, custom authorization header, or gateway URL as CLI auth. When a Cloud command fails
with an expired or missing session, ask the user to log in again. Do not retry a Cloud mutation.

## Target resolution

- `query`, `shell`, `doctor`, `logs`: an explicit instance name, or for `query`, `shell` and
  `doctor` a typed `tenant:<id>` / `cluster:<id>` (which needs no `helix.toml`); otherwise `dev`,
  then the only instance in `helix.toml`, then a prompt, else an error listing the instances.
  `status` without an instance shows every instance.
- Cloud resource commands: an explicit `--workspace` / `--project` / `--database` / positional
  name (matched by ID, then slug, then display name); otherwise the project and databases linked in
  `helix.toml`; then the only candidate; then a prompt; else an error listing candidates.
- There is no global workspace selection and no `workspace switch`.

## Main workflows

```bash
# Local
helix init local                 # writes helix.toml, AGENTS.md, examples/request.json
helix start dev
helix query dev --file examples/request.json
helix stop dev

# Cloud, after the user ran `helix auth login`
helix workspace list --json
helix project list --workspace <workspace> --json
helix database list --project <project> --json
helix query tenant:<id> --file request.json --json        # no helix.toml needed

# Cloud project directory (fresh directory, no helix.toml yet)
helix init cloud --database tenant:<id> --no-skills --json
helix query production --file request.json --json
```

`helix project link` and `helix add cloud` edit an existing `helix.toml`; in a fresh directory
they fail. Use `helix init cloud` (or `helix init local` then `helix add cloud`).

Cloud `query`/`shell` need the independent `database.query.read` / `database.query.write`
permission on the database's project; management `read`/`write` does not imply them.

Query input is exactly one of `--file request.json`, `--body '<inline JSON>'`, `-e '<TS DSL>'`
(needs Node 20+) or `--ts-file query.ts`. The global `--json` is the output flag, not an input.

## Secret lifecycle

- `helix database create` creates a default read-write application key and prints its token once;
  the CLI never stores or uses it.
- `helix database key create --database <ref> --access read-only|read-write` prints an application
  token once.
- `helix service-credential create` prints a headless API/MCP token (`hlxs_`) once; it is never a
  CLI login.
- Never put any token in `helix.toml`, agent instructions, source control, or command history;
  capture it straight into the user's secret store.

## Docs and skills

`helix init --skills` and `helix chef` install these skills plus the Helix docs MCP, registered as
`helixdb-docs` (`https://docs.helix-db.com/mcp`). Query it for syntax this skill does not cover.
`helix skills update --json` refreshes installed skills.

## Removed and excluded surfaces

Do not use or recommend `compile`, `check`, `deploy`, `push`, `sync`, `auth create-key`,
`workspace switch`, `--compact`, `--workspace-id`, `--format`, query bundles, dedicated-cluster
lifecycle, networking, regions/SKUs, branches/backups, schema introspection, execution
polling/cancellation, webhooks, or project update. Use a `helix-query-*` skill to author v3
request bodies.

## Which Helix skill

| Task | Skill |
| --- | --- |
| Run or manage local/Cloud instances from a shell | `helix-cli` |
| Discover Cloud resources, active indexes, insights, latency, usage, health over MCP | `helix-mcp` |
| Run an explicitly requested Cloud read or write over MCP | `helix-query-mcp` |
| Create/delete a tenant database or create/revoke a database key over MCP | `helix-admin-mcp` |
| Write query bodies | `helix-query-typescript`, `-rust`, `-python`, `-go`, `-json-dynamic` |
| Build an app's own agent memory on Helix | `helix-memory-system` |
| Ask or read a business's Foundry ontology | `helix-foundry-mcp` |
