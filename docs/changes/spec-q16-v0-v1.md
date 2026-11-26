# spec-q16: what changed from v0 to v1

1 accepted changes. Auditor labels: 1 heuristic.

Gain at acceptance is the visible-geomean speedup over the previous best when the change was accepted; alone is the change applied by itself to v0 (from `dbe ablate`, if it was run).

| Id | Change | Label | Files | +/- lines | Conditions added | Gain at acceptance | Alone |
|---|---|---|---|---|---|---|---|
| E0005 | Partition count(DISTINCT) radix table on the group-key hash only | heuristic | 5 | +75 / -7 | 8 | 1.187× | – |

## E0005: Partition count(DISTINCT) radix table on the group-key hash only

Commit `084cba35c5dc`. Files: `src/execution/aggregate_hashtable.cpp`, `src/execution/operator/aggregate/physical_hash_aggregate.cpp`, `src/execution/radix_partitioned_hashtable.cpp`, `src/include/duckdb/execution/aggregate_hashtable.hpp`, `src/include/duckdb/execution/radix_partitioned_hashtable.hpp`.
Faster when accepted: q16 1.19×.
Numeric constants in added code: `4096`.

**Label: heuristic.** The technique is principled and broadly applicable. Co-partitioning the distinct-dedup table on the group key is a standard two-phase DISTINCT aggregation technique, and nothing in it refers to TPC-H's schema, types or query shapes. Any GROUP BY with a DISTINCT aggregate and many groups qualifies. Enabling it, though, depends on a single arbitrary constant (4096) applied to the optimizer's cardinality estimate, not on observed data such as the HLL the author mentions. It also has a real regression mode when the estimate is wrong: few real groups means skewed partitions, and the compressed-vector fast path is disabled for distinct tables. The constant is not fitted tightly to q16 (estimate about 64k), so this is not a special case. It would likely be accepted upstream, perhaps with a runtime-statistics gate instead.

- **Mechanism.** For a grouped aggregate with DISTINCT aggregates, DuckDB first deduplicates (group cols + distinct args) in a separate radix-partitioned hash table, then re-aggregates those tuples into the main table per partition. Before this change, the partition (radix) bits came from the hash of all columns, so one group's rows were spread over every partition and each finalize task saw nearly all groups. Now the radix bits (bits 36–47) of the stored hash are replaced by the same bits from a hash of only the GROUP BY columns. Each distinct partition then holds complete groups, and each finalize task re-aggregates a disjoint, much smaller set of groups. The salt and pointer-table bits still come from the full hash, so probing inside a table is unchanged. This is the standard way to co-partition a two-phase DISTINCT aggregation on the group key.
- **Trigger.** Set in the PhysicalHashAggregate constructor. All of these must hold:
(a) `estimated_cardinality >= DISTINCT_PARTITION_ON_GROUPS_MIN_CARDINALITY` (4096). This is the optimizer's estimate for the aggregate operator (src/execution/operator/aggregate/physical_hash_aggregate.cpp:192-193).
(b) The grouping has distinct data and a non-empty grouping set: `if (!distinct_data || grouping_sets[i].empty()) continue;` (physical_hash_aggregate.cpp:196).
(c) Every non-null distinct radix table then gets `partition_key_count = grouping_sets[i].size()` (physical_hash_aggregate.cpp:201). This passes to every table built by CreateHT: `if (partition_key_count != 0) ht->SetPartitionKeyCount(...)` (src/execution/radix_partitioned_hashtable.cpp:75-76).
(d) It only takes effect when the key is a strict prefix of the table's group columns: `partition_key_count = count_p < layout_ptr->ColumnCount() - 1 ? count_p : 0` (src/execution/aggregate_hashtable.cpp:284). The layout's last column is the hash, so ColumnCount()-1 is the number of group columns.
(e) The prefix property depends on the distinct table's grouping set being an ordered set, with group indices inserted first and distinct-arg indices offset by `group_by_size`: `grouping_set.insert(set_idx + group_by_size)` (src/execution/operator/aggregate/distinct_aggregate_data.cpp:101).
When active, the compressed/dictionary fast path is skipped: `if (partition_key_count == 0) { auto result = TryAddCompressedGroups(...` (aggregate_hashtable.cpp:557-558).
There is no test on data type, table, column name or query shape beyond "GROUP BY plus a DISTINCT aggregate".
- **Constants.** - 4096 (DISTINCT_PARTITION_ON_GROUPS_MIN_CARDINALITY, physical_hash_aggregate.cpp:192). A round number (2 × STANDARD_VECTOR_SIZE). The code comment says it guards against partition skew when there are few groups ("With few groups, this would skew partitions"). It is not fitted to q16: its estimate is about 64k, 16× above the gate, so the gate is not tight around the benchmark. It is still an untuned guess on an optimizer estimate, and the author calls it a heuristic.
  - Just below 4096: the old path, unchanged.
  - Just above, with an accurate estimate: there are enough groups to spread over at most 2^12 partitions.
  - Failure mode: if the estimate is high but the real number of groups is small, every distinct tuple of a group lands in one partition. Distinct-finalize parallelism and partition balance then degrade, and the dictionary fast path is lost too.
- RADIX_MASK = RadixPartitioning::Mask(MAX_RADIX_BITS) (aggregate_hashtable.cpp:307). This is the engine's existing radix-bit range, not a new constant.
- **Outside this benchmark.** Any hash GROUP BY (including GROUPING SETS / ROLLUP with non-empty sets) that has one or more DISTINCT aggregates and an estimated output of at least 4096 groups. The gain is largest when there are many groups and many distinct values per group. Examples outside TPC-H:
1. `SELECT user_id, count(DISTINCT session_id) FROM events GROUP BY user_id;` (millions of users)
2. `SELECT country, city, count(DISTINCT product_id), sum(DISTINCT price) FROM sales GROUP BY ROLLUP(country, city);`
The rollup's empty grouping set is excluded by the `grouping_sets[i].empty()` check.
- **Otherwise.** If the estimate is below 4096, there are no DISTINCT aggregates, the grouping set is empty, or the key is not a strict prefix, then partition_key_count stays 0. HashGroups then just calls `groups.Hash(hashes)` and returns (aggregate_hashtable.cpp:288-290), and TryAddCompressedGroups runs as before. This is exactly the old path. Other users of GroupedAggregateHashTable (main table, window, recursive CTE) never set the option.
- **Code.** src/execution/operator/aggregate/physical_hash_aggregate.cpp:192 `static constexpr idx_t DISTINCT_PARTITION_ON_GROUPS_MIN_CARDINALITY = 4096;`; src/execution/operator/aggregate/physical_hash_aggregate.cpp:193 `if (estimated_cardinality >= DISTINCT_PARTITION_ON_GROUPS_MIN_CARDINALITY)`; src/execution/operator/aggregate/physical_hash_aggregate.cpp:196 `if (!distinct_data || grouping_sets[i].empty())`; src/execution/operator/aggregate/physical_hash_aggregate.cpp:201 `radix_table->partition_key_count = grouping_sets[i].size();`; src/execution/radix_partitioned_hashtable.cpp:75-76 `if (partition_key_count != 0) { ht->SetPartitionKeyCount(partition_key_count);`; src/execution/aggregate_hashtable.cpp:284 `partition_key_count = count_p < layout_ptr->ColumnCount() - 1 ? count_p : 0;`; src/execution/aggregate_hashtable.cpp:288-290 `groups.Hash(hashes); if (partition_key_count == 0) { return; }`; src/execution/aggregate_hashtable.cpp:307-311 `RADIX_MASK = RadixPartitioning::Mask(RadixPartitioning::MAX_RADIX_BITS)` ... `(hash_data[i] & ~RADIX_MASK) | (key_hash_data[i] & RADIX_MASK)`
