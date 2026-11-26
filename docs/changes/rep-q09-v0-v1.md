# rep-q09: what changed from v0 to v1

3 accepted changes. Auditor labels: 2 heuristic, 1 general.

Gain at acceptance is the visible-geomean speedup over the previous best when the change was accepted; alone is the change applied by itself to v0 (from `dbe ablate`, if it was run).

| Id | Change | Label | Files | +/- lines | Conditions added | Gain at acceptance | Alone |
|---|---|---|---|---|---|---|---|
| E0001 | Length-aware selectivity for substring contains() scan filters | heuristic | 1 | +33 / -0 | 7 | 1.417× | – |
| E0002 | Bloom filter on first equality key of multi-condition hash joins | general | 2 | +18 / -5 | 2 | 1.277× | – |
| E0004 | Exact key bitmap mode for join BF on dense integer build keys | heuristic | 4 | +297 / -11 | 64 | 1.253× | – |

## E0001: Length-aware selectivity for substring contains() scan filters

Commit `be9721f0374e`. Files: `src/optimizer/join_order/relation_statistics_helper.cpp`.
Faster when accepted: q09 1.42×.
Numeric constants in added code: `0.01`, `0.75`.

**Label: heuristic.** The idea is a recognised technique: length-based LIKE selectivity in the style of PostgreSQL's per-character FIXED_CHAR_SEL. It applies to any `LIKE '%x%'` on any column, with no tests on schema or query shape, so it is not a special case. However, the constants (0.75 per character, the 0.01 floor) have no stated derivation. For the only TPC-H literal that triggers it ('green', L=5), they produce 4.7%, very close to the true 5.4% in TPC-H. The constants appear fitted to make Q9's estimate correct, and the win comes from that one query flipping its join order. Upstream would probably accept something similar, maybe with different constants or a version based on statistics.

- **Mechanism.** When the join-order optimizer estimates a base table's cardinality, it used to treat a pushed-down substring filter `contains(col, 'lit')` (what `LIKE '%lit%'` is rewritten to) as an unknown predicate with the default selectivity 0.2. It now estimates selectivity as 0.2 × 0.75^L, where L is the literal length (capped at 64), with a floor of 0.01 and at least 1 row. Longer needles are assumed to be rarer. Only the cardinality estimate changes, which can change the join order and build/probe sides; execution itself does not change. Because the new estimate is below the base cardinality, ExtractGetStats now treats the table as having a selective ("equality-like") filter and skips the blanket 0.2 default.
- **Trigger.** The new path runs in RelationStatisticsHelper::InspectTableFilter, which ExtractGetStats calls for every table filter on a LogicalGet whose scan supplies column statistics (relation_statistics_helper.cpp:135 `if (column_statistics) { ... InspectTableFilter(...)`). All of the following must hold:
- the filter is `case TableFilterType::EXPRESSION_FILTER` (:472). This exists only if the scan accepted generic expression pushdown on a single column (filter_combiner.cpp:379 `if (!get.function.pushdown_expression)`, :390 "refer to exactly one column");
- the expression is a BOUND_FUNCTION (:476) with `func.function.name != "contains" || func.children.size() != 2` false (:480);
- child 0 is a BOUND_REF or BOUND_COLUMN_REF (:484), so the bare column with no wrapping function (no lower(col), etc.);
- child 1 is a BOUND_CONSTANT (:487) that is not NULL and has type VARCHAR (:491 `constant.IsNull() || constant.type().id() != LogicalTypeId::VARCHAR`), and its length is not 0 (:495).
There are no tests on table name, column or plan shape. NOT contains, OR, prefix/suffix LIKE, multi-wildcard LIKE ('%a%b%'), ILIKE and regexp all fall through to `return cardinality_after_filters` (:505). Within TPC-H, only Q9 (`p_name like '%green%'`) matches. Q13's `'%special%requests%'` is not a single contains. Q2, Q14 and Q20 use suffix/prefix patterns.
- **Constants.** - Base 0.2: the engine's existing DEFAULT_SELECTIVITY (relation_statistics_helper.hpp:57 `DEFAULT_SELECTIVITY = 0.2`), not new.
- Per-character factor 0.75 (:499 `pow(0.75, ...)`): no source is cited. The idea of a fixed per-character selectivity is standard (PostgreSQL's like_selectivity multiplies by FIXED_CHAR_SEL=0.2 per literal character), but 0.75 is a much weaker decay and looks hand-picked. For Q9's 'green' (L=5) it gives 0.2×0.237 ≈ 0.047. The true selectivity in TPC-H is ≈0.054 (5 words drawn from 92 colours, so 1-(91/92)^5). The constant lands almost exactly on the benchmark's real value. With L=4 the estimate is 0.063, with L=6 it is 0.036.
- Floor 0.01 (:500): reached once 0.75^L < 0.05, i.e. L ≥ 11. Every literal of 11 or more characters gets 1%. This is an arbitrary safety clamp.
- Length cap 64 (:499 `MinValue<idx_t>(literal_length, 64)`): has no effect, because the floor already applies at 11.
- Minimum 1 row and `MinValue(..., cardinality_after_filters)` (:502): sanity bounds.
Just outside the trigger (empty literal, non-constant needle, an expression on the column, NOT/OR) the estimate stays at the old 0.2 default.
- **Outside this benchmark.** Any query on a native DuckDB table (or another scan that supports expression pushdown and statistics) with a positive single-substring filter on a bare VARCHAR column, written as `LIKE '%lit%'` or `contains(col,'lit')`, where the join order matters. Examples outside TPC-H:
1) `SELECT u.name, count(*) FROM events e JOIN users u ON e.user_id=u.id WHERE u.email LIKE '%@example.org%' GROUP BY 1;` (L=12, so 1% instead of 20%. This makes users a smaller build side.)
2) `SELECT p.title, c.body FROM posts p JOIN comments c ON c.post_id=p.id WHERE p.title LIKE '%duckdb%';` (L=6, so ≈3.6% instead of 20%.)
The direction is reasonable in general. The magnitude can be badly wrong in either direction: a short common needle like '%e%' gets 15%, and a long but very common one like '%http://%' (L=7) gets 2.7%, so the estimate can underestimate heavily and pick bad build sides.
- **Otherwise.** If any condition fails, the function returns the input cardinality, exactly as the old `default:` branch did (:477-496, :505). ExtractGetStats then applies the unchanged 0.2 default when no filter reduced the estimate (:147-152). CONJUNCTION_AND still takes the minimum over its children (:451-457), so contains ANDed with other filters on the same column also picks up the new estimate. Execution operators are unchanged.
- **Code.** src/optimizer/join_order/relation_statistics_helper.cpp:472 `case TableFilterType::EXPRESSION_FILTER: {`; src/optimizer/join_order/relation_statistics_helper.cpp:480 `if (func.function.name != "contains" || func.children.size() != 2)`; src/optimizer/join_order/relation_statistics_helper.cpp:484 `if (child_class != ExpressionClass::BOUND_REF && child_class != ExpressionClass::BOUND_COLUMN_REF)`; src/optimizer/join_order/relation_statistics_helper.cpp:491 `if (constant.IsNull() || constant.type().id() != LogicalTypeId::VARCHAR)`; src/optimizer/join_order/relation_statistics_helper.cpp:498-500 `DEFAULT_SELECTIVITY * pow(0.75, ...MinValue<idx_t>(literal_length, 64)); selectivity = MaxValue(selectivity, 0.01);`; src/optimizer/join_order/relation_statistics_helper.cpp:502 `return MinValue(MaxValue<idx_t>(estimate, 1), cardinality_after_filters);`; src/optimizer/join_order/relation_statistics_helper.cpp:505 `default: return cardinality_after_filters;`; src/optimizer/join_order/relation_statistics_helper.cpp:135-138 `if (column_statistics) { ... InspectTableFilter(base_table_cardinality, ...)`

## E0002: Bloom filter on first equality key of multi-condition hash joins

Commit `b27ef33b293d`. Files: `src/execution/join_hashtable.cpp`, `src/execution/operator/join/physical_hash_join.cpp`.
Faster when accepted: q09 1.28×.

**Label: general.** This is general. It extends an existing technique, probe-side bloom-filter pushdown, from single-key joins to multi-key ones by filtering on one key, which is a standard and correct relaxation: a match on all keys implies a match on key 0. The only new gate is "two or more equality keys", which is broad and natural. Every threshold was already there for single-key joins, and nothing depends on TPCH's schema, data sizes or query shapes. q09 benefits because of its composite key (partsupp joined on part key and supplier key), but any composite-key join with a filtered build side would too. The weak spot is choosing key 0 blindly instead of the most selective key. When key 0 is unselective, the build side does extra work, which the adaptive selectivity filter only partly limits. That is a quality limitation, not overfitting to the benchmark.

- **Mechanism.** Before this change, DuckDB built a bloom filter on the hash-join build side and pushed it into the probe-side table scan only when the join had a single key. Now joins with several equality keys also get one, but it covers only the first join condition's key column. For multi-key joins the build side reads that key column back out of the hash table's row storage, hashes it alone with VectorOperations::Hash and inserts those hashes into the filter. The usual row hash can't be used because it mixes all the keys together. The probe side was already set up for a filter on conditions[0], and it applies the filter to that one column during the scan, wrapped in the existing self-disabling selectivity filter.
- **Trigger.** All of these must hold:
(a) The pushdown filter being finalised belongs to join condition 0: `const bool is_first_key = join_condition[filter_idx] == 0;` (physical_hash_join.cpp:900).
(b) That condition has no cast: `!has_cast` (physical_hash_join.cpp:899-901).
(c) `CanUseBloomFilter` returns true. The hash table exists and is not a perfect hash table (`if (is_perfect_hashtable) return false;`, physical_hash_join.cpp:769). The new check `cmp == ExpressionType::COMPARE_EQUAL && ht->conditions[0].comparison == ExpressionType::COMPARE_EQUAL` replaces the old `ht->conditions.size() == 1` (physical_hash_join.cpp:775-776). The build side has a filter (`build_side_has_filter`). The probe side is estimated larger than the build side: `build_to_probe_ratio > 1.0` (physical_hash_join.cpp:780-782).
(d) The filter is only pushed on the deferred, in-memory finalize path (`if (deferred_bloom_filters)`, physical_hash_join.cpp:903).
(e) On the build side, the multi-key branch runs when `bloom_filter.IsInitialized()` and `conditions.size() != 1` (join_hashtable.cpp:720-731).
The hash-table constructor puts equality conditions first ("all non-equality conditions are at the back", join_hashtable.cpp:57) and a hash join always has at least one equality (join_hashtable.cpp:68 `D_ASSERT(!equality_types.empty())`). So `conditions[0].comparison == EQUAL` is effectively always true. The real new gate is simply "hash join with two or more keys". No data type, schema or table-size condition is added.
- **Constants.** The change adds no new constants. The ones it relies on were already there:
- `build_to_probe_ratio > 1.0` (physical_hash_join.cpp:782): a principled break-even point, only build a filter when there are more probe rows than build rows. Just below it, no bloom filter is built and the old behaviour applies.
- `BF_THRESHOLD = 0.25f` and `BF_CHECK_N = 75` (selectivity_optional_filter.hpp:52-53): the existing adaptive switch-off for the probe-side filter, shared with single-key joins and not tuned in this change.
- Condition index `0`: not a tuned value, but a structural choice. The filter always goes on whichever equality key the planner listed first, whether or not it is the selective one; the author admits this. When key 0 is unselective, the build side pays an extra gather and hash per row (join_hashtable.cpp:726-730) and gets nothing for it, until the selectivity filter turns the probe check off.
- **Outside this benchmark.** Any hash join that meets all of these:
- it has two or more equality keys (composite foreign keys);
- the build side is filtered;
- the probe side is larger than the build side;
- the probe side is a real table scan, so the filter can be pushed down;
- the first key matches the scan column's type exactly (no cast).
The filter is useful when the first key alone already removes many probe rows.

Example 1, order lines against a filtered composite-key shipment table:
`SELECT sum(l.qty) FROM order_lines l JOIN shipments s ON l.order_id = s.order_id AND l.line_no = s.line_no WHERE s.carrier = 'UPS';`

Example 2, a fact table joined to a snapshot dimension on (customer_id, region_id):
`SELECT count(*) FROM events e JOIN customer_snapshot c ON e.customer_id = c.customer_id AND e.region_id = c.region_id WHERE c.tier = 'gold';`

Composite-key joins like these are common in star and snowflake schemas and in bridge tables.
- **Otherwise.** - Single-key joins keep the original path exactly: `if (conditions.size() == 1) { bloom_filter.InsertHashes(hashes_v, count); }` (join_hashtable.cpp:721-722). Their eligibility logic is unchanged apart from the redundant equality check on condition 0.
- In a multi-key join, filters on keys other than condition 0 get only the existing min/max zone-map filters, as before.
- Joins that fail any other guard (perfect hash table, no build-side filter, probe not larger than build, cast, external join) get no bloom filter, as before.
- **Code.** src/execution/join_hashtable.cpp:720 `if (bloom_filter.IsInitialized()) {`; src/execution/join_hashtable.cpp:721 `if (conditions.size() == 1) {`; src/execution/join_hashtable.cpp:728-731 `data_collection->Gather(chunk_state.row_locations, sel, count, 0, key_v, sel, nullptr); VectorOperations::Hash(key_v, key_hashes_v, count); bloom_filter.InsertHashes(key_hashes_v, count);`; src/execution/join_hashtable.cpp:57 `// all non-equality conditions are at the back`; src/execution/join_hashtable.cpp:68 `D_ASSERT(!equality_types.empty());`; src/execution/join_hashtable.cpp:752-753 `if (should_build_bloom_filter) { bloom_filter.Initialize(context, Count());`; src/execution/operator/join/physical_hash_join.cpp:769 `if (is_perfect_hashtable) { return false;`; src/execution/operator/join/physical_hash_join.cpp:775-776 `cmp == ExpressionType::COMPARE_EQUAL && ht->conditions[0].comparison == ExpressionType::COMPARE_EQUAL`

## E0004: Exact key bitmap mode for join BF on dense integer build keys

Commit `a496c6c900cc`. Files: `src/execution/join_hashtable.cpp`, `src/execution/operator/join/physical_hash_join.cpp`, `src/include/duckdb/planner/filter/bloom_filter.hpp`, `src/planner/filter/bloom_filter.cpp`.
Faster when accepted: q09 1.25×.
Numeric constants in added code: `128`, `2048`.

**Label: heuristic.** The technique is standard and principled: an exact bitmap or range filter for dense integer keys, as used in perfect hashing and bitmap semi-join filters. It applies to a broad, natural class of joins on integer and surrogate keys, with no references to TPC-H schema, columns or literals. However, the gate that decides when it beats the hashed filter is a density cap of 128 bits/key. That cap is unprincipled, and the author says a sibling run tuned it against q21. It also lets the exact bitmap grow several times larger than the hashed BF it replaces, which works against the stated footprint rationale. A small cap derived from the hashed BF's bits/key, or a cache-size bound, would be more defensible. The mechanism is likely acceptable upstream with a different constant, so this is "heuristic" rather than "general".

- **Mechanism.** When the hash join's runtime Bloom filter would be pushed into the probe-side scan, and the first build key is an integer whose build-side [min,max] range is small enough, the filter becomes an exact bitmap with one bit per value in [min,max]. Bit (key-min) is set for each build key. Probing tests that bit on the raw key value with no hashing and no false positives. Values outside the range are rejected. Zone-map pruning (CheckStatistics) also gains an exact range-overlap test plus the existing probe of up to 2048 values. If the trigger fails, the old hashed BF is built unchanged.
- **Trigger.** All of these must hold.

1. The existing deferred-BF path is reached (physical_hash_join.cpp:956): `!has_cast && is_first_key && ht && CanUseBloomFilter(...)` and `deferred_bloom_filters` is non-null. CanUseBloomFilter (physical_hash_join.cpp:769-785) requires all of:
   - not a perfect hash table;
   - `cmp == COMPARE_EQUAL`;
   - `build_side_has_filter`;
   - probe cardinality estimate greater than the HT count.
   It is also reached only when min != max (line 911).
2. Then TrySetExactBloomFilterRange (physical_hash_join.cpp:845-868) requires:
   - the BF is not already initialized or exact, and min/max are non-NULL;
   - `build_type.InternalType() == probe_type.InternalType()` and `min_val.type() == build_type`;
   - the physical type is INT8/16/32/64 or UINT8/16/32 (GetExactBloomFilterKey, lines 815-841). That includes logical types stored as these, such as DATE and DECIMAL; UINT64, HUGEINT, VARCHAR and floats are excluded;
   - `range >= MAX_EXACT_RANGE || range / MAX_EXACT_BITS_PER_KEY >= ht.Count()` must be false, with MAX_EXACT_RANGE = 2^31 and MAX_EXACT_BITS_PER_KEY = 128.

In practice: equality hash joins on an integer key where a filtered build side has at most about 128 distinct-range values per build row, and the join did not qualify for the perfect hash table.
- **Constants.** - **MAX_EXACT_RANGE = 2^31** (physical_hash_join.cpp:847): caps the bitmap at 256 MB. That is principled: it stays under the hashed BF's own cap of `MAX_NUM_SECTORS = (1ULL << 26)` 64-bit sectors (bloom_filter.cpp:7), and it is not tuned to TPC-H sizes. A range of 2^31 or more uses the hashed BF.
- **MAX_EXACT_BITS_PER_KEY = 128** (line 846): a density cutoff. It is not derived from anything. The hashed BF uses `MIN_NUM_BITS_PER_KEY = 12` rounded up to a power of two, so roughly 12-24 bits/key. At 128 bits/key the exact bitmap can therefore be about 5-10x larger than the filter it replaces, which contradicts the code comment "typically a smaller footprint". The author's notes say a sibling run found the cap "mattered for q21", so the value was picked against this benchmark. q09, the query that gained, runs at about 4.6 bits/key and would qualify under almost any cap. Just above the cap, the old hashed BF is used unchanged, so only performance is affected, never correctness.
- **2048** in TemplatedCheckStatisticsExact (bloom_filter.cpp `if (range > 2048)`): the author says it matches the existing hashed CheckStatistics probe limit ("as before"), so it is inherited, not new. Zone ranges above 2048 get only the range-overlap test.
- **Outside this benchmark.** Any equality hash join on a surrogate or integer key (INT, BIGINT, SMALLINT, DATE, small DECIMAL) where:
- the build side is filtered;
- the probe side is larger;
- the surviving build keys span a range no more than about 128x the build row count;
- the perfect-hash-join path was not taken (for example because build keys repeat or the range is too large for a PHT).

This is the common star or snowflake pattern of a filtered dimension joined to a fact table on a dense id. Examples:
- `SELECT sum(s.amount) FROM sales s JOIN products p ON s.product_id = p.id WHERE p.category = 'Toys';` (p.id is a dense INTEGER sequence).
- `SELECT e.user_id, count(*) FROM events e JOIN sessions x ON e.session_id = x.session_id WHERE x.started_at > now() - INTERVAL 1 DAY GROUP BY 1;` (session_id is a BIGINT identity, and recent sessions form a dense range).

Not covered: string or UUID keys, UINT64 or HUGEINT keys, sparse or hashed ids, and the non-first keys of multi-key joins.
- **Otherwise.** If any trigger condition fails, TrySetExactBloomFilterRange returns without calling SetKeyRange. `exact` stays false, and Initialize, InsertHashes, Filter, FilterValue and CheckStatistics all take the original hashed-BF branches, which the diff leaves unchanged apart from being nested under `else` (bloom_filter.cpp:24-30; join_hashtable.cpp:721-727; the Filter else-branch).

One new failure mode exists: if a build key falls outside the recorded min/max, InsertKeys throws `InternalException("BloomFilter: exact key out of range")` instead of degrading gracefully.

The author's own tests did not exercise the exact path with NULL or negative keys (their EXPLAIN ANALYZE showed no BF on the probe scan), so those cases were never run.
- **Code.** src/execution/operator/join/physical_hash_join.cpp:956 "if (!has_cast && is_first_key && ht && CanUseBloomFilter(context, ht, op, cmp, is_perfect_hashtable))"; src/execution/operator/join/physical_hash_join.cpp:961 "TrySetExactBloomFilterRange(*ht, condition_type, final_min_max->data[min_idx].GetValue(0), ...)"; src/execution/operator/join/physical_hash_join.cpp:769 "if (is_perfect_hashtable) { return false; }"; src/execution/operator/join/physical_hash_join.cpp:785 "return can_use_bf && build_side_has_filter && probe_larger_then_build;"; src/execution/operator/join/physical_hash_join.cpp:846 "static constexpr uint64_t MAX_EXACT_BITS_PER_KEY = 128;"; src/execution/operator/join/physical_hash_join.cpp:847 "static constexpr uint64_t MAX_EXACT_RANGE = (1ULL << 31);"; src/execution/operator/join/physical_hash_join.cpp (TrySetExactBloomFilterRange) "if (build_type.InternalType() != probe_type.InternalType() || min_val.type() != build_type ..."; src/execution/operator/join/physical_hash_join.cpp (TrySetExactBloomFilterRange) "if (range >= MAX_EXACT_RANGE || range / MAX_EXACT_BITS_PER_KEY >= ht.Count()) return;"
