## Memory (planner, q18 specialisation run)

### Workload facts (q18 only visible template; current best ~556 ms hot, 8 threads; start ~640)
- Plan: IN-subquery `GROUP BY l_orderkey HAVING sum(l_quantity) > X` over all of lineitem (60M rows -> 15M groups -> ~111 after HAVING).
  HASH_GROUP_BY ~455-470 ms wall isolated (CPU-bound, all 8 threads).
- R6 wall ablation (alternating): full q18 ~577, without customer join ~522, aggregate-only count(*) ~470 ms.
  => customer part ~55 ms, orders+lineitem outer ~50 ms. Everything is CPU-bound, so overlapping pipelines does not hide cost; only less CPU helps.
- Customer join: builds a 1.5M-row HT (0.39s CPU + scan 0.12s) for 111 probe rows. The cause is the estimate: the semi-joined orders side is ~3.5M
  because the HAVING filter gets the 0.2 DEFAULT_SELECTIVITY (relation_manager.cpp:274 aggregate case). A manual LIMIT-capped rewrite flips the
  sides: ~-5% (511/551 vs 551/574 ms).
- Perfect HJ is not used for customer: MAX_BUILD_SIZE=1048576 (perfect_hash_join_executor.cpp:108) < 1.5M range. The perfect HJ build
  (FullScanHashTable) is single-threaded.
- After E0005: lineitem probe scan emits 17.5M/60M rows (~13.6M floor), orders scan 9.0M/15M.
- Group key arrives compressed as UINTEGER (compressed materialization). sum_no_overflow(decimal) -> SumState<int64_t>.

### Key measurements / tooling
- dbe-tool sql: several ;-separated statements per call work; the first run is cold; ±10-15% noise -> ALTERNATE variants in one call.
- Bash: pipes to grep are allowed, but patterns containing '~', '=' or '<' trigger approval prompts; keep grep patterns simple.
  Shell variables ($Q) are blocked; inline the SQL.
- Agg per-group cost ~125 ns CPU at 8t. R4 ablation (E0004): no sink sub-step >8%. THE AGGREGATE IS EXHAUSTED; no more radix-agg tweaks.

### Codebase facts
- Radix sink: Sink() (radix_partitioned_hashtable.cpp:548) -> ht.AddChunk (aggregate_hashtable.cpp:519) -> FindOrCreateGroupsInternal (:641).
- Join filter pushdown: optimizer join_filter_pushdown_optimizer.cpp; runtime physical_hash_join.cpp (CanUseInFilter, PushInFilter, FinalizeFilters,
  CanUseBloomFilter :849, bloom only if build side has a filter and probe estimate > build count). E0005 added storage_offset through compress projections
  plus the gap-split range-set OptionalFilter.
- Join order: relation_manager.cpp ExtractJoinRelations. Filters directly above a relation-needing op go to datasource_filters -> x0.2 once per relation.
  PROJECTION/AGGREGATE/GET need a relation. SEMI RHS is optimized by a child optimizer (:320). ModifyStatsIfLimit in the aggregate case (:278) is applied
  to child_stats, not operator_stats (looks like an upstream bug; LIMIT on aggregates does not cap the estimate).
- Compressed materialization runs inside statistics propagation, after join order and JOIN_FILTER_PUSHDOWN setup.
- rules.md: default settings are off-limits. Hidden queries are checked for correctness only, but generality is reviewed.

### Directions
- Accepted: E0005 key-set zonemap filter (-13.6% q18).
- Retired: E0001 run-collapse, E0002 in-place finalize, E0003 skip staging, E0004 agg ablation.
- R6 dispatched: extra selectivity for HAVING range predicates on aggregate results (join-order flip so customer is probed). If it fails, check whether
  the flip happened (EXPLAIN) before blaming the idea. The hand-rewrite measured about -5%, so a gain below noise is possible even when it works.
- Backlog: more than 50 zonemap ranges (~1%); radix sink partition growth (dead, superseded by E0004).
- Other ideas: raise the perfect-HJ MAX_BUILD_SIZE together with a parallel perfect build (helps dense-key dimension joins of 1-4M rows).
