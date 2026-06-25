# Helix CLI — Reference

Full command catalog and config reference for the `helix` CLI (crate `helix-cli`, v3.x). Sourced from the CLI clap definitions and config module; where the published docs disagree with the source, the source wins. Install with:

```bash
curl -sSL "https://install.helix-db.com" | bash   # installs ~/.helix/bin/helix
```

## Global Flags

Apply to every command:

| Flag | Effect |
|---|---|
| `--quiet` | Suppress output — errors and the final result only. |
| `-v`, `--verbose` | Detailed output with timing information. |
| `-V`, `--version` | Print the CLI version. |
| `-h`, `--help` | Show help for the command. |

With no subcommand, `helix` prints a welcome banner (and any available CLI/skills update notice).

## Project Setup

### `helix init [OPTIONS] [TARGET]`

Scaffold a new project: writes `helix.toml`, a `.helix/` workspace dir, `.gitignore` entries (`.helix/`, `target/`, `*.log`), and — for local targets only — `examples/request.json` and an `AGENTS.md` (instructions for coding agents picking up the project; never overwrites an existing one). With no target it prompts interactively.

Top-level flags (before or independent of the target):

| Flag | Default | Purpose |
|---|---|---|
| `-p, --path <DIR>` | current dir | Project directory. |
| `--skills` | — | Install the Helix agent skills + docs MCP (conflicts with `--no-skills`). |
| `--no-skills` | — | Skip installing skills/MCP. |

Targets:

- `helix init local` — local dev project.
  - `-n, --name <NAME>` (default `dev`)
  - `--port <PORT>` (default `6969`)
  - `--disk` — on-disk storage backed by a local MinIO container (default is in-memory)
  - `--skills` / `--no-skills` — also accepted after the subcommand
- `helix init cloud` (alias `enterprise`) — Helix Cloud project.
  - `-n, --name <NAME>` (default `production`)
  - `--cluster-id <ID>` — omit to pick interactively from the cluster list
  - `--gateway-url <URL>` — optional; fetched by `helix sync` if omitted
  - `--skills` / `--no-skills`

### `helix chef` (alias `cook`)

Interactive one-shot bootstrapper that hands off to a coding agent. **Takes no flags** — fully interactive. It: ensures Helix Cloud auth, asks your build intent, installs skills + docs MCP, runs `helix init local`, writes `HELIX_CHEF_PROMPT.md`, starts the dev instance, optionally seeds data, detects and launches a coding agent (Claude Code → Codex → OpenCode), and opens the generated app at `http://localhost:3000`.

- `HELIX_SKIP_CLOUD_AUTH=1` — skip the optional Cloud login in an interactive shell.
- Non-TTY (agents/CI): skips login automatically.

### `helix add [TARGET]`

Add an instance to an existing `helix.toml` without clobbering others.

- `-p, --path <DIR>` — project directory containing `helix.toml` (default: walk up from the current dir). Accepted before or after the target: `helix add --path ./app local --name qa` and `helix add local --name qa --path ./app` both work.
- `helix add local` — `-n, --name <NAME>` (required), `--port <PORT>` (default `6969`), `--disk`.
- `helix add cloud` (alias `enterprise`) — `-n, --name <NAME>` (required), `--cluster-id <ID>`, `--gateway-url <URL>`.

## Local Lifecycle

### `helix start [INSTANCE] [OPTIONS]` (alias `run`)

Start a local container (named `helix-<project>-<instance>`) in the background. Pulls `ghcr.io/helixdb/enterprise-dev:latest`, publishes the host port to container port 8080, and waits (~30s) until `POST /v1/query` is ready before returning.

| Flag | Purpose |
|---|---|
| `[INSTANCE]` | Local instance name (default `dev`). |
| `--foreground` | Run attached; Ctrl-C stops the container. (`--detach` is a hidden alias for the default background mode.) |
| `--port <PORT>` | Override the host port for this run. |
| `--disk` | Use on-disk/MinIO storage for this run (starts a MinIO sidecar + network + volume; creates a `helix-db` bucket). |
| `--persist` | Write the resolved port/storage back to `helix.toml`. |

In-memory is the default; the data-loss warning is shown once per instance.

### `helix stop [INSTANCE]`

Stop (and remove) the background container. Idempotent — succeeds even if not running. Disk-mode keeps the persistent volume.

### `helix restart [INSTANCE]`

Restart the container in place; if it was removed, falls back to a fresh `start`. In-memory data is lost on restart; disk-mode data persists.

### `helix status [INSTANCE]`

Show project + per-instance details (URL, cluster id, storage mode, container state). Local state comes from `docker/podman ps -a`; cloud state from `helix.toml`. Omit the instance to show all.

### `helix logs [INSTANCE] [OPTIONS]`

- Local: `docker/podman logs`. `-f, --follow` streams live.
- Cloud (Enterprise): `-r, --range` fetches a historical time range; `--start <RFC3339>` (default end − 1h), `--end <RFC3339>` (default now UTC). Requires `helix auth login`.

### `helix prune [INSTANCE] [OPTIONS]`

Remove Helix-owned resources: the container, plus (disk mode) the MinIO sidecar, network, and volume, and the per-instance `.helix/` dir. Does **not** run a broad `docker/podman system prune`.

- `-a, --all` — prune every local instance.
- `-y, --yes` — skip confirmation (required with `--all` in non-TTY). Non-interactive needs an instance name or `--all`.

### `helix delete <INSTANCE> [OPTIONS]`

Remove an instance from `helix.toml` **and** its local runtime state (containers/volumes/workspace). For cloud instances, removes only the config block (the cluster is untouched). Instance arg is required.

- `-y, --yes` — skip confirmation (required in non-TTY).

## Queries

### `helix query [INSTANCE] <INPUT> [OPTIONS]`

Send a dynamic query to `POST /v1/query`. `[INSTANCE]` defaults to `dev`.

Exactly one input flag is required (mutually exclusive arg group):

| Flag | Input |
|---|---|
| `-f, --file <PATH>` | Raw dynamic-query JSON request file. |
| `--json '<JSON>'` | Inline raw dynamic-query JSON string. |
| `-e, --ts '<TS>'` | TypeScript DSL expression, evaluated inline (like `mysql -e`). |
| `--ts-file <PATH>` | TypeScript DSL from a file. |

Options:

| Flag | Purpose |
|---|---|
| `--warm` | Add `X-Helix-Warm` to pre-warm caches (read requests only); output suppressed. |
| `--host <HOST>` | Override host for local instances (default `localhost`). |
| `--port <PORT>` | Override port for local instances. |
| `--compact` | Print single-line JSON (default is pretty). |

**Request JSON shape** (`--file` / `--json`):

```json
{
  "request_type": "read",          // lowercase "read" or "write" (required)
  "query_name": "node_count",      // optional; defaults to __dynamic__
  "query": {                        // required
    "queries": [
      {
        "Query": {
          "name": "node_count",
          "steps": [
            { "NWhere": { "Eq": ["$label", { "String": "User" }] } },
            "Count"
          ],
          "condition": null
        }
      }
    ],
    "returns": ["node_count"]
  },
  "parameters": {}                  // optional
}
```

See `helix-query-json-dynamic` for the full inline-AST grammar.

**TypeScript DSL** (`-e` / `--ts-file`):

- Auto-imports in scope: `g`, `readBatch`, `writeBatch`, `defineParams`, `param`.
- The CLI evaluates the expression in Node (needs Node 20+ on PATH), calls `.toDynamicJson()`, and infers `request_type` from read-vs-write batch.
- The `@helix-db/helix-db` SDK is `npm install`ed once into `<helix cache>/ts-runtime/` (spec `^2.0.6`, i.e. the latest 2.x), reused thereafter.

**Cloud auth:** for an `[enterprise.<instance>]` target, the CLI posts to `<gateway_url>/v1/query` with the header named by `query_auth_header` (default `Authorization`), valued from the env named by `query_auth_env` (default `HELIX_API_KEY`), read from the shell or a project-root `.env`.

**Connection errors:** if the instance is unreachable, the CLI reports `cannot reach Helix instance '<instance>' at <endpoint>` with a kind-specific hint — local: `helix start <instance>` then `helix status <instance>` (or pass `--host`/`--port`); enterprise: check `gateway_url` in `helix.toml` and run `helix sync <instance>`.

## Cloud

### `helix auth <SUBCOMMAND>`

- `login` — GitHub device-code OAuth; stores `~/.helix/credentials`.
- `logout` — clear credentials.
- `create-key <CLUSTER>` — rotate a cluster API key (shown once; update `HELIX_API_KEY` before the next query).

### `helix push [INSTANCE]`

Deploy an Enterprise instance to Helix Cloud; streams progress. Errors on a local instance (use `helix start`). Prompts for the instance in a TTY if omitted.

### `helix sync [INSTANCE] [OPTIONS]`

Reconcile enterprise metadata + source between local and cloud (SHA256/mtime diff). Updates `[enterprise.<instance>]` in `helix.toml`: `gateway_url`, `query_auth_header`, `query_auth_env`, `availability_mode`, `gateway_node_type`, `db_node_type`. Syncs all enterprise instances if omitted. Requires `helix auth login`.

- `--dry-run` — fetch remote state and print the plan without writing (conflicts with `--yes`).
- `-y, --yes` — skip interactive conflict prompts (CI).

### `helix workspace <list|show|switch>`

Manage the active cloud workspace (persisted in `~/.helix/config`, global across projects).

- `list` / `show` — `--format <human|json>` (default human).
- `switch <WORKSPACE>` — by slug, or `--id` to treat the arg as an ID.
- No subcommand in a TTY → interactive picker.

### `helix project <list|show|switch>`

Manage the linked cloud project (persisted in `helix.toml` under `[project] workspace_id` / `id`).

- `list` — `--workspace-id <ID>`, `--format <human|json>`.
- `show` — `--format`.
- `switch <PROJECT>` — by name, or `--id`.

### `helix cluster <list|indexes>`

- `list` — `--workspace-id <ID>`, `--project-id <ID>`, `--format <human|json>`.
- `indexes` (alias `indices`) — `--cluster-id <ID>` (defaults to the current project's Enterprise cluster), `--format`.

(`helix config <workspace|project|cluster> …` is a hidden parent grouping these.)

## Utility

### `helix metrics <full|basic|off|status>`

Manage telemetry level (`~/.helix/metrics.toml`). `full` prompts for an email; `basic` is anonymous; `off` disables; `status` shows the current level.

### `helix update [OPTIONS]`

Self-update the CLI binary (and refresh installed skills; failure degrades to a warning).

- `--force` — update even if already on latest.
- `--v1` — pin the last v1-compatible release.

### `helix feedback [MESSAGE]`

Open a pre-filled GitHub issue (prompts for the message in a TTY if omitted).

### `helix skills <install|update|list> [OPTIONS]`

Manage the Helix agent skills (`HelixDB/skills`).

- `install` / `update` / `list`.
- `--project` — operate on the current project instead of globally.

## Removed Commands

These exist only as hidden stubs that print a friendly error — do not use them:

| Removed | What to do instead |
|---|---|
| `helix compile` | Nothing — v3 validates queries server-side; there is no compile step. |
| `helix check` | Nothing — validation is server-side; there is no check step. |
| `helix deploy` | `helix push <instance>` to deploy an Enterprise Cloud instance. |

There is also no `.hx` query workflow — queries are JSON dynamic queries (or the TS DSL) sent to a running instance.

## Configuration Files

### `helix.toml` (project config)

Found by walking up the directory tree. Annotated example with all common fields:

```toml
[project]
name = "my-helix-app"           # required; used in container name helix-<project>-<instance>
id = "prj_01HX..."              # optional; set by `helix project switch`
workspace_id = "ws_01HX..."     # optional; set by `helix project switch`
queries = "db"                  # optional; query files path (default "db")
container_runtime = "docker"    # "docker" (default) or "podman"

[local.dev]                     # one block per local instance
port = 6969                     # default 6969 (host → container port 8080)
image = "ghcr.io/helixdb/enterprise-dev"   # default
tag = "latest"                  # default
storage = "memory"              # "memory" (default) or "disk"

[local.staging]
port = 9090
storage = "disk"                # persistent (MinIO-backed)

[enterprise.production]         # one block per Helix Cloud instance
cluster_id = "ec_01HX..."       # required
workspace_id = "ws_01HX..."     # optional
project_id = "prj_01HX..."      # optional
gateway_url = "https://gateway.example.com"   # filled by `helix sync`
query_auth_header = "Authorization"           # default
query_auth_env = "HELIX_API_KEY"              # default; env var read for the auth value
availability_mode = "ha"        # from `helix sync`
gateway_node_type = "GW-40"     # from `helix sync`
db_node_type = "HLX-160"        # from `helix sync`
min_instances = 1               # default 1
max_instances = 1               # default 1
# flattened DbConfig fields also live here:
# mcp = true, bm25 = true, schema = "...", embedding_model = "text-embedding-ada-002",
# graphvis_node_label = "name", plus [enterprise.production.vector_config]
# (m=16, ef_construction=128, ef_search=768, db_max_size_gb=20) and
# [enterprise.production.graph_config] (secondary_indices = [...]).
```

`HelixConfig::validate` requires a non-empty project name, ≥1 instance, non-empty instance names, and a non-empty `cluster_id` for each enterprise instance. A fresh `init local` seeds a single in-memory `local.dev`.

### `~/.helix/` (user state)

| File | Contents |
|---|---|
| `~/.helix/config` | TOML; active `workspace_id` (set by `helix workspace switch`). |
| `~/.helix/credentials` | Auth from `helix auth login` (e.g. `helix_user_id`, `helix_user_key`). Never commit. |
| `~/.helix/metrics.toml` | Telemetry `level` (`full`/`basic`/`off`), `user_id`, `email`. |

## Key Constants

| Constant | Value |
|---|---|
| Default local port | `6969` |
| Dev image / tag | `ghcr.io/helixdb/enterprise-dev` / `latest` |
| Container name | `helix-<project>-<instance>` |
| Container internal port | `8080` |
| Default auth header | `Authorization` |
| Default auth env var | `HELIX_API_KEY` |

## Environment Variables

| Variable | Used by | Purpose |
|---|---|---|
| `HELIX_API_KEY` | `helix query` (cloud) | API key value for the auth header (override per-instance via `query_auth_env`). |
| `HELIX_NO_UPDATE_CHECK` | CLI startup | Skip the CLI/skills update check (`HELIX_DISABLE_UPDATE_CHECK` also accepted). |
| `HELIX_SKIP_CLOUD_AUTH` | `helix chef` | Skip the optional Cloud login in an interactive shell. |
| `HELIX_CACHE_DIR` | CLI | Override the cache dir (TS runtime, update markers). |
| `CLOUD_AUTHORITY` | cloud commands | Override the cloud API host (default `cloud.helix-db.com`). |
