## Round g1r1 (2026-11-23)
- Workload: q16 only (count DISTINCT ps_suppkey GROUP BY p_brand,p_type,p_size; partsupp JOIN part, NOT IN supplier MARK join). Baseline 179ms.
- E0001 ACCEPTED: distinct radix HT partitioned on hash(G): -13.4%. Current best 1.155x; q16 ~115-183ms (noisy).
- Facts from earlier runs (global auto-memory):
  - Skip unpartitioned staging for heap (VARCHAR) layouts: ~-5%, noisy.
  - Early HT grow (-3%) and early SkipLookups (<=3%) are noise. Don't repeat.
  - Join output reaches the agg as ~300-row chunks. Main-HT re-sink costs ~88-150ns/row.
  - Gotcha: wrapping q16 in count(*) lets the optimizer drop DISTINCT. Use max(cnt).
- Code locations: RadixPartitionedHashTable::Sink radix_partitioned_hashtable.cpp:548; AddChunk aggregate_hashtable.cpp:564; FindOrCreateGroupsInternal :641; staging decision :755-761.

## Round g1r2: profile after E0001 (operator CPU)
- HASH_GROUP_BY 0.31-0.79s (distinct HT only; CanSkipRegularSink skips the main sink when all aggs are DISTINCT).
- Distinct HT key: p_brand compressed to uhugeint, p_type raw VARCHAR (heap), p_size utinyint, plus suppkey.
- partsupp scan 0.20-0.29s (8M rows, min/max + hashed BF, emits 1.236M; the join keeps 1.185M).
- E0002 RETIRED: IN list as a scan ExpressionFilter. Correct, but the MARK join is ~0.01s. Bad target.

## Round g1r3
- E0003 RETIRED: sparse perfect HJ + BF +39..56%. Serial 66MB dictionary build. Bad idea for wide payloads.
- RULE: divide EXPLAIN ANALYZE operator CPU by 8 for a wall-time estimate before predicting gains.
- Perfect HJ: range cap 1M (perfect_hash_join_executor.cpp:108); dup check off by one; a perfect HJ disables the BF.

## Round g1r4
- E0004 RETIRED (not implemented): distinct finalize CPU: distinct GetData 150-168ms, main-HT sink 104ms, Combine 1.5ms. Group-aligned main sink <=3.5%.
- Combine resets the local HT; the next Sink re-allocates the full pointer table.
- Debug tip: Printer::Print output shows up as "ERROR:" on stderr from dbe-tool sql.

## Round g1r5
- E0005 RETIRED: staging gate for heap layouts (AllConstant at aggregate_hashtable.cpp:755): -5.7% visible, rejected as noise. Third attempt overall (-6.5, -7.7 in the implementer's runs). A real but marginal gain; only worth stacking with something else.

## Round g1r6
- Dispatched: exact bitmap BF for dense-int keys (bloom_filter.hpp/.cpp, PushBloomFilter physical_hash_join.cpp:787, deferred push :587, min/max at :862; BLOOM_FILTER eval at column_segment.cpp:558, table_scan.cpp:498, table_filter_state.cpp:16). Expected -4..-8%.
- Fresh profile (0.30s total with profiling on): HASH_GROUP_BY 0.79s CPU, INNER HJ 0.27s, partsupp scan 0.29s, part scan 0.07s, everything else <=0.04s.

## Remaining levers for q16 (if a future generation continues)
- Count DISTINCT directly from group-aligned distinct partitions (backlog; removes ~104ms CPU of main sink, ~7% max; medium-high risk in the distinct finalize protocol, AggregateDistinctGrouping physical_hash_aggregate.cpp:665).
- p_type VARCHAR in the distinct HT key (>16 bytes, so no CM compression): dictionary-ID group keys would avoid the heap layout. Largest potential but invasive.
- Stacking the staging gate (E0005) with another win.
