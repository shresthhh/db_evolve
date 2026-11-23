# Memory

## Round 1 (gen 1) findings
- q19 is the only visible template (TPC-H Q19 shape: OR of 3 branches, each with join eq + part preds + lineitem preds). Baseline ~307ms hot.
- E0001 ACCEPTED (-46%): JoinDependentFilterRule (src/optimizer/rule/join_dependent_filter.cpp) only fires on ROOT OR; DistributivityRule factored the join eq out first. Fixed by reordering in optimizer.cpp.
- ExpressionRewriter::ApplyRules: is_root=true only on top call from VisitExpression. Rewriter runs once per optimization.
- dbe-tool sql: no shell loops/variables (blocked). Multiple statements separated by ';' inside ONE dbe-tool sql call run in one process (warm-ish) -> best way to A/B isolated predicates. Separate calls are cold and noisy (2x variance).
- bench noise: ~±10% between runs. Need >~10% or repeated runs.

## Round 2 (gen 1)
- E0002 ACCEPTED (-38%): l_quantity OR-of-ranges is an EXPRESSION_FILTER (not ConjunctionOr). Dense mask eval + gather in column_segment.cpp TryDenseFilterSelection.
- Scan filter loop: RowGroup::Scan (row_group.cpp ~760-820) applies filters in AdaptiveFilter permutation order; filter columns are fully decoded (ColumnData::Filter = Scan + FilterSelection) regardless of sel sparsity; other cols use Select (only selected rows). SetFilterAlwaysTrue clears column_has_filter -> column moves to Select path.
- BFTableFilter (planner/filter/bloom_filter.cpp): blocked BF, 12 bits/key, hashes only selected rows.

## Round 3 (gen 1)
- E0003 RETIRED (0%): dictionary-level filter for plain Dictionary VARCHAR. String compares cheap; cost is per-vector scan overhead (a pass-all dict filter ~0.46s cum).
- Storage: l_shipinstruct/l_shipmode = VARCHAR Dictionary; l_partkey/l_quantity BitPacking (no select/filter callbacks). Sparse BitPacking select = 0%.

## Round 4 (gen 1) - best 149.7ms q19 (2.996x)
- E0004 RETIRED: AND-of-optional shipmode filter wasn't present then. Always check the live `dbe-tool profile` before planning.
- SelectivityOptionalFilter (BF + min/max dynamic filters) subclasses OptionalFilter with the same filter_type but DOES filter.

## Round 5 (gen 1)
- E0005 RETIRED (bench noise): cost-aware BF ordering cut scan cum 5.88->4.70s in the profile but no bench wall gain. Ordering is not the bottleneck.
- Latent bug: ExpressionHeuristics::Cost(Expression&) BOUND_REF casts to BoundColumnRefExpression (throws).

## Round 6 (gen 1)
- Live q19.m0 profile NOW shows `optional: l_shipmode IN AND optional: l_shipmode IN` (a ConjunctionAnd of two plain optionals) on the lineitem scan. CheckZonemap (row_group.cpp:626) only skips top-level OPTIONAL_FILTER -> the AND is decoded and evaluated per row for no effect.
- Dispatched: treat a pure-optional AND (excluding SelectivityOptionalFilter) as always-true in CheckZonemap.
- Profile: lineitem scan 82,782 rows out, FILTER shipmode above -> 11,797; part scan+filter ~0.15s cum; join 0.01s.

## Next ideas
- If the skip lands: find/dedupe the source of the duplicated optional pushdown (likely the derived OR filter plus the original both pushed via FilterCombiner).
- Apply the shipmode IN inside the scan as a real filter (drop the FILTER above, 0.15s cum) - needs the optional-filter policy changed.
- Exact bitmap instead of BF for small dense integer build-key ranges.
- ConjunctionOr-of-And TableFilters for OR-of-ranges => zonemap pruning (riskier; quantity is not clustered).
