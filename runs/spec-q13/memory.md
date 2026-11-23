## Memory (planner notes)

### Workload: q13 only (customer LEFT JOIN orders with NOT LIKE '%a%b%' filter, count per key, then count per count)
Current best (after E0004): about 458-476ms hot (1.551x). Operator CPU: orders TABLE_SCAN with LIKE 2.37s; PERFECT_HASH_GROUP_BY 0.46s; HASH_JOIN (perfect, RIGHT) 0.22s; decompress_bigint projection above the join 0.17s; outer HASH_GROUP_BY 0.07s. Fully parallel (CPU/8 is about wall).
Baseline was about 784ms.

### Scan cost breakdown (round 5 microbenchmarks, scan operator CPU at 8 threads on orders)
- o_custkey+o_orderkey only: 0.41s
- + o_comment decode (length>45 filter): 1.92s, so decode is about 1.5s, about 100ns/string, far above FSST decoder speed.
- NOT contains: 2.23-2.44s; q13 NOT LIKE: 2.36s. So the matcher costs about 0.3-0.5s.
- threads=1: 2.09s, so the cost is per-row compute, not bandwidth.
- SET enable_fsst_vectors=true is slower (2.93s). The default is off, so the scan decodes eagerly via StringScanPartial<false>.
- `length(o_comment) > 3` is pruned by stats, so use a selective threshold for tests.

### Round 6 hypothesis for the decode overhead (dispatched)
- FSSTPrimitives::DecompressValue (common/fsst.hpp:36) does arena AllocateShrinkableBuffer(len*8) for each string on the result vector's VectorStringBuffer.
- The vector auxiliary is fresh every chunk (StringVector::GetStringBuffer, vector.cpp:2218). Its ArenaAllocator starts at 2KB and doubles (arena_allocator.cpp:63), so about 7 mallocs of up to 256KB per vector, with cold or mmapped pages. No jemalloc is loaded (glibc malloc).
- ArenaAllocator::Reset keeps the head block, so reuse gives zero mallocs after warm-up.
- The fix caches a VectorStringBuffer in FSSTScanState and reuses it when use_count()==1.
- If it fails with no gain, the allocation theory is wrong and the overhead is elsewhere (bitunpack or delta decode per call? FetchStringPointer?).

### Facts learned
- CanUsePerfectHashAggregate: plan_aggregate.cpp:127. perfect_ht_threshold defaults to 12; settings defaults are off limits.
- PerfectAggregateHashTable allocates outside the buffer manager, so it needs a memory guard.
- Perfect hash join: perfect_hash_join_executor.cpp CanDoPerfectHashJoin now handles INNER+RIGHT, up to 2^22 dense.
- Filter scan path: RowGroup::Scan -> StandardColumnData::Filter. FSST has no compression->filter, so the path is Scan + ToUnifiedFormat + ColumnSegment::FilterSelection (EXPRESSION_FILTER at column_segment.cpp:563).
- FSST scan: FSSTStorage::StringScanPartial (fsst.cpp:645), FSSTScanState::DecompressString (fsst.cpp:556), all_values_inlined fast path when max len <= 12.
- LikeMatcher::Match (like.cpp:231) -> FindStrInStr (contains.cpp:76).
- dbe-tool sql accepts "SET ...; EXPLAIN ANALYZE ...". One dbe-tool call per Bash call.
- Wall noise on q13 is ±15%; acceptance needs at least -5%.

### Experiments
- E0001 dense-range PHA: RETIRED -3.6% (it needed a parallel combine/source).
- E0002 conditional found-match store: no gain. Don't retry.
- E0003 parallel combine + source for large PHA: ACCEPTED -20.1%.
- E0004 perfect HJ for RIGHT joins: ACCEPTED -19.3%.
- E0005 SWAR/SSE2 first+last-byte strstr: RETIRED at -4.8% official, although the implementer's bench said -11.8%. It is a good idea that missed narrowly. Worth re-landing combined with an AVX2 path or another scan win.
- Round 6 dispatched: FSST string heap reuse (see above).

### Directions
- Scan decode (about 1.5s) is the biggest item; see the round 6 hypothesis.
- Re-land E0005 (maybe plus AVX2) once the decode overhead is cut; the matcher's share then grows.
- Backlog: remove the cancelling compress/decompress projection pair (0.17s, -3 to -5%, near noise).
- PHA: per-thread init of 2M slots plus a scan of every slot (0.46s); lazy local tables or an occupancy bitmap could help a little.
