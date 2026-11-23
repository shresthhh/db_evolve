## Memory (gen1 round6)

### Workload
- Only template q16: partsupp JOIN part (filtered: brand<>, type NOT LIKE prefix, size IN 8 consts) + NOT IN (supplier LIKE) mark join, GROUP BY brand,type,size count(DISTINCT suppkey). ~27.8k groups, ~1.18M rows into the agg. Bench ~154 ms after E0005. The machine is very noisy (profile total ranges 0.19-0.29s) and the first run in a dbe-tool sql call is cold (always discard it).
- R6 profile CPU: HASH_GROUP_BY 0.45-0.73s, partsupp scan (with BF) 0.27s, join 0.27s, part scan 0.10s (1.86M rows), filter 0.03s.

### Accepted
- E0005: distinct radix table partitioned on hash(G) only (partition_key_count, gated on estimated_cardinality >= 4096): q16 -12%. Current best is 1.187x.

### R6 dispatched: inline integral IN-list evaluation (skip the MARK join for lists of 6-64 int constants)
- Facts: TryPushdownInFilter (filter_combiner.cpp:515) pushes only OptionalFilter(InFilter) unless the list is a dense range. ColumnSegment::FilterSelection (column_segment.cpp:405) has NO IN_FILTER case, and no extension (parquet) handles IN_FILTER, so a mandatory scan-level InFilter is unsafe. CONJUNCTION_OR filter evaluation is O(n^2) per vector (dedup loop), so it is bad too. That is why the plan keeps the IN as an expression and speeds up execute_operator.cpp:23.
- If it fails: check whether the gain was hidden by the build pipeline overlapping. Then it is a bad idea for q16, not a bad implementation.

### R5 measurements (temp table t = q16 join output, warm)
- count(DISTINCT x) GROUP BY G 102-145 ms; SELECT DISTINCT G,x 65 ms; GROUP BY G count(*) 30 ms.
- Chunk compaction is only ~10% of agg CPU and noisy (CACHE_THRESHOLD = 64, physical_operator.hpp:270): a weak lever.

### KEY FINDING R4: the non-inlined VARCHAR key (p_type, 25 chars) costs the aggregate
- DISTINCT on the 4 keys: 46-59 ms (p_type) vs 35 (hash) vs 29 (fixed-width). CompressedMaterialization packs strings up to 16 bytes only. TryAddDictionaryGroups (aggregate_hashtable.cpp:359) handles only a single dictionary group column.

### Exhausted / no-gain (do not repeat)
- E0001 early HT grow ~3%; E0002/E0004 unpartitioned staging for AllConstant layouts ~-1%; E0003 early SkipLookups ≤3%. Sink-side probe/staging tweaks are exhausted.
- Manual 2-level rewrite of count(DISTINCT): same speed.
- Lesson: CPU saved in the distinct sink doesn't show in wall time (it overlaps the join pipeline). Target serial phases: distinct finalize, main re-sink, main finalize, and the build-side pipeline of the join.

### Codebase facts
- Radix HT (radix_partitioned_hashtable.cpp): with more than 2 threads the sink capacity is 32768. Abandon() when full. DecideAdaptation runs at 1M rows per thread. MAXIMUM_FINAL_SINK_RADIX_BITS = 8. CreateHT is at line 71.
- Hash bits: salt = top 16. Radix bits = [48-r, 48), r ≤ 12. Slot = low bits.
- Distinct tables: DistinctAggregateData ctor (distinct_aggregate_data.cpp:75). grouping_set lists the group indices first.
- AggregateDistinctGrouping (physical_hash_aggregate.cpp:666-772): GetData from the distinct radix table, Sink into the main table, then Combine. FinishEvent inserts HashAggregateFinalizeEvent. CanSkipRegularSink is at line 98. partition_key_count is set at line ~201.
- Per-partition finalize: RadixHTLocalSourceState::Finalize (~853).
- InClauseRewriter::VisitReplace (in_clause_rewriter.cpp:35): 1 const → '=', <6 → OR chain, otherwise MARK join. The IN executor loop is in execute_operator.cpp:23 (Equals+Or per constant).
- Perfect HJ: CanDoPerfectHashJoin (perfect_hash_join_executor.cpp:66), MAX_BUILD_SIZE 1M. A perfect HT disables the BF (physical_hash_join.cpp:761), and the BF cuts the partsupp scan from 8M rows to 1.24M, so a perfect HJ is likely a loss for q16.
- dbe-tool: multiple statements per sql call work; grep piping is allowed. Use max(col), not count(*), to keep the distinct agg.

### Backlog (ranked)
1. Main-HT bypass for all-distinct aggs with aligned partitions (filed; high risk, 5-10%).
2. Dictionary-ID substitution for long-string group keys (large).
3. Chunk compaction (weak). Perfect HJ (doubtful because of the BF).
