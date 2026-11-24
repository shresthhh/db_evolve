# Memory

## Round g1r1 (2026-11-23)
- Workload: q16 only (count DISTINCT ps_suppkey GROUP BY p_brand,p_type,p_size; partsupp JOIN part, NOT IN supplier MARK join). Baseline 179ms.
- E0001 ACCEPTED: distinct radix HT partitioned on hash(G): -13.4%. Current best 1.155x, q16 ~115-170ms (noisy).
- Facts from earlier db_evolve runs (global auto-memory, same engine):
  - Skip unpartitioned staging for heap (VARCHAR) layouts: ~-5% median, noisy (-15.8, -8.1, +1.6, -5.9).
  - Early HT grow (-3%) and early SkipLookups (<=3%) are noise. Don't repeat.
  - Join output reaches the agg as ~300-row chunks. Main-HT re-sink costs ~150ns/row.
  - Old per-phase CPU (pre-E0001): distinct sink AddChunk ~250ms, Abandon ~40, MaybeRepartition ~100-146, distinct source Finalize ~120, main-HT sink ~180, main finalize ~30.
  - Gotcha: wrapping q16 in count(*) lets the optimizer drop DISTINCT. Use max(cnt) instead.
- Code locations: RadixPartitionedHashTable::Sink radix_partitioned_hashtable.cpp:548; AddChunk aggregate_hashtable.cpp:564; FindOrCreateGroupsInternal :641.

## Round g1r2 (2026-11-24): profile after E0001 (operator CPU)
- HASH_GROUP_BY 0.31-0.57s (distinct HT only: CanSkipRegularSink skips the main sink when all aggs are DISTINCT).
- Distinct HT key: p_brand compressed to uhugeint, p_type raw VARCHAR (heap layout), p_size utinyint, plus suppkey.
- partsupp scan 0.12-0.28s (8M rows, min/max + hashed BF, emits 1.236M; the join keeps 1.185M).
- E0002 RETIRED: IN list pushed as a scan ExpressionFilter. Correct, but the part-side MARK join costs only ~0.01s, so 0%. Bad target, not a bad implementation.

## Round g1r3 (2026-11-24)
- E0003 RETIRED: sparse perfect HJ + BF was +39..56%. The serial Finalize build of 2M-slot payload dictionaries (66MB) plus worse locality also slowed the agg. Bad idea for wide payloads. HJ is only ~19ms of wall time.
- RULE: divide EXPLAIN ANALYZE operator CPU by 8 for a wall-time estimate before predicting gains.
- Perfect HJ facts: range cap 1M (perfect_hash_join_executor.cpp:108); the duplicate check is off by one; a perfect HJ disables the BF.

## Round g1r4 (2026-11-24)
- Profile: total 137ms. HASH_GROUP_BY 0.43s CPU (~54ms wall) dominates. partsupp scan 0.16s (~20ms), HJ 0.19s incl. scan, part scan 0.05s, everything else ~0.
- Distinct finalize flow (physical_hash_aggregate.cpp:600-771): HashAggregateDistinctFinalizeEvent creates tasks = min(sum MaxThreads, threads). Each task GetData's the distinct radix HT (which re-aggregates (G,x) per partition) and Sinks it into the main table_data local sink, then calls Combine. So 1.18M rows pass through ~3 hash passes. Nearly all (G,x) are unique (partsupp keys are unique, G depends on partkey).
- Dispatched: staging gate for heap layouts (backlog, low risk).
- Filed: group-aligned main-HT sink in distinct finalize (medium risk; add timers first).

## Backlog / next ideas
- Exact bitmap BF for dense-int keys (partsupp scan ~20ms wall; likely <=5%). Earlier runs: q09/q21 -9..-15%; a 128 bits/key cap was needed.
- Group-aligned distinct finalize (above).
- p_type VARCHAR in the distinct HT key: dictionary-ID group keys or longer-string CM compression.
- Compact ~300-row join output chunks before the agg sink (idea).
