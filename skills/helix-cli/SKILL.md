---
name: helix-cli
description: Drive the HelixDB v3 `helix` CLI (3.7.0) for local Docker/Podman instances and WorkOS-session Helix Cloud discovery, resource management, query, shell, cypher, doctor, status and logs. Use for helix init/add/start/stop/query/shell/cypher/doctor/explorer/auth/workspace/project/cluster/database/service-credential/api/skills and helix.toml. Run it with --json in agent sessions. Cloud login is interactive and WorkOS-only, so the user runs `helix auth login`; never supply API keys or service credentials as a CLI login. Defer query-body authoring to helix-query-* skills.
license: MIT
metadata:
  author: HelixDB
  version: 5.0.0
---

# Helix CLI

A runtime and control-plane client: no `.hx` compile, query-bundle deploy, source push or gateway
sync. All commands and flags: `REFERENCE.md`. End-to-end sessions: `EXAMPLES.md`.

## Run it as an agent

- Pass global `--json` on every command: never prompts, compact result JSON on stdout, failures on
  stderr as `{"error": {"message", "context"?, "caused_by"?, "hint"?, "candidates"?: [{"id", "name"}]}}`.
  Runtime failure exits 1; usage error (bad flag/argument) exits 2.
- Under `--json` or without a terminal (stdin or stderr not a TTY), a picker fails and lists
  `candidates`: ask the user, then re-run with one (`--workspace`, `--project`, `--database`, an
  instance name, or `tenant:<id>` / `cluster:<id>`). Never guess.
- `delete`, `prune`, `project delete`, `database delete`, `database key revoke` and
  `service-credential revoke` need `--yes` without a terminal. `--yes` is per command, not global;
  pass it only after the user confirmed that exact action.
- `--quiet` (errors and final result only) and `-v`/`--verbose` (timings) don't combine with `--json`.
- `helix chef`, `helix skills install` and `helix skills list` are interactive and refuse `--json`.

## Execution boundaries

| Target | Path | Auth |
| --- | --- | --- |
| Local `[local.<name>]` | Docker/Podman, `/v2/query` on the instance port | None (auth disabled) |
| Cloud `[enterprise.<name>]`, `tenant:<id>`, `cluster:<id>` | Backend query broker; never a direct gateway request | User's WorkOS session |
| App gateway (SDK or HTTP from the user's app) | Outside the CLI | Explicitly created database key |

## Local runtime

- Default image `ghcr.io/helixdb/helixdb:v0.0.16`; `helix init` writes that `tag` into
  `[local.<name>]`. An older pinned `tag` (e.g. `v0.0.5`) lacks `/v2/cypher` and `/v2/diagnostics`,
  so `helix cypher` and `helix doctor` fail: update it to `v0.0.16`; never add older pins. One run:
  `helix start --image-version <tag|sha256:...> --pull always|missing|never`; `--persist` saves it.
- Container port 8080 (`/healthz`, `/readyz`, `/v2/query`, `/v2/cypher`), host port 6969 by
  default; the CLI waits for `/healthz`.
- Storage: memory (default; lost on stop/restart); `--disk` (CLI-managed SeaweedFS sidecar volume;
  can't read data from older MinIO-based CLIs, whose volume stays until `helix prune`);
  `--storage-uri s3://bucket/prefix` (credentials from AWS env vars or the project-root `.env`, never
  `helix.toml`). Direct `docker run` persistence uses `HELIX_DATA_DIR` (`EXAMPLES.md`).

## Cloud authentication

- `helix auth login` is interactive only (under an agent: "logging in needs an interactive
  terminal"). Ask the user to run `helix auth login` (or `helix auth login
  github|google|microsoft|sso|password`) in their own terminal, then check `helix auth status --json`.
  Expired or missing session: ask them to log in again.
- The WorkOS session lives in `~/.helix/credentials` (mode 0600; `$HELIX_HOME` overrides
  `~/.helix`). Never ask for or set a Cloud API key, legacy admin/user key, service credential,
  custom authorization header or gateway URL as CLI auth.
- Never retry a Cloud mutation.

## Target resolution

- `query`, `shell`, `doctor`, `logs`: explicit instance (or, except `logs`, `tenant:<id>` /
  `cluster:<id>`, no `helix.toml` needed) → `dev` → the only instance → prompt → error listing
  instances. `status` with no instance shows all.
- Cloud resource commands: explicit `--workspace` / `--project` / `--database` / positional (by ID,
  then slug, then display name) → project and databases linked in `helix.toml` → the only
  candidate → prompt → error listing candidates.
- No global workspace selection, no `workspace switch`.

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

- `helix project link` and `helix add cloud` need an existing `helix.toml`; in a fresh directory use
  `helix init cloud` (or `helix init local`, then `helix add cloud`).
- Cloud `query`/`shell` need `database.query.read` / `database.query.write` on the database's
  project; management `read`/`write` doesn't imply them.
- Query input is exactly one of `--file`, `--body '<JSON>'`, `-e '<TS DSL>'`, `--ts-file` (TS needs
  Node 20+); `--json` is output, not input. Author v3 bodies with a `helix-query-*` skill.

## Secrets

Each token prints once and the CLI never keeps or uses it. Capture it straight into the user's
secret store; never into `helix.toml`, agent instructions, source control or command history.

| Command | Prints |
| --- | --- |
| `helix database create` | Default read-write application key |
| `helix database key create --database <ref> --access read-only\|read-write` | Application key |
| `helix service-credential create` | Headless API/MCP token (`hlxs_`); never a CLI login |

## Docs and skills

`helix init --skills` and `helix chef` install these skills and the docs MCP `helixdb-docs`
(`https://docs.helix-db.com/mcp`; query it for syntax not covered here). `helix skills update
--json` refreshes them.

## Removed or excluded

Never use or recommend `compile`, `check`, `deploy`, `push`, `sync`, `auth create-key`,
`workspace switch`, `--compact`, `--workspace-id`, `--format`, query bundles, dedicated-cluster
lifecycle, networking, regions/SKUs, branches/backups, schema introspection, execution
polling/cancellation, webhooks or project update.

## Which Helix skill

| Task | Skill |
| --- | --- |
| Run or manage local/Cloud instances from a shell | `helix-cli` |
| Cloud discovery, active indexes, insights, latency, usage, health over MCP | `helix-mcp` |
| Explicitly requested Cloud read or write over MCP | `helix-query-mcp` |
| Tenant database create/delete or database key create/revoke over MCP | `helix-admin-mcp` |
| Write query bodies | `helix-query-typescript`, `-rust`, `-python`, `-go`, `-json-dynamic` |
| Build an app's own agent memory on Helix | `helix-memory-system` |
| Ask or read a business's Foundry ontology | `helix-foundry-mcp` |
