---
name: helix-cli
description: Drive the HelixDB v3 `helix` CLI for local Docker/Podman instances and WorkOS-session-authenticated Helix Cloud discovery, resource management, query, shell, status, and logs. Use for helix init/add/start/stop/query/shell/auth/workspace/project/cluster/database/service-credential/api and helix.toml. Cloud CLI auth is WorkOS-only; never supply API keys or service credentials as CLI login. Defer query-body authoring to helix-query-* skills.
license: MIT
metadata:
  author: HelixDB
  version: 4.0.0
---

# Helix CLI

Use the CLI as a runtime and control-plane client. It does not compile `.hx` files, deploy query
bundles, push source, or sync gateway metadata.

## Choose the execution boundary

- Local `[local.<name>]`: Docker/Podman, auth-disabled local `/v2/query`.
- Cloud `[enterprise.<name>]`: stable `tenant:<id>` or dedicated `cluster:<id>` linkage.
- Cloud `query` and `shell`: backend query broker, never a direct gateway request.
- Direct application gateway access: outside CLI authentication; explicitly created database key.

## Cloud authentication

Use only:

```bash
helix auth login
helix auth status
helix auth logout
```

Login is WorkOS PKCE. The CLI rotates the session through WFE. Never ask for or set a Cloud API key,
legacy admin/user key, service credential, custom authorization header, or gateway URL. Do not retry
a Cloud mutation: the client may retry once only when WFE explicitly rejects the session before
handler dispatch.

## Target resolution

Prefer an explicit `--workspace`, `--project`, `cluster:<id>`, or `tenant:<id>`. For `query` and
`shell`, an explicit instance wins; otherwise use local `dev`, then the sole linked instance. If
multiple instances remain, list them and require an explicit instance. Other Cloud commands use the
database/project linked in the current `helix.toml` only when unambiguous. There is no global
workspace selection and no `workspace switch`.

## Main workflows

```bash
# Local
helix init local
helix start dev
helix query dev --file examples/request.json
helix shell dev
helix stop dev

# Cloud discovery and linkage
helix auth login
helix workspace list
helix project list --workspace-id <workspace>
helix database list --project <project>
helix project link <project>
helix add cloud --name production --database tenant:<tenant>
helix query production --file request.json
```

Cloud read/write envelopes require independent `database.query.read` / `database.query.write` access.
Management `read`/`write` does not imply query access.

## Secret lifecycle

- `helix database create` creates a default read-write application key and prints its token once;
  the CLI never stores or uses it.
- `helix database key create ... --access read-only|read-write` prints an application token once;
  the CLI never stores or uses it.
- `helix service-credential create` prints a headless API/MCP token once; the CLI never stores or
  authenticates with it.
- Never put any token in `helix.toml`, agent instructions, source control, or command history.

## Removed and excluded surfaces

Do not use or recommend `push`, `sync`, `auth create-key`, `workspace switch`, query bundles,
dedicated-cluster lifecycle, networking, regions/SKUs, branches/backups, schema introspection,
execution polling/cancellation, webhooks, or project update.

Open `REFERENCE.md` for exact commands/config and `EXAMPLES.md` for safe sessions. Use a
`helix-query-*` skill to author v3 request bodies.
