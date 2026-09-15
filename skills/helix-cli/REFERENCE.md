# Helix CLI reference

## Local

```text
helix init local [--name N] [--port P] [--disk | --storage-uri s3://...]
helix add local --name N [--port P] [--disk | --storage-uri s3://...]
helix start [INSTANCE] [--foreground] [--port P] [--disk | --storage-uri s3://...] [--persist]
helix stop|restart|status [INSTANCE]
helix logs [INSTANCE] [--follow]
helix prune [INSTANCE] [--all] [--yes]
helix delete INSTANCE [--yes]
```

`init local`, `add local`, and `start` accept `--s3-region REGION`,
`--s3-endpoint-url URL`, and `--s3-allow-http` for an S3-compatible endpoint.
Supply `--storage-uri` when selecting S3 storage; `start` can also override the
options of an existing S3 instance. Credentials come from the standard AWS
environment variables or the project-root `.env`, not `helix.toml`.

Pin `ghcr.io/helixdb/helixdb:v0.0.5` through the local block below, including
when using an older CLI with a different default. `start` publishes the configured
host port to container port 8080 and waits for `GET /healthz`.

Storage is memory by default; `stop` and `restart` discard memory data.
`--disk` starts CLI-managed MinIO and preserves its volume on stop; `prune`
deletes it. `--storage-uri` uses an externally owned S3-compatible store whose
data is not deleted by the CLI. `start --persist` saves the resolved port/storage
settings. Direct Docker native volumes use `HELIX_DATA_DIR`; see `EXAMPLES.md`.

## Query

```text
helix query [INSTANCE] (--file P | --json J | -e TS | --ts-file P) [--compact]
helix shell [INSTANCE] [--compact]
```

`--host`, `--port`, and read-only `--warm` are local query options. Cloud selects read/write broker
RPC from lowercase `request_type`. Without `INSTANCE`, query and shell use local `dev`, then a sole
linked instance; multiple candidates require an explicit instance. Query bundles are unsupported.

Query failures use the stable `error` code and diagnostic `msg` inside the decoded
query response. Preserve unknown codes and the HTTP status; see
`../../docs/error-handling.md`. Cloud query execution follows the no-retry boundary
in `SKILL.md`; direct SDK/HTTP retry guidance does not authorize a CLI replay.

## Cloud

```text
helix auth login|status|logout
helix workspace list|get
helix project list|get|create|delete|link
helix cluster list|get|indexes
helix database list|get|create|delete|indexes
helix database key create|list|revoke
helix service-credential create|list|get|update|revoke
helix api get|post|patch|delete /v1/...
helix init|add cloud [--database tenant:<id>|cluster:<id>] [--project ID] [--workspace ID]
```

Database create is tenant-only. It creates a default read-write application key and returns the raw
token once; the CLI displays but never stores or uses it. Dedicated cluster deletion is rejected.
Additional application-key access values are `read-only` or `read-write`. Service-credential grants
are repeatable `PROJECT=project-read,project-write,query-read,query-write`, with matching read required
for write.

## `helix.toml`

```toml
[project]
name = "example"
id = "project-id"             # optional stable link
workspace_id = "workspace-id" # optional stable link

[local.dev]
port = 6969
image = "ghcr.io/helixdb/helixdb"
tag = "v0.0.5"
storage = "memory"

[enterprise.production]
database = "tenant:tenant-id"
project_id = "project-id"     # optional
workspace_id = "workspace-id" # optional
```

Cloud blocks reject gateway/auth/sync/source/query-bundle fields. `~/.helix/credentials` is a strict,
mode-0600 WorkOS session file; do not edit it.
