# Case 05: Tenant creation and separate application keys

## Prompt

Create a tenant called example in project:example-id through my authorized human session. I need no direct gateway client or application key.

## Expected Skills

- `helix-admin-mcp`

## Gold Expectations and Scoring Checklist

- [ ] Use the unified endpoint and management permissions; do not use a separate Admin MCP host.
- [ ] Prepare create_tenant with target project:example-id and payload containing matching project_id, name, and slug.
- [ ] Review the exact mutation before executing once with the unchanged operation, target, payload, confirmation_id, and confirmation_token.
- [ ] Expect tenant_id and slug with no application key.
- [ ] Do not automatically create a database key; that is a separate operation requiring authorization.
- [ ] An agent registration has no admin tools and must not attempt this workflow.
