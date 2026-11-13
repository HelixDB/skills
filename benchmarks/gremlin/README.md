# Gremlin Benchmarks

Tests whether `helix-query-from-gremlin` maps Gremlin step chains to Helix
anchors, traversals and result shaping with the same semantics.

Coverage goals:

- start-step anchoring
- `hasLabel` and `has` filtering, including target labels
- directional traversal
- dedup, ordering, range, and limit
- bounded repeat with the emit mode that matches Gremlin's emit position
