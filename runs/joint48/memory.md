## Memory (gen3)

## State
- gen1: accepted JoinDependent rule order (q19), contains() selectivity (q09), perfect HJ RIGHT (q13), BF first key multi-key HJ (q09), key-set range filter through compress projs (q18), exact bitmap BF, semi-join estimate, OR-of-ranges mask, FSST simple decode + substring prefilter (q13), DELIM_GET-build BF (q22). Best 1.281x.
- gen2: E0021 deliminate SEMI + exact BF through CM offset (this also removed the RIGHT_SEMI/RIGHT_ANTI bail-out in join filter pushdown: ALREADY LANDED, do not re-file); E0022 exact-BF small-range floor; E0023 ANTI deliminator; E0024 parallel perfect-HJ build; E0027 BitPacking per-value select + exact BF 2^27; E0029 sparse perfect-HJ exact BF; E0031 block cache 256MB + large perfect HA v3. Best 1.800x.
- gen3 r1-r4: E0033 clustered-key agg, E0034 staged perfect HA sink, E0035 parallel HJ finalize 64K-1M, E0036 streaming run agg: all ACCEPTED. Best 2.120x.
- gen3 r5-r7: E0037 partition-local HJ slots RETIRED; E0039 THP v2 ACCEPTED.
- gen3 r8: E0040 coalesce sparse scan chunks ACCEPTED. r9: E0041 caching threshold RETIRED.
- gen3 r10: E0042 FSST DFA LIKE filter v2 ACCEPTED (q13 -24%). Best 2.468x.
- gen3 r11: E0043 DFA ILP RETIRED. r12: E0044 DFA SIMD state-0 skip RETIRED.
- gen3 r13: E0045 ACCEPTED (branch-free run detection): q18 -15..-32%. Best 2.500x.
- r14: E0046 template-copy state init RETIRED (q18 ~-2%, noise, abandoned).
- r15: E0047 q18 bundle (batched RegisterRunInterval + template init) RETIRED: q09 +12.5%, q14 +7% (probably noise or memory state), geomean +0.9%. Template init also costs the perfect HA (q13 +3%?).
- r16: dispatched the leaner staged perfect HA sink (no local table + fused typed scatter into stage buffers). Expected q13 -2..-5%, likely inside noise.

## Where the remaining time is (r16 profile, ms): q09 305, q13 226, q18 172, q16 164, q07 134, q03 130, q05 124, q08 110, q04 100, q22 95, q17 88, q14 86, q19 84, q02 54. Geomean 121.3.
- q13 profile CPU: orders scan+DFA 1.12s (exhausted), RIGHT perfect HJ 0.25s, decompress proj 0.22s (removing the decompress/compress pair was tried: perfect HA got slower on dictionary input, dead), perfect HA 0.43s, c_count agg 0.05s.
- q09: the nation join is nested inside the supplier build side, not at the top of the tree, so eager pre-agg needs a non-local rewrite (high risk).

## q18 facts (after E0045)
- HAVING micro 136-143ms. Per-group CPU: alloc/address fill 93, InitializeStates 62-72, UpdateStates 112, CDC append 70, FinalizeStates 90 ms.
- RegisterRunInterval (radix_partitioned_hashtable.cpp:813): global mutex + std::map per chunk. Do NOT coalesce adjacent intervals (false overlap). Batching was tried in E0047 and did not clear noise.
- Timer method: write to the worktree's tmp/ (gitignored). stderr breaks dbe-tool and /tmp is denied.

## q16 facts
- HASH_GROUP_BY count(DISTINCT) is 0.31s CPU; the partsupp⋈part HJ is 0.13s. Many q16 ideas are already dead.

## q09 facts
- Profile CPU: lineitem scan 3.66s, HJ o_orderkey 1.07s (latency-bound), HJ partkey/suppkey 0.44s, HASH_GROUP_BY 0.16-0.20s, CM string compress 0.08s.
- Group key n_name vs n_nationkey: ~30ms (~10%).

## Measurement lessons
- The first run in a dbe-tool sql session is cold (2-4x); use runs 2+.
- EXPLAIN ANALYZE CPU is inflated 3-4x vs bench; use .timer A/B.
- Bench noise: q16 ~8-10%, q18 ~5%, q13 ~14%, q09 ~8.6%, q14 ~5%, q05 ~20%, q04 ~20%, q07 ~13%, q02 ~10%.
- Acceptance needs a template faster beyond noise AND a better geomean. Bundle near misses on the SAME template.
- Late in a generation, most remaining low-risk ideas are below noise. Use the next generation's early rounds for bigger structural ideas: q09 eager pre-agg, and a q07/q09 latency-bound HJ (e.g. partitioned probe or radix join).

## Codebase facts
- Table scan: table_scan.cpp TableScanFunc. CachingPhysicalOperator: physical_operator.cpp:287-470.
- HJ BF: JoinHashTable::InsertHashes; bloom_filter.cpp TemplatedLookupExact :111. PushBloomFilter physical_hash_join.cpp:1055. CanUseBloomFilter :962.
- Substring prefilter: column_segment.cpp:662-860. CM: src/optimizer/compressed_materialization*. Deliminator: deliminator.cpp.
- FSST filter: fsst.cpp FSSTPatternDFA (:535), Filter (:1081). Fast path only for NULL-free segments.
- Clustered agg: radix_partitioned_hashtable.cpp SinkClustered :838, RegisterRunInterval :813, SinkInteriorRuns ~:700-809, MergeRunStores ~:989.
- Agg state init: RowOperations::InitializeStates row_aggregate.cpp:8.
- Perfect HA: perfect_aggregate_hashtable.cpp (lazy ctor :34, AddChunkLazy :229, AddChunkStaged :257, FlushStagePartition :320, SetStageTarget :348, UpdateLazy :362). STAGE_STRIPE_BITS=16, 4 buffers/stripe. physical_perfecthash_aggregate.cpp Sink :145 (is_large path :183).
- Perfect HJ: perfect_hash_join_executor.cpp. THP: HugePageUtil.
- Build has no -march (SSE2 only).

## Dead / exhausted
- CM join-key removal, HJ prefetch, agg run-collapse, in-place finalize, FSST heap reuse, dictionary filter, scan filter cost ordering, early HT grow, sparse perfect HJ (8M range), hashed BF through CM offset, q13 eager aggregation, fused hashed BF probe, allocator flush thresholds, private staging for perfect HA, partition-local HJ slots, q05 join order, operator caching threshold, all FSST DFA speedups, CM fold decompress/compress (q13), VARCHAR low-card key, template init (alone and bundled), batched run intervals.

## Next candidates (next generation)
1. q09 eager pre-agg below the dimension join (high risk; needs a non-local rewrite because nation sits inside the supplier build side).
2. Latency-bound large HJ probes (q09 orders, q07): radix-partitioned probe, not prefetch (prefetch is dead).
3. Skip aggregate CM compress for perfect-HA group keys (backlog; only if measurement shows the compress pass matters).
