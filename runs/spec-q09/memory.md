# Memory (planner)

## Round 1 (gen1) findings: q09 specialisation
- Baseline q09 was about 918-980 ms. The old plan built hash tables on 15M orders and 8M partsupp. The LIKE contains filter got 0.2 selectivity.
- E0001 ACCEPTED: STRING_PATTERN_SELECTIVITY 0.05 in relation_statistics_helper.cpp ExtractGetStats. q09 went 980 to 723 ms.
- BuildProbeSideOptimizer (build_probe_side_optimizer.cpp TryFlipJoinChildren) compares row_width*cardinality, with penalties for VARCHAR/column count.
- SQL experiment trick: SET disabled_optimizers='join_order,build_side_probe_side' plus explicit JOINs (left=probe, right=build).

## Round 2: E0002 ACCEPTED (multi-key BF on first key), q09 723 to 536 ms
- CanUseBloomFilter (physical_hash_join.cpp ~761) allows multi-key joins on condition 0.
- A BF is built only when it is pushed. BF size is 12 bits/key, rounded up to a power of 2 (bloom_filter.cpp). For 3.27M keys that is 8MB.
- build_side_has_filter = IsFiltering(build child), which recurses through joins (join_filter_pushdown_optimizer.cpp:184).

## Round 3: E0003 prefetch RETIRED at -4.7% (whole-vector pre-pass, crude).
## Round 4: E0004 prefetch v2 ACCEPTED -10..-15% (distance 16, 4MB gate, build+probe+chain).
- join_hashtable.cpp: HT_PREFETCH_DISTANCE line 200, ShouldPrefetch line 204, probe loop line 215, build insert line ~694, chain prefetch line ~1017.
## Round 5: E0005 Bitpacking select RETIRED (0% hot). Scan decode of non-filter cols is NOT the cost on hot runs; the earlier 20ms estimate came from cold single-shot sql timings. Scan-decode direction exhausted.
## Round 6: dispatched prefetch distance 16 -> 32 (test 16/32/48). If neutral, the prefetch direction is exhausted.

## MEASUREMENT (important)
- Profile operator times are inflated (scans especially). Use wall time from batches: `dbe-tool sql "q; q; q; q; q"`, which prints the total. Divide by N. Cold single-shot timings mislead (buffer/IO), see E0005.
- NOISE IS LARGE between processes (+-15%). Always compare A and B back to back, and repeat if the gap is under 15%.
- compressed_materialization on vs off is NEUTRAL. Do not pursue CM changes.
- The bench reports about 444 ms for q09 vs about 85 ms/run in sql batches (different harness). Use ratios only.

## Current q09 shape (profile, gen1 r6)
- The orders join (o_orderkey = l_orderkey; 15M probe orders, 3.27M build, 64MB table, about 80% misses) is the largest operator at 1.31s. It gets no BF; a BF was tested slower earlier. Min/max is useless (the keys span the range).
- lineitem scan with BF on l_partkey, then the 2-key partsupp join.
- Tail: compress projection 0.16s, HASH_GROUP_BY (175 groups) 0.18s operator time.

## Remaining ideas (ranked)
1. (dispatched r6) Prefetch distance tuning.
2. Agg tail: compress/decompress projections around a 175-group aggregate (0.16s+0.18s). Possibly skip compressed materialization of the group keys when the groups are few, but CM on/off measured neutral, so weak.
3. Orders join: smaller table (lower load factor) or a BF tuned to fit L2/L3. Earlier BF was slower; would need new evidence.
4. Multi-key join cardinality (backlog). Low priority; the plan is already good.

## Tool notes
- Grep with output_mode content and -o on .dbe/profile.md gives the rows/timings quickly. The Bash grep pipe needs approval.
- `dbe-tool profile q09.m0` shows dynamic filters (plain EXPLAIN does not).
- `pragma_storage_info('tbl')` shows compression and segment_info.
