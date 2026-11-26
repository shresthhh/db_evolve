# spec-q01: what changed from v0 to v1

3 accepted changes. Auditor labels: 3 general.

Gain at acceptance is the visible-geomean speedup over the previous best when the change was accepted; alone is the change applied by itself to v0 (from `dbe ablate`, if it was run).

| Id | Change | Label | Files | +/- lines | Conditions added | Gain at acceptance | Alone |
|---|---|---|---|---|---|---|---|
| E0003 | Perfect HT: replicate group states (K=4) to break same-state dependenc | general | 3 | +73 / -19 | 6 | 1.140× | – |
| E0004 | avg on int32/int64/decimal(int64): int64 sum state when stats prove no | general | 1 | +79 / -4 | 7 | 1.053× | – |
| E0005 | Perfect HT: fused single-pass update for int64 sum/avg/count_star aggr | general | 2 | +181 / -0 | 20 | 1.063× | – |

## E0003: Perfect HT: replicate group states (K=4) to break same-state dependency chains

Commit `4d9e1c7f1f87`. Files: `extension/core_functions/aggregate/algebraic/avg.cpp`, `src/execution/perfect_aggregate_hashtable.cpp`, `src/include/duckdb/execution/perfect_aggregate_hashtable.hpp`.
Faster when accepted: q01 1.14×.

**Label: general.** This is a well-known technique (replicated or privatized accumulators that break same-address read-modify-write dependencies in low-cardinality aggregation). Its gate is semantic (all aggregates exact and order-independent, no DISTINCT) plus a cache-sized memory cap. It does not depend on TPCH's columns, types or query shapes, and any low-cardinality integer-key GROUP BY with count/sum/min/max/integer-avg benefits. Caveats:
- K=4 is an untuned guess.
- The 1 MiB cap limits bytes, not group count. Near the 4096-slot limit it can replicate where few rows per group per chunk give little benefit, at the cost of more init, combine and fold work. Gating on rows per group would be more principled.
- The global avg order-dependence change has effects beyond this path, though they are sound.
None of this makes it a benchmark branch. At most it would invite upstream tuning of the constants.

- **Mechanism.** In the perfect-hash (direct-indexed) group-by table, each group now has K=4 copies of its aggregate state, laid out as 4 consecutive arrays of total_groups tuples. Row i of a chunk updates copy (i & 3) of its group. Consecutive rows of the same group therefore hit 4 independent accumulators instead of forming one serial read-modify-write chain through a single state. This is the standard accumulator privatization/replication trick for low-cardinality aggregation. When threads combine, all source copies are merged into the target's copy 0 (CombineReplicas(other, 0)). Before the first Scan, the table merges its own copies 1..3 into copy 0, once. Separately, avg over integer, hugeint, decimal and interval inputs is now marked NOT_ORDER_DEPENDENT for the whole engine, so it qualifies for replication. That flag is also read by the ordered-aggregate optimizer and by window segment trees.
- **Trigger.** 1. The planner must already pick a perfect-hash aggregate (unchanged code). From src/execution/physical_plan/plan_aggregate.cpp:
   - No grouping sets: "op.grouping_sets.size() > 1 || !op.grouping_functions.empty()" returns false (:128).
   - All group keys are integer-typed (:136-148).
   - Each key has min/max statistics, and its range is below 2^31 (:220).
   - The summed bits stay within the setting: "perfect_hash_bits > Settings::Get<PerfectHtThresholdSetting>(context)" (:230). The default is 12 bits (src/common/settings.json:916, "default_value": "12"), so at most 4096 slots.
   - No DISTINCT, and every aggregate has a combine function (:237).
2. New gate in the PerfectAggregateHashTable constructor (src/execution/perfect_aggregate_hashtable.cpp):
   - At least one aggregate: "bool can_replicate = !layout_ptr->GetAggregates().empty();".
   - Every aggregate is NOT_ORDER_DEPENDENT and none is distinct: "if (aggr.function.GetOrderDependent() != AggregateOrderDependent::NOT_ORDER_DEPENDENT || aggr.IsDistinct()) { can_replicate = false; }" (:39-42).
   - Size cap: "if (can_replicate && total_groups * tuple_size * MAX_REPLICA_COUNT <= MAX_REPLICATED_HT_SIZE) { replica_count = MAX_REPLICA_COUNT; }" (:44-46).
   - NOT_ORDER_DEPENDENT aggregates: count/count_star (src/function/aggregate/distributive/count.cpp:235,243), min/max (minmax.cpp:381), integer and decimal sum (extension/core_functions/aggregate/distributive/sum.cpp:166-211), bool_and/bool_or, quantile/mad, and now integer/decimal/interval avg (avg.cpp:272).
   - Double sum/avg and list/string_agg/first are order-dependent, so any query using them stays on K=1.
- **Constants.** - MAX_REPLICA_COUNT = 4 (perfect_aggregate_hashtable.cpp:10).
  - This is a guess, not a value derived from hardware or the workload. The author says "K=8 was not tried".
  - It must be a power of two because the code uses the mask "i & replica_mask".
  - A typical out-of-order core can overlap a handful of independent load-add-store chains, so 4 is a reasonable default.
  - Nothing about it is specific to TPCH; Q1 has only about 4 groups, so even K=2 would expose the effect.
- MAX_REPLICATED_HT_SIZE = 1 MiB (:12, "1ULL << 20ULL").
  - A cache-capacity style cap (roughly an L2 size), so the 4 copies do not spill out of cache.
  - Just above the cap, replica_count = 1 and the table behaves exactly as before.
  - At the default 4096-slot maximum, the cap allows tuple_size <= 64 B. Wider states or more groups fall back to K=1.
  - The cap limits bytes, not group count. Example: 2000 groups x 100 B is allowed, and there replication brings little benefit (few rows per group per chunk, so short chains). It does cost 4x initialization, 4x Destroy, and roughly 4x combine/fold work per thread.
  - Neither constant appears to be fitted to TPCH table sizes.
- **Outside this benchmark.** Any GROUP BY that DuckDB executes with the perfect hash table and whose aggregates are all exact and order-independent: count, min, max, sum/avg over integer or decimal inputs, bool_and/or. This typically means low-cardinality integer keys (or keys that compressed materialization turns into small integers), with many rows per group.

Example 1:
  SELECT status_code, count(*), sum(bytes), avg(latency_us), max(ts)
  FROM web_logs
  GROUP BY status_code;
(status_code is SMALLINT or INTEGER with min/max stats; bytes and latency_us are integers.)

Example 2:
  SELECT store_id, day_of_week, sum(qty), avg(price_cents), min(price_cents)
  FROM sales
  GROUP BY store_id, day_of_week;
(store_id ranges 1..200 and day_of_week 0..6, so 8+3 bits.)

Not covered:
  - The same queries using DOUBLE sum/avg.
  - Queries with string_agg/list/first.
  - High-cardinality or string keys, which use the radix hash table.
- **Otherwise.** If any aggregate is order-dependent or DISTINCT, or the 4x state array exceeds 1 MiB, then replica_count = 1. Effects:
- The address computation reduces to the old "group * tuple_size", because the mask is 0.
- CombineReplicas(other, 0) loops over r in [0,1), which is the old Combine.
- Scan skips the fold: "if (replica_count > 1)".
- Destroy covers total_groups*1 tuples.
So the behaviour is the old path, refactored but functionally unchanged. Queries that don't use the perfect hash table are unaffected by the hash-table change.

The avg change is not gated. Integer/decimal/interval avg is now NOT_ORDER_DEPENDENT everywhere. For example, the ordered-aggregate optimizer (src/optimizer/rule/ordered_aggregate_optimizer.cpp:27) can now drop ORDER BY inside avg(...), and window segment trees (src/function/window/window_segment_tree.cpp:157) treat it as order-insensitive. This is semantically sound because the states are exact integer sums and counts.
- **Code.** src/execution/perfect_aggregate_hashtable.cpp:10 "static constexpr idx_t MAX_REPLICA_COUNT = 4;"; src/execution/perfect_aggregate_hashtable.cpp:12 "static constexpr idx_t MAX_REPLICATED_HT_SIZE = 1ULL << 20ULL;"; src/execution/perfect_aggregate_hashtable.cpp:40 "if (aggr.function.GetOrderDependent() != AggregateOrderDependent::NOT_ORDER_DEPENDENT || aggr.IsDistinct())"; src/execution/perfect_aggregate_hashtable.cpp:44 "if (can_replicate && total_groups * tuple_size * MAX_REPLICA_COUNT <= MAX_REPLICATED_HT_SIZE)"; src/execution/perfect_aggregate_hashtable.cpp:163 "address_data[i] = uintptr_t(data) + (group + (i & replica_mask) * total_groups) * tuple_size;"; src/execution/perfect_aggregate_hashtable.cpp:190 "CombineReplicas(other, 0);"; src/execution/perfect_aggregate_hashtable.cpp:291-296 "if (!replicas_folded) { ... if (replica_count > 1) { CombineReplicas(*this, 1);"; extension/core_functions/aggregate/algebraic/avg.cpp:272 "function.SetOrderDependent(AggregateOrderDependent::NOT_ORDER_DEPENDENT);"

## E0004: avg on int32/int64/decimal(int64): int64 sum state when stats prove no overflow

Commit `1e7c5bc7108f`. Files: `extension/core_functions/aggregate/algebraic/avg.cpp`.
Faster when accepted: q01 1.05×.

**Label: general.** This is a principled, correctness-preserving optimisation: proving from statistics that an accumulator cannot overflow, then using a narrower accumulator. DuckDB already applies it to sum() (sum.cpp:126-188), and this change extends it to avg. The only threshold is the int64 range itself, and nothing depends on TPC-H's schema, data or query shapes. Any avg over a bounded int32/int64/decimal(≤18) column benefits. The measured gain is modest and noisy (−1.7% to −7% on q01), but that bears on how much it helps, not on how general it is.

- **Mechanism.** avg() over INTEGER, BIGINT and DECIMAL types stored as int32 or int64 used to add values into a 128-bit hugeint state. A new statistics callback now checks the input column's min/max statistics and the operator's maximum cardinality. If it can prove that the running sum cannot overflow int64, it swaps the bound function's state callbacks for ones that use an int64 sum (RegularAdd) plus a count. The finalize step widens the int64 sum to hugeint before dividing, so the result is bit-identical to the old path. This is the overflow-proof narrowing that DuckDB's sum() already does (SumPropagateStats), now applied to avg.
- **Trigger.** All of the following must hold, checked during statistics propagation:
(1) The aggregate is avg bound to the INT32 or INT64 variant (avg.cpp:317-328, `function.SetStatisticsCallback(AvgPropagateStats)`). This includes DECIMAL with int32/int64 storage, i.e. precision ≤ 18, because `BindDecimalAvg` calls `GetAverageAggregate(decimal_type.InternalType())` (avg.cpp:354).
(2) Node statistics exist and carry a max cardinality: `if (!input.node_stats || !input.node_stats->has_max_cardinality) return nullptr;` (avg.cpp:260).
(3) The child has min/max statistics: `if (!NumericStats::HasMinMax(numeric_stats))`.
(4) The child's internal type is INT32 or INT64 (the switch at avg.cpp:271-279; anything else returns nullptr).
(5) |min|·max_cardinality and |max|·max_cardinality stay strictly inside int64: `if (max_sum_positive >= NumericLimits<int64_t>::Maximum() || max_sum_negative <= NumericLimits<int64_t>::Minimum()) return nullptr;` (avg.cpp:284).
No operator type, plan shape, column name or query shape is tested.
- **Constants.** The only constants are NumericLimits<int64_t>::Maximum()/Minimum() (avg.cpp:284). They are the representable range of the narrower state type, not tuned values. The check is copied from the existing SumPropagateStats (sum.cpp:150, `max_sum_positive >= NumericLimits<int64_t>::Maximum()`). Just outside the bound, i.e. when min/max × cardinality could reach the int64 limits (large BIGINT values or very large tables), the callback returns nullptr and the hugeint state is kept, so correctness never depends on luck. The bound is conservative: it uses worst-case max_cardinality, not actual row counts.
- **Outside this benchmark.** Any avg over an int32/int64-backed integer or decimal column where the column has min/max statistics (e.g. base-table columns, or expressions over them whose statistics propagate) and the bound proves the sum fits in int64. That covers most real-world averages of prices, amounts, counts, ages and so on, with or without GROUP BY. Examples:
`SELECT store_id, avg(quantity) FROM sales GROUP BY store_id;` (quantity INTEGER)
`SELECT avg(price_cents) FROM orders WHERE created_at > '2024-01-01';` (price_cents BIGINT with modest range)
`SELECT category, avg(amount) FROM payments GROUP BY category;` (amount DECIMAL(12,2))
- **Otherwise.** When any condition fails, AvgPropagateStats returns nullptr without changing anything. The function keeps its original AvgState<hugeint_t> / IntegerAverageOperationHugeint callbacks, so the old path runs unchanged. Name, return type, bind and bind_info (the decimal scale) are untouched in both cases. A serialised plan that is re-bound gets the hugeint variant again, which gives the same results.
- **Code.** extension/core_functions/aggregate/algebraic/avg.cpp:130 `struct IntegerAverageOperationInt64 : public BaseSumOperation<AverageSetOperation, RegularAdd>`; extension/core_functions/aggregate/algebraic/avg.cpp:137 `target = Hugeint::Cast<long double>(hugeint_t(state.value)) / divident;`; extension/core_functions/aggregate/algebraic/avg.cpp:260 `if (!input.node_stats || !input.node_stats->has_max_cardinality) {`; extension/core_functions/aggregate/algebraic/avg.cpp:271-279 `case PhysicalType::INT32: ... case PhysicalType::INT64: ... default: return nullptr;`; extension/core_functions/aggregate/algebraic/avg.cpp:284 `if (max_sum_positive >= NumericLimits<int64_t>::Maximum() ||`; extension/core_functions/aggregate/algebraic/avg.cpp:307 `function.SetStatisticsCallback(nullptr);`; extension/core_functions/aggregate/algebraic/avg.cpp:321,328 `function.SetStatisticsCallback(AvgPropagateStats);`; extension/core_functions/aggregate/algebraic/avg.cpp:354 `function = GetAverageAggregate(decimal_type.InternalType());`

## E0005: Perfect HT: fused single-pass update for int64 sum/avg/count_star aggregates

Commit `212b144ff9a3`. Files: `src/execution/perfect_aggregate_hashtable.cpp`, `src/include/duckdb/execution/perfect_aggregate_hashtable.hpp`.
Faster when accepted: q01 1.06×.

**Label: general.** The change specialises the update loop by type, replacing generic function-pointer scatter with direct typed loops. This is a standard way to cut interpretation overhead, and it has no workload-sized thresholds. The gates are exact layout and type checks plus an all-or-nothing rule. Any perfect-hash GROUP BY with only count(*) and int64-state sum/avg benefits, whatever the schema or data. Two caveats:
- The supported set {count_star, sum, avg} is exactly what Q1 uses, and adding any other aggregate (min, max, count(x), double sum) turns the path off. Coverage is therefore narrower than "general" might suggest, but the condition is still a natural one.
- Identifying aggregates by name string and copying the state structs from core_functions is fragile. An upstream maintainer would likely ask for an aggregate-function callback instead.

- **Mechanism.** In the perfect-hash GROUP BY operator, a check now runs when the hash table is built. If every aggregate is count_star, an int64-state sum, or an int64-state avg, then each chunk updates the states in one typed loop per aggregate. Each loop adds or increments directly into the state at its row offset. This replaces the generic path, which made a function-pointer UpdateStates call per aggregate and then ran an AddInPlace pass over the address vector to reach the next state. The state layouts and the Combine, Scan and Finalize steps are unchanged. The change removes interpretation overhead by specialising the update for a few common aggregate kinds; the algorithm is the same.
- **Trigger.** 1. The planner has already chosen the perfect aggregate hash table, which needs small integer group keys with a range proven by statistics. That rule existed before this change.
2. AddChunk takes the new path only if `use_fused_update` is set (src/execution/perfect_aggregate_hashtable.cpp:326 `if (use_fused_update) { FusedUpdate(payload, groups.size()); return; }`).
3. The flag is set in InitializeFusedUpdate only if ALL aggregates qualify. One unsupported aggregate disables the path for the whole table:
   - the list is not empty (`if (aggregates.empty()) return;`);
   - no aggregate has a FILTER, DISTINCT or a state destructor (`if (aggr.filter || aggr.IsDistinct() || aggr.function.HasStateDestructorCallback()) return;`);
   - an aggregate with no child must be `name == "count_star"` with `state_size == sizeof(int64_t)`;
   - any other aggregate must have `child_count == 1`, an input whose physical type is `INT32 || INT64`, and either `name == "sum_no_overflow" && state_size == sizeof(FusedSumState)` (16) or `name == "avg" && state_size == sizeof(FusedAvgState)` (16).
4. sum_no_overflow only exists when SumPropagateStats proves from min/max statistics and maximum cardinality that the total fits in int64 (extension/core_functions/aggregate/distributive/sum.cpp:150-156 `if (max_sum_positive >= NumericLimits<int64_t>::Maximum() ... return nullptr; ... expr.function = GetSumAggregateNoOverflow(internal_type);`).
5. A 16-byte avg state over INT32/INT64 only exists after the same stats-based switch from E0004 (extension/core_functions/aggregate/algebraic/avg.cpp:284-298 `AvgState<int64_t>`). Decimals stored as int32 or int64 qualify too, because both sum and avg on them bind through these same functions.
6. At run time, HAS_NULLS selects a separate loop version (`if (!format.validity.AllValid()) has_nulls = true;`).
- **Constants.** There are no tuned thresholds.
- The state sizes 8 and 16 are layout guards, not tuning values. They must match SumState<int64_t> and AvgState<int64_t> in core_functions (`static_assert(sizeof(FusedSumState) == 16 && offsetof(FusedSumState, value) == 8 ...)`). If the size differs, for example AvgState<hugeint_t> at 24 bytes, the whole table uses the old path.
- The kind values 0 to 4 are internal enum encodings, guarded by a static_assert in FusedUpdate.
- The only data-dependent bound is the existing int64 no-overflow proof from statistics: max(|min|,|max|) times max_cardinality must stay below the int64 range. It comes from the engine's statistics, not from this change. If a column's statistics cannot rule out overflow, sum and avg keep their hugeint states, the name or size check fails, and the old path is used.
- Matching aggregates by their name strings ("count_star", "sum_no_overflow", "avg") is fragile engineering, but it is not tied to the workload.
- **Outside this benchmark.** Any query the perfect hash aggregate handles (low-cardinality integer, enum or compressed group keys with known ranges) whose aggregates are only count(*), and sum/avg over INTEGER, BIGINT or int-backed DECIMAL columns with statistics that prove no int64 overflow. Examples outside TPCH:
- `SELECT status_code, count(*), sum(bytes_sent), avg(latency_ms) FROM web_logs GROUP BY status_code;` (status_code is a SMALLINT/INTEGER with a small range; bytes_sent and latency_ms are INTEGER)
- `SELECT store_id, day_of_week, sum(amount_cents), avg(quantity), count(*) FROM sales GROUP BY store_id, day_of_week;`

These are excluded: count(x), min/max, sum/avg over DOUBLE, SMALLINT or hugeint states, FILTER clauses and DISTINCT. If any one of them appears in the SELECT list, the whole query falls back, so the covered mix is fairly narrow. It happens to be exactly TPCH Q1's aggregate mix, but it is also the most common reporting pattern.
- **Otherwise.** If the flag is false, AddChunk runs the original loop unchanged: UpdateStates or UpdateFilteredStates for each aggregate, followed by `VectorOperations::AddInPlace(addresses, ... payload_size ...)` (src/execution/perfect_aggregate_hashtable.cpp:330-345). Group-location computation, the E0003 replicas, Combine, Scan and Finalize are shared by both paths and unchanged.
- **Code.** src/execution/perfect_aggregate_hashtable.cpp:326 `if (use_fused_update) { FusedUpdate(payload, groups.size()); return; }`; src/execution/perfect_aggregate_hashtable.cpp:96 `if (aggr.filter || aggr.IsDistinct() || aggr.function.HasStateDestructorCallback()) { return; }`; src/execution/perfect_aggregate_hashtable.cpp:104 `if (name != "count_star" || state_size != sizeof(int64_t))`; src/execution/perfect_aggregate_hashtable.cpp:112 `if (input_type != PhysicalType::INT32 && input_type != PhysicalType::INT64) { return; }`; src/execution/perfect_aggregate_hashtable.cpp:117 `if (name == "sum_no_overflow" && state_size == sizeof(FusedSumState))`; src/execution/perfect_aggregate_hashtable.cpp:119 `} else if (name == "avg" && state_size == sizeof(FusedAvgState))`; src/execution/perfect_aggregate_hashtable.cpp:82 `static_assert(sizeof(FusedSumState) == 16 && offsetof(FusedSumState, value) == 8`; src/execution/perfect_aggregate_hashtable.cpp:330-345 original loop `RowOperations::UpdateStates(...)` / `VectorOperations::AddInPlace(addresses, ...)`
