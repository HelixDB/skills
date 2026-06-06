---
name: helix-cli
description: Drive the HelixDB `helix` CLI to run, query, and deploy Helix instances. Use when the task is to scaffold a project (helix init / chef / add), manage a local Docker/Podman instance (helix start, stop, restart, status, logs, prune), send a dynamic query to a running instance (helix query with --file / --json / -e TypeScript DSL / --ts-file, against POST /v1/query), or operate on Helix Cloud (helix auth, push, sync, workspace, project, cluster). Covers helix.toml, the local-vs-cloud workflow, and the v3 mental model (NO helix compile / helix check / .hx files). For writing the query bodies themselves, defer to the helix-query-* skills. See REFERENCE.md for the full command catalog and EXAMPLES.md for end-to-end walkthroughs.
license: MIT
metadata:
  author: HelixDB
  version: 0.1.0
---

# Helix CLI

Drive the `helix` CLI (crate `helix-cli`, binary `helix`) to operate live Helix instances. In v3 the CLI is a **runtime orchestrator, not a compiler**.

The mental model that matters most:

- **There is no `helix compile`, no `helix check`, and no `.hx` query workflow.** Those are stale v2 concepts — the v3 CLI hides them and errors with a hint if you try them.
- **Queries are JSON "dynamic queries"** sent to a *running* instance via `POST /v1/query` (`helix query`). Validation happens server-side, in the instance.
- **Local instances are Docker/Podman containers** (image `ghcr.io/helixdb/enterprise-dev:latest`). `helix start` runs one; in-memory by default, on-disk (MinIO-backed) with `--disk`.
- **Helix Cloud instances deploy via `helix push`**, with auth and metadata managed by `helix auth`, `helix sync`, and the `workspace`/`project`/`cluster` commands.

This skill is about *driving the CLI*. For authoring the query bodies themselves, use the query skills (`helix-query-rust`, `helix-query-typescript`, `helix-query-json-dynamic`, etc.).

## When To Use

Use this skill when the task is to:

- scaffold a Helix project (`helix init`, `helix chef`, `helix add`)
- start, stop, restart, or inspect a local instance (`helix start`/`stop`/`restart`/`status`/`logs`)
- send a query to a running instance (`helix query`)
- clean up local resources (`helix prune`, `helix delete`)
- authenticate to and deploy on Helix Cloud (`helix auth`, `helix push`, `helix sync`)
- manage cloud workspace / project / cluster selection
- read or edit `helix.toml`

Do not use this skill to write the query AST/DSL itself — defer to `helix-query-rust`, `helix-query-typescript`, or `helix-query-json-dynamic`. This skill only covers *getting that query to a running instance and back*.

## First Steps

Before running anything:

1. **Find the project.** Check for a `helix.toml` (the CLI walks up the directory tree to find it). Run `helix status` to see configured instances and their state. If there is no project yet, you are in scaffold territory (`helix init local`).
2. **For local work, confirm a container runtime is up.** `helix start` needs Docker or Podman running. The runtime is chosen by `[project] container_runtime` (default `docker`).
3. **Decide local vs cloud.** Local instances live in `[local.<name>]` and run as containers; cloud instances live in `[enterprise.<name>]` and run on Helix Cloud.
4. **For cloud, ensure auth.** Cloud commands require `helix auth login` (credentials in `~/.helix/credentials`), and `helix query` against a cloud instance needs the API key in `HELIX_API_KEY` (or the env named by `query_auth_env`), readable from the shell or a project-root `.env`.

If you need a builder/flag beyond the common surface, open `REFERENCE.md` — do not guess flag names. For copy-pasteable sessions, see `EXAMPLES.md`.

## Core Workflows

### 1. Local Dev Loop (start here)

```bash
helix init local                          # scaffold helix.toml + .helix/ + examples/request.json
helix start dev                           # start the 'dev' container (waits until /v1/query is ready)
helix status dev                          # confirm it is running and note the URL
helix query dev --file examples/request.json   # send a dynamic query
# ...edit the request and re-run helix query to iterate...
helix stop dev                            # stop the container
```

Key facts:

- The instance name defaults to `dev`; the default port is **6969** (host → container port 8080).
- **In-memory is the default — data is wiped on `stop` and `restart`.** Use `--disk` for persistence (MinIO-backed). With disk mode, `stop` keeps the volume; use `helix prune <instance>` to delete the data.
- `--port <p>` and `--disk` apply to a single `start`; add `--persist` to write those choices back to `helix.toml`.
- `helix logs dev -f` streams container logs; `helix restart dev` restarts in place (re-creating fresh if the container was removed).

### 2. Helix Cloud

```bash
helix auth login                          # GitHub device-code flow → ~/.helix/credentials
helix workspace switch <slug>             # pick the active workspace
helix project switch <name>               # link the project (writes ids to helix.toml)
helix cluster list                        # find the cluster id
helix add cloud --name production --cluster-id ec_01HX...   # add an [enterprise.production] block
helix sync production                      # fetch gateway_url + auth metadata into helix.toml
export HELIX_API_KEY="hlxk_..."           # or put it in a project-root .env
helix push production                      # deploy to Helix Cloud
helix query production --file examples/request.json   # query the cloud gateway
```

Key facts:

- `helix push` **deploys**; it errors on a local instance. (The old `helix deploy` is removed.)
- `helix sync` reconciles metadata (gateway URL, auth header/env, node types) between local and cloud; `--dry-run` previews without writing, `-y/--yes` skips conflict prompts (for CI).
- Cloud queries post to the instance's `gateway_url` with the header named by `query_auth_header` (default `Authorization`), valued from the env named by `query_auth_env` (default `HELIX_API_KEY`).

## Core Usage Rules

### 1. Query A Running Instance, By Name

`helix query [instance]` defaults to `dev`. The instance must be running (local) or deployed + synced (cloud). If a local query connection fails, check `helix status` first.

### 2. Exactly One Query Input Flag

`helix query` requires exactly one of `--file <req.json>`, `--json '<body>'`, `-e/--ts '<expr>'`, or `--ts-file <query.ts>` (enforced by a clap arg group). `--file`/`--json` carry raw dynamic-query JSON; `-e`/`--ts-file` carry a TypeScript DSL expression that the CLI evaluates in Node (needs Node 20+) and converts via `.toDynamicJson()`.

### 3. `request_type` Is Lowercase

In a JSON request body, `request_type` must be lowercase `"read"` or `"write"`. With the TS DSL, the type is inferred from `readBatch()` vs `writeBatch()`.

### 4. `--warm` Is Read-Only

`--warm` adds the `X-Helix-Warm` header to pre-warm caches and is for read requests only. Output is suppressed.

### 5. Prefer `helix push`, Not Removed Commands

`compile`, `check`, and `deploy` are removed. Use `helix push <instance>` to deploy; there is no compile/check step (validation is server-side).

### 6. Never Commit Secrets

`~/.helix/credentials` and the `HELIX_API_KEY` value (or `.env`) are secrets. Do not commit them. `helix init` already adds `.helix/` to `.gitignore`.

### 7. Use `helix prune`, Not `docker system prune`

To remove Helix-owned containers/volumes/networks, use `helix prune [instance]` (or `--all`). It scopes to Helix resources only — never run a broad `docker system prune`.

## Anti-Patterns

Do not:

- run `helix compile`, `helix check`, or `helix deploy` — they are removed (compile/check don't exist; use `push` to deploy)
- create or edit `.hx` query files — v3 uses JSON dynamic queries to `POST /v1/query`
- assume local data survives `stop`/`restart` — it does not unless the instance uses `--disk`
- run `helix query` before the instance is ready (local: not started; cloud: not pushed/synced)
- hardcode the cloud API key in a command or file — read it from `HELIX_API_KEY` / `.env`
- pass more than one query input flag, or use uppercase `READ`/`WRITE` in `request_type`
- reach for `docker system prune` to clean up — use `helix prune`
- guess at flags from memory — confirm against `REFERENCE.md`

## Validation Checklist

Before running (or after, to debug):

- the instance exists in `helix.toml` and the name passed matches it
- local: the instance is started (`helix status`) and the container runtime is up
- cloud: `helix auth login` done, instance `push`ed + `sync`ed, `HELIX_API_KEY` set
- `helix query` has exactly one input flag and (for JSON) lowercase `request_type`
- not using any removed command (`compile`/`check`/`deploy`) or `.hx` workflow
- secrets (`credentials`, API key) are not being committed

## Reference Files

- `REFERENCE.md` — full command catalog (every subcommand, flag, alias, default) plus the `helix.toml` / `~/.helix/*` config formats, key constants, and environment variables.
- `EXAMPLES.md` — copy-pasteable end-to-end sessions: local dev loop (memory + disk), each `helix query` input form, a full Helix Cloud deploy, and a troubleshooting block.
