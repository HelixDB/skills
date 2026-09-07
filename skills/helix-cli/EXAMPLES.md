# Helix CLI examples

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
