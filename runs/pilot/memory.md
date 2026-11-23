## db_evolve planner memory (duckdb)

### Round log
- G1R1: baseline 1.000x, geomean 40.0ms. E0001 (substring-match selectivity) retired because the implementer ran out of time, not because the idea was bad.
- G1R2: E0002, a minimal version of E0001, built OK. Estimates moved but the physical plan did NOT change, so there was no gain. RETIRED. The premise was wrong.
- G2R1: E0003, estimate-based perfect-hash acceptance. RETIRED. With k=8: q13 -24% but q17 +64%. Estimate gating is the wrong mechanism.
- G2R2: E0004, lazy-init perfect HT plus an 18-bit extension at the default threshold. RETIRED at -0.3% geomean (the implementer's own run gave -3.0%). q13 -20% is consistent. This was a good idea with too narrow a gain. Don't resubmit unless it is bundled with another win.
- G3R1: E0005, per-key multi-key join BF. RETIRED at +6.7%. The premise was wrong: in q09 partsupp is the BUILD side of the 2-key join. The code works but has no use here.
- G3R2: dispatched "Collapse adjacent duplicate group keys before hash-table probe in aggregation" (aimed at q18's subquery GROUP BY l_orderkey).

### Lessons for dispatching
- Keep diffs out of widely included headers (long rebuilds). Use file-local statics or constexpr.
- Ask implementers to build in the background and to EXPLAIN-check before the full bench.
- CHEAP EXPERIMENTS: `dbe-tool sql "SET <setting>=X; <query>; <query>"` prints per-statement ms (first run cold, second hot). Use it to time subqueries in isolation; it is very effective.
- rules.md item 4: never change default settings.
- Planner estimates after LIKE filters and outer joins are off by 5-1000x. Prefer runtime-adaptive mechanisms.
- The bar is -2.7% visible geomean. A 20% gain on one of 14 templates (about -1.6%) does NOT clear it. Cut a big template by 30%+ or help several.
- VERIFY probe/build sides in the plan BEFORE proposing join ideas. Two retirements came from misreading sides.

### Tooling facts
- EXPLAIN (FORMAT JSON) hangs. EXPLAIN ANALYZE via `dbe-tool sql` works.
- profile.md truncates big plans. Operator times are summed CPU.
- Bench noise is about ±10% per query on quick runs.

### Codebase facts (verified)
- HASH_JOIN: the LEFT child is the probe and the RIGHT child is the build. BFs only reach probe-side scans.
- Join BF: CanUseBloomFilter physical_hash_join.cpp:761 requires conditions.size()==1. E0005 has a working per-key BF design (see ledger) if a use appears.
- LIKE: LikeMatcher is already good. FSST scan decompresses every row.
- RelationStatisticsHelper::DEFAULT_SELECTIVITY=0.2 applies flat to non-equality filters.
- Perfect hash agg: CanUsePerfectHashAggregate plan_aggregate.cpp:127, threshold :230. E0004 had a working lazy version.
  - q13 inner agg forced perfect 115→90ms. A 20-bit table on empty input costs +10ms.
- Radix HT adaptation: DecideAdaptation radix_partitioned_hashtable.cpp:424.
- Agg HT: GroupedAggregateHashTable::AddChunk aggregate_hashtable.cpp:519 → TryAddCompressedGroups (constant/dictionary fast paths) → FindOrCreateGroupsInternal :641 (probe loop with a sel_vector IsSet template variant, RowMatcher compare, skip_lookups branch :685) → UpdateAggregates :533.
- Measured: q18's subquery agg (6M rows→1.5M groups, GROUP BY l_orderkey) takes ~65-72ms hot. A plain sum scan of lineitem takes 3ms. lineitem is clustered by l_orderkey (~4 rows/key).

### Profile hotspots (G3R2, geomean 43.5ms)
- q09 121ms, q13 105, q18 87, q16 49, q19 47, q22 43, q03 39, rest 22-37ms.
- q09: the join operator is dominated by building an 800k-row partsupp HT; lineitem scan 0.43s.
- q13: orders scan + NOT LIKE 0.22s, RIGHT join 0.10-0.15s, HASH_GROUP_BY 0.20s.

### Directions
- Active: run collapse for clustered agg keys (G3R2). If the gain is real but small, combine it with E0004's lazy perfect HT (the q13 win) into one aggregation bundle. If the duplicate path adds no gain, check whether the time is in Finalize/repartition rather than probing (profile the radix HT phases).
- Next candidates: q16 and q19/q22 plans are not yet inspected (q16 plan is in profile.md at line ~550). For q09, the planner could flip the join sides, or a semi-join filter could be pushed into the build side; both are large changes.
- Exhausted: cardinality-selectivity tweaks for q09; estimate-gated perfect hashing; standalone lazy perfect HT; multi-key BF for q09.
