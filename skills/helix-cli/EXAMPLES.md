# Helix CLI examples

## Local CLI persistence

Initialize a local instance with a CLI-managed MinIO volume:

```bash
helix init local --name dev --disk
```

Set `tag = "v0.0.5"` in the generated `[local.dev]` block in `helix.toml`, then:

```bash
helix start dev
helix query dev --file examples/request.json
helix stop dev
```

Stopping keeps the volume. `helix prune dev` deletes its persisted data. For an
external S3-compatible store, supply AWS credentials in the environment or a
project-root `.env` and select the store instead:

```bash
helix start dev \
  --storage-uri s3://helix-db/my-app \
  --s3-region us-east-1 \
  --s3-endpoint-url https://minio.example.com \
  --persist
```

Use `--s3-allow-http` only for a trusted plain-HTTP endpoint. The CLI does not
delete externally owned object-store data.

## Direct Docker native persistence

This mode uses the filesystem directly and does not need MinIO:

```bash
docker volume create helixdb-data
docker run --rm --name helixdb \
  -p 6969:8080 \
  -e HELIX_DATA_DIR=/var/lib/helix \
  --mount type=volume,source=helixdb-data,target=/var/lib/helix \
  ghcr.io/helixdb/helixdb:v0.0.5
```

Stop with `docker stop helixdb`. Start another container with the same volume to
retain the database; removing the volume deletes it. The image runs as
`65532:65532`, so bind mounts and existing volumes must be writable by that user.
Leave `S3_BUCKET` unset for this mode; setting it with `HELIX_DATA_DIR` fails
startup. Memory mode requires both variables to be unset.

Use `docker` commands to manage a directly started container. The CLI manages
only the instances and resources configured in its project.

## Cloud broker query

```bash
helix auth login
helix project link project_123
helix add cloud --name production --database tenant:tenant_123
helix query production --file request.json
```

No API key, gateway URL, push, or sync step is used.

## Create a database and capture its default application key

```bash
helix database create --project project_123 --name app --slug app --plan starter
```

Capture the returned default read-write token in the application's secrets manager. The CLI does not
retain or use it. Create another key only when the application needs a separate credential:

```bash
helix database key create tenant:tenant_123 --access read-only --name reporting
```

Capture that printed token once as well.

## Headless MCP credential

```bash
helix service-credential create --workspace workspace_123 --name agent \
  --grant project_123=query-read
```

Capture the token once for the intended MCP audience. Do not use it with `helix auth`.
