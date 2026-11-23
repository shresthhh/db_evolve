# Memory (planner, specialisation run on q02 = TPC-H Q2 shape, SF10)

## Round 1 findings (gen1)
- q02 baseline ~80ms wall. Plan: part scan (p_size=, suffix LIKE) builds HT -> partsupp scan probes with
  pushed bloom filter (73k of 8M rows survive); supplier probes tiny nation-region HT, result materialised as CTE
  __common_subplan; correlated min() subquery decorrelated via LEFT_DELIM_JOIN + HASH_GROUP_BY.
- Bloom filter pushdown already exists (JoinFilterPushdownInfo in physical_hash_join.cpp). Don't propose "add BF".
- E0001 ACCEPTED (-18.5%): sub-row-group morsels (RowGroupCollection::GetParallelScanMorselVectors).

## Rounds 2-5 (all RETIRED, all "bad idea", not bad implementation)
- E0002 sparse BitPacking select: no gain (payload decode not the bottleneck).
- E0003 compaction of sparse scan chunks: no gain (per-chunk overhead not the bottleneck).
- E0004 row-level small IN filter on supplier: no gain (FSST full scans emit lazy vectors).
- E0005 CTE CARDINALITY_RATIO 2->8: removed CTE, median only ~-5%, noisy -> retired. Barrier cheaper than thought.
- Noise: q02 hot ±7%; bar is -5%. Profile operator times are cumulative across threads.

## Round 6 (hot breakdown, 8 threads, measured via repeated queries in one dbe-tool sql call)
- outer 5-way join count(*): 17ms; with full projection + TopN: ~30ms; full q02: ~47ms.
  => subquery side (second partsupp scan + delim + CTE) costs ~17-20ms.
- Hand-written window rewrite (min() OVER (PARTITION BY p_partkey), filter =) gives ~36ms: -23%.
- DISPATCHED E0006: WinMagic-style rewrite of correlated MIN/MAX scalar subquery -> window, in Binder::PlanFilter
  (plan_select_node.cpp:11; condition is the whole WHERE, root is the unfiltered FROM cross product at that point).
  If it failed on implementation (binding remap bugs), the idea is still good; retry with stricter/simpler matching.
- Wide strings (s_address, s_phone, s_comment) on supplier build side add ~5-10ms (noisy); scan of them alone ~2ms.
- supplier string scan is cheap (~2ms at 8 threads), so E0004's "0.06s" was cumulative/cold noise.
- partsupp: sum(ps_partkey) full decode 2.6ms hot; BF-filtered join partsupp⋈part ~11ms total.

## Measurement method
- Each `dbe-tool sql` call is a fresh process; first query is cold (2x). Run 2-3 repeats in one call and
  grep -E "ms\)". Inline SQL text literally (no shell vars, no $(cat) — blocked).
- EXPLAIN ANALYZE box output is wide/truncated; grep -E "[A-Z_][A-Z_][A-Z_]+ |main|rows|=" gives a usable view.
  EXPLAIN (FORMAT JSON) hung (timeout) — avoid.
- SET disabled_optimizers='...' is a cheap way to test whole optimizer passes.

## Codebase facts
- RowGroupCollection::NextParallelScan now sub-row-group. RowGroup::Scan (row_group.cpp) filters then Selects.
- StandardColumnData::Select falls back to Scan+Slice without compression select. FSST/dict_fsst have selects.
- Vector::Slice on FSST_VECTOR flattens only selected rows (vector.cpp:260) — not wasteful.
- JoinFilterPushdownOptimizer::GenerateJoinFilters (join_filter_pushdown_optimizer.cpp:206): NOT_DISTINCT_FROM
  conditions get no filters; DELIM_GET build -> build_side_has_filter = IsFiltering(probe child).
- CanUseBloomFilter: no BF for perfect HT; needs build filter and probe est > build count.
- Correlated subquery planning: plan_subquery.cpp PlanCorrelatedSubquery (SINGLE delim join for SCALAR).
- CommonSubplanFinder::IsSelectiveMultiTablePlan (common_subplan_optimizer.cpp:~975) decides CTE materialisation.
- dbe-tool tips: no braces {n}, no awk/sed/head, no `cd ;` compounds, no shell variables, no `$`/`*` in some grep
  patterns (needs approval).

## Directions
- Promising: plan-shape rewrites (subquery->window). Measure with hand-rewritten SQL first; it's cheap and decisive.
- Exhausted: scan-level decode/filter micro-optimizations on q02 (E0002-E0004); CTE threshold tuning (E0005).
