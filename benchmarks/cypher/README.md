# Cypher Benchmarks

These cases test whether `helix-query-from-cypher` sends statements the server
runs natively (`POST /v2/cypher`) and translates the rest with correct
semantics.

Coverage goals:

- native execution of supported statements (OPTIONAL MATCH, DETACH DELETE)
- optional traversal with row bindings (`bind` + `optional` + `project_bindings`)
- upsert on a unique key with `var_as_if`
- relationship MERGE without duplicate edges
- per-element write expansion (`for_each_param`)
- null checks and delete-after-filter
- best-item selection and null ordering
- bounded multi-hop traversal with `emit_after` and target labels
- server-side timestamps (`Expr::timestamp()`)
