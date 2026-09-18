# Case 04: Static review when telemetry is unavailable

## Prompt

Review this Cloud read query for likely performance problems. I supplied the schema, but no MCP tools are available. Do not execute anything.

## Expected Skills

- `helix-query-optimize`

## Gold Expectations and Scoring Checklist

- [ ] Continue static analysis using the supplied query and schema.
- [ ] Identify assumptions and state that active indexes and actual latency were not verified.
- [ ] Do not stop all authoring work or invent p99/usage values.
- [ ] Offer the MCP setup guide for live verification without making setup a prerequisite for static review.
- [ ] Do not query a direct gateway, request a key, or execute the query.
