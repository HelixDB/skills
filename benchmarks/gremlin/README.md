# Gremlin Benchmarks

These cases test whether `helix-query-from-gremlin` maps imperative Gremlin step chains into deliberate Helix anchors, traversals, and result shaping.

Coverage goals:

- start-step anchoring
- `hasLabel` and `has` filtering
- directional traversal
- dedup, ordering, range, and limit
- bounded repeat with emit semantics
