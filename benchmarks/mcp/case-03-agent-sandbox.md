# Case 03: Agent sandbox setup and authoring

## Prompt

I have an agent registration with both query scopes. Set up its sandbox and draft a node-insertion query. No Cloud discovery or insights tools are listed.

## Expected Skills

- `helix-query-mcp`
- `helix-query-json-dynamic`

## Gold Expectations and Scoring Checklist

- [ ] Call helix_get_started with an empty argument object.
- [ ] Use the returned database only when status is ready; never select another tenant or cluster.
- [ ] Do not require human discovery, observability, or admin tools.
- [ ] Draft from the supplied task context; state that live index and performance evidence is unavailable.
- [ ] Do not execute the draft: the user asked for setup and authoring, not insertion.
- [ ] If scopes are missing or setup fails, report the failure and do not invent a database reference.
