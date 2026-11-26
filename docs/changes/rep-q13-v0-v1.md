# rep-q13: what changed from v0 to v1

2 accepted changes. Auditor labels: 2 heuristic.

Gain at acceptance is the visible-geomean speedup over the previous best when the change was accepted; alone is the change applied by itself to v0 (from `dbe ablate`, if it was run).

| Id | Change | Label | Files | +/- lines | Conditions added | Gain at acceptance | Alone |
|---|---|---|---|---|---|---|---|
| E0001 | Perfect hash join for RIGHT joins with dense keys up to 2^22 | heuristic | 4 | +61 / -6 | 10 | 1.221× | – |
| E0003 | Large perfect hash aggregate (up to 22 bits) with parallel combine and | heuristic | 5 | +185 / -28 | 12 | 1.436× | – |

## E0001: Perfect hash join for RIGHT joins with dense keys up to 2^22

Commit `a5a01aab8f9b`. Files: `src/execution/operator/join/perfect_hash_join_executor.cpp`, `src/execution/operator/join/physical_hash_join.cpp`, `src/include/duckdb/execution/operator/join/perfect_hash_join_executor.hpp`, `src/optimizer/join_filter_pushdown_optimizer.cpp`.
Faster when accepted: q13 1.22×.

**Label: heuristic.** Extending the direct-array join to RIGHT joins by tracking build-side matches is a standard, general technique. It applies to any single-integer-key RIGHT or flipped LEFT join and does not look at TPC-H's schema or queries. The range increase is the part tied to the benchmark. 2^22, with an unexplained 1/4 density guard, is a round constant that happens to admit the q13 customer key range (1.5M, just over the old 2^20 limit). Nothing such as cache or memory budget justifies it, and it ignores per-column memory cost. Upstream would likely accept the mechanism, possibly with different constants, so it is not a special case.

- **Mechanism.** The perfect (direct-indexed array) hash join used to apply only to INNER joins, and only when the build key range was at most 2^20. It now also handles RIGHT joins, where unmatched build rows must be output. Each array slot stores the pointer to its hash-table row, and probe threads set a byte in a compact per-slot match array. Before the full-outer scan, those bytes are copied into the rows' found_match flags in one pass, so the existing ScanFullOuter emits the unmatched build rows unchanged. The accepted key range also grows from 2^20 to 2^22, but only when the build side fills at least a quarter of that range. NULL build keys are now skipped when the array is filled. The optimizer now also computes build-side min/max for RIGHT joins, so the runtime check has statistics to work with.
- **Trigger.** CanDoPerfectHashJoin (src/execution/operator/join/perfect_hash_join_executor.cpp:74-75) requires: `(op.join_type != JoinType::INNER && op.join_type != JoinType::RIGHT) || op.conditions.size() != 1 || ... != COMPARE_EQUAL || !TypeIsInteger(key_type.InternalType())` → false. In words: exactly one integer equality condition, on an INNER or RIGHT join. There must be no STRUCT/LIST/ARRAY column on the build side (:79-88). Min/max must be extractable with max >= min (:93-100). Then `build_range > Hugeint::Convert(MAX_DENSE_BUILD_SIZE)` → false, with MAX_DENSE_BUILD_SIZE = `idx_t(1) << 22` (:110-113). If `build_range > MAX_BUILD_SIZE && ht.Count() < build_range / 4` → false, with MAX_BUILD_SIZE = 1048576 (:109, :116-118). If `ht.Count() > build_range + 1` → false (:121). At build time, any duplicate key makes FillSelectionVector fail, and the join falls back (:156-160). For RIGHT joins, min/max now come from the join-filter aggregates even when nothing is pushed down: `(join.join_type == JoinType::INNER || join.join_type == JoinType::RIGHT) && ...` (src/optimizer/join_filter_pushdown_optimizer.cpp:275). The match tracking runs only when `PropagatesBuildSide(join.join_type)` (perfect_hash_join_executor.cpp:173). Of the newly admitted join types, that is RIGHT.
- **Constants.** 1) MAX_BUILD_SIZE = 1048576 (2^20) is the old upstream limit and is unchanged. 2) MAX_DENSE_BUILD_SIZE = 2^22 (~4.19M) is new. It is a round power of two that is not derived from cache or memory sizes. The array costs (range+1) entries per build column, plus an 8-byte pointer and a 1-byte match flag per slot for RIGHT joins. At 2^22 that is about 64 MB for a single VARCHAR column. The motivating q13 build side (customer, c_custkey 1..1.5M at SF10) sits just above the old 2^20 limit and well inside 2^22. The raise is plausibly sized to admit that table. A build range of 2^22+1 or more falls back to the regular hash join. 3) The density guard `count >= range/4` is a principled kind of rule (bounds the space wasted per real row), but the 1/4 factor is not justified anywhere. q13's customer table has density 1.0, so the factor isn't tuned to the data. A build range between 2^20 and 2^22 with fewer than range/4 rows falls back. 4) `range + 1` fixes an off-by-one: a range of N spans N+1 values.
- **Outside this benchmark.** Any RIGHT join (including a LEFT join the optimizer flips so the preserved side becomes the build side) on a single integer equality key, with duplicate-free build keys whose span is at most 2^22, or at most 2^20 at any density. Typical cases are primary-key or dimension tables with surrogate keys joined from a fact table. Under the larger range, INNER joins with dense builds of 1M–4M keys also qualify. Examples: `SELECT u.id, count(e.event_id) FROM users u LEFT JOIN events e ON e.user_id = u.id GROUP BY u.id;` (users, 2M dense ids, as build). `SELECT p.product_id, p.name, s.qty FROM sales s RIGHT JOIN products p ON s.product_id = p.product_id;` Also an INNER join of `orders_fact` with `dim_date` on an int date_key.
- **Otherwise.** If any condition fails (wrong join type, multiple or non-equality conditions, non-integer key, nested build column, range above 2^22, sparse build above 2^20, duplicate keys), CanDoPerfectHashJoin or BuildPerfectHashTable returns false. perfect_join_executor is then reset and the regular hash-join finalize is scheduled (physical_hash_join.cpp:1016-1019). That old path is unchanged. MarkMatchedBuildRows returns immediately when build_matched is null (perfect_hash_join_executor.cpp:200-201). One behavioural change also reaches existing INNER perfect joins: NULL build keys are now skipped (:256-258), and the off-by-one fix admits slightly more builds.
- **Code.** src/execution/operator/join/perfect_hash_join_executor.cpp:74 `(op.join_type != JoinType::INNER && op.join_type != JoinType::RIGHT) || op.conditions.size() != 1`; src/execution/operator/join/perfect_hash_join_executor.cpp:109 `static constexpr idx_t MAX_BUILD_SIZE = 1048576;`; src/execution/operator/join/perfect_hash_join_executor.cpp:111 `static constexpr idx_t MAX_DENSE_BUILD_SIZE = idx_t(1) << 22;`; src/execution/operator/join/perfect_hash_join_executor.cpp:116 `if (perfect_join_statistics.build_range > MAX_BUILD_SIZE && ht.Count() < perfect_join_statistics.build_range / 4)`; src/execution/operator/join/perfect_hash_join_executor.cpp:121 `if (ht.Count() > perfect_join_statistics.build_range + 1)`; src/execution/operator/join/perfect_hash_join_executor.cpp:173 `if (PropagatesBuildSide(join.join_type)) {`; src/execution/operator/join/perfect_hash_join_executor.cpp:199 `void PerfectHashJoinExecutor::MarkMatchedBuildRows()`; src/execution/operator/join/perfect_hash_join_executor.cpp:256 `if (!vector_data.validity.RowIsValid(data_idx)) { continue; // NULL keys never match`

## E0003: Large perfect hash aggregate (up to 22 bits) with parallel combine and source

Commit `6eb234ec7c02`. Files: `src/execution/operator/aggregate/physical_perfecthash_aggregate.cpp`, `src/execution/perfect_aggregate_hashtable.cpp`, `src/execution/physical_plan/plan_aggregate.cpp`, `src/include/duckdb/execution/operator/aggregate/physical_perfecthash_aggregate.hpp`, `src/include/duckdb/execution/perfect_aggregate_hashtable.hpp`.
Faster when accepted: q13 1.44×.

**Label: heuristic.** The technique is general and standard. Direct-indexed aggregation on dense integer keys, plus a parallel combine and scan of a partitioned array, contains no TPCH schema, column, or query-shape tests, and helps any dense-integer-key GROUP BY.

The gating, however, rests on unexplained constants:
- the 22-bit cap, which conveniently sits just above q13's 21-bit o_custkey domain at SF10;
- a 1/2 density ratio, applied to an estimate the author admits is off by 5x;
- a 1/8 memory fraction.
The change also overrides the user's perfect_ht_threshold setting.

Upstream would plausibly accept the idea, with constants adjusted to thread count and cache size, and with the setting respected. So this is not a special case, but it is not a clean general change either.

- **Mechanism.** Before this change DuckDB used its perfect-hash (direct-indexed array) GROUP BY only when the integer key ranges, taken from min/max statistics, fit in perfect_ht_threshold bits (12 by default, so 4K slots). Now a second, "large" tier allows up to 22 bits (4M slots). It is used only if the estimated input has at least half as many rows as there are slots, and if one table per thread plus the global table fits in 1/8 of the memory limit. For tables of at least 2^16 slots, the merge of thread-local tables into the global table now runs in parallel: the slots are split into 64 stripes, each with its own lock. The final scan also runs in parallel, in blocks of 16K slots. Smaller tables keep the old single-lock merge and the single-threaded scan.
- **Trigger.** Planner, CanUsePerfectHashAggregate (src/execution/physical_plan/plan_aggregate.cpp). The checks that already existed still apply:
- a single grouping set and no GROUPING() functions;
- every key is an INT8..UINT64 column with min/max statistics;
- each key's range is below 2^31 ("range >= NumericLimits<int32_t>::Maximum()" → reject, :254);
- no DISTINCT aggregates, and every aggregate has a combine callback (:271).

The new checks:
- Total bits across all keys (each key's range+2, rounded up to a power of two) must satisfy "perfect_hash_bits > MaxValue<idx_t>(perfect_ht_threshold, LARGE_PERFECT_HT_MAX_BITS)" → reject (:264).
- If "perfect_hash_bits > perfect_ht_threshold" (:276), CanUseLargePerfectHashAggregate runs:
  - "perfect_hash_bits > LARGE_PERFECT_HT_MAX_BITS" → reject (:136);
  - density: "input_cardinality < total_groups / 2" → reject (:141). input_cardinality is the child plan's estimate, "plan.get().estimated_cardinality" (:338);
  - memory: "required_memory <= max_memory / 8" (:156), where required_memory = 2^bits × (1 + 8 + sum of aggregate state sizes) × (NumberOfThreads + 1) (:153).

Executor (physical_perfecthash_aggregate.cpp): the striped combine and the parallel source run when "ht->TotalGroups() >= PERFECT_HT_PARALLEL_MIN_GROUPS" (2^16, :84, :94, :215). This depends only on table size, so it also covers the existing tier whenever a user has raised perfect_ht_threshold to 16 bits or more.
- **Constants.** - LARGE_PERFECT_HT_MAX_BITS = 22 (:130). No justification is given; it is the size of one direct-indexed array per thread (4M slots).
  - TPCH q13 groups on o_custkey. At SF10 that column has 1.5M values, which needs 21 bits, so 22 covers it with one bit to spare. Related commit E0001 also used 2^22 for perfect hash joins.
  - At 23 bits the query falls back to the radix hash aggregate.
  - The cap does not adapt to thread count or L2/L3 cache size, except through the memory guard.
- Density factor 1/2 (:141): a rule of thumb, not derived anywhere.
  - It uses the estimate. The author notes q13's estimate (3M) is far below the actual 15M and still passes. A slightly worse estimate would silently turn the path off.
  - It compares input rows to slots, not distinct groups to slots. A big input with few actual groups still allocates and scans the whole table in every thread.
- Memory guard max_memory/8 × (threads+1) (:156): principled in form, but the 1/8 fraction is arbitrary. With many threads or wide aggregate states the guard fails and the radix hash aggregate is used.
- PERFECT_HT_PARALLEL_MIN_GROUPS = 2^16 (:84), 64 stripes (:86), scan block = STANDARD_VECTOR_SIZE×8 = 16K slots (:88): ordinary parallelism granularity choices with no evidence of tuning. Below 2^16 slots the old serial code runs.
- The default perfect_ht_threshold = 12 (settings.json:916) is unchanged. As the author admits, a lowered threshold no longer turns the large path off.
- **Outside this benchmark.** Any GROUP BY on one or more integer columns that have min/max statistics, a combined key domain between 2^13 and 2^22 (about 8K to 4M values), and an estimated input of at least half the domain size, with aggregates that support combine (count, sum, min, max, avg, list, ...). The typical case is grouping a fact table on a dense surrogate or foreign key with up to a few million distinct values. Two examples:

SELECT user_id, count(*), sum(amount) FROM events GROUP BY user_id;
(user_id dense in 1..2,000,000; events has 50M rows)

SELECT store_id, day_of_year, avg(price) FROM sales GROUP BY store_id, day_of_year;
(store_id in 1..5000, 13 bits; day_of_year 1..366, 9 bits; 22 bits in total)

These are common analytic shapes. Sparse keys (for example 64-bit IDs or hashes) are excluded by the range check, and large domains with little input are excluded by the density check.
- **Otherwise.** If the large-tier checks fail, CanUsePerfectHashAggregate returns false. CreatePlan then builds the normal radix-partitioned PhysicalHashAggregate, the same as before.

Tables of 12 bits or fewer take the old path: Combine under a single global lock (:183, "if (!gstate.stripe_locks)") and a single-threaded scan (MaxThreads returns 1; :265, "if (!state.parallel)"). The scan now sits behind ParallelSource()=true but behaves the same. Combine was refactored into a ranged version plus TakeAllocator, which has the same effect for the old path.

One behaviour change remains: a user-lowered perfect_ht_threshold no longer stops perfect hashing for ranges of 22 bits or fewer that pass the guards.
- **Code.** src/execution/physical_plan/plan_aggregate.cpp:130 "static constexpr idx_t LARGE_PERFECT_HT_MAX_BITS = 22;"; src/execution/physical_plan/plan_aggregate.cpp:136 "if (perfect_hash_bits > LARGE_PERFECT_HT_MAX_BITS) {"; src/execution/physical_plan/plan_aggregate.cpp:141 "if (input_cardinality < total_groups / 2) {"; src/execution/physical_plan/plan_aggregate.cpp:153 "TaskScheduler::GetScheduler(context).NumberOfThreads()"; src/execution/physical_plan/plan_aggregate.cpp:156 "return required_memory <= max_memory / 8;"; src/execution/physical_plan/plan_aggregate.cpp:254 "if (range >= NumericLimits<int32_t>::Maximum()) {"; src/execution/physical_plan/plan_aggregate.cpp:264 "if (perfect_hash_bits > MaxValue<idx_t>(perfect_ht_threshold, LARGE_PERFECT_HT_MAX_BITS)) {"; src/execution/physical_plan/plan_aggregate.cpp:271 "if (aggregate.IsDistinct() || !aggregate.function.HasStateCombineCallback()) {"
