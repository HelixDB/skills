# Helix CLI examples

Every example uses `--json` the way an agent should; drop it when a person reads the output.

## Local with persistence

```bash
helix init local --name dev --disk --no-skills --json   # SeaweedFS-backed volume
helix start dev --json
helix query dev --file examples/request.json --json
helix query dev --json --body '{"request_type":"read","query":{"read":{"entries":[{"query":{"name":"nodes","root":{"count":{"input":{"nodes_where":{"predicate":{"eq":{"left":{"property":"$label"},"right":{"constant":{"string":"User"}}}}}}}}}}],"returns":["nodes"]}}}'
helix stop dev --json
```

`helix init` pins `tag = "v0.0.16"` in `[local.dev]`. If an older project pins an older tag, set it
to `v0.0.16` (or try one run with `helix start dev --image-version v0.0.16`, then `--persist`).

Stopping keeps the volume; `helix prune dev --yes` deletes it, after the user confirmed. For an
external S3-compatible store, put AWS credentials in the environment or the project-root `.env`:

```bash
helix start dev \
  --storage-uri s3://helix-db/my-app \
  --s3-region us-east-1 \
  --s3-endpoint-url https://s3.example.com \
  --persist --json
```

Use `--s3-allow-http` only for a trusted plain-HTTP endpoint. The CLI never deletes externally
owned object-store data.

## Check an instance

```bash
helix status --json
helix doctor dev --json          # exits 1 when a check fails
helix logs dev --follow          # local container logs (no --json)
helix cypher dev -e 'MATCH (u:User) RETURN count(u) AS users' --json
```

## Direct Docker native persistence

This mode uses the filesystem directly and needs no sidecar:

```bash
docker volume create helixdb-data
docker run --rm --name helixdb \
  -p 6969:8080 \
  -e HELIX_DATA_DIR=/var/lib/helix \
  --mount type=volume,source=helixdb-data,target=/var/lib/helix \
  ghcr.io/helixdb/helixdb:v0.0.16
```

Stop with `docker stop helixdb`. Start another container with the same volume to keep the
database; removing the volume deletes it. The image runs as `65532:65532`, so bind mounts and
existing volumes must be writable by that user. Leave `S3_BUCKET` unset for this mode; setting it
with `HELIX_DATA_DIR` fails startup. Memory mode requires both unset. Manage a directly started
container with `docker`; the CLI manages only instances in its `helix.toml`.

## Cloud: first session in a fresh directory

The user logs in once in their own terminal; the agent cannot:

```text
Agent: Please run `helix auth login` in your terminal and tell me when it says "Logged in".
```

```bash
helix auth status --json
helix workspace list --json
helix project list --workspace acme --json
helix database list --project app --json   # rows {"kind":"tenant"|"dedicated","id",...}: tenant:<id> / cluster:<id>

# Either query a typed reference with no helix.toml at all:
helix query tenant:tenant_123 --file request.json --json

# Or create a project directory linked to that database:
helix init cloud --database tenant:tenant_123 --no-skills --json
helix query production --file request.json --json
```

`helix project link` and `helix add cloud` only edit an existing `helix.toml`. No API key, gateway
URL, push or sync step is used.

## Handle a non-interactive ambiguity

```bash
helix database get --project app --json
# stderr: {"error":{"message":"2 databases found; choose one",
#          "hint":"pass the database by ID, slug, or name, or as tenant:<id> / cluster:<id>",
#          "candidates":[{"id":"...","name":"app"},{"id":"...","name":"reports"}]}}
# exit 1
```

Show the user the candidates and re-run with the one they pick, such as `helix database get
tenant:tenant_123 --json`. A bad flag exits 2 with the same error shape.

## Create a database and capture its default application key

```bash
helix database create app --slug app --project project_123 --plan <workspace-plan-code> --json
```

Capture the returned default read-write token in the application's secrets manager. The CLI does not
retain or use it. Create another key only when the application needs a separate credential:

```bash
helix database key create --database tenant:tenant_123 --access read-only --name reporting --json
```

Capture that printed token once as well. On a dedicated cluster use `--cluster <cluster>` instead
of `--plan`.

## Headless MCP credential

```bash
helix service-credential create --workspace workspace_123 --name agent \
  --grant project_123=query-read --expires-at 2030-01-01T00:00:00Z --json
```

Capture the token once into the automation's secret store and send it as the bearer to
`https://mcp.helix-db.com/mcp`. It never logs in to the CLI.
