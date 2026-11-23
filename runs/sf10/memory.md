## db_evolve planner memory (duckdb)

### Round log (pilot run, SF1 data, old geomean bar)
- E0001/E0002 contains-selectivity 0.04: retired at SF1 (the plan did not change). At SF10 the plan flips, and it was accepted as E0008.
- E0003 estimate-gated perfect hash agg: q13 -24% but q17 +64%. Estimate gating is the wrong mechanism.
- E0004/E0007 lazy-init perfect hash AGG plus an 18-bit extension: retired (q02 +8%). Perfect agg range is bounded by a SETTING (perfect_ht_threshold), so it cannot change.
- E0006 run-collapse in agg probe: about 10% less agg CPU, no wall gain.

### New run (SF10 data; bar: some templates faster beyond noise, none slower)
- G1R1: E0008 contains-selectivity ACCEPTED (q09 1211 -> 709ms).
- G1R2: E0009 per-key BF for multi-key joins ACCEPTED (q09 -15 to -19%).
- G2R1: E0010 OR-filter derivation under a root AND ACCEPTED (q19 347 -> 186, q14).
- G2R2: E0011 Deliminator SEMI/ANTI without blocking ops ACCEPTED (q04 -30%, q22 -20%).
- G3R1: E0012 RIGHT_SEMI/RIGHT_ANTI join filters + equality for deliminated EXISTS + no CM on RIGHT_SEMI/ANTI keys ACCEPTED (q22 -12%, q04 flat: BF cut join CPU 0.55s but scan CPU rose 1s). Geomean 1.156x.
- G3R2: dispatched "Perfect hash join for RIGHT joins on dense integer keys (range up to 4M)". Target is q13's RIGHT join (orders probe 14.8M, customer build 1.5M dense, 2.06s CPU). perfect_hash_join_executor.cpp:73 is INNER only; MAX_BUILD_SIZE=1M at :108 is a constant, not a setting. Plan: a matched-flag array per slot, copied into the rows' found_match before the outer scan, plus a 50% density gate. If it fails on perf, check whether the gather/build cost outweighs the probe saving. If it fails on correctness, look at NULL build keys and the found_match handoff.

### Verified this round (do not redo)
- q09: compressed materialization DOES block the o_orderkey BF on the orders probe (__internal_compress_integral_uinteger wraps the probe key). With CM disabled the BF reaches orders (15M -> 2.96M) but q09 wall is unchanged (560 vs 560ms), and the join stays at 1.58s CPU (build of 3.27M lineitem rows plus payload). So "CM blocks INNER join filters" is NOT a lever for q09. Low priority overall.
- Standalone agg on orders: GROUP BY o_custkey (1M groups) about 165ms wall (scan only 10ms), GROUP BY o_custkey%1000 61ms, GROUP BY o_orderkey (15M unique) 228ms. That is about 80ns/row for 1M groups. q13's HASH_GROUP_BY (15.3M -> 1.5M groups) is 2.69s CPU.
- The BF probe code (planner/filter/bloom_filter.cpp) is already a tight scalar loop (sector-blocked, 4 bits). Its zone-map check works only for a range <= 2048. Not a micro-opt target.

### Lessons for dispatching
- Keep diffs out of widely included headers. Use file-local statics.
- Ask implementers to EXPLAIN-check before the full bench. Bench noise is +-10-35% per template on single runs; re-run before calling a regression.
- `dbe-tool sql "q; q; q"` prints per-statement ms; the first run is cold. Use `$(cat .dbe/queries/qXX.m0.sql)` inside the sql string (a shell variable assignment gets blocked). Pipe into `| grep -E "ms\)"` or `| cut -c1-120 | tail -N`. `grep -v` with special chars needs approval. EXPLAIN ANALYZE output is truncated at about 110 lines.
- MANUAL REWRITE TEST / `SET disabled_optimizers='x'; q` = cheap validation of optimizer ideas. Do it before dispatching.
- rules.md: never change default settings.
- Planner estimates after LIKE filters and outer joins are off by 5-1000x.
- VERIFY probe/build sides in the plan before proposing join ideas.

### Codebase facts (verified)
- HASH_JOIN: LEFT child = probe, RIGHT child = build. BFs only reach probe-side scans.
- Join filter generation: JoinFilterPushdownOptimizer::GenerateJoinFilters (join_filter_pushdown_optimizer.cpp:206). The exclusion list is at 207. build_side_has_filter is set from IsFiltering (:184), which recurses through children. CanUseBloomFilter is at physical_hash_join.cpp:762 (needs build_side_has_filter, probe est > build count, no perfect HT).
- Perfect hash JOIN: perfect_hash_join_executor.cpp:66 CanDoPerfectHashJoin; FullScanHashTable :141 gathers build columns into vectors with bitmap_build_idx; probe at :269. Physical hookup is in physical_hash_join.cpp 145-149 and 1016-1030.
- Compressed materialization (compress_comparison_join.cpp) wraps join keys of builds below JOIN_BUILD_CARDINALITY_THRESHOLD=1M. Join pushdown cannot pass through compress functions.
- Radix agg adaptation: radix_partitioned_hashtable.cpp:424 DecideAdaptation (skip lookups when HLL > 0.95; ADAPTIVITY_THRESHOLD 1M at :382).
- Expression rewriter rule order: optimizer.cpp:50-71. Deliminator: deliminator.cpp:69/88/205.
- Scan filter estimate: relation_statistics_helper.cpp ExtractGetStats. LIKE: like.cpp + contains.cpp.

### SF10 profile (G3R2, wall ms): q13 773, q18 657, q09 590, q05 267, q03 252, q08 225, q04 220, q17 218, q16 197, q07 193, q19 184, q14 158, q22 128, q02 79.
- q13: orders scan NOT LIKE 2.79s CPU; RIGHT join 2.06s; HASH_GROUP_BY 2.69s (15.3M rows -> 1.5M groups).
- q09: lineitem scan with BF 2.40s CPU; o_orderkey join 1.51s.
- q18: subquery agg over 60M lineitem -> 15M groups dominates.

### Directions
- Active: perfect HJ for RIGHT joins (q13).
- Next candidates: (a) q13/q18 high-cardinality agg (backlog issue; needs a perf profile first; 80ns/row at 1M groups). (b) q04: run the BF before the residual filter / late-decode the date columns (from the E0012 follow-up). (c) Deeper-nested OR derivation (q07?); manual-test first. (d) If RIGHT perfect HJ works: LEFT/FULL variants.
- Low value / exhausted: CM blocking pushdown (q09 verified no gain); estimate-gated perfect hash agg; agg duplicate-run collapse; LIKE matcher micro-opts; BF probe micro-opts.
