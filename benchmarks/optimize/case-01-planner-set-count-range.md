# Case 01: Planner-Aware Set, Count, And Range Optimization

## Prompt

Review this query for a large `Order` dataset. Available indexes are non-unique equality indexes on `(Order, status)` and `(Order, region)`, plus a descending range index on `(Order, createdAt)`.

```rust
g().n_with_label("Order")
    .where_(Predicate::or(vec![
        Predicate::eq("status", "open"),
        Predicate::eq("status", "queued"),
    ]))
    .where_(Predicate::eq("region", "eu"))
    .order_by("createdAt", Order::Desc)
    .limit(50)
    .id()
```

The caller only needs the number of matching rows in that ordered 50-row window. Propose the optimized logical shape and explain the expected planner behavior. Also explain what happens if the status disjunction is replaced by `Predicate::is_in_param("status", "statuses")`, and whether the two adjacent `where_` calls prevent combined access planning. Cover null, NaN, a unique equality index, and late-bound values.

## Expected Skill

- `helix-query-optimize`

## Focus Areas

- same-index equality bitmap union
- multi-index intersection before row materialization
- ordered range driver filtering before limit
- dedicated count program instead of ID materialization
- exact numeric/NaN/null semantics
- unique verification and late-bound dynamic equality
- bounded runtime membership and authoritative fallback
- adjacent-filter canonicalization and semantic boundaries
- normalized saturating limit/skip/range windows

## Gold Expectations

- Keep `status == open OR status == queued` as one logical source expression so same-index points can use a batched bitmap union.
- Intersect the status union with the `(Order, region)` equality bitmap before loading rows.
- Use the descending `createdAt` range index as the ordered driver, apply equality filters before satisfying `limit(50)`, and avoid a redundant sort.
- End in `.count()`, not `.id()` plus client-side length, so the planner can select a dedicated count program.
- Explain that count windows use normalized saturating arithmetic while preserving operator order.
- State that exact cross-numeric equality does not round integers through `f64`; signed zero normalizes; NaN is non-reflexive/non-indexable.
- State that null equality needs an authoritative scan, unique equality verifies the owner, range candidates are verified, and a genuinely late-bound parameter may use a dynamic equality program.
- State that bounded scalar/array `is_in_param` values can use a runtime equality union; duplicate values normalize, NaN members are skipped, and null, unsupported, oversized, or over-limit domains use authoritative evaluation.
- State that contiguous filters canonicalize into one conjunction, while a non-filter operation remains a boundary.
- Avoid claiming that only immediate `step -> Limit` lookahead enables the optimization.

## Gold Shape Sketch

```rust
g().n_with_label_where(
    "Order",
    SourcePredicate::and(vec![
        SourcePredicate::or(vec![
            SourcePredicate::eq("status", "open"),
            SourcePredicate::eq("status", "queued"),
        ]),
        SourcePredicate::eq("region", "eu"),
    ]),
)
.order_by("createdAt", Order::Desc)
.limit(50)
.count()
```

## Scoring Checklist

- [ ] Uses one same-index equality union for the two status values
- [ ] Intersects status and region ID sets before row materialization
- [ ] Selects the descending range index as the ordered driver
- [ ] Applies equality filters before the 50-row limit
- [ ] Avoids an unnecessary in-memory sort
- [ ] Replaces ID materialization/client length with `.count()`
- [ ] Mentions dedicated bitmap/range/streaming count alternatives and normalized saturating windows
- [ ] Correctly covers exact cross-numeric equality, normalized zero, and non-indexable NaN
- [ ] Retains null scans, unique-owner verification, range verification, and late-bound parameter handling
- [ ] Covers bounded runtime membership, normalization, and authoritative fallback
- [ ] Explains adjacent-filter canonicalization without moving filters across boundaries
- [ ] Does not repeat the stale exact-lookahead-only mental model
