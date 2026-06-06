# Helix CLI — Examples

Copy-pasteable, end-to-end sessions for the `helix` CLI. Pair these with `REFERENCE.md` for the full flag list and `SKILL.md` for the rules and anti-patterns. For the contents of the query bodies, see the `helix-query-*` skills.

## 1. Local Dev Loop (in-memory)

```bash
# Scaffold a project (writes helix.toml, .helix/, examples/request.json, .gitignore entries)
helix init local

# Start the default 'dev' instance — pulls the image and waits until /v1/query is ready
helix start dev

# Confirm it is up and note the URL
helix status dev

# Run the example read query that init scaffolded
helix query dev --file examples/request.json

# Pretty output is the default; pipe compact output into jq for a single field
helix query dev --file examples/request.json --compact | jq '.node_count'

# ...edit examples/request.json and re-run helix query to iterate...

# Stop when done (in-memory data is discarded)
helix stop dev
```

A minimal `examples/request.json` (count `User` nodes):

```json
{
  "request_type": "read",
  "query_name": "node_count",
  "query": {
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
  "parameters": {}
}
```

## 2. Local Dev Loop (persistent disk)

```bash
# Add a named instance that uses on-disk (MinIO-backed) storage
helix add local --name staging --port 9090 --disk

# Or start an existing instance with disk storage for this run and save the choice
helix start staging --disk --persist

helix query staging --file examples/request.json

# Stop keeps the persistent volume; the data survives
helix stop staging

# To actually delete the persisted data and Helix-owned resources:
helix prune staging
```

## 3. The Four `helix query` Input Forms

```bash
# (a) JSON request file
helix query dev --file examples/request.json

# (b) Inline JSON string
helix query dev --json '{"request_type":"read","query_name":"ping","query":{"queries":[],"returns":[]},"parameters":{}}'

# (c) Inline TypeScript DSL expression (like `mysql -e`; needs Node 20+)
helix query dev -e 'readBatch().varAs("c", g().nWithLabel("User").count()).returning(["c"])'

# (d) TypeScript DSL from a file
helix query dev --ts-file queries/count_users.ts
```

`queries/count_users.ts` (note: `g`, `readBatch`, `writeBatch`, `defineParams`, `param` are auto-imported):

```ts
readBatch()
  .varAs("c", g().nWithLabel("User").count())
  .returning(["c"]);
```

Pre-warm caches without printing output (read-only):

```bash
helix query dev --file examples/request.json --warm
```

## 4. Full Helix Cloud Deploy

```bash
# 1. Authenticate (GitHub device-code flow → ~/.helix/credentials)
helix auth login

# 2. Select workspace and project
helix workspace list
helix workspace switch my-team
helix project list
helix project switch payments-api

# 3. Find the cluster and add a cloud instance
helix cluster list
helix add cloud --name production --cluster-id ec_01HX...

# 4. Sync metadata (fills gateway_url + auth fields in helix.toml). Preview first:
helix sync production --dry-run
helix sync production

# 5. Provide the API key (shell env or a project-root .env)
export HELIX_API_KEY="hlxk_..."

# 6. Deploy and query
helix push production
helix query production --file examples/request.json
```

Inspect the deployed cluster and its indexes:

```bash
helix cluster list --format json
helix cluster indexes --cluster-id ec_01HX... --format json
```

Fetch the last hour of cloud logs (or a fixed range):

```bash
helix logs production --range
helix logs production --range --start 2026-05-12T10:00:00Z --end 2026-05-12T11:00:00Z
```

Rotate the cluster API key (printed once — update `HELIX_API_KEY` before the next query):

```bash
helix auth create-key ec_01HX...
```

## 5. CI / Non-Interactive Patterns

```bash
helix stop staging || true          # idempotent; safe even if not running
helix prune --all --yes             # remove everything Helix-owned, no prompt
helix delete staging --yes          # remove from helix.toml + runtime state, no prompt
helix sync production --yes          # skip conflict prompts
HELIX_NO_UPDATE_CHECK=1 helix status # skip the update check in CI
```

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `helix compile` / `helix check` errors out | Removed in v3 (validation is server-side) | Drop the step; queries are validated when sent to `POST /v1/query`. |
| `helix deploy` errors out | Removed | Use `helix push <instance>`. |
| `helix query` connection refused (local) | Instance not started / not ready | `helix status`, then `helix start <instance>`; the start command waits for readiness. |
| `helix start` fails immediately | Container runtime not running | Start Docker/Podman; check `[project] container_runtime`. |
| Data gone after `stop`/`restart` | In-memory storage (the default) | Use `--disk` (and `--persist` to save it) for persistence. |
| Cloud query: 401 / missing auth | `HELIX_API_KEY` not set or not synced | `export HELIX_API_KEY=...` (or `.env`), and `helix sync <instance>`; ensure `helix auth login`. |
| Cloud query: no gateway URL | Metadata not synced | `helix sync <instance>` to populate `gateway_url`. |
| `helix push` rejects the instance | Target is a local instance | Use `helix start` for local; `push` is cloud-only. |
| TS DSL query fails to evaluate | Node missing/old | Install Node 20+ on PATH (the CLI evaluates `-e`/`--ts-file` in Node). |
