# Helix CLI reference (3.7.0)

Global options on every command: `--json` (result JSON on stdout, errors as `{"error": {...}}` on
stderr, never prompts), `--quiet`, `-v`/`--verbose`, `-h`/`--help`. `helix -V`/`--version`
prints the CLI version (top level only). `helix <command> --help` prints that command's flags.

## Project setup

```text
helix init [--path DIR] [--skills | --no-skills] local [--name N] [--port P]
           [--disk | --storage-uri s3://...] [--s3-region R] [--s3-endpoint-url URL] [--s3-allow-http]
helix init [--path DIR] [--skills | --no-skills] cloud [--name N] [--database REF]
           [--project P] [--workspace W]
helix add [--path DIR] local --name N [--port P] [--disk | --storage-uri s3://...] [S3 flags]
helix add [--path DIR] cloud --name N [--database REF] [--project P] [--workspace W]
helix chef                       # alias: cook; interactive app bootstrap with a coding agent
```

- `init` refuses a directory that already has `helix.toml`. Without a subcommand and without a
  terminal it creates a local `dev` instance. `init local --name` defaults to `dev`, `init cloud
  --name` to `production`. `--skills` installs the agent skills and the `helixdb-docs` MCP; without
  a terminal neither is installed unless `--skills` is given.
- `init cloud` resolves the database (needs the user's `helix auth login` session) and writes
  `[project] id`/`workspace_id` and an `[enterprise.<name>]` block.
- `add` needs an existing `helix.toml`; `add cloud` defaults to the linked project.
- `REF` is a database ID, slug, name, or `tenant:<id>` / `cluster:<id>`.

## Local runtime

```text
helix start [INSTANCE] [--foreground] [--port P] [--disk | --storage-uri s3://...] [S3 flags]
            [--image-version TAG|sha256:DIGEST] [--pull always|missing|never] [--persist]
                                  # alias: run
helix stop|restart [INSTANCE]
helix status [INSTANCE]           # local containers and Cloud databases; all when omitted
helix logs [INSTANCE] [-f|--follow]                  # local: container logs
helix logs [INSTANCE] [--start RFC3339] [--end RFC3339]   # Cloud: recent query errors
helix doctor [INSTANCE|tenant:<id>|cluster:<id>] [--url URL]
helix explorer [INSTANCE] [--port P] [--no-open] [--image REF] [--stop]
helix prune [INSTANCE] [-a|--all] [-y|--yes]
helix delete INSTANCE [-y|--yes]
```

- `start` runs in the background by default and waits for `GET /healthz`; `--foreground` stops on
  Ctrl-C. `--pull` defaults to `always` for `latest` and `missing` for other tags. `--persist`
  writes the resolved port, storage and image settings back to `helix.toml`.
- Storage is memory by default; `stop` and `restart` discard it. `--disk` runs a CLI-managed
  SeaweedFS sidecar and keeps its volume across stops; `prune` (or `delete`) removes it, along with
  any MinIO volume left by older CLIs, which SeaweedFS cannot read. `--storage-uri` uses an external
  S3-compatible store; the CLI never deletes its data. S3 credentials come from the standard AWS
  environment variables or the project-root `.env`.
- `logs --follow` is local only; Cloud logs list query errors in a window (default: the hour before
  `--end`, which defaults to now) and accept `--json`. Local logs reject `--start`/`--end` and
  `--json`.
- `doctor` is read-only: CLI version, container runtime, image, then the server's
  `GET /v2/diagnostics` (storage durability, S3 round trip, disk cache, memory, index publication,
  index use). It exits 1 when a check fails; warnings exit 0. `--url` diagnoses any server without a
  `helix.toml`.
- `explorer` opens the graph Explorer (`ghcr.io/helixdb/helix-explorer:v0.1.0`, override with
  `--image` or `HELIX_EXPLORER_IMAGE`) for a running local instance; `--stop` removes it.
- `delete` removes the instance from `helix.toml` and its local runtime state; it refuses the last
  instance.

## Query

```text
helix query [INSTANCE|tenant:<id>|cluster:<id>] (-f|--file REQUEST.json | --body JSON | -e|--ts TS | --ts-file QUERY.ts)
            [--host H] [--port P] [--warm]
helix shell [INSTANCE|tenant:<id>|cluster:<id>]        # one v3 JSON request per line; :quit exits
helix cypher [INSTANCE] (-e|--query STATEMENT | -f|--file FILE) [--parameters JSON] [--explain]
             [--host H] [--port P]
```

- Exactly one `query` input. `--body` takes inline request JSON; `-e`/`--ts-file` evaluate the
  TypeScript DSL and need Node 20+. `--host`, `--port` and `--warm` (reads only) are local-only.
- A Cloud target runs through the backend broker: the CLI picks the read or write broker call from
  the request's lowercase `request_type`. Query bundles are unsupported.
- `cypher` targets a local instance only (`POST /v2/cypher`); `--parameters` must be a JSON object;
  `--explain` shows the plan without executing.
- The decoded response prints on stdout. A non-2xx `query` response fails with message
  `query failed with HTTP <status>` and the server body in `caused_by` (`cypher` instead puts it
  in the message: `Cypher failed with HTTP <status>: <body>`). That body is
  `{"error": "<stable_code>", "msg": "<diagnostic>"}`: branch on `error` (for example
  `transaction_conflict` 409, `index_not_found` 404, `unique_constraint_violation`), never on `msg`,
  and keep unknown codes. A CLI query is never retried for you. Do not replay a Cloud write after a
  timeout or ambiguous failure; read the state back first.

## Cloud

```text
helix auth login [github|google|microsoft|sso [--email E]|password [--email E]]   # interactive only
helix auth status|logout
helix workspace [list | get [WORKSPACE]]
helix project [list [--workspace W] | get [PROJECT] [--workspace W]
              | create NAME [--slug S] [--workspace W] [--link]
              | delete [PROJECT] [--workspace W] [-y] | link [PROJECT] [--workspace W]]
helix cluster [list | get [CLUSTER] | indexes [CLUSTER]] [--workspace W] [--project P]
helix database [list | get [REF] | indexes [REF]] [--workspace W] [--project P]
helix database create NAME [--slug S] (--plan CODE | --cluster CLUSTER) [--workspace W] [--project P]
helix database delete [REF] [-y] [--workspace W] [--project P]
helix database key create --access read-only|read-write [--name N] [--database REF] [--workspace W] [--project P]
helix database key list [--database REF] [--workspace W] [--project P]
helix database key revoke KEY [--database REF] [-y] [--workspace W] [--project P]
helix service-credential [list [--workspace W] | get CREDENTIAL [--workspace W]]
helix service-credential create --name N --grant PROJECT_ID=PERMS... [--expires-at RFC3339] [--workspace W]
helix service-credential update CREDENTIAL [--name N] [--grant PROJECT_ID=PERMS...]
                                [--expires-at RFC3339 | --clear-expiry] [--workspace W]
helix service-credential revoke CREDENTIAL [-y] [--workspace W]
helix api get|delete /v1/PATH
helix api post|patch /v1/PATH [--body JSON]          # body defaults to {}
```

- A group without a subcommand lists (`helix database` = `helix database list`). `indexes` (alias
  `indices`) lists active indexes only.
- `project link` and `project create --link` write the link into the current `helix.toml`, which
  must exist.
- `database create` always makes a tenant database: on shared infrastructure with `--plan`, or on
  a dedicated cluster with `--cluster` (not both). Without a terminal `--plan` must be non-empty
  for a shared tenant. Helix Cloud bills shared tenants to the workspace's pooled subscription and
  currently does not read the code, so it does not pick a size or price; a workspace without a
  subscription is refused whatever the code. Ask the user which code to pass rather than inventing
  one. The response holds the default read-write key's token, shown once.
- Dedicated cluster deletion is refused; `database delete` deletes tenant databases only.
- Service-credential `PERMS` are a comma list of `project-read`, `project-write`, `query-read`,
  `query-write`; each `-write` requires its `-read`. `--grant` repeats per project, and on `update`
  replaces all grants. The token prints once; it authenticates the Helix MCP and HTTP APIs, never
  `helix auth`.

## Agent skills, metrics and the CLI itself

```text
helix skills install|list [--project]   # interactive (npx skills); refuses --json
helix skills update [--project]         # non-interactive refresh; supports --json
helix metrics full|basic|off|status
helix update [--force] [--v1]           # --v1 installs CLI 2.3.5, the last v1-compatible release
helix feedback [MESSAGE]                # opens a GitHub issue form in the browser
```

Skills install globally unless `--project`. `helix init --skills` and `helix chef` also add the docs
MCP as `helixdb-docs` (`https://docs.helix-db.com/mcp`) through `npx add-mcp`.

## `helix.toml`

```toml
[project]
name = "example"
id = "project-id"                # optional Cloud link
workspace_id = "workspace-id"    # optional Cloud link
container_runtime = "docker"     # or "podman"
# queries = "db"                 # accepted, unused by v3 commands

[local.dev]
port = 6969
image = "ghcr.io/helixdb/helixdb"
tag = "v0.0.16"                  # tag or sha256 digest
# pull = "missing"               # always | missing | never
storage = "memory"               # memory | disk | s3

[local.staging]
storage = "s3"
[local.staging.s3]
bucket = "helix-db"
prefix = "my-app/"               # default "db/"
region = "us-east-1"             # default
endpoint_url = "https://s3.example.com"   # optional
allow_http = false

[enterprise.production]
database = "tenant:tenant-id"    # or "cluster:cluster-id"
project_id = "project-id"        # optional
workspace_id = "workspace-id"    # optional
```

`[project]`, `[enterprise.*]` and the top level reject unknown keys, so gateway/auth/sync/source/
query-bundle fields fail to load. Instance names are ASCII letters, digits, `-` and `_`, at most 32.

## Environment

| Variable | Effect |
| --- | --- |
| `HELIX_HOME` | Directory for credentials, config, update caches and metrics (default `~/.helix`) |
| `HELIX_CACHE_DIR` | Disposable cache directory (default `HELIX_HOME`) |
| `CLOUD_AUTHORITY` | Cloud API host override (default `api.prod.helix-db.com`); leave unset for production |
| `HELIX_NO_UPDATE_CHECK`, `HELIX_DISABLE_UPDATE_CHECK` | Skip the update check (also skipped under `--json`) |
| `HELIX_EXPLORER_IMAGE` | Explorer image for `helix explorer` |
| `AWS_*`, project-root `.env` | Credentials for `--storage-uri` S3 storage |
