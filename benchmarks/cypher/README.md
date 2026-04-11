# Cypher Benchmarks

These cases test whether `helix-query-from-cypher` handles the supported Cypher-to-Helix mappings rather than falling back to older weaker translations.

Coverage goals:

- optional traversal
- upsert branching
- per-element write expansion
- delete-after-filter
- null and existence checks
- conditional branching
- best-item selection after collection
- bounded multi-hop traversal
- server-side timestamps
