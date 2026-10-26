# Case 02: Service credential without discovery

## Prompt

My service credential has query-read for the project containing tenant:example-id. Execute an empty read. The session has no helix_list_workspaces or insights tools.

## Expected Skills

- `helix-query-mcp`

## Gold Expectations and Scoring Checklist

- [ ] Use https://mcp.helix-db.com/mcp with the existing scoped credential.
- [ ] Use the supplied tenant:example-id; do not invoke human discovery or ask for an application database key.
- [ ] Use helix_execute_read_query only if available, with a complete v3 read request as query_json.
- [ ] Do not claim telemetry or active indexes were verified.
- [ ] If the requested target is denied, report it and do not switch to a direct gateway or another credential.
